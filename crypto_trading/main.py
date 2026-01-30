#!/usr/bin/env python3
"""
Poloniex 量化交易主程序
"""
import logging
import time
from exchange.poloniex_api import PoloniexAPI
from strategy.ma_strategy import MAStrategy
from config.config import DEFAULT_SYMBOL, DEFAULT_AMOUNT

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """主函数"""
    try:
        # 初始化交易所API
        logger.info("初始化 Poloniex API...")
        exchange = PoloniexAPI()
        
        # 检查API连接
        balance = exchange.get_balance('USDT')
        logger.info(f"USDT余额: {balance}")
        
        # 初始化策略
        symbol = DEFAULT_SYMBOL
        strategy = MAStrategy(exchange, symbol, fast_period=5, slow_period=20)
        
        logger.info(f"开始监控交易对: {symbol}")
        
        # 主循环
        while True:
            try:
                # 获取K线数据
                ohlcv = exchange.get_ohlcv(symbol, timeframe='1h', limit=50)
                
                # 分析市场
                signal = strategy.analyze(ohlcv)
                logger.info(f"交易信号: {signal}")
                
                # 根据信号执行交易（这里只是示例，实际需要添加风险控制）
                if signal['signal'] == 'buy':
                    logger.info("检测到买入信号，但未执行交易（需要手动启用）")
                    # 取消注释以下代码来执行实际交易
                    # amount = DEFAULT_AMOUNT
                    # order = exchange.create_market_buy_order(symbol, amount)
                    # logger.info(f"买入订单: {order}")
                
                elif signal['signal'] == 'sell':
                    logger.info("检测到卖出信号，但未执行交易（需要手动启用）")
                    # 取消注释以下代码来执行实际交易
                    # balance = exchange.get_balance(symbol.split('/')[0])
                    # if balance['free'] > 0:
                    #     order = exchange.create_market_sell_order(symbol, balance['free'])
                    #     logger.info(f"卖出订单: {order}")
                
                # 等待一段时间后再次检查
                time.sleep(60)  # 每分钟检查一次
                
            except KeyboardInterrupt:
                logger.info("收到中断信号，退出程序")
                break
            except Exception as e:
                logger.error(f"循环中发生错误: {e}")
                time.sleep(60)
    
    except Exception as e:
        logger.error(f"程序启动失败: {e}")
        raise


if __name__ == '__main__':
    main()
