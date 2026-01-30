#!/usr/bin/env python3
"""
移动平均策略示例
"""
import pandas as pd
import numpy as np
from typing import List, Dict
from .base_strategy import BaseStrategy
import logging

logger = logging.getLogger(__name__)


class MAStrategy(BaseStrategy):
    """移动平均交叉策略"""
    
    def __init__(self, exchange, symbol: str, fast_period: int = 5, slow_period: int = 20, **kwargs):
        """
        初始化移动平均策略
        
        Args:
            exchange: 交易所API实例
            symbol: 交易对
            fast_period: 快速均线周期
            slow_period: 慢速均线周期
        """
        super().__init__(exchange, symbol, **kwargs)
        self.fast_period = fast_period
        self.slow_period = slow_period
        logger.info(f"MA策略: 快线={fast_period}, 慢线={slow_period}")
    
    def _calculate_ma(self, closes: List[float], period: int) -> float:
        """计算移动平均"""
        if len(closes) < period:
            return None
        return np.mean(closes[-period:])
    
    def analyze(self, data: List) -> Dict:
        """
        分析K线数据
        
        Args:
            data: K线数据 [[timestamp, open, high, low, close, volume], ...]
        
        Returns:
            交易信号
        """
        if len(data) < self.slow_period:
            return {'signal': 'hold', 'reason': '数据不足'}
        
        # 转换为 DataFrame
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        closes = df['close'].tolist()
        
        # 计算移动平均
        fast_ma = self._calculate_ma(closes, self.fast_period)
        slow_ma = self._calculate_ma(closes, self.slow_period)
        current_price = closes[-1]
        
        if fast_ma is None or slow_ma is None:
            return {'signal': 'hold', 'reason': '数据不足'}
        
        # 判断信号
        if fast_ma > slow_ma:
            # 快线上穿慢线，买入信号
            prev_fast = self._calculate_ma(closes[:-1], self.fast_period)
            prev_slow = self._calculate_ma(closes[:-1], self.slow_period)
            
            if prev_fast and prev_slow and prev_fast <= prev_slow:
                return {
                    'signal': 'buy',
                    'price': current_price,
                    'reason': f'金叉: 快线({fast_ma:.2f}) > 慢线({slow_ma:.2f})'
                }
        
        elif fast_ma < slow_ma:
            # 快线下穿慢线，卖出信号
            prev_fast = self._calculate_ma(closes[:-1], self.fast_period)
            prev_slow = self._calculate_ma(closes[:-1], self.slow_period)
            
            if prev_fast and prev_slow and prev_fast >= prev_slow:
                return {
                    'signal': 'sell',
                    'price': current_price,
                    'reason': f'死叉: 快线({fast_ma:.2f}) < 慢线({slow_ma:.2f})'
                }
        
        return {'signal': 'hold', 'reason': '等待信号'}
    
    def should_buy(self, data: List) -> bool:
        """判断是否应该买入"""
        signal = self.analyze(data)
        return signal['signal'] == 'buy'
    
    def should_sell(self, data: List) -> bool:
        """判断是否应该卖出"""
        signal = self.analyze(data)
        return signal['signal'] == 'sell'
