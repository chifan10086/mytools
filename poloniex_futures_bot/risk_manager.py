# -*- coding: utf-8 -*-
"""
风控：连续亏损 N 次停机（config.MAX_CONSECUTIVE_LOSSES）；每日亏损 5% 停机。
"""
import time
from typing import Optional, Tuple
from config import MAX_CONSECUTIVE_LOSSES, DAILY_LOSS_RATIO


class RiskManager:
    def __init__(self):
        self.consecutive_losses = 0
        self.daily_pnl: float = 0.0
        self.daily_reset_ts: int = 0  # 当日 0 点时间戳（秒）

    def _ensure_day(self, equity: float) -> None:
        now = int(time.time())
        day_start = now - (now % 86400)
        if day_start != self.daily_reset_ts:
            self.daily_reset_ts = day_start
            self.daily_pnl = 0.0

    def record_trade(self, pnl: float, equity: float) -> None:
        self._ensure_day(equity)
        self.daily_pnl += pnl
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    def should_stop_consecutive_loss(self) -> bool:
        return self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES

    def should_stop_daily_loss(self, equity: float) -> bool:
        if equity <= 0:
            return True
        self._ensure_day(equity)
        return self.daily_pnl <= -equity * DAILY_LOSS_RATIO

    def can_trade(self, equity: float) -> Tuple[bool, str]:
        """返回 (是否可以交易, 原因)。"""
        if self.should_stop_consecutive_loss():
            return False, f"连续亏损 {self.consecutive_losses} 次，已达上限 {MAX_CONSECUTIVE_LOSSES}"
        if self.should_stop_daily_loss(equity):
            return False, f"当日亏损 {self.daily_pnl:.2f} 已达权益 {equity:.2f} 的 {DAILY_LOSS_RATIO*100}%"
        return True, ""
