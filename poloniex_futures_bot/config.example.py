# Poloniex BTC 永续合约机器人配置模板
# 使用：复制为 config.py 后填写，config.py 已加入 .gitignore 不会推送到 GitHub
# cp config.example.py config.py
#
# ---------- 保守版（减频、降杠杆、改善盈亏比）----------
# 默认：5m + composite（EMA 定方向 + 短周期动量）+ 盘口挂单失衡确认 + Freqtrade EMA/MACD 同向。

# API（在 Poloniex 后台创建，需开通期货交易权限）
API_KEY = ""
API_SECRET = ""

# 交易对与周期
SYMBOL = "BTC_USDT_PERP"
KLINE_INTERVAL = "MINUTE_5"
KLINE_LIMIT = 200

# 策略选择：auto | hf | ema_cross | macd | rsi | composite | consensus | mtf | freqtrade（technical/qtpylib）
# 保守默认 composite；auto 会在不同市况切换子策略（见文末 AUTO_* 映射，已改为偏稳健）
STRATEGY = "composite"
# True：主策略与 freqtrade 风格必须同向才开仓（显著减少逆势单）
FREQTRADE_CONFIRM = True

# Freqtrade 风格参数（freqtrade_advisory）
FT_EMA_SHORT = 12
FT_EMA_LONG = 26
FT_MACD_FAST = 12
FT_MACD_SLOW = 26
FT_MACD_SIGNAL = 9
FT_USE_MACD_FILTER = True
# 要求 MACD 柱相对前一根「走强/走弱」，过滤横盘弱交叉
FT_REQUIRE_HIST_MOMENTUM = True
FT_RSI_PERIOD = 14
FT_RSI_LONG_MAX = 64
FT_RSI_SHORT_MIN = 36

# 模拟：Taker 手续费（与账户实际费率一致）；资金费来自 API fR 或兜底
FUTURES_TAKER_FEE_RATE = 0.0005
FUNDING_SETTLEMENT_SECONDS = 28800
USE_API_FUNDING_RATE = True
FUNDING_RATE_FALLBACK = 0.0

# 每小时 Telegram 汇总（秒）
HOURLY_REPORT_INTERVAL_SEC = 3600

# 高频策略（hf）：快均线、无 ATR 过滤，信号多（易亏手续费，默认已不用）
EMA_HF_FAST = 5
EMA_HF_SLOW = 20

# EMA 交叉策略（ema_cross / composite 趋势）
EMA_FAST = 20
EMA_SLOW = 60
ATR_PERIOD = 14
# 越大越「挑趋势」：价离 EMA 须明显超过 ATR×系数才允许交叉信号
ATR_FILTER_MULT = 1.25

# MACD 策略（macd）
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9         # 信号线周期
MACD_ATR_FILTER = True   # 是否用 ATR 过滤弱信号

# RSI 策略（rsi）/ 组合策略过滤（composite）
RSI_PERIOD = 14
RSI_OVERSOLD = 28       # 略收紧，减少「接飞刀」
RSI_OVERBOUGHT = 72
RSI_NEUTRAL_LOW = 42    # composite：做空时若 RSI<此（超卖）不追空
RSI_NEUTRAL_HIGH = 58   # composite：做多时若 RSI>此（偏高）不追多

# 组合短线：EMA 定方向后，用近 N 根动量入场（不再死等金叉）
COMPOSITE_ALLOW_TREND_FOLLOW = True
MOMENTUM_BARS = 3
MOMENTUM_MIN_RATIO = 0.002
MOMENTUM_LOOKBACK_BARS = 6

# 多交易所共识策略（consensus）：pressure = a*momentum + b*OI_change - c*funding_rate
# 成交额仅作权重；global_pressure = Σ(volume_weight_i × pressure_i)
CONSENSUS_EXCHANGES = ["binance", "bybit", "okx", "bitget", "gate", "htx", "kucoin", "mexc"]  # ccxt 别名；可删减
CONSENSUS_A = 1.0       # 短周期价格动量系数（如 5m 涨跌幅）
CONSENSUS_B = 0.5       # 未平仓量变化系数（无 OI 时为 0）
CONSENSUS_C = 100.0     # 资金费率系数（越高越偏空，取负）
CONSENSUS_THRESHOLD_LONG = 0.35   # 略提高，减少边缘多单
CONSENSUS_THRESHOLD_SHORT = -0.35
CONSENSUS_MOMENTUM_MINUTES = 5   # 动量周期（分钟）

# 多时间框架策略（mtf）：高周期定趋势 + 低周期找入场 + 成交量/RSI 过滤
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
MTF_VOL_MULT = 1.35             # 量能要求更高，减少无量假突破
MTF_ATR_SL_MULT = 2.0
MTF_ATR_TP_MULT = 3.5           # 略抬高止盈相对止损

# 自动策略（auto）：市场分类后选用子策略（以下为保守映射，减少 rsi/macd 单策略在错误市况的连亏）
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

# 止损止盈：标价比例。TAKE > STOP 形成约 2:1 盈亏比（仍需覆盖双边手续费）
# 杠杆下本金波动 ≈ 标价变动% × 杠杆；LEVERAGE 已下调时请自行换算
STOP_LOSS_RATIO = 0.004
TAKE_PROFIT_RATIO = 0.008
# 最大持仓周期数：每 60 秒一轮；120≈2 小时强平换手机会，避免长时间扛单
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

