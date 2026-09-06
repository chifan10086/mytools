# Poloniex BTC 永续合约机器人配置
# 合约短线：5m + composite（EMA方向 + 近3根动量）+ 盘口确认 + Freqtrade 同向

# API（在 Poloniex 后台创建，需开通期货交易权限）
API_KEY = ""
API_SECRET = ""

# 交易对与周期
SYMBOL = "BTC_USDT_PERP"
KLINE_INTERVAL = "MINUTE_5"
KLINE_LIMIT = 200

# 策略选择：auto | hf | ema_cross | macd | rsi | composite | consensus | mtf | freqtrade
STRATEGY = "composite"
FREQTRADE_CONFIRM = True

# Freqtrade 风格参数
FT_EMA_SHORT = 12
FT_EMA_LONG = 26
FT_MACD_FAST = 12
FT_MACD_SLOW = 26
FT_MACD_SIGNAL = 9
FT_USE_MACD_FILTER = True
FT_REQUIRE_HIST_MOMENTUM = True
FT_RSI_PERIOD = 14
FT_RSI_LONG_MAX = 64
FT_RSI_SHORT_MIN = 36

# 模拟手续费与资金费
FUTURES_TAKER_FEE_RATE = 0.0005
FUNDING_SETTLEMENT_SECONDS = 28800
USE_API_FUNDING_RATE = True
FUNDING_RATE_FALLBACK = 0.0

# 每小时 Telegram 汇总（秒）
HOURLY_REPORT_INTERVAL_SEC = 3600

# 高频策略（hf）
EMA_HF_FAST = 5
EMA_HF_SLOW = 20

# EMA 交叉策略
EMA_FAST = 20
EMA_SLOW = 60
ATR_PERIOD = 14
ATR_FILTER_MULT = 1.25

# MACD 策略
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
MACD_ATR_FILTER = True

# RSI 策略 / 组合策略过滤
RSI_PERIOD = 14
RSI_OVERSOLD = 28
RSI_OVERBOUGHT = 72
RSI_NEUTRAL_LOW = 42
RSI_NEUTRAL_HIGH = 58

# 组合短线：EMA 定方向后，用近 N 根动量入场（不再死等金叉）
COMPOSITE_ALLOW_TREND_FOLLOW = True
MOMENTUM_BARS = 3
MOMENTUM_MIN_RATIO = 0.002
MOMENTUM_LOOKBACK_BARS = 6

# 多交易所共识策略（consensus）
CONSENSUS_EXCHANGES = ["binance", "bybit", "okx", "bitget", "gate", "htx", "kucoin", "mexc"]
CONSENSUS_A = 1.0
CONSENSUS_B = 0.5
CONSENSUS_C = 100.0
CONSENSUS_THRESHOLD_LONG = 0.35
CONSENSUS_THRESHOLD_SHORT = -0.35
CONSENSUS_MOMENTUM_MINUTES = 5

# 多时间框架策略（mtf）
MTF_HTF_INTERVAL = "MINUTE_15"
MTF_HTF_LIMIT = 200
MTF_LTF_INTERVAL = "MINUTE_5"
MTF_LTF_LIMIT = 120
MTF_HTF_EMA_FAST = 50
MTF_HTF_EMA_SLOW = 200
MTF_LTF_EMA_FAST = 9
MTF_LTF_EMA_SLOW = 21
MTF_RSI_PERIOD = 14
MTF_RSI_LONG_MAX = 65
MTF_RSI_SHORT_MIN = 35
MTF_VOL_MA_PERIOD = 20
MTF_VOL_MULT = 1.35
MTF_ATR_SL_MULT = 2.0
MTF_ATR_TP_MULT = 3.5

# 自动策略（auto）
AUTO_ADX_PERIOD = 14
AUTO_ADX_TREND_THRESHOLD = 25
AUTO_ADX_STRONG_TREND = 40
AUTO_ATR_LOOKBACK = 50
AUTO_ATR_HIGH_PERCENTILE = 75
AUTO_RSI_EXTREME_LOW = 18
AUTO_RSI_EXTREME_HIGH = 82
AUTO_STRATEGY_STRONG_TREND = "mtf"
AUTO_STRATEGY_TREND = "composite"
AUTO_STRATEGY_RANGING = "composite"
AUTO_STRATEGY_HIGH_VOLATILITY = "composite"
AUTO_STRATEGY_EXTREME = "composite"

# 止损止盈：5m BTC 的 ATR 约 0.20%，各取 3×ATR。
# 旧值 SL=2×ATR 落在噪声带里，23 笔止损的 MAE 全部集中在 -0.40%~-0.50%
STOP_LOSS_RATIO = 0.006
TAKE_PROFIT_RATIO = 0.006
MAX_HOLD_CYCLES = 120

# 仓位与风控
POSITION_EQUITY_RATIO = 0.08
MAX_CONSECUTIVE_LOSSES = 2
DAILY_LOSS_RATIO = 0.04
# 单笔风险预算：触发止损时（含开平双边手续费）最多亏掉的权益比例
# 名义仓位 = 权益 × RISK_PER_TRADE / (STOP_LOSS_RATIO + 2×手续费率)，并受 LEVERAGE 上限约束
RISK_PER_TRADE = 0.015
# 连亏达上限后的冷静期（秒），到点自动复位计数，避免永久停机
CONSECUTIVE_LOSS_COOLDOWN_SEC = 14400

