# Poloniex BTC 永续合约机器人配置模板
# 使用：复制为 config.py 后填写，config.py 已加入 .gitignore 不会推送到 GitHub
# cp config.example.py config.py

# API（在 Poloniex 后台创建，需开通期货交易权限）
API_KEY = ""
API_SECRET = ""

# 交易对与周期
SYMBOL = "BTC_USDT_PERP"
# 高频用 MINUTE_1，普通用 MINUTE_15
KLINE_INTERVAL = "MINUTE_1"
KLINE_LIMIT = 100

# 策略选择：hf=高频(快均线无过滤) | ema_cross | macd | rsi | composite
STRATEGY = "hf"

# 高频策略（hf）：快均线、无 ATR 过滤，信号多
EMA_HF_FAST = 5
EMA_HF_SLOW = 20

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

# 止损止盈：按「标的价格」涨跌比例。30 倍杠杆下 本金盈亏 ≈ 价格变动% × 30
STOP_LOSS_RATIO = 0.004   # 约本金 12% 止损（30x）
TAKE_PROFIT_RATIO = 0.004 # 约本金 12% 止盈（30x）
# 最大持仓周期数：每 60 秒一轮；高频建议 2（约 2 分钟），0=不限制
MAX_HOLD_CYCLES = 2

# 仓位与风控
POSITION_EQUITY_RATIO = 0.10   # 仓位 = 权益的 10%
MAX_CONSECUTIVE_LOSSES = 3     # 连续亏损 3 次停机
DAILY_LOSS_RATIO = 0.05        # 当日亏损达权益 5% 停机

# 运行模式
PAPER_MODE = True   # True=模拟，False=实盘
SIMULATE_ONLY = True
# 模拟初始本金（重启进程即按此重新开始）
INITIAL_EQUITY = 10000.0
LEVERAGE = 30

# Telegram 通知（直接填写，不填则不发）
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = None  # 如 -1001234567890

# Redis（Docker Compose 时改为 redis://redis:6379/0）
REDIS_URL = "redis://127.0.0.1:6379/0"

# 请求
BASE_URL = "https://api.poloniex.com"
RECV_WINDOW_MS = 15000
REQUEST_TIMEOUT = 30
RATE_LIMIT_RETRY = 3
RATE_LIMIT_BACKOFF = 2.0
