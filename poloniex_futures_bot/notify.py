# -*- coding: utf-8 -*-
"""
模拟交易：决策后发 Telegram、写 Redis 记录交易价格。
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
) -> None:
    """决策后：发 Telegram + 写 Redis，记录交易价格。"""
    from config import SYMBOL, LEVERAGE, INITIAL_EQUITY

    sl_tp = f"止损: {sl:.2f} | 止盈: {tp:.2f}" if (sl is not None and tp is not None) else ""
    text = (
        f"【模拟交易】{side} @ {price:.2f}\n"
        f"数量: {size:.4f} | 杠杆: {LEVERAGE}x\n"
        f"{sl_tp}"
    )
    if current_equity is not None and initial_equity is not None:
        pnl = current_equity - initial_equity
        text += f"\n当前权益: {current_equity:.2f} | 累计收益: {pnl:+.2f}"
    if reason:
        text += f"\n{reason}"
    if decision_reason:
        text += f"\n---决策依据---\n{decision_reason}"
    send_telegram_long(text)

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
    save_trade_redis(trade)
    if current_equity is not None:
        save_equity_redis(current_equity, initial_equity or INITIAL_EQUITY)


def notify_close(side: str, price: float, pnl: float, reason: str = "", current_equity: Optional[float] = None, initial_equity: Optional[float] = None) -> None:
    """平仓通知 + 写 Redis；可带当前权益与累计收益。"""
    from config import SYMBOL, INITIAL_EQUITY

    text = f"【模拟平仓】{side} 平 @ {price:.2f}\n本笔盈亏: {pnl:+.2f}"
    if current_equity is not None and initial_equity is not None:
        total_pnl = current_equity - initial_equity
        text += f"\n当前权益: {current_equity:.2f} | 累计收益: {total_pnl:+.2f}"
    if reason:
        text += f"\n{reason}"
    send_telegram(text)
    save_trade_redis({
        "action": "close",
        "side": side,
        "price": price,
        "pnl": pnl,
        "reason": reason,
        "symbol": SYMBOL,
        **({"equity": current_equity} if current_equity is not None else {}),
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
) -> None:
    """
    每小时汇总：权益变化（已含模拟盘手续费与资金费线性摊销）、累计盈亏、决策依据。
    """
    hour_pnl = equity - equity_at_hour_start
    cum_pnl = equity - initial_equity
    unreal_txt = ""
    if pos_side and pos_size > 0:
        if pos_side.upper() == "LONG":
            u = (mark_price - entry_price) * pos_size
        else:
            u = (entry_price - mark_price) * pos_size
        side_cn = "多" if pos_side.upper() == "LONG" else "空"
        unreal_txt = f"\n持仓: {side_cn} | 开仓 {entry_price:.2f} | 标记 {mark_price:.2f}\n未实现价差盈亏(未扣平仓费): {u:+.2f}"
    head = (
        f"【小时汇总】{symbol}\n"
        f"当前权益: {equity:.2f}（初始 {initial_equity:.2f}）\n"
        f"本小时权益变动: {hour_pnl:+.2f}（已计入本段资金费摊销与历史成交手续费）\n"
        f"累计净变动: {cum_pnl:+.2f}\n"
        f"累计手续费(模拟): {total_fees_paid:.4f}\n"
        f"累计资金费收支(模拟): {total_funding_cashflow:+.4f}\n"
        f"本次使用资金费率 fR: {funding_rate_used:.6f} | Taker 费率: {taker_fee_rate:.5f}"
        f"{unreal_txt}"
    )
    send_telegram_long(head)
    if last_decision_rationale:
        send_telegram_long("【最近一轮决策依据】\n" + last_decision_rationale)