# 开仓门禁（按 logs/decision_journal.jsonl 复盘：边际 quality≈0.30–0.35 的成交易连亏；可提高阈值并要求多所 pressure 同向）
# 设为 0 可关闭对应项。反手默认更严（多付一次平仓手续费）。
ENTRY_MIN_SIGNAL_QUALITY = 0.42
ENTRY_MIN_SIGNAL_QUALITY_REVERSE = 0.52
ENTRY_REQUIRE_CROSS_PRESSURE_ALIGN = True
# 做多需 global_pressure >= 该值；做空需 global_pressure <= -该值（与 consensus 公式一致）
ENTRY_CROSS_PRESSURE_MIN_ALIGN = 0.0006
# 有效交易所数量不足时：True=仍允许开仓（避免因网络丢数据完全停摆）
ENTRY_CROSS_PRESSURE_FAIL_OPEN = True
ENTRY_CROSS_MIN_EXCHANGES_OK = 4
ENTRY_REQUIRE_BOOK_ALIGN = True
ENTRY_BOOK_EXCHANGES = ["binance", "coinbase"]
ENTRY_BOOK_LIMIT = 20
ENTRY_BOOK_MIN_IMBALANCE = 0.03
ENTRY_BOOK_FAIL_OPEN = True

# 运行模式
PAPER_MODE = True   # True=模拟，False=实盘
SIMULATE_ONLY = True
INITIAL_EQUITY = 10000.0
# 模拟全仓名义 = 权益×杠杆；保守默认 12x，远低於 30x 可显著降低单笔回撤
LEVERAGE = 30

# Telegram 通知（直接填写，不填则不发）
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = None  # 如 -1001234567890

# Redis（Docker Compose 时改为 redis://redis:6379/0）
REDIS_URL = "redis://127.0.0.1:6379/0"

# 决策与多所数据 JSONL 日志（每轮一行，供复盘；与 STRATEGY 无关，始终记录 cross_exchange）
DECISION_JOURNAL_ENABLED = True
DECISION_JOURNAL_PATH = "logs/decision_journal.jsonl"
# 日志里拉取的交易所（可多于 CONSENSUS_EXCHANGES）；需与 multi_exchange.fetch_exchanges 内实现一致
DECISION_JOURNAL_EXCHANGES = ["binance", "bybit", "okx", "bitget", "gate", "htx", "kucoin", "mexc"]
DECISION_JOURNAL_PARALLEL = True
# 空转轮次（停机/无信号/不加仓）的最小写入间隔，action 变化时不受限制；0 = 每轮都写
DECISION_JOURNAL_IDLE_MIN_INTERVAL_SEC = 900
# 超过该体积轮转一代（.1），磁盘占用约束在 2 倍以内；0 = 不轮转
DECISION_JOURNAL_MAX_MB = 64

# 交易日志（每笔一条，含 pnl / MFE / MAE / 质量分项，用于归因与参数标定）
TRADE_JOURNAL_ENABLED = True
TRADE_JOURNAL_PATH = "logs/trades.jsonl"

# ccxt 拉取多所公开数据时的 HTTP/SOCKS 代理（国内访问 binance 等常用）；留空则直连
# 例：CCXT_PROXY = "http://127.0.0.1:7890" 或 "socks5://127.0.0.1:1080"
CCXT_PROXY = ""

# 请求
BASE_URL = "https://api.poloniex.com"
RECV_WINDOW_MS = 15000
REQUEST_TIMEOUT = 30
RATE_LIMIT_RETRY = 3
RATE_LIMIT_BACKOFF = 2.0

# ════════════════════════════════════════════════════
# Decision Layer - 币圈新闻情绪决策层
# 参考 https://github.com/PeymanKh/crypto_news_pipeline
# ════════════════════════════════════════════════════

# 总开关：True 启用新闻情绪决策层
DECISION_LAYER_ENABLED = True

# 新闻 API（cryptonews-api.com）
# 注册获取 key: https://cryptonews-api.com
DECISION_LAYER_NEWS_API_KEY = ""
DECISION_LAYER_NEWS_URL = "https://cryptonews-api.com/api/v1/category?section=general&source=Bitcoin+Magazine,Bloomberg+Markets+and+Finance,Bloomberg+Technology,CNBC,Coindesk,CoinMarketCap,Crypto+Daily,Decrypt,Forbes,The+Block&items=10&page=1"

# OpenAI API（用于情绪分析）
DECISION_LAYER_OPENAI_API_KEY = ""
DECISION_LAYER_OPENAI_MODEL = "gpt-4o-mini"  # gpt-4o-mini 兼顾成本与质量

# 采集间隔（秒）：每 60 秒拉取一次新闻
DECISION_LAYER_INTERVAL_SEC = 60

# Telegram 推送：复用主 Bot 配置（TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID）
# 仅推送重要性 >= 此等级的新闻（HIGH / MEDIUM / LOW）
DECISION_LAYER_TELEGRAM_MIN_IMPORTANCE = "MEDIUM"

# 缓存文件路径（防止重复分析同一新闻）
DECISION_LAYER_CACHE_PATH = "logs/news_cache.json"

# 入场门禁集成：
# True 时，decision_layer 评分将作为 entry_gates 的额外过滤条件
DECISION_LAYER_GATE_ENABLED = True
# 做多时新闻情绪不得低于此值（-1~1），否则阻止开仓
DECISION_LAYER_GATE_LONG_MIN_SCORE = -0.4
# 做空时新闻情绪不得高于此值（-1~1），否则阻止开仓
DECISION_LAYER_GATE_SHORT_MAX_SCORE = 0.4
# 评分置信度低于此值时不生效（避免数据不足时误判）
DECISION_LAYER_GATE_MIN_CONFIDENCE = 0.3
