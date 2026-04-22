# -*- coding: utf-8 -*-
"""
模拟交易：决策后发 Telegram、写 Redis 记录交易价格。
增强版：详细汇报、风险指标、交易统计。
"""
import json
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional, Dict, Any

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, REDIS_URL

# Redis 键：交易列表、当前权益（方便查询收益）
REDIS_KEY_TRADES = "poloniex_simulate:trades"
REDIS_KEY_LAST = "poloniex_simulate:last_trade"
REDIS_KEY_EQUITY = "poloniex_simulate:equity"


def send_telegram(text: str) -> bool:
    """发送消息到 Telegram 群组。"""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is None:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    body = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": True}
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


def send_telegram_long(text: str, chunk: int = 3900) -> None:
    """Telegram 单条上限约 4096，超长时分段发送。"""
    if not text:
        return
    t = text.strip()
    if len(t) <= chunk:
        send_telegram(t)
        return
    n = (len(t) + chunk - 1) // chunk
    for i in range(n):
        part = t[i * chunk : (i + 1) * chunk]
        send_telegram(f"（{i + 1}/{n}）\n{part}")


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

    # 计算风险回报比
    risk_reward = ""
    if sl is not None and tp is not None:
        risk = abs(price - sl)
        reward = abs(tp - price)
        rr_ratio = reward / risk if risk > 0 else 0
        sl_pct = abs(price - sl) / price * 100
        tp_pct = abs(tp - price) / price * 100
        risk_reward = f"止损: {sl:.2f} (-{sl_pct:.2f}%) | 止盈: {tp:.2f} (+{tp_pct:.2f}%)\n风险回报比: 1:{rr_ratio:.2f}"
    
    # 仓位信息
    position_value = price * size
    position_info = f"数量: {size:.4f} | 杠杆: {LEVERAGE}x | 名义价值: {position_value:.2f} USDT"
    if position_scale and position_scale != 1.0:
        position_info += f"\n仓位系数: {position_scale:.2f}x"
    
    text = (
        f"🔔 【{side}】@ {price:.2f}\n"
        f"{position_info}\n"
        f"{risk_reward}"
    )
    
    # 权益信息
    if current_equity is not None and initial_equity is not None:
        pnl = current_equity - initial_equity
        pnl_pct = (pnl / initial_equity * 100) if initial_equity > 0 else 0
        text += f"\n\n当前权益: {current_equity:.2f} USDT\n累计收益: {pnl:+.2f} USDT ({pnl_pct:+.2f}%)"
    
    # 信号质量
    if signal_quality is not None:
        quality_emoji = "🟢" if signal_quality >= 0.7 else "🟡" if signal_quality >= 0.5 else "🔴"
        text += f"\n信号质量: {quality_emoji} {signal_quality:.1%}"
    
    if reason:
        text += f"\n{reason}"
    
    send_telegram_long(text)
    
    # 决策依据单独发送
    if decision_reason:
        send_telegram_long("━━━━ 【决策依据】━━━━\n" + decision_reason)

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

    # 盈亏表情
    emoji = "✅" if pnl > 0 else "❌" if pnl < 0 else "➖"
    
    # 收益率
    pnl_pct_text = ""
    if entry_price and entry_price > 0:
        if side.upper() == "LONG":
            pnl_pct = (price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - price) / entry_price * 100
        pnl_pct_text = f" ({pnl_pct:+.2f}%)"
    
    # 持仓时长
    hold_text = ""
    if hold_time:
        hours = hold_time // 3600
        minutes = (hold_time % 3600) // 60
        hold_text = f"\n持仓时长: {hours}小时{minutes}分钟"
    
    text = (
        f"{emoji} 【平仓】{side} @ {price:.2f}\n"
        f"本笔盈亏: {pnl:+.2f} USDT{pnl_pct_text}"
        f"{hold_text}"
    )
    
    if current_equity is not None and initial_equity is not None:
        total_pnl = current_equity - initial_equity
        total_pnl_pct = (total_pnl / initial_equity * 100) if initial_equity > 0 else 0
        text += f"\n当前权益: {current_equity:.2f} USDT\n累计收益: {total_pnl:+.2f} USDT ({total_pnl_pct:+.2f}%)"
    
    if reason:
        text += f"\n原因: {reason}"
    
    send_telegram(text)
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
    
    # 持仓信息
    unreal_txt = ""
    if pos_side and pos_size > 0:
        if pos_side.upper() == "LONG":
            u = (mark_price - entry_price) * pos_size
            u_pct = ((mark_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        else:
            u = (entry_price - mark_price) * pos_size
            u_pct = ((entry_price - mark_price) / entry_price * 100) if entry_price > 0 else 0
        side_cn = "多" if pos_side.upper() == "LONG" else "空"
        unreal_txt = f"\n\n【持仓】{side_cn} | 开仓 {entry_price:.2f} | 标记 {mark_price:.2f}\n未实现盈亏: {u:+.2f} ({u_pct:+.2f}%，未扣平仓费)"
    
    # 基础汇总
    head = (
        f"━━━━ 【小时汇总】{symbol} ━━━━\n"
        f"⏰ 时间: {time.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"【权益】\n"
        f"当前: {equity:.2f} USDT\n"
        f"初始: {initial_equity:.2f} USDT\n"
        f"本小时变动: {hour_pnl:+.2f} USDT\n"
        f"累计盈亏: {cum_pnl:+.2f} USDT ({cum_pnl_pct:+.2f}%)\n"
        f"累计手续费: {total_fees_paid:.4f} USDT\n"
        f"累计资金费: {total_funding_cashflow:+.4f} USDT"
        f"{unreal_txt}"
    )
    
    # 交易统计
    if risk_stats:
        stats_txt = (
            f"\n\n【交易统计】\n"
            f"总交易: {risk_stats.get('total_trades', 0)} 笔\n"
            f"胜率: {risk_stats.get('win_rate', 0):.1%} "
            f"({risk_stats.get('winning_trades', 0)}胜/{risk_stats.get('losing_trades', 0)}负)\n"
            f"盈亏比: {risk_stats.get('profit_factor', 0):.2f}\n"
            f"平均盈利: {risk_stats.get('avg_win', 0):.2f} | "
            f"平均亏损: {risk_stats.get('avg_loss', 0):.2f}\n"
            f"最大单笔盈利: {risk_stats.get('max_win', 0):.2f}\n"
            f"最大单笔亏损: {risk_stats.get('max_loss', 0):.2f}\n"
            f"最大回撤: {risk_stats.get('max_drawdown', 0):.2%}\n"
            f"当前回撤: {risk_stats.get('current_drawdown', 0):.2%}\n"
            f"连续亏损: {risk_stats.get('consecutive_losses', 0)} 次\n"
            f"{risk_stats.get('recent_performance', '')}"
        )
        head += stats_txt
    
    # 市场状态
    if market_state:
        head += f"\n\n【市场状态】\n{market_state}"
    
    # 费率信息
    head += f"\n\n【费率】资金费率 {funding_rate_used:.6f} | Taker {taker_fee_rate:.5f}"
    
    send_telegram_long(head)
    
    # 决策依据
    if last_decision_rationale:
        send_telegram_long("━━━━ 【最近决策依据】━━━━\n" + last_decision_rationale)
