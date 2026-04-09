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

# 策略选择：auto | hf | ema_cross | macd | rsi | composite | consensus | mtf | freqtrade（technical/qtpylib）
STRATEGY = "auto"
# True：主策略须与 freqtrade 风格同向才开仓
FREQTRADE_CONFIRM = False

# Freqtrade 风格参数（freqtrade_advisory）
FT_EMA_SHORT = 12
FT_EMA_LONG = 26
FT_MACD_FAST = 12
FT_MACD_SLOW = 26
FT_MACD_SIGNAL = 9
FT_USE_MACD_FILTER = True
FT_RSI_PERIOD = 14
FT_RSI_LONG_MAX = 72
FT_RSI_SHORT_MIN = 28

# 模拟：Taker 手续费（与账户实际费率一致）；资金费来自 API fR 或兜底
FUTURES_TAKER_FEE_RATE = 0.0005
FUNDING_SETTLEMENT_SECONDS = 28800
USE_API_FUNDING_RATE = True
FUNDING_RATE_FALLBACK = 0.0

# 每小时 Telegram 汇总（秒）
HOURLY_REPORT_INTERVAL_SEC = 3600

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

# 多交易所共识策略（consensus）：pressure = a*momentum + b*OI_change - c*funding_rate
# 成交额仅作权重；global_pressure = Σ(volume_weight_i × pressure_i)
CONSENSUS_EXCHANGES = ["binance", "bybit", "okx", "bitget"]  # 已实现公开 API 的 4 家，可删减
CONSENSUS_A = 1.0       # 短周期价格动量系数（如 5m 涨跌幅）
CONSENSUS_B = 0.5       # 未平仓量变化系数（无 OI 时为 0）
CONSENSUS_C = 100.0     # 资金费率系数（越高越偏空，取负）
CONSENSUS_THRESHOLD_LONG = 0.3   # 超过此开多
CONSENSUS_THRESHOLD_SHORT = -0.3 # 低于此开空
CONSENSUS_MOMENTUM_MINUTES = 5   # 动量周期（分钟）

# 多时间框架策略（mtf）：高周期定趋势 + 低周期找入场 + 成交量/RSI 过滤
MTF_HTF_INTERVAL = "MINUTE_15"     # 高周期 K 线周期（趋势判定）
MTF_HTF_LIMIT = 200                # 高周期 K 线拉取数量（需覆盖 EMA200）
MTF_LTF_INTERVAL = "MINUTE_1"     # 低周期 K 线周期（入场时机）
MTF_LTF_LIMIT = 100               # 低周期 K 线拉取数量
MTF_HTF_EMA_FAST = 50             # 高周期快均线（趋势方向）
MTF_HTF_EMA_SLOW = 200            # 高周期慢均线（长期趋势）
MTF_LTF_EMA_FAST = 9              # 低周期快均线（入场信号）
MTF_LTF_EMA_SLOW = 21             # 低周期慢均线（入场信号）
MTF_RSI_PERIOD = 14               # RSI 周期
MTF_RSI_LONG_MAX = 70             # 做多时 RSI 不超此值（防追高）
MTF_RSI_SHORT_MIN = 30            # 做空时 RSI 不低于此值（防杀跌）
MTF_VOL_MA_PERIOD = 20            # 成交量均线周期
MTF_VOL_MULT = 1.2                # 信号确认需成交量 > 均量 × 此系数
MTF_ATR_SL_MULT = 2.0             # 止损 = ATR × 此系数（动态止损）
MTF_ATR_TP_MULT = 3.0             # 止盈 = ATR × 此系数（动态止盈）

# 自动策略（auto）：实时分析市场状态，自动切换最适合的子策略
# 市场分类依据 ADX 趋势强度 + ATR 波动率百分位 + RSI 极端值
AUTO_ADX_PERIOD = 14              # ADX 计算周期
AUTO_ADX_TREND_THRESHOLD = 25     # ADX > 此值判为趋势市；≤ 此值为震荡市
AUTO_ADX_STRONG_TREND = 40        # ADX > 此值判为强趋势（用 mtf）
AUTO_ATR_LOOKBACK = 50            # ATR 波动率百分位回看窗口
AUTO_ATR_HIGH_PERCENTILE = 75     # ATR 百分位 > 此值判为高波动
AUTO_RSI_EXTREME_LOW = 20         # RSI < 此值判为极端超卖
AUTO_RSI_EXTREME_HIGH = 80        # RSI > 此值判为极端超买
# 市场状态 → 策略映射（可改为任意已有策略名）
AUTO_STRATEGY_STRONG_TREND = "mtf"        # 强趋势 → 多时间框架
AUTO_STRATEGY_TREND = "composite"         # 普通趋势 → EMA+RSI 组合
AUTO_STRATEGY_RANGING = "rsi"             # 震荡 → RSI 抄底摸顶
AUTO_STRATEGY_HIGH_VOLATILITY = "macd"    # 高波动 → MACD 捕捉动量
AUTO_STRATEGY_EXTREME = "rsi"             # 极端行情 → RSI 超买超卖反转

# 止损止盈：按「标的价格」涨跌比例。30 倍杠杆下 本金盈亏 ≈ 价格变动% × 30
STOP_LOSS_RATIO = 0.004   # 约本金 12% 止损（30x）
TAKE_PROFIT_RATIO = 0.004 # 约本金 12% 止盈（30x）
# 本金 10% 止盈 → 价格动 10%/30≈0.333% → 取 0.00333；同理本金 10% 止损
# 最大持仓周期数：每 60 秒一轮；0=不限制持仓时间
MAX_HOLD_CYCLES = 0

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
