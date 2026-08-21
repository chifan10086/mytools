# -*- coding: utf-8 -*-
"""
风控：连续亏损 N 次停机（config.MAX_CONSECUTIVE_LOSSES）；每日亏损 5% 停机。
连亏停机为冷静期而非永久熔断：经过 CONSECUTIVE_LOSS_COOLDOWN_SEC 后自动复位。
增强：交易统计、胜率、盈亏比、最大回撤、动态仓位调整。
"""
import time
from typing import Optional, Tuple, Dict, Any

import config_bootstrap  # noqa: F401

from config import MAX_CONSECUTIVE_LOSSES, DAILY_LOSS_RATIO, CONSECUTIVE_LOSS_COOLDOWN_SEC


class RiskManager:
    def __init__(self):
        self.consecutive_losses = 0
        self.daily_pnl: float = 0.0
        self.daily_reset_ts: int = 0
        self.cooldown_until_ts: float = 0.0
        
        # 交易统计
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0
        self.total_loss = 0.0
        self.max_win = 0.0
        self.max_loss = 0.0
        
        # 回撤跟踪
        self.peak_equity = 0.0
        self.max_drawdown = 0.0
        self.current_drawdown = 0.0
        
        # 最近 N 笔交易（用于动态调整）
        self.recent_trades = []  # [(pnl, equity, timestamp)]
        self.recent_limit = 20

    def _ensure_day(self, equity: float) -> None:
        now = int(time.time())
        day_start = now - (now % 86400)
        if day_start != self.daily_reset_ts:
            self.daily_reset_ts = day_start
            self.daily_pnl = 0.0

    def record_trade(self, pnl: float, equity: float) -> None:
        self._ensure_day(equity)
        self.daily_pnl += pnl
        self.total_trades += 1
        
        # 胜率统计
        if pnl > 0:
            self.consecutive_losses = 0
            self.winning_trades += 1
            self.total_profit += pnl
            self.max_win = max(self.max_win, pnl)
        else:
            self.consecutive_losses += 1
            self.losing_trades += 1
            self.total_loss += abs(pnl)
            self.max_loss = max(self.max_loss, abs(pnl))
            if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
                self.cooldown_until_ts = time.time() + CONSECUTIVE_LOSS_COOLDOWN_SEC
        
        # 回撤计算
        if equity > self.peak_equity:
            self.peak_equity = equity
        self.current_drawdown = (self.peak_equity - equity) / self.peak_equity if self.peak_equity > 0 else 0
        self.max_drawdown = max(self.max_drawdown, self.current_drawdown)
        
        # 记录最近交易
        self.recent_trades.append((pnl, equity, time.time()))
        if len(self.recent_trades) > self.recent_limit:
            self.recent_trades.pop(0)

    def should_stop_consecutive_loss(self) -> bool:
        """连亏达上限后进入冷静期；冷静期满则复位计数，避免永久停机。"""
        if self.consecutive_losses < MAX_CONSECUTIVE_LOSSES:
            return False
        if time.time() >= self.cooldown_until_ts:
            self.consecutive_losses = 0
            self.cooldown_until_ts = 0.0
            return False
        return True

    def should_stop_daily_loss(self, equity: float) -> bool:
        if equity <= 0:
            return True
        self._ensure_day(equity)
        return self.daily_pnl <= -equity * DAILY_LOSS_RATIO

    def can_trade(self, equity: float) -> Tuple[bool, str]:
        """返回 (是否可以交易, 原因)。"""
        if self.should_stop_consecutive_loss():
            left = int(max(0.0, self.cooldown_until_ts - time.time()))
            return False, (
                f"连续亏损 {self.consecutive_losses} 次，已达上限 {MAX_CONSECUTIVE_LOSSES}，"
                f"冷静期剩余 {left}s"
            )
        if self.should_stop_daily_loss(equity):
            return False, f"当日亏损 {self.daily_pnl:.2f} 已达权益 {equity:.2f} 的 {DAILY_LOSS_RATIO*100}%"
        return True, ""
    
    def get_win_rate(self) -> float:
        """胜率"""
        return self.winning_trades / self.total_trades if self.total_trades > 0 else 0.0
    
    def get_profit_factor(self) -> float:
        """盈亏比（总盈利/总亏损）"""
        return self.total_profit / self.total_loss if self.total_loss > 0 else 0.0
    
    def get_avg_win(self) -> float:
        """平均盈利"""
        return self.total_profit / self.winning_trades if self.winning_trades > 0 else 0.0
    
    def get_avg_loss(self) -> float:
        """平均亏损"""
        return self.total_loss / self.losing_trades if self.losing_trades > 0 else 0.0
    
    def get_recent_performance(self) -> str:
        """最近表现摘要"""
        if len(self.recent_trades) < 5:
            return "交易样本不足"
        recent_pnl = sum(t[0] for t in self.recent_trades[-10:])
        recent_wins = sum(1 for t in self.recent_trades[-10:] if t[0] > 0)
        recent_rate = recent_wins / min(10, len(self.recent_trades))
        return f"近10笔: 盈亏{recent_pnl:+.2f} 胜率{recent_rate:.1%}"
    
    def suggest_position_scale(self) -> float:
        """根据近期表现建议仓位缩放系数 (0.5-1.5)"""
        if self.total_trades < 10:
            return 1.0
        
        win_rate = self.get_win_rate()
        profit_factor = self.get_profit_factor()
        
        # 连续亏损降低仓位
        if self.consecutive_losses >= 2:
            return 0.6
        elif self.consecutive_losses >= 1:
            return 0.8
        
        # 胜率和盈亏比好时增加仓位
        if win_rate > 0.6 and profit_factor > 1.5:
            return 1.3
        elif win_rate > 0.5 and profit_factor > 1.2:
            return 1.1
        elif win_rate < 0.4 or profit_factor < 0.8:
            return 0.7
        
        return 1.0
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取完整统计数据"""
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.get_win_rate(),
            "profit_factor": self.get_profit_factor(),
            "avg_win": self.get_avg_win(),
            "avg_loss": self.get_avg_loss(),
            "max_win": self.max_win,
            "max_loss": self.max_loss,
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown,
            "consecutive_losses": self.consecutive_losses,
            "daily_pnl": self.daily_pnl,
            "recent_performance": self.get_recent_performance(),
            "position_scale": self.suggest_position_scale(),
        }