# 开仓门禁
ENTRY_MIN_SIGNAL_QUALITY = 0.42
ENTRY_MIN_SIGNAL_QUALITY_REVERSE = 0.52
ENTRY_REQUIRE_CROSS_PRESSURE_ALIGN = True
# 仅当 |global_pressure| 达到该值且与方向相反时拦截；弱压力当噪声
ENTRY_CROSS_PRESSURE_MIN_ALIGN = 0.02
ENTRY_CROSS_PRESSURE_FAIL_OPEN = True
ENTRY_CROSS_MIN_EXCHANGES_OK = 4
# 盘口：币安永续 + Coinbase/Kraken。≥2 所时需至少 2 所同向（|imb|≥门槛），避免三所平均互相抵消
ENTRY_REQUIRE_BOOK_ALIGN = True
ENTRY_BOOK_EXCHANGES = ["binance", "coinbase", "kraken"]
ENTRY_BOOK_LIMIT = 20
ENTRY_BOOK_MIN_IMBALANCE = 0.03
ENTRY_BOOK_FAIL_OPEN = True

# 运行模式
PAPER_MODE = True
SIMULATE_ONLY = True
INITIAL_EQUITY = 10000.0
LEVERAGE = 30

# ═══════════════════ 需要你填写的敏感配置 ═══════════════════

# Telegram 通知（不填则不推送）
TELEGRAM_BOT_TOKEN = ""        # TODO: 填入你的 Bot Token
TELEGRAM_CHAT_ID = None        # TODO: 填入群组 ID，如 -1001234567890

# Redis
REDIS_URL = "redis://127.0.0.1:6379/0"

# 决策日志（逐轮快照，用于排查「为什么没开仓」）
DECISION_JOURNAL_ENABLED = True
DECISION_JOURNAL_PATH = "logs/decision_journal.jsonl"
DECISION_JOURNAL_EXCHANGES = ["binance", "bybit", "okx", "bitget", "gate", "htx", "kucoin", "mexc"]
DECISION_JOURNAL_PARALLEL = True
# 空转轮次（停机/无信号/不加仓）的最小写入间隔，action 变化时不受限制；0 = 每轮都写
DECISION_JOURNAL_IDLE_MIN_INTERVAL_SEC = 900
# 超过该体积轮转一代（.1），磁盘占用约束在 2 倍以内；0 = 不轮转
DECISION_JOURNAL_MAX_MB = 64

# 交易日志（每笔一条，含 pnl / MFE / MAE / 质量分项，用于归因与参数标定）
TRADE_JOURNAL_ENABLED = True
TRADE_JOURNAL_PATH = "logs/trades.jsonl"

# 代理（国内访问 binance 等需要）
CCXT_PROXY = ""                # 如 "http://127.0.0.1:7890"

# 请求
BASE_URL = "https://api.poloniex.com"
RECV_WINDOW_MS = 15000
REQUEST_TIMEOUT = 30
RATE_LIMIT_RETRY = 3
RATE_LIMIT_BACKOFF = 2.0

# ═══════════════════ Decision Layer - 新闻情绪决策层 ═══════════════════

DECISION_LAYER_ENABLED = True

# 新闻 API（https://cryptonews-api.com 注册获取免费 key）
DECISION_LAYER_NEWS_API_KEY = ""      # TODO: 填入 cryptonews-api.com 的 API Key
DECISION_LAYER_NEWS_URL = "https://cryptonews-api.com/api/v1/category?section=general&source=Bitcoin+Magazine,Bloomberg+Markets+and+Finance,Bloomberg+Technology,CNBC,Coindesk,CoinMarketCap,Crypto+Daily,Decrypt,Forbes,The+Block&items=10&page=1"

# OpenAI API（用于 LLM 情绪分析）
DECISION_LAYER_OPENAI_API_KEY = ""    # TODO: 填入 OpenAI API Key
DECISION_LAYER_OPENAI_MODEL = "gpt-4o-mini"

# 采集间隔（秒）
DECISION_LAYER_INTERVAL_SEC = 60

# Telegram 新闻推送（复用上面的 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID）
DECISION_LAYER_TELEGRAM_MIN_IMPORTANCE = "MEDIUM"  # HIGH / MEDIUM / LOW

# 缓存
DECISION_LAYER_CACHE_PATH = "logs/news_cache.json"

# 入场门禁集成
DECISION_LAYER_GATE_ENABLED = True
DECISION_LAYER_GATE_LONG_MIN_SCORE = -0.4     # 做多时情绪不得低于此值
DECISION_LAYER_GATE_SHORT_MAX_SCORE = 0.4     # 做空时情绪不得高于此值
DECISION_LAYER_GATE_MIN_CONFIDENCE = 0.3      # 置信度低于此值时门禁不生效
