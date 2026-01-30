# Poloniex 量化交易系统

基于 Python 的 Poloniex 交易所量化交易框架。

## 功能特性

- ✅ Poloniex API 封装
- ✅ 策略框架（支持自定义策略）
- ✅ 移动平均策略示例
- ✅ 实时行情监控
- ✅ 账户余额查询
- ✅ 市价/限价订单

## 安装依赖

```bash
cd crypto_trading
pip install -r requirements.txt
```

## 配置

1. 复制配置文件示例：
```bash
cp config/.env.example config/.env
```

2. 编辑 `config/config.py` 或 `.env` 文件，填入你的 Poloniex API 密钥：
```python
POLONIEX_API_KEY = 'your_api_key'
POLONIEX_SECRET = 'your_secret'
```

## 使用方法

### 1. 测试连接

```python
from exchange.poloniex_api import PoloniexAPI

exchange = PoloniexAPI()
balance = exchange.get_balance('USDT')
print(f"USDT余额: {balance}")
```

### 2. 运行策略

```bash
python main.py
```

### 3. 自定义策略

继承 `BaseStrategy` 类创建自己的策略：

```python
from strategy.base_strategy import BaseStrategy

class MyStrategy(BaseStrategy):
    def analyze(self, data):
        # 你的策略逻辑
        return {'signal': 'buy', 'price': 100}
```

## 安全提示

⚠️ **重要**：
- 不要将 API 密钥提交到代码仓库
- 建议使用 `.env` 文件存储密钥
- 首次使用建议使用测试环境
- 实盘交易前请充分测试

## 项目结构

```
crypto_trading/
├── config/          # 配置文件
├── exchange/        # 交易所API封装
├── strategy/        # 交易策略
├── main.py         # 主程序
└── requirements.txt # 依赖包
```

## 下一步

- [ ] 添加回测功能
- [ ] 添加风险控制模块
- [ ] 添加更多技术指标
- [ ] 添加WebSocket实时行情
- [ ] 添加交易日志记录
- [ ] 添加邮件/Telegram通知
