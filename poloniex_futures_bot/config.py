# Poloniex BTC 永续合约机器人配置
# 1h ema_cross（EMA20/60 金叉 / 死叉，价离两条均线都超过 1.25×ATR 才算）+ Freqtrade EMA/MACD 同向确认；
# 止损 3×ATR、不设固定止盈，靠止损或反向信号离场

# API（在 Poloniex 后台创建，需开通期货交易权限）
API_KEY = ""
API_SECRET = ""

# 交易对与周期
SYMBOL = "BTC_USDT_PERP"
# 1h：回放 2026-06～10 的币安 K 线，5m/15m 下 composite 在所有参数组合里都是负收益
# （手续费约占本金 40%/4 个月）；1h 把交易频次从 4 笔/天降到 0.5 笔/天，手续费占比降到 1/10。
KLINE_INTERVAL = "HOUR_1"
KLINE_LIMIT = 200
# 信号用 K 线来源：多家交易所 BTC 永续 K 线逐根取中位数合成（单家插针/断流被平掉），不足 KLINE_MIN_SOURCES 家
# 时回退币安单家，再回退 Poloniex。1h 回放：共识 K 线样本内 +42.7%，六家单独跑在 +29%～+40% 之间。
# kucoin 与共识价偏差最大（中位 1.1bp，其他 0.2～0.35bp），不放入。
KLINE_SOURCES = ["binance", "bybit", "okx", "gate", "mexc"]
KLINE_MIN_SOURCES = 3

# 策略选择：auto | hf | ema_cross | macd | rsi | composite | consensus | mtf | freqtrade
# 2026-11-18 由 composite 换成 ema_cross。币安 1h K 线 2023-01～2026-11 回放（python3 backtest.py，按年看）：
#   composite + 固定止损 0.8% / 止盈 1.6%：2023 −31.6%、2024 −34.3%、2025 −34.3%、2026 +39.5%，10000 → 4111。
#     赚钱的只有 2026-06～10 那 120 天——正是 10-03 调参用的窗口；实盘 10-04～11-16 共 29 笔，净 −13.5。
#   ema_cross + 3×ATR 止损 + 不设止盈：2023 +29.6%、2024 +73.3%、2025 +4.5%、2026 +15.1%，10000 → 26994，最大回撤 16.7%。
#     止损倍数取 2 / 3 / 4 都为正，不是只有一个点好看；FREQTRADE_CONFIRM 开不开结果几乎一样。
# 这套的脾气：约每周 1 笔，胜率只有 30%，利润几乎全来自少数几笔大趋势单（198 笔里最大的 5 笔 ≈ 全部利润），
# 连亏最长 14 笔，空头基本不赚，震荡的年份（2025）接近白干。回测不含资金费，实盘会少一截（按多空都付 0.01%/8h 估，约少一成多）。
STRATEGY = "ema_cross"
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
# 1h 下 3 根动量门槛 0.3%：0.3/0.4 回放结果相近，取低的多出手；0.8% 以上信号过少
MOMENTUM_MIN_RATIO = 0.003
MOMENTUM_LOOKBACK_BARS = 6

# 多交易所共识策略（consensus）
CONSENSUS_EXCHANGES = ["binance", "bybit", "okx", "bitget", "gate", "htx", "kucoin", "mexc"]
CONSENSUS_A = 1.0
CONSENSUS_B = 0.5
# funding 加权后标准差仅 0.000022，为 momentum 标准差（0.00162）的 1.4%，不携带方向信息。
# C=100 时该项贡献恒定 -0.006 偏置，令 global_pressure 在 1797 次观测中 99.1% 为负；
# C=5 把偏置压到 momentum 标准差的 18%，保留资金费的温和修正作用。
CONSENSUS_C = 5.0
# 阈值须与 global_pressure 实际量级（约 ±0.01）匹配；旧值 ±0.35 恒不可达，consensus 永远无信号
CONSENSUS_THRESHOLD_LONG = 0.0025
CONSENSUS_THRESHOLD_SHORT = -0.0025
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

