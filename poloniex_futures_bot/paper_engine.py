# -*- coding: utf-8 -*-
"""
Paper 模式：模拟持仓与权益，不真实下单。
"""
from typing import Optional, Dict, Any
from config import SYMBOL, POSITION_EQUITY_RATIO


class PaperEngine:
    def __init__(self, initial_equity: float = 10000.0):
        self.equity = initial_equity
        self.position_side: Optional[str] = None  # LONG / SHORT / None
        self.position_size: float = 0.0
        self.entry_price: float = 0.0
        self.stop_loss: Optional[float] = None
        self.take_profit: Optional[float] = None

    def get_equity(self) -> float:
        return self.equity

    def get_position(self) -> Dict[str, Any]:
        return {
            "side": self.position_side,
            "sz": str(self.position_size),
            "entryPrice": self.entry_price,
            "symbol": SYMBOL,
        }

    def position_value(self, mark_price: float) -> float:
        if self.position_side is None or self.position_size == 0:
            return 0.0
        if self.position_side == "LONG":
            return self.position_size * (mark_price - self.entry_price)
        return self.position_size * (self.entry_price - mark_price)

    def open_long(self, price: float, size: float, sl: Optional[float], tp: Optional[float]) -> None:
        self.position_side = "LONG"
        self.position_size = size
        self.entry_price = price
        self.stop_loss = sl
        self.take_profit = tp

    def open_short(self, price: float, size: float, sl: Optional[float], tp: Optional[float]) -> None:
        self.position_side = "SHORT"
        self.position_size = size
        self.entry_price = price
        self.stop_loss = sl
        self.take_profit = tp

    def close_position(self, price: float) -> float:
        """平仓，返回本次盈亏。"""
        pnl = self.position_value(price)
        self.equity += pnl
        self.position_side = None
        self.position_size = 0.0
        self.entry_price = 0.0
        self.stop_loss = None
        self.take_profit = None
        return pnl

    def position_size_from_equity(self, price: float) -> float:
        """按权益的 POSITION_EQUITY_RATIO 计算张数（简化：1 张 = 1 单位 BTC）。"""
        if price <= 0:
            return 0.0
        notional = self.equity * POSITION_EQUITY_RATIO
        return notional / price
