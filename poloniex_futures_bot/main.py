# -*- coding: utf-8 -*-
"""
Poloniex BTC 永续合约交易机器人主循环。
单向持仓；多策略；止损止盈；模拟模式含 Taker 手续费与资金费摊销、每小时 Telegram 汇报。
增强版：动态仓位管理、信号质量评分、趋势过滤、详细统计汇报。
"""
import time
import logging
from typing import Any, Dict, Optional

import config_bootstrap  # noqa: F401  # 旧版 config.py 缺省字段时补齐

from config import (
    SYMBOL,
    PAPER_MODE,
    SIMULATE_ONLY,
    LEVERAGE,
    MAX_HOLD_CYCLES,
    INITIAL_EQUITY,
    FUTURES_TAKER_FEE_RATE,
    FUNDING_SETTLEMENT_SECONDS,
    USE_API_FUNDING_RATE,
    FUNDING_RATE_FALLBACK,
    HOURLY_REPORT_INTERVAL_SEC,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)
import strategy
from strategy import parse_klines, compute_signal, check_stop_loss_take_profit
from risk_manager import RiskManager
from paper_engine import PaperEngine
from exchange import (
    get_equity_and_position,
    fetch_klines,
    open_long,
    open_short,
    close_position,
    position_size_from_equity,
    position_size_full_leverage,
)
from notify import notify_trade, notify_close, save_equity_redis, notify_hourly_pnl_report
from rest_client import get_market_funding_rate
from decision_journal import append_cycle_journal, prefetch_cross_exchange_for_cycle
from entry_gates import passes_entry_gates, will_open_or_reverse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 持仓后经过的轮询周期数，用于 MAX_HOLD_CYCLES 到时强制平仓
_cycles_with_position = 0
_last_decision_rationale = ""
_last_funding_rate_used = 0.0
_hour_start_equity: Optional[float] = None
_last_hourly_report_time = 0.0
_position_entry_time: Optional[float] = None  # 开仓时间戳
_last_signal_quality: Optional[float] = None  # 最近信号质量


def _telegram_enabled() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID is not None)


def _resolve_funding_rate() -> float:
    """从 Poloniex 公开接口读 fR，失败则用兜底。"""
    global _last_funding_rate_used
    if not USE_API_FUNDING_RATE:
        _last_funding_rate_used = FUNDING_RATE_FALLBACK
        return FUNDING_RATE_FALLBACK
    d = get_market_funding_rate(SYMBOL)
    if isinstance(d, dict):
        for k in ("fR", "fundingRate", "fr"):
            if k in d and d[k] is not None:
                try:
                    _last_funding_rate_used = float(d[k])
                    return _last_funding_rate_used
                except (TypeError, ValueError):
                    pass
    _last_funding_rate_used = FUNDING_RATE_FALLBACK
    return FUNDING_RATE_FALLBACK


def _maybe_hourly_report(
    paper: Optional[PaperEngine],
    equity: float,
    mark_price: float,
    pos_side: Optional[str],
    pos_size: float,
    entry_price: float,
    risk: RiskManager,
) -> None:
    global _hour_start_equity, _last_hourly_report_time
    if not _telegram_enabled() or paper is None:
        return
    now = time.time()
    if _hour_start_equity is None:
        _hour_start_equity = equity
    if now - _last_hourly_report_time < HOURLY_REPORT_INTERVAL_SEC:
        return
    snap = paper.accounting_snapshot()
    
    # 获取市场状态摘要
    market_state = _get_market_state_summary(mark_price)
    
    notify_hourly_pnl_report(
        equity=equity,
        initial_equity=INITIAL_EQUITY,
        equity_at_hour_start=_hour_start_equity,
        mark_price=mark_price,
        pos_side=pos_side,
        entry_price=entry_price,
        pos_size=pos_size,
        total_fees_paid=float(snap.get("total_fees_paid", 0.0)),
        total_funding_cashflow=float(snap.get("total_funding_cashflow", 0.0)),
        funding_rate_used=_last_funding_rate_used,
        taker_fee_rate=FUTURES_TAKER_FEE_RATE,
        last_decision_rationale=_last_decision_rationale,
        symbol=SYMBOL,
        risk_stats=risk.get_statistics(),
        market_state=market_state,
    )
    _last_hourly_report_time = now
    _hour_start_equity = equity


