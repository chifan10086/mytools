# -*- coding: utf-8 -*-
"""
模拟交易：决策后发 Telegram、写 Redis 记录交易价格。
增强版：详细汇报、风险指标、交易统计。
"""
import html
import json
import time
import unicodedata
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional, Dict, Any, List

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, REDIS_URL

# Redis 键：交易列表、当前权益（方便查询收益）
REDIS_KEY_TRADES = "poloniex_simulate:trades"
REDIS_KEY_LAST = "poloniex_simulate:last_trade"
REDIS_KEY_EQUITY = "poloniex_simulate:equity"


def send_telegram(text: str, parse_mode: Optional[str] = None) -> bool:
    """发送消息到 Telegram 群组。"""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is None:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    body = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": True}
    if parse_mode:
        body["parse_mode"] = parse_mode
    data = urllib.parse.urlencode(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "PoloniexBot/1.0 (Python)")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        # 403 多为 Token 错误、Chat ID 错误或 Bot 未加入群组
        if e.code == 403:
            body = e.read().decode("utf-8", errors="ignore") if e.fp else ""
            import logging
            logging.getLogger(__name__).warning("Telegram 403: %s %s", e.reason, body[:200])
        return False
    except Exception:
        return False


def save_trade_redis(trade: Dict[str, Any]) -> bool:
    """将单笔交易写入 Redis（列表追加 + 最近一笔）。"""
    if not REDIS_URL:
        return False
    try:
        import redis
        r = redis.from_url(REDIS_URL)
        trade["_ts"] = time.time()
        s = json.dumps(trade, ensure_ascii=False)
        r.rpush(REDIS_KEY_TRADES, s)
        r.set(REDIS_KEY_LAST, s)
        return True
    except Exception:
        return False


def save_equity_redis(equity: float, initial_equity: float) -> bool:
    """写入当前权益到 Redis，便于查询收益。"""
    if not REDIS_URL:
        return False
    try:
        import redis
        r = redis.from_url(REDIS_URL)
        r.set(REDIS_KEY_EQUITY, json.dumps({"equity": equity, "initial": initial_equity, "pnl": equity - initial_equity, "_ts": time.time()}, ensure_ascii=False))
        return True
    except Exception:
        return False


def send_telegram_long(text: str, chunk: int = 3900, parse_mode: Optional[str] = None) -> None:
    """Telegram 单条上限约 4096，超长时分段发送。"""
    if not text:
        return
    t = text.strip()
    if len(t) <= chunk:
        send_telegram(t, parse_mode)
        return
    n = (len(t) + chunk - 1) // chunk
    for i in range(n):
        part = t[i * chunk : (i + 1) * chunk]
        send_telegram(f"（{i + 1}/{n}）\n{part}", parse_mode)


# ───────── 报表渲染：Telegram 不支持任意文字颜色，只有代码块能语法高亮。
# 用 language-diff 让 "+" 开头的行显绿（盈利）、"-" 开头的行显红（亏损）。 ─────────

