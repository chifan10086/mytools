# -*- coding: utf-8 -*-
"""
Poloniex BTC 永续合约交易机器人主循环。
单向持仓；EMA20/60 + ATR14；止损止盈；模拟模式可全仓 30 倍、发 Telegram、写 Redis。
"""
import time
import logging
from typing import Optional

from config import SYMBOL, PAPER_MODE, SIMULATE_ONLY, LEVERAGE, MAX_HOLD_CYCLES, INITIAL_EQUITY
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
from notify import notify_trade, notify_close, save_equity_redis, notify_position_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 持仓后经过的轮询周期数，用于 MAX_HOLD_CYCLES 到时强制平仓
_cycles_with_position = 0
# 每 10 分钟向 TG 汇报持仓盈亏（仅在有持仓时）
_position_report_interval = 600
_last_position_report_time = 0.0


def run_once(paper: Optional[PaperEngine], risk: RiskManager) -> None:
    global _cycles_with_position, _last_position_report_time
    # 1. K 线
    data = fetch_klines()
    if not data:
        logger.warning("无 K 线数据")
        return
    o, h, l, c, _ = parse_klines(data)
    if len(c) < 2:
        return
    mark_price = c[-1]

    # 2. 权益与持仓
    equity, pos_side, pos_size, entry_price = get_equity_and_position(paper, mark_price)
    if equity <= 0:
        logger.warning("权益<=0，跳过")
        return

    # 2.1 每 10 分钟汇报持仓盈亏（仅在有持仓时）
    if pos_side and pos_size > 0 and paper is not None:
        if time.time() - _last_position_report_time >= _position_report_interval:
            notify_position_report(pos_side, entry_price, mark_price, pos_size, equity, INITIAL_EQUITY)
            _last_position_report_time = time.time()

    # 3. 风控
    can_trade, reason = risk.can_trade(equity)
    if not can_trade:
        logger.warning("风控停机: %s", reason)
        return

    # 4. 止损/止盈检查（有持仓时）
    if pos_side and pos_size > 0:
        sl_tp = check_stop_loss_take_profit(pos_side, entry_price, mark_price)
        if sl_tp:
            pnl = close_position(pos_side, pos_size, mark_price, paper)
            risk.record_trade(pnl, equity)
            _cycles_with_position = 0
            equity_after = get_equity_and_position(paper, mark_price)[0]
            notify_close(pos_side, mark_price, pnl, sl_tp, current_equity=equity_after, initial_equity=INITIAL_EQUITY)
            logger.info("平仓 %s @ %s, 盈亏=%.2f", sl_tp, mark_price, pnl)
            return
        # 最大持仓周期：到点强制平仓，便于频繁重新开仓
        if MAX_HOLD_CYCLES > 0:
            _cycles_with_position += 1
            if _cycles_with_position >= MAX_HOLD_CYCLES:
                pnl = close_position(pos_side, pos_size, mark_price, paper)
                risk.record_trade(pnl, equity)
                _cycles_with_position = 0
                equity_after = get_equity_and_position(paper, mark_price)[0]
                notify_close(pos_side, mark_price, pnl, "最大持仓周期", current_equity=equity_after, initial_equity=INITIAL_EQUITY)
                logger.info("平仓 最大持仓周期 @ %s, 盈亏=%.2f", mark_price, pnl)
                return
    else:
        _cycles_with_position = 0

    # 5. 信号
    direction, sl, tp = compute_signal(o, h, l, c)

    # 6. 仓位：模拟模式全仓 30 倍，否则按比例
    if SIMULATE_ONLY:
        size = position_size_full_leverage(equity, mark_price, LEVERAGE)
    else:
        size = position_size_from_equity(equity, mark_price)
    if size <= 0:
        return

    if pos_side == "LONG" and direction == -1:
        pnl = close_position("LONG", pos_size, mark_price, paper)
        risk.record_trade(pnl, equity)
        _cycles_with_position = 0
        equity_after = get_equity_and_position(paper, mark_price)[0]
        logger.info("平多 @ %s, 盈亏=%.2f，准备开空", mark_price, pnl)
        notify_close("LONG", mark_price, pnl, "反向开空", current_equity=equity_after, initial_equity=INITIAL_EQUITY)
        open_short(mark_price, size, sl, tp, paper)
        equity_now = get_equity_and_position(paper, mark_price)[0]
        notify_trade("开空", mark_price, size, sl, tp, current_equity=equity_now, initial_equity=INITIAL_EQUITY)
        logger.info("开空 size=%.4f sl=%s tp=%s", size, sl, tp)
        return
    if pos_side == "SHORT" and direction == 1:
        pnl = close_position("SHORT", pos_size, mark_price, paper)
        risk.record_trade(pnl, equity)
        _cycles_with_position = 0
        equity_after = get_equity_and_position(paper, mark_price)[0]
        logger.info("平空 @ %s, 盈亏=%.2f，准备开多", mark_price, pnl)
        notify_close("SHORT", mark_price, pnl, "反向开多", current_equity=equity_after, initial_equity=INITIAL_EQUITY)
        open_long(mark_price, size, sl, tp, paper)
        equity_now = get_equity_and_position(paper, mark_price)[0]
        notify_trade("开多", mark_price, size, sl, tp, current_equity=equity_now, initial_equity=INITIAL_EQUITY)
        logger.info("开多 size=%.4f sl=%s tp=%s", size, sl, tp)
        return

    # 无仓或同向不加仓
    if pos_side:
        if paper:
            save_equity_redis(equity, INITIAL_EQUITY)
        return
    if direction == 1:
        open_long(mark_price, size, sl, tp, paper)
        equity_now = get_equity_and_position(paper, mark_price)[0]
        notify_trade("开多", mark_price, size, sl, tp, current_equity=equity_now, initial_equity=INITIAL_EQUITY)
        logger.info("开多 size=%.4f sl=%s tp=%s", size, sl, tp)
    elif direction == -1:
        open_short(mark_price, size, sl, tp, paper)
        equity_now = get_equity_and_position(paper, mark_price)[0]
        notify_trade("开空", mark_price, size, sl, tp, current_equity=equity_now, initial_equity=INITIAL_EQUITY)
        logger.info("开空 size=%.4f sl=%s tp=%s", size, sl, tp)
    elif paper:
        save_equity_redis(equity, INITIAL_EQUITY)


def main() -> None:
    paper = PaperEngine(initial_equity=INITIAL_EQUITY) if (PAPER_MODE or SIMULATE_ONLY) else None
    risk = RiskManager()

    if SIMULATE_ONLY:
        logger.info("模拟交易模式：不配置 Key，自动多空决策，全仓 %s 倍，Telegram + Redis", LEVERAGE)
    if PAPER_MODE or SIMULATE_ONLY:
        logger.info("Paper 初始本金 %.2f", INITIAL_EQUITY)

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