def _get_market_state_summary(mark_price: float) -> str:
    """获取市场状态摘要"""
    try:
        data = fetch_klines()
        if not data or len(data) < 50:
            return "数据不足"
        o, h, l, c, _ = parse_klines(data)
        
        # 趋势
        ema_20 = strategy._ema(c, 20)
        ema_50 = strategy._ema(c, 50)
        trend = "上升" if ema_20[-1] > ema_50[-1] else "下降"
        
        # 波动率
        atr = strategy._atr(h, l, c, 14)
        atr_pct = (atr[-1] / mark_price * 100) if mark_price > 0 else 0
        volatility = "高" if atr_pct > 2 else "中" if atr_pct > 1 else "低"
        
        # RSI
        rsi = strategy._rsi(c, 14)
        rsi_val = rsi[-1] if rsi[-1] is not None else 50
        rsi_state = "超买" if rsi_val > 70 else "超卖" if rsi_val < 30 else "中性"
        
        return f"趋势: {trend} | 波动: {volatility} ({atr_pct:.2f}%) | RSI: {rsi_val:.1f} ({rsi_state})"
    except Exception as e:
        return f"获取失败: {str(e)}"


def run_once(paper: Optional[PaperEngine], risk: RiskManager) -> None:
    global _cycles_with_position, _last_decision_rationale, _position_entry_time, _last_signal_quality
    jm: Dict[str, Any] = {"unix_ts": time.time()}
    try:
        # 1. K 线
        data = fetch_klines()
        if not data:
            logger.warning("无 K 线数据")
            jm["abort"] = "no_klines"
            jm["action"] = "abort_no_klines"
            return
        o, h, l, c, _ = parse_klines(data)
        if len(c) < 2:
            jm["abort"] = "insufficient_bars"
            jm["action"] = "abort_insufficient_bars"
            return
        mark_price = c[-1]
        jm.update(
            {
                "o": o,
                "h": h,
                "l": l,
                "c": c,
                "mark_price": mark_price,
            }
        )

        # 1.1 资金费摊销（仅 Paper）
        if paper is not None:
            fr = _resolve_funding_rate()
            paper.accrue_funding(mark_price, fr, time.time())
            jm["funding_rate"] = _last_funding_rate_used

        # 2. 权益与持仓
        equity, pos_side, pos_size, entry_price = get_equity_and_position(paper, mark_price)
        jm.update(
            {
                "equity": equity,
                "pos_side": pos_side,
                "pos_size": pos_size,
                "entry_price": entry_price,
            }
        )
        if equity <= 0:
            logger.warning("权益<=0，跳过")
            jm["abort"] = "bad_equity"
            jm["action"] = "abort_bad_equity"
            return

        # 3. 信号与依据（返回包含信号质量）
        direction, sl, tp, rationale, signal_quality = compute_signal(o, h, l, c)
        _last_decision_rationale = rationale
        _last_signal_quality = signal_quality
        jm.update(
            {
                "direction": direction,
                "sl": sl,
                "tp": tp,
                "rationale": rationale,
                "signal_quality": signal_quality,
            }
        )

        prefetch_cross_exchange_for_cycle(mark_price, jm)

        _maybe_hourly_report(paper, equity, mark_price, pos_side, pos_size, entry_price, risk)

        # 4. 风控
        can_trade, reason = risk.can_trade(equity)
        jm["can_trade"] = can_trade
        jm["risk_reason"] = reason
        if not can_trade:
            logger.warning("风控停机: %s", reason)
            jm["action"] = "risk_blocked"
            return

        # 5. 止损/止盈检查（有持仓时）
        if pos_side and pos_size > 0:
            sl_tp = check_stop_loss_take_profit(pos_side, entry_price, mark_price)
            if sl_tp:
                hold_time = int(time.time() - _position_entry_time) if _position_entry_time else None
                pnl = close_position(pos_side, pos_size, mark_price, paper)
                risk.record_trade(pnl, equity)
                _cycles_with_position = 0
                _position_entry_time = None
                equity_after = get_equity_and_position(paper, mark_price)[0]
                notify_close(
                    pos_side,
                    mark_price,
                    pnl,
                    sl_tp + "（本笔已扣平仓手续费）",
                    current_equity=equity_after,
                    initial_equity=INITIAL_EQUITY,
                    entry_price=entry_price,
                    hold_time=hold_time,
                )
                logger.info("平仓 %s @ %s, 盈亏=%.2f", sl_tp, mark_price, pnl)
                jm["action"] = "close_" + str(sl_tp)
                return
            # 最大持仓周期：到点强制平仓，便于频繁重新开仓
            if MAX_HOLD_CYCLES > 0:
                _cycles_with_position += 1
                if _cycles_with_position >= MAX_HOLD_CYCLES:
                    hold_time = int(time.time() - _position_entry_time) if _position_entry_time else None
                    pnl = close_position(pos_side, pos_size, mark_price, paper)
                    risk.record_trade(pnl, equity)
                    _cycles_with_position = 0
                    _position_entry_time = None
                    equity_after = get_equity_and_position(paper, mark_price)[0]
                    notify_close(
                        pos_side,
                        mark_price,
                        pnl,
                        "最大持仓周期（本笔已扣平仓手续费）",
                        current_equity=equity_after,
                        initial_equity=INITIAL_EQUITY,
                        entry_price=entry_price,
                        hold_time=hold_time,
                    )
                    logger.info("平仓 最大持仓周期 @ %s, 盈亏=%.2f", mark_price, pnl)
                    jm["action"] = "close_max_hold_cycles"
                    return
        else:
            _cycles_with_position = 0

        # 6. 仓位：根据风控建议动态调整
        position_scale = risk.suggest_position_scale()
        jm["position_scale"] = position_scale
        if SIMULATE_ONLY:
            size = position_size_full_leverage(equity, mark_price, LEVERAGE) * position_scale
        else:
            size = position_size_from_equity(equity, mark_price) * position_scale
        if size <= 0:
            jm["action"] = "skip_zero_size"
            return

        if will_open_or_reverse(direction, pos_side):
            ok_gate, gate_reason = passes_entry_gates(
                direction, signal_quality, pos_side, jm.get("cross_exchange")
            )
            if not ok_gate:
                jm["entry_gate_reason"] = gate_reason
                jm["action"] = "skip_entry_gate"
                logger.info("开仓门禁拦截: %s", gate_reason)
                if paper:
                    save_equity_redis(equity, INITIAL_EQUITY)
                return

        if pos_side == "LONG" and direction == -1:
            hold_time = int(time.time() - _position_entry_time) if _position_entry_time else None
            pnl = close_position("LONG", pos_size, mark_price, paper)
            risk.record_trade(pnl, equity)
            _cycles_with_position = 0
            equity_after = get_equity_and_position(paper, mark_price)[0]
            logger.info("平多 @ %s, 盈亏=%.2f，准备开空", mark_price, pnl)
            notify_close(
                "LONG",
                mark_price,
                pnl,
                "反向开空（本笔已扣平仓手续费）",
                current_equity=equity_after,
                initial_equity=INITIAL_EQUITY,
                entry_price=entry_price,
                hold_time=hold_time,
            )
            open_short(mark_price, size, sl, tp, paper)
            _position_entry_time = time.time()
            equity_now = get_equity_and_position(paper, mark_price)[0]
            notify_trade(
                "开空",
                mark_price,
                size,
                sl,
                tp,
                current_equity=equity_now,
                initial_equity=INITIAL_EQUITY,
                decision_reason=rationale,
                signal_quality=signal_quality,
                position_scale=position_scale,
            )
            logger.info("开空 size=%.4f sl=%s tp=%s", size, sl, tp)
            jm["action"] = "reverse_long_to_short"
            return
        if pos_side == "SHORT" and direction == 1:
            hold_time = int(time.time() - _position_entry_time) if _position_entry_time else None
            pnl = close_position("SHORT", pos_size, mark_price, paper)
            risk.record_trade(pnl, equity)
            _cycles_with_position = 0
            equity_after = get_equity_and_position(paper, mark_price)[0]
            logger.info("平空 @ %s, 盈亏=%.2f，准备开多", mark_price, pnl)
            notify_close(
                "SHORT",
                mark_price,
                pnl,
                "反向开多（本笔已扣平仓手续费）",
                current_equity=equity_after,
                initial_equity=INITIAL_EQUITY,
                entry_price=entry_price,
                hold_time=hold_time,
            )
            open_long(mark_price, size, sl, tp, paper)
            _position_entry_time = time.time()
            equity_now = get_equity_and_position(paper, mark_price)[0]
            notify_trade(
                "开多",
                mark_price,
                size,
                sl,
                tp,
                current_equity=equity_now,
                initial_equity=INITIAL_EQUITY,
                decision_reason=rationale,
                signal_quality=signal_quality,
                position_scale=position_scale,
            )
            logger.info("开多 size=%.4f sl=%s tp=%s", size, sl, tp)
            jm["action"] = "reverse_short_to_long"
            return

        # 无仓或同向不加仓
        if pos_side:
            if paper:
                save_equity_redis(equity, INITIAL_EQUITY)
            jm["action"] = "hold_same_direction_no_add"
            return
        if direction == 1:
            open_long(mark_price, size, sl, tp, paper)
            _position_entry_time = time.time()
            equity_now = get_equity_and_position(paper, mark_price)[0]
            notify_trade(
                "开多",
                mark_price,
                size,
                sl,
                tp,
                current_equity=equity_now,
                initial_equity=INITIAL_EQUITY,
                decision_reason=rationale,
                signal_quality=signal_quality,
                position_scale=position_scale,
            )
            logger.info("开多 size=%.4f sl=%s tp=%s", size, sl, tp)
            jm["action"] = "open_long"
        elif direction == -1:
            open_short(mark_price, size, sl, tp, paper)
            _position_entry_time = time.time()
            equity_now = get_equity_and_position(paper, mark_price)[0]
            notify_trade(
                "开空",
                mark_price,
                size,
                sl,
                tp,
                current_equity=equity_now,
                initial_equity=INITIAL_EQUITY,
                decision_reason=rationale,
                signal_quality=signal_quality,
                position_scale=position_scale,
            )
            logger.info("开空 size=%.4f sl=%s tp=%s", size, sl, tp)
            jm["action"] = "open_short"
        elif paper:
            save_equity_redis(equity, INITIAL_EQUITY)
            jm["action"] = "flat_no_signal"
        else:
            jm["action"] = "flat_no_signal"
    finally:
        append_cycle_journal(jm, risk)


def main() -> None:
    paper = (
        PaperEngine(
            initial_equity=INITIAL_EQUITY,
            taker_fee_rate=FUTURES_TAKER_FEE_RATE,
            funding_settlement_seconds=FUNDING_SETTLEMENT_SECONDS,
        )
        if (PAPER_MODE or SIMULATE_ONLY)
        else None
    )
    risk = RiskManager()

    if SIMULATE_ONLY:
        logger.info("模拟交易模式：不配置 Key，自动多空决策，全仓 %s 倍，Telegram + Redis", LEVERAGE)
    if PAPER_MODE or SIMULATE_ONLY:
        logger.info(
            "Paper 初始本金 %.2f | Taker 费率 %.5f | 资金费 API=%s",
            INITIAL_EQUITY,
            FUTURES_TAKER_FEE_RATE,
            USE_API_FUNDING_RATE,
        )

    interval_sec = 60  # 每分钟轮询一次
    while True:
        try:
            run_once(paper, risk)
            if PAPER_MODE and paper:
                logger.info("Paper 权益 ≈ %.2f", paper.get_equity())
        except Exception as e:
            logger.exception("run_once error: %s", e)
        time.sleep(interval_sec)


if __name__ == "__main__":
    main()
