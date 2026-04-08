# -*- coding: utf-8 -*-
"""
Paper 模式：模拟持仓与权益，不真实下单。
含 Taker 手续费（开/平各扣一次名义×费率）与资金费按结算周期线性摊销。
"""
import time
from typing import Optional, Dict, Any
from config import SYMBOL, POSITION_EQUITY_RATIO


class PaperEngine:
    def __init__(
        self,
        initial_equity: float = 10000.0,
        taker_fee_rate: float = 0.0,
        funding_settlement_seconds: float = 28800.0,
    ):
        self.equity = initial_equity
        self.taker_fee_rate = float(taker_fee_rate)
        self.funding_settlement_seconds = max(1.0, float(funding_settlement_seconds))
        self.position_side: Optional[str] = None  # LONG / SHORT / None
        self.position_size: float = 0.0
        self.entry_price: float = 0.0
        self.stop_loss: Optional[float] = None
        self.take_profit: Optional[float] = None
        self.total_fees_paid: float = 0.0
        self.total_funding_cashflow: float = 0.0
        self._last_funding_ts: float = time.time()

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
        fee = price * size * self.taker_fee_rate
        self.equity -= fee
        self.total_fees_paid += fee
        self.position_side = "LONG"
        self.position_size = size
        self.entry_price = price
        self.stop_loss = sl
        self.take_profit = tp

    def open_short(self, price: float, size: float, sl: Optional[float], tp: Optional[float]) -> None:
        fee = price * size * self.taker_fee_rate
        self.equity -= fee
        self.total_fees_paid += fee
        self.position_side = "SHORT"
        self.position_size = size
        self.entry_price = price
        self.stop_loss = sl
        self.take_profit = tp

    def close_position(self, price: float) -> float:
        """平仓，返回本次价格盈亏净额（已扣平仓手续费；开仓手续费已在开仓时扣除）。"""
        gross = self.position_value(price)
        fee_close = price * self.position_size * self.taker_fee_rate
        self.total_fees_paid += fee_close
        net = gross - fee_close
        self.equity += net
        self.position_side = None
        self.position_size = 0.0
        self.entry_price = 0.0
        self.stop_loss = None
        self.take_profit = None
        return net

    def accrue_funding(self, mark_price: float, funding_rate: float, now_ts: Optional[float] = None) -> float:
        """
        按结算周期将资金费线性摊入权益。funding_rate 与接口 fR 一致。
        多仓: rate>0 通常支付（权益减少）。
        返回本次摊销金额（正=入账增加权益）。
        """
        ts = time.time() if now_ts is None else float(now_ts)
        if self.position_side is None or self.position_size <= 0 or mark_price <= 0:
            self._last_funding_ts = ts
            return 0.0
        dt = max(0.0, ts - self._last_funding_ts)
        notional = self.position_size * mark_price
        side_mult = 1.0 if self.position_side == "LONG" else -1.0
        frac = dt / self.funding_settlement_seconds
        payment = -side_mult * notional * float(funding_rate) * frac
        self.equity += payment
        self.total_funding_cashflow += payment
        self._last_funding_ts = ts
        return payment

    def accounting_snapshot(self) -> Dict[str, Any]:
        return {
            "total_fees_paid": self.total_fees_paid,
            "total_funding_cashflow": self.total_funding_cashflow,
        }

    def position_size_from_equity(self, price: float) -> float:
        """按权益的 POSITION_EQUITY_RATIO 计算张数（简化：1 张 = 1 单位 BTC）。"""
        if price <= 0:
            return 0.0
        notional = self.equity * POSITION_EQUITY_RATIO
        return notional / price
