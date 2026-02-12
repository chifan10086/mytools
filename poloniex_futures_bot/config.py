# Poloniex BTC 永续合约机器人配置

# API（在 Poloniex 后台创建，需开通期货交易权限）
API_KEY = ""
API_SECRET = ""

# 交易对与周期
SYMBOL = "BTC_USDT_PERP"
KLINE_INTERVAL = "MINUTE_15"   # MINUTE_1, MINUTE_5, MINUTE_15, HOUR_1, HOUR_4, DAY_1
KLINE_LIMIT = 100

# 策略选择：ema_cross | macd | rsi | composite
STRATEGY = "ema_cross"

# EMA 交叉策略（ema_cross / composite 趋势）
EMA_FAST = 20
EMA_SLOW = 60
ATR_PERIOD = 14
ATR_FILTER_MULT = 1.0   # 信号需满足 收盘价与均线距离 > ATR * 此系数

# MACD 策略（macd）
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9         # 信号线周期
MACD_ATR_FILTER = True   # 是否用 ATR 过滤弱信号

# RSI 策略（rsi）/ 组合策略过滤（composite）
RSI_PERIOD = 14
RSI_OVERSOLD = 30       # 低于此做多
RSI_OVERBOUGHT = 70     # 高于此做空
RSI_NEUTRAL_LOW = 40    # composite 做多时要求 RSI < 此
RSI_NEUTRAL_HIGH = 60   # composite 做空时要求 RSI > 此

# 止损止盈（相对开仓价的倍数，如 0.02 = 2%）
STOP_LOSS_RATIO = 0.02
TAKE_PROFIT_RATIO = 0.03

# 仓位与风控
POSITION_EQUITY_RATIO = 0.10   # 仓位 = 权益的 10%
MAX_CONSECUTIVE_LOSSES = 3     # 连续亏损 3 次停机
DAILY_LOSS_RATIO = 0.05        # 当日亏损达权益 5% 停机

# 运行模式
PAPER_MODE = True   # True=模拟，False=实盘
# 模拟交易：不配置 API Key，仅用公开 K 线 + 自动决策，发 Telegram + 写 Redis
SIMULATE_ONLY = True
# 全仓杠杆倍数（模拟/实盘下单时的名义仓位 = 权益 * LEVERAGE）
LEVERAGE = 30

# Telegram 通知（决策后发到群组，可复用 bot/config 的 API_TOKEN 与 ALLOWED_GROUP_ID）
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = None  # 如 -1001234567890，不填则不发

# Redis 记录交易（不填则不用 Redis）
REDIS_URL = "redis://127.0.0.1:6379/0"

# 请求
BASE_URL = "https://api.poloniex.com"
RECV_WINDOW_MS = 15000
REQUEST_TIMEOUT = 30
RATE_LIMIT_RETRY = 3
RATE_LIMIT_BACKOFF = 2.0
