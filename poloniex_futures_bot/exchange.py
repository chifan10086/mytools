# -*- coding: utf-8 -*-
"""
交易所接口封装：获取权益、持仓、下单、平仓。
实盘用 REST，Paper 用 paper_engine。
"""
from typing import Optional, Dict, Any, List

from config import SYMBOL, POSITION_EQUITY_RATIO, PAPER_MODE, LEVERAGE, SIMULATE_ONLY
from rest_client import (
    get_klines,
    get_account_balance,
    get_positions,
    place_order,
    close_position_at_market,
)
from paper_engine import PaperEngine

# 合约面值（1 张 = 多少 BTC）。Poloniex 常见为 0.001
CONTRACT_SIZE = 0.001


def get_equity_and_position(paper: Optional[PaperEngine], mark_price: float) -> tuple:
    """返回 (equity, position_side, position_size, entry_price)。position_side 为 None/LONG/SHORT。"""
    if (PAPER_MODE or SIMULATE_ONLY) and paper is not None:
        eq = paper.get_equity() + paper.position_value(mark_price)
        pos = paper.get_position()
        side = pos.get("side")
        sz = float(pos.get("sz") or 0)
        entry = pos.get("entryPrice") or 0
        return eq, side, sz, entry

    # 实盘：从账户与持仓解析（Poloniex V3 账户接口返回格式以官方文档为准，此处做兼容）
    balance = get_account_balance()
    equity = 0.0
    if isinstance(balance, list) and balance:
        for item in balance:
            if isinstance(item, dict):
                equity = float(
                    item.get("totalEquity") or item.get("equity") or item.get("balance") or 0
                )
                if equity > 0:
                    break
    elif isinstance(balance, dict):
        equity = float(
            balance.get("totalEquity") or balance.get("equity") or balance.get("balance") or 0
        )

    positions = get_positions(SYMBOL)
    position_side = None
    position_size = 0.0
    entry_price = 0.0
    for p in positions:
        if isinstance(p, dict) and p.get("symbol") == SYMBOL:
            side = p.get("posSide") or p.get("side")
            if side in ("LONG", "SHORT"):
                position_side = side
                position_size = float(p.get("qty") or p.get("sz") or 0)
                entry_price = float(p.get("openAvgPx") or p.get("avgPx") or 0)
            break
    return equity, position_side, position_size, entry_price


def fetch_klines() -> List[List]:
    from config import KLINE_INTERVAL, KLINE_LIMIT
    return get_klines(SYMBOL, KLINE_INTERVAL, limit=KLINE_LIMIT)


def fetch_klines_mtf(interval: str, limit: int) -> List[List]:
    """获取指定周期的 K 线，供多时间框架策略使用。"""
    return get_klines(SYMBOL, interval, limit=limit)


def open_long(mark_price: float, size: float, sl: Optional[float], tp: Optional[float], paper: Optional[PaperEngine]) -> None:
    if (PAPER_MODE or SIMULATE_ONLY) and paper is not None:
        paper.open_long(mark_price, size, sl, tp)
        return
    sz_str = str(round(size / CONTRACT_SIZE, 0))  # 张数
    place_order(SYMBOL, "BUY", "LONG", "MARKET", sz_str, reduce_only=False)


def open_short(mark_price: float, size: float, sl: Optional[float], tp: Optional[float], paper: Optional[PaperEngine]) -> None:
    if (PAPER_MODE or SIMULATE_ONLY) and paper is not None:
        paper.open_short(mark_price, size, sl, tp)
        return
    sz_str = str(round(size / CONTRACT_SIZE, 0))
    place_order(SYMBOL, "SELL", "SHORT", "MARKET", sz_str, reduce_only=False)


def close_position(side: str, size: float, mark_price: float, paper: Optional[PaperEngine]) -> float:
    """平仓。返回本次盈亏（paper 时）。"""
    if (PAPER_MODE or SIMULATE_ONLY) and paper is not None:
        return paper.close_position(mark_price)
    sz_str = str(round(size / CONTRACT_SIZE, 0))
    close_position_at_market(SYMBOL, side, sz_str)
    return 0.0


def position_size_from_equity(equity: float, price: float) -> float:
    """按权益比例计算仓位（BTC 数量）。"""
    if price <= 0:
        return 0.0
    notional = equity * POSITION_EQUITY_RATIO
    return notional / price


def position_size_by_risk(
    equity: float,
    price: float,
    risk_ratio: float,
    stop_loss_ratio: float,
    fee_rate: float,
    leverage: Optional[int] = None,
) -> float:
    """
    按单笔风险预算定仓：触发止损时（含开平双边手续费）亏损 ≈ 权益 × risk_ratio。
    名义仓位受 leverage 上限约束，返回 BTC 数量。
    """
    if price <= 0 or risk_ratio <= 0:
        return 0.0
    loss_per_notional = stop_loss_ratio + 2 * fee_rate
    if loss_per_notional <= 0:
        return 0.0
    lev = leverage if leverage is not None else LEVERAGE
    notional = min(equity * risk_ratio / loss_per_notional, equity * lev)
    return notional / price