# 止损：开仓时按波动定距离 = STOP_LOSS_ATR_MULT × ATR(ATR_PERIOD) ÷ 价格，定下后不再移动，不低于 STOP_LOSS_ATR_MIN_RATIO。
# 1h 下 3×ATR 通常在 1%～3%。仓位按「触发止损亏掉 RISK_PER_TRADE」反推，止损放远时仓位自动变小，每笔最多亏的钱不变。
# 固定 0.8% 对趋势单太近：同样的 ema_cross 入场，2025 年固定 0.8% 止损累计 −29R，换成 3×ATR 是 +6R（R = 单笔风险）。
# 0 = 不按波动，用下面固定的 STOP_LOSS_RATIO。
STOP_LOSS_ATR_MULT = 3.0
STOP_LOSS_ATR_MIN_RATIO = 0.002
# 固定止损比例：只在 STOP_LOSS_ATR_MULT=0、或 K 线不够算 ATR 时用
STOP_LOSS_RATIO = 0.008
# 0 = 不设固定止盈，盈利单一直拿到反向信号或回到止损价。回放里加固定止盈都更差：3×ATR 止损配 3 倍止盈，
# 四年累计从 +120R 掉到 +44R——利润来自少数大趋势，止盈正好把它们截断。
TAKE_PROFIT_RATIO = 0
# 0 = 不以持仓时间平仓。离场只走止损、止盈（设了的话）、反向信号、浮盈回撤。
MAX_HOLD_CYCLES = 0
# True：信号只用已收盘 K 线（丢掉最后一根未收盘的），标价仍取最新价。
# 1h 周期下每分钟轮询，盘中半根 K 线会让动量/EMA 反复跳变；回测也是按收盘算的。
SIGNAL_ON_CLOSED_BARS = True
# 运行状态落盘：Paper 权益/持仓、风控计数、未平仓交易。重启不再回到 INITIAL_EQUITY；想归零就删这个文件。
RUNTIME_STATE_PATH = "logs/runtime_state.json"
# 浮盈保护：曾达到 ARM 后回落到 LOCK 就提前平。ARM=0 关闭。旧值 LOCK 0.10% 低于双边手续费 0.10%，11 笔「浮盈保护」平均只赚 4.3 USDT；
# 回放里任何 ARM/LOCK 组合都比不加差。
MAX_HOLD_ARM_RATIO = 0
MAX_HOLD_LOCK_RATIO = 0.001

# 仓位与风控
POSITION_EQUITY_RATIO = 0.08
# 只防极端情况，不作为日常限频：1h 回放里连亏 2 停 4h 与连亏 3 停、日亏 4% 与 6% 结果几乎一样
MAX_CONSECUTIVE_LOSSES = 3
DAILY_LOSS_RATIO = 0.06
# 单笔风险预算：触发止损时（含开平双边手续费）最多亏掉的权益比例
# 名义仓位 = 权益 × RISK_PER_TRADE / (这次开仓的止损距离 + 2×手续费率)，并受 LEVERAGE 上限约束
RISK_PER_TRADE = 0.015
# 连亏达上限后的冷静期（秒），到点自动复位计数，避免永久停机
CONSECUTIVE_LOSS_COOLDOWN_SEC = 14400

# 开仓门禁
# 0 = 关闭。106 笔实盘样本里 quality 与盈亏无关（q=0.9 胜率 25%，q=0.45 胜率 34%）；
# 回放中 0.42 门禁把 1h 平均收益从 +16.9% 砍到 +4.9%，只是在随机删单。策略内部仍保留 <0.3 的硬过滤。
ENTRY_MIN_SIGNAL_QUALITY = 0
ENTRY_MIN_SIGNAL_QUALITY_REVERSE = 0
# 策略内部的质量硬过滤（原来写死 0.3）。0 = 关闭：1h 回放关掉后样本内 +22%→+33%、样本外 +5%→+8%，多出手反而更好
SIGNAL_MIN_QUALITY = 0
# False：106 笔样本里 pressure 同向的单（72 笔）胜率 36%，反向的（34 笔）胜率 44%，不携带信息
ENTRY_REQUIRE_CROSS_PRESSURE_ALIGN = False
# 仅当 |global_pressure| 达到该值且与方向相反时拦截；弱压力当噪声
# 旧值 0.02 超过 |global_pressure| 实际最大值 0.0166，该门禁 61 笔交易从未触发；
# 0.0025 取 C=5 下 |gp| 的 p90，仅拦明显反向
ENTRY_CROSS_PRESSURE_MIN_ALIGN = 0.0025
ENTRY_CROSS_PRESSURE_FAIL_OPEN = True
ENTRY_CROSS_MIN_EXCHANGES_OK = 4
# 盘口：币安永续 + Coinbase/Kraken。≥2 所时需至少 2 所同向（|imb|≥门槛），避免三所平均互相抵消
# False：盘口同向的单（77 笔）胜率 36%，中性/反向的（29 笔）胜率 45%；门禁拦掉的 53 次只是随机删单
ENTRY_REQUIRE_BOOK_ALIGN = False
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


# ═══════════════════ 本地覆盖（不提交 git） ═══════════════════
# 敏感值（Telegram Token 等）写在 config_local.py，该文件已在 .gitignore 中，
# 放在最末尾以覆盖上面的同名默认值。
try:
    from config_local import *  # noqa: F401,F403
except ImportError:
    pass