def _disp_width(s: str) -> int:
    """显示宽度：中日韩全角字符占 2 列。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def _pad(s: str, width: int) -> str:
    """左对齐补空格，按显示宽度算，保证等宽字体下中文标签能对齐。"""
    return s + " " * max(0, width - _disp_width(s))


def _rpad(s: str, width: int) -> str:
    """右对齐补空格；值里可能含中文（如「24分」），不能用 f-string 的 :>N。"""
    return " " * max(0, width - _disp_width(s)) + s


def _tone(v: float) -> int:
    """正数→绿，负数→红，零→中性。"""
    return 1 if v > 0 else -1 if v < 0 else 0


def _row(label: str, value: str, tone: int = 0, note: str = "") -> str:
    """diff 代码块中的一行；行首符号决定颜色。"""
    mark = "+" if tone > 0 else "-" if tone < 0 else " "
    line = f"{mark} {_pad(label, 12)}{_rpad(value, 13)}"
    return f"{line}  {note}" if note else line


def _diff_block(rows: List[str]) -> str:
    """包成语法高亮代码块。内容需 HTML 转义，否则含 < > & 时发送失败。"""
    body = html.escape("\n".join(rows))
    return f'<pre><code class="language-diff">{body}</code></pre>'


def _section(title: str, rows: List[str]) -> str:
    """小标题 + 彩色数据块。"""
    return f"<b>{html.escape(title)}</b>\n{_diff_block(rows)}"


def send_pre_text(title: str, body: str, limit: int = 3800) -> None:
    """长自由文本（如决策依据）分段发送，每段独立包代码块，避免 HTML 标签被截断。

    长度按「转义后」算：html.escape 会把 < 变成 &lt;（长度 4 倍），
    按原文长度分页会超出 Telegram 的 4096 上限。
    """
    if not body:
        return
    # 按行拆；单行自身超限时按转义后长度硬切
    units: List[str] = []
    for ln in body.strip().splitlines() or [body.strip()]:
        if len(html.escape(ln)) <= limit:
            units.append(ln)
            continue
        buf: List[str] = []
        buf_len = 0
        for ch in ln:
            c = len(html.escape(ch))
            if buf_len + c > limit and buf:
                units.append("".join(buf))
                buf, buf_len = [], 0
            buf.append(ch)
            buf_len += c
        if buf:
            units.append("".join(buf))

    pages: List[List[str]] = [[]]
    size = 0
    for u in units:
        n = len(html.escape(u)) + 1
        if size + n > limit and pages[-1]:
            pages.append([])
            size = 0
        pages[-1].append(u)
        size += n

    total = len(pages)
    for i, page in enumerate(pages, 1):
        head = f"<b>{html.escape(title)}</b>" + (f" <i>({i}/{total})</i>" if total > 1 else "")
        send_telegram(f"{head}\n<pre>{html.escape(chr(10).join(page))}</pre>", "HTML")


def notify_trade(
    side: str,
    price: float,
    size: float,
    sl: Optional[float],
    tp: Optional[float],
    reason: str = "",
    current_equity: Optional[float] = None,
    initial_equity: Optional[float] = None,
    decision_reason: str = "",
    signal_quality: Optional[float] = None,
    position_scale: Optional[float] = None,
) -> None:
    """决策后：发 Telegram + 写 Redis，记录交易价格。"""
    from config import SYMBOL, LEVERAGE, INITIAL_EQUITY

    is_long = "多" in side or "LONG" in side.upper()
    title = "🟢 开多" if is_long else "🔴 开空"

    rows = [
        _row("开仓价格", f"{price:.2f}", note="USDT"),
        _row("合约数量", f"{size:.4f}"),
        _row("名义价值", f"{price * size:.2f}", note="USDT"),
        _row("杠杆", f"{LEVERAGE}x"),
    ]
    if position_scale and position_scale != 1.0:
        hint = "风控降仓" if position_scale < 1.0 else "表现良好加仓"
        rows.append(_row("仓位系数", f"{position_scale:.2f}x", _tone(position_scale - 1.0), hint))

    text = f"<b>{title}</b>  <code>{html.escape(SYMBOL)}</code>\n" + _diff_block(rows)

    if sl is not None and tp is not None:
        risk = abs(price - sl)
        rr_ratio = (abs(tp - price) / risk) if risk > 0 else 0
        text += "\n" + _section("🎯 风险控制", [
            _row("止盈", f"{tp:.2f}", 1, f"+{abs(tp - price) / price * 100:.2f}%"),
            _row("止损", f"{sl:.2f}", -1, f"-{abs(price - sl) / price * 100:.2f}%"),
            _row("风险回报比", f"1:{rr_ratio:.2f}"),
        ])

    if current_equity is not None and initial_equity is not None:
        pnl = current_equity - initial_equity
        pnl_pct = (pnl / initial_equity * 100) if initial_equity > 0 else 0
        text += "\n" + _section("💰 账户状态", [
            _row("当前权益", f"{current_equity:.2f}", note="USDT"),
            _row("累计收益", f"{abs(pnl):.2f}", _tone(pnl), f"{pnl_pct:+.2f}%"),
        ])

    if signal_quality is not None:
        quality_emoji = "🟢" if signal_quality >= 0.7 else "🟡" if signal_quality >= 0.5 else "🔴"
        quality_text = "优秀" if signal_quality >= 0.7 else "良好" if signal_quality >= 0.5 else "一般"
        text += f"\n📊 信号质量 {quality_emoji} <b>{quality_text}</b> ({signal_quality:.0%})"

    if reason:
        text += f"\n💡 {html.escape(reason)}"

    send_telegram_long(text, parse_mode="HTML")

    # 决策依据单独发送（中文化）
    if decision_reason:
        send_pre_text("📋 决策依据", _format_decision_reason(decision_reason))

    trade = {
        "side": side,
        "price": price,
        "size": size,
        "sl": sl,
        "tp": tp,
        "symbol": SYMBOL,
        "leverage": LEVERAGE,
    }
    if current_equity is not None:
        trade["equity"] = current_equity
    if decision_reason:
        trade["decision_reason"] = decision_reason
    if signal_quality is not None:
        trade["signal_quality"] = signal_quality
    save_trade_redis(trade)
    if current_equity is not None:
        save_equity_redis(current_equity, initial_equity or INITIAL_EQUITY)


def _format_decision_reason(reason: str) -> str:
    """格式化决策依据，中文化关键术语"""
    # 替换常见英文术语
    replacements = {
        "EMA": "指数移动平均线",
        "MACD": "平滑异同移动平均线",
        "RSI": "相对强弱指标",
        "ATR": "平均真实波幅",
        "ADX": "平均趋向指标",
        "stop_loss": "止损",
        "take_profit": "止盈",
        "LONG": "多头",
        "SHORT": "空头",
        "cross": "交叉",
        "golden cross": "金叉",
        "death cross": "死叉",
        "overbought": "超买",
        "oversold": "超卖",
        "trend": "趋势",
        "momentum": "动量",
        "volatility": "波动率",
        "volume": "成交量",
    }
    
    formatted = reason
    for en, cn in replacements.items():
        formatted = formatted.replace(en, cn)
    
    return formatted


def notify_close(
    side: str, 
    price: float, 
    pnl: float, 
    reason: str = "", 
    current_equity: Optional[float] = None, 
    initial_equity: Optional[float] = None,
    entry_price: Optional[float] = None,
    hold_time: Optional[int] = None,
) -> None:
    """平仓通知 + 写 Redis；可带当前权益与累计收益。"""
    from config import SYMBOL, INITIAL_EQUITY

    # 盈亏表情和状态
    if pnl > 0:
        emoji = "✅"
        status = "盈利"
    elif pnl < 0:
        emoji = "❌"
        status = "亏损"
    else:
        emoji = "➖"
        status = "持平"
    
    side_cn = "多单" if "LONG" in side.upper() else "空单"
    
    # 收益率
    pct_note = ""
    if entry_price and entry_price > 0:
        if side.upper() == "LONG":
            pnl_pct = (price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - price) / entry_price * 100
        pct_note = f"{pnl_pct:+.2f}%"
    
    # 平仓原因中文化
    reason_cn = reason
    if "stop_loss" in reason.lower():
        reason_cn = "触发止损"
    elif "take_profit" in reason.lower():
        reason_cn = "触发止盈"
    elif "最大持仓周期" in reason:
        reason_cn = "达到最大持仓时间"
    elif "反向" in reason:
        reason_cn = reason.replace("反向开", "反向信号，准备开")
    
    rows = [_row("本笔盈亏", f"{abs(pnl):.2f}", _tone(pnl), pct_note)]
    if entry_price and entry_price > 0:
        rows.append(_row("开仓价格", f"{entry_price:.2f}", note="USDT"))
    rows.append(_row("平仓价格", f"{price:.2f}", note="USDT"))
    if hold_time:
        hours, minutes = hold_time // 3600, (hold_time % 3600) // 60
        rows.append(_row("持仓时长", f"{hours}时{minutes}分" if hours else f"{minutes}分"))
    
    text = (
        f"<b>{emoji} 平仓·{status}</b>  <code>{html.escape(SYMBOL)}</code> {side_cn}\n"
        + _diff_block(rows)
    )
    
    if current_equity is not None and initial_equity is not None:
        total_pnl = current_equity - initial_equity
        total_pnl_pct = (total_pnl / initial_equity * 100) if initial_equity > 0 else 0
        text += "\n" + _section("💰 账户状态", [
            _row("当前权益", f"{current_equity:.2f}", note="USDT"),
            _row("累计收益", f"{abs(total_pnl):.2f}", _tone(total_pnl), f"{total_pnl_pct:+.2f}%"),
        ])
    
    if reason_cn:
        text += f"\n💡 平仓原因: {html.escape(reason_cn)}"
    
    send_telegram(text, "HTML")
    save_trade_redis({
        "action": "close",
        "side": side,
        "price": price,
        "pnl": pnl,
        "reason": reason,
        "symbol": SYMBOL,
        **({"equity": current_equity} if current_equity is not None else {}),
        **({"entry_price": entry_price} if entry_price else {}),
        **({"hold_time": hold_time} if hold_time else {}),
    })
    if current_equity is not None:
        save_equity_redis(current_equity, initial_equity or INITIAL_EQUITY)


def notify_hourly_pnl_report(
    *,
    equity: float,
    initial_equity: float,
    equity_at_hour_start: float,
    mark_price: float,
    pos_side: Optional[str],
    entry_price: float,
    pos_size: float,
    total_fees_paid: float,
    total_funding_cashflow: float,
    funding_rate_used: float,
    taker_fee_rate: float,
    last_decision_rationale: str,
    symbol: str,
    risk_stats: Optional[Dict[str, Any]] = None,
    market_state: Optional[str] = None,
) -> None:
    """
    每小时汇总：权益变化、累计盈亏、决策依据、交易统计、风险指标。
    """
    hour_pnl = equity - equity_at_hour_start
    cum_pnl = equity - initial_equity
    cum_pnl_pct = (cum_pnl / initial_equity * 100) if initial_equity > 0 else 0
    
    text = (
        f"<b>📊 小时汇总报告</b>\n"
        f"<code>{html.escape(symbol)}</code> · {time.strftime('%Y-%m-%d %H:%M')}\n"
        + _section("💰 权益状况", [
            _row("本小时", f"{abs(hour_pnl):.2f}", _tone(hour_pnl), "USDT"),
            _row("累计盈亏", f"{abs(cum_pnl):.2f}", _tone(cum_pnl), f"{cum_pnl_pct:+.2f}%"),
            _row("当前权益", f"{equity:.2f}", note="USDT"),
            _row("初始权益", f"{initial_equity:.2f}", note="USDT"),
            _row("累计手续费", f"{total_fees_paid:.2f}", -1 if total_fees_paid else 0, "USDT"),
            _row("累计资金费", f"{abs(total_funding_cashflow):.4f}", _tone(total_funding_cashflow), "USDT"),
        ])
    )
    
    # 持仓信息
    if pos_side and pos_size > 0:
        if pos_side.upper() == "LONG":
            u = (mark_price - entry_price) * pos_size
        else:
            u = (entry_price - mark_price) * pos_size
        u_pct = (u / (entry_price * pos_size) * 100) if entry_price > 0 and pos_size > 0 else 0
        side_cn = "多单" if pos_side.upper() == "LONG" else "空单"
        text += "\n" + _section("📈 持仓情况", [
            _row("方向", side_cn),
            _row("开仓价格", f"{entry_price:.2f}", note="USDT"),
            _row("当前价格", f"{mark_price:.2f}", note="USDT"),
            _row("持仓数量", f"{pos_size:.4f}"),
            _row("浮动盈亏", f"{abs(u):.2f}", _tone(u), f"{u_pct:+.2f}%"),
        ])
        text += "\n<i>注: 浮动盈亏未扣除平仓手续费</i>"
    
    # 交易统计
    if risk_stats:
        win_rate = risk_stats.get('win_rate', 0)
        profit_factor = risk_stats.get('profit_factor', 0)
        
        # 胜率评级
        if win_rate >= 0.6:
            wr_tone, wr_level = 1, "优秀"
        elif win_rate >= 0.5:
            wr_tone, wr_level = 1, "良好"
        elif win_rate >= 0.4:
            wr_tone, wr_level = 0, "一般"
        else:
            wr_tone, wr_level = -1, "较差"
        
        # 盈亏比评级
        if profit_factor >= 1.5:
            pf_tone, pf_level = 1, "优秀"
        elif profit_factor >= 1.2:
            pf_tone, pf_level = 1, "良好"
        elif profit_factor >= 1.0:
            pf_tone, pf_level = 0, "一般"
        else:
            pf_tone, pf_level = -1, "较差"
        
        max_dd = risk_stats.get('max_drawdown', 0)
        cur_dd = risk_stats.get('current_drawdown', 0)
        losses = risk_stats.get('consecutive_losses', 0)
        text += "\n" + _section("📊 交易统计", [
            _row("总交易", f"{risk_stats.get('total_trades', 0)}", note="笔"),
            _row("胜率", f"{win_rate:.1%}", wr_tone, wr_level),
            _row("盈利/亏损", f"{risk_stats.get('winning_trades', 0)} / {risk_stats.get('losing_trades', 0)}", note="笔"),
            _row("盈亏比", f"{profit_factor:.2f}", pf_tone, pf_level),
            _row("平均盈利", f"{risk_stats.get('avg_win', 0):.2f}", 1, "USDT"),
            _row("平均亏损", f"{abs(risk_stats.get('avg_loss', 0)):.2f}", -1, "USDT"),
            _row("最大盈利", f"{risk_stats.get('max_win', 0):.2f}", 1, "USDT"),
            _row("最大亏损", f"{abs(risk_stats.get('max_loss', 0)):.2f}", -1, "USDT"),
            _row("最大回撤", f"{max_dd:.2%}", -1 if max_dd else 0),
            _row("当前回撤", f"{cur_dd:.2%}", -1 if cur_dd else 0),
            _row("连续亏损", f"{losses}", -1 if losses else 0, "次"),
        ])
        recent = risk_stats.get('recent_performance', '')
        if recent:
            text += f"\n📈 {html.escape(str(recent))}"
    
    # 市场状态
    if market_state:
        text += f"\n\n<b>🌐 市场状态</b>\n{html.escape(str(market_state))}"
    
    # 费率信息
    text += "\n" + _section("⚙️ 费率信息", [
        _row("资金费率", f"{funding_rate_used:.6f}"),
        _row("Taker 费率", f"{taker_fee_rate:.5f}"),
    ])
    
    send_telegram_long(text, parse_mode="HTML")
    
    # 决策依据（中文化）
    if last_decision_rationale:
        send_pre_text("📋 最近决策依据", _format_decision_reason(last_decision_rationale))
