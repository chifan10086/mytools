#!/usr/bin/env python3
"""
Poloniex 交易所 API 封装
"""
import ccxt
import logging
from typing import Dict, List, Optional
from config.config import POLONIEX_API_KEY, POLONIEX_SECRET

logger = logging.getLogger(__name__)


class PoloniexAPI:
    """Poloniex 交易所 API 封装类"""
    
    def __init__(self, api_key: str = None, secret: str = None, sandbox: bool = False):
        """
        初始化 Poloniex API
        
        Args:
            api_key: API 密钥
            secret: API 密钥
            sandbox: 是否使用测试环境
        """
        self.api_key = api_key or POLONIEX_API_KEY
        self.secret = secret or POLONIEX_SECRET
        
        # 创建 Poloniex 交易所实例
        self.exchange = ccxt.poloniex({
            'apiKey': self.api_key,
            'secret': self.secret,
            'enableRateLimit': True,  # 启用速率限制
            'options': {
                'adjustForTimeDifference': True,  # 调整时间差
            }
        })
        
        if sandbox:
            self.exchange.set_sandbox_mode(True)
        
        logger.info("Poloniex API 初始化完成")
    
    def get_balance(self, currency: str = None) -> Dict:
        """
        获取账户余额
        
        Args:
            currency: 币种，如 'BTC', 'USDT'，None 返回所有余额
        
        Returns:
            余额字典
        """
        try:
            balance = self.exchange.fetch_balance()
            if currency:
                return {
                    'free': balance.get(currency, {}).get('free', 0),
                    'used': balance.get(currency, {}).get('used', 0),
                    'total': balance.get(currency, {}).get('total', 0)
                }
            return balance
        except Exception as e:
            logger.error(f"获取余额失败: {e}")
            raise
    
    def get_ticker(self, symbol: str) -> Dict:
        """
        获取交易对行情
        
        Args:
            symbol: 交易对，如 'BTC/USDT'
        
        Returns:
            行情信息
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'last': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'high': ticker['high'],
                'low': ticker['low'],
                'volume': ticker['volume'],
                'timestamp': ticker['timestamp']
            }
        except Exception as e:
            logger.error(f"获取行情失败: {e}")
            raise
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> List:
        """
        获取K线数据
        
        Args:
            symbol: 交易对
            timeframe: 时间周期，如 '1m', '5m', '1h', '1d'
            limit: 获取数量
        
        Returns:
            K线数据列表 [[timestamp, open, high, low, close, volume], ...]
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            raise
    
    def create_market_buy_order(self, symbol: str, amount: float) -> Dict:
        """
        创建市价买单
        
        Args:
            symbol: 交易对
            amount: 买入数量
        
        Returns:
            订单信息
        """
        try:
            order = self.exchange.create_market_buy_order(symbol, amount)
            logger.info(f"市价买入成功: {symbol} {amount}")
            return order
        except Exception as e:
            logger.error(f"市价买入失败: {e}")
            raise
    
    def create_market_sell_order(self, symbol: str, amount: float) -> Dict:
        """
        创建市价卖单
        
        Args:
            symbol: 交易对
            amount: 卖出数量
        
        Returns:
            订单信息
        """
        try:
            order = self.exchange.create_market_sell_order(symbol, amount)
            logger.info(f"市价卖出成功: {symbol} {amount}")
            return order
        except Exception as e:
            logger.error(f"市价卖出失败: {e}")
            raise
    
    def create_limit_buy_order(self, symbol: str, amount: float, price: float) -> Dict:
        """
        创建限价买单
        
        Args:
            symbol: 交易对
            amount: 买入数量
            price: 买入价格
        
        Returns:
            订单信息
        """
        try:
            order = self.exchange.create_limit_buy_order(symbol, amount, price)
            logger.info(f"限价买入成功: {symbol} {amount} @ {price}")
            return order
        except Exception as e:
            logger.error(f"限价买入失败: {e}")
            raise
    
    def create_limit_sell_order(self, symbol: str, amount: float, price: float) -> Dict:
        """
        创建限价卖单
        
        Args:
            symbol: 交易对
            amount: 卖出数量
            price: 卖出价格
        
        Returns:
            订单信息
        """
        try:
            order = self.exchange.create_limit_sell_order(symbol, amount, price)
            logger.info(f"限价卖出成功: {symbol} {amount} @ {price}")
            return order
        except Exception as e:
            logger.error(f"限价卖出失败: {e}")
            raise
    
    def get_open_orders(self, symbol: str = None) -> List:
        """
        获取未成交订单
        
        Args:
            symbol: 交易对，None 返回所有
        
        Returns:
            订单列表
        """
        try:
            orders = self.exchange.fetch_open_orders(symbol)
            return orders
        except Exception as e:
            logger.error(f"获取未成交订单失败: {e}")
            raise
    
    def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """
        取消订单
        
        Args:
            order_id: 订单ID
            symbol: 交易对
        
        Returns:
            取消结果
        """
        try:
            result = self.exchange.cancel_order(order_id, symbol)
            logger.info(f"取消订单成功: {order_id}")
            return result
        except Exception as e:
            logger.error(f"取消订单失败: {e}")
            raise
