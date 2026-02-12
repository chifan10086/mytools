# Poloniex BTC 永续合约交易机器人

Python 实现的 Poloniex BTC 永续合约自动交易机器人：单向持仓（多/空/空仓）、REST 鉴权与限频重试、**多策略可选**（EMA 交叉 / MACD / RSI / 组合）、止损止盈与风控。

## 功能

- **REST 客户端**：HMAC-SHA256 鉴权、限频重试（429/5xx 退避）
- **K 线**：从 `/v3/market/candles` 获取
- **下单/平仓**：市价开多/开空、市价平仓
- **仓位与权益**：读取当前持仓与账户权益
- **Paper 模式**：模拟盘，不真实下单
- **策略（可配置）**：`config.STRATEGY` 选择
  - **hf**：高频，EMA 5/20 金叉死叉、无 ATR 过滤，配 1 分钟 K 线，信号多、不蹲守
  - **ema_cross**：EMA 快/慢线金叉死叉 + ATR 过滤（原逻辑）
  - **macd**：MACD 线与信号线交叉，可选 ATR 过滤弱信号
  - **rsi**：RSI 超卖做多、超买做空（阈值可配）
  - **composite**：EMA 趋势 + RSI 过滤（避免超买追多、超卖追空）
- **仓位**：权益的 10%（可配）
- **风控**：连续亏损 3 次停机；当日亏损达权益 5% 停机
- **模拟交易模式**（`SIMULATE_ONLY=True`）：不配置 API Key，仅用公开 K 线自动多空决策；全仓 30 倍；每次决策后发 Telegram、写 Redis 记录交易价格

## 目录结构

```
poloniex_futures_bot/
├── Dockerfile       # Docker 镜像
├── docker-compose.yml  # Bot + Redis 编排
├── DOCKER.md        # Docker 运行详细步骤
├── config.example.py  # 配置模板（复制为 config.py 后填写，config.py 不提交 GitHub）
├── rest_client.py   # REST 鉴权、签名、限频重试
├── strategy.py      # 多策略：EMA/MACD/RSI/组合，止损止盈
├── risk_manager.py  # 连续亏损、当日亏损停机
├── paper_engine.py  # 模拟持仓与权益
├── exchange.py      # 统一封装：权益/持仓/下单/平仓（实盘或 Paper）
├── notify.py        # 模拟交易：Telegram 通知 + Redis 记录
├── main.py          # 主循环
├── requirements.txt
└── README.md
```

## 配置

**首次使用**：`cp config.example.py config.py`，再在 `config.py` 中填写。`config.py` 已加入 .gitignore，不会推送到 GitHub。

- `API_KEY` / `API_SECRET`：Poloniex 后台创建，需开通期货交易权限
- `SYMBOL`：默认 `BTC_USDT_PERP`
- `KLINE_INTERVAL`：K 线周期，如 `MINUTE_15`、`HOUR_1`
- **策略**：`STRATEGY` = `hf` | `ema_cross` | `macd` | `rsi` | `composite`
  - 高频 hf：`EMA_HF_FAST`(5) / `EMA_HF_SLOW`(20)，建议 `KLINE_INTERVAL=MINUTE_1`、`MAX_HOLD_CYCLES=2`
  - EMA：`EMA_FAST` / `EMA_SLOW`、`ATR_PERIOD` / `ATR_FILTER_MULT`
  - MACD：`MACD_FAST`(12) / `MACD_SLOW`(26) / `MACD_SIGNAL`(9)、`MACD_ATR_FILTER`
  - RSI：`RSI_PERIOD`(14)、`RSI_OVERSOLD`(30)、`RSI_OVERBOUGHT`(70)
  - 组合：`RSI_NEUTRAL_LOW`(40)、`RSI_NEUTRAL_HIGH`(60) 用于过滤
- `STOP_LOSS_RATIO` / `TAKE_PROFIT_RATIO`：止损/止盈比例（如 0.02 / 0.03）
- `POSITION_EQUITY_RATIO`：仓位占权益比例（默认 0.1）
- `MAX_CONSECUTIVE_LOSSES`：连续亏损次数上限（默认 3）
- `DAILY_LOSS_RATIO`：当日亏损占权益比例上限（默认 0.05）
- `PAPER_MODE`：`True` 为模拟，`False` 为实盘
- **模拟交易**（可不填 API Key）；key、token 等**直接写在 config.py**，不用环境变量：
  - `INITIAL_EQUITY`：模拟初始本金（默认 10000），重启即按此重新开始
  - `SIMULATE_ONLY`：`True` 时仅用公开 K 线、自动多空、全仓 `LEVERAGE` 倍（默认 30）
  - `LEVERAGE`：全仓杠杆倍数
  - `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`：决策后发到 Telegram，在 config 中填写
  - `REDIS_URL`：在 config 中填写，如 `redis://127.0.0.1:6379/0`，记录到 `poloniex_simulate:trades`、`poloniex_simulate:last_trade`；**当前权益/累计收益** 写入 `poloniex_simulate:equity`（开平仓 Telegram 通知里也会带「当前权益」「累计收益」）

## 运行

**本机直接运行：**
```bash
cd poloniex_futures_bot
python3 main.py
```

**Docker 运行（Bot + Redis）：** 见 [DOCKER.md](DOCKER.md)，含 Dockerfile、docker-compose 与详细步骤。

- 默认 **Paper 模式**，初始本金在 `config.INITIAL_EQUITY`（默认 10000），不发起真实订单。**更新代码后无需清 Redis**；重启进程即按新本金重新开始模拟（权益仅内存，不持久化）。
- 实盘前请先在 Poloniex 确认合约规格（如张数、面值），必要时在 `exchange.py` 中调整 `CONTRACT_SIZE` 及权益/持仓解析逻辑。

## 依赖

- 模拟交易写 Redis 需安装：`pip install -r requirements.txt`（含 `redis`）
- 其余为 Python 标准库（`urllib`、`hmac`、`json` 等）。若希望改用 `requests`，可自行替换 `rest_client.py` 中的请求实现。

## 风险与免责

- 本机器人按“写死”策略与风控逻辑运行，不保证盈利。
- 实盘前务必在测试环境或小资金充分验证。
- 使用实盘模式即表示您自行承担全部交易与资金风险。
