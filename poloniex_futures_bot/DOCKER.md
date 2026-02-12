# Docker 运行说明

在 Docker 中运行 Poloniex 永续合约机器人（模拟交易 + Redis + 可选 Telegram）。

---

## 一、前置要求

- 已安装 [Docker](https://docs.docker.com/get-docker/) 与 [Docker Compose](https://docs.docker.com/compose/install/)（或 Docker Desktop 自带 Compose）
- 本机在 `poloniex_futures_bot` 目录下执行以下命令

---

## 二、仅构建并运行机器人镜像（单容器）

不启用 Redis、仅跑 bot 时，可用默认 `config.py`（需本机有 Redis 或关闭 Redis 写入）。

### 步骤

1. **进入项目目录**
   ```bash
   cd /path/to/poloniex_futures_bot
   ```

2. **构建镜像**
   ```bash
   docker build -t poloniex-bot .
   ```

3. **运行容器（须挂载项目目录，镜像内无代码）**
   ```bash
   docker run -d --name poloniex_bot -v "$(pwd)":/app poloniex-bot
   ```
   - 镜像只含 Python 与依赖，代码通过 `-v` 挂载到 `/app`，改代码后重启容器即可生效。
   - 所有 key、token、Redis 地址等均在 **config.py** 中直接填写。

4. **查看日志**
   ```bash
   docker logs -f poloniex_bot
   ```

5. **停止并删除容器**
   ```bash
   docker stop poloniex_bot && docker rm poloniex_bot
   ```

---

## 三、使用 Docker Compose（推荐：Bot + Redis）

Compose 会同时启动 Redis 与机器人；**代码通过挂载当前目录到 `/app`**，镜像内不拷贝代码，改代码后重启 bot 即可生效。

### 步骤

1. **进入项目目录**
   ```bash
   cd /path/to/poloniex_futures_bot
   ```

2. **在 config.py 中填写配置**  
   - **API_KEY / API_SECRET**：实盘时填写，模拟可留空。  
   - **TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID**：需要通知时填写，不填则不发。  
   - **REDIS_URL**：使用 Compose 时请改为 **`redis://redis:6379/0`**（容器内 Redis 服务名为 `redis`）；本机直接运行时用 `redis://127.0.0.1:6379/0`。  
   所有 key、token 均直接写在 config.py 中，不用环境变量。

3. **构建并启动**
   ```bash
   docker-compose up -d --build
   ```
   - 首次会构建镜像并拉取 Redis 镜像，然后后台启动两个容器。

4. **查看运行状态**
   ```bash
   docker-compose ps
   ```

5. **查看机器人日志**
   ```bash
   docker-compose logs -f bot
   ```

6. **查看 Redis 日志（可选）**
   ```bash
   docker-compose logs -f redis
   ```

7. **停止并删除容器（保留 Redis 数据卷）**
   ```bash
   docker-compose down
   ```

8. **停止并删除容器及 Redis 数据**
   ```bash
   docker-compose down -v
   ```

---

## 四、config.py 配置说明

所有敏感信息与连接地址均**直接写在 config.py**，不通过环境变量：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `API_KEY` / `API_SECRET` | Poloniex 实盘 API（模拟可留空） | 仅实盘时填写 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token，不填则不发 | 从 @BotFather 获取 |
| `TELEGRAM_CHAT_ID` | 群组/频道 Chat ID | 如 `-1001234567890` |
| `REDIS_URL` | Redis 地址；**Compose 下请写 `redis://redis:6379/0`** | 本机 `redis://127.0.0.1:6379/0` |

其余策略、杠杆、K 线周期等也在 config.py 中修改。

---

## 五、挂载说明

- **Compose** 已把当前目录挂载到容器的 `/app`，本机改任意代码或 config 后执行 `docker-compose restart bot` 即可生效，无需重建镜像。
- **单容器** 运行必须挂载项目目录：`docker run -d --name poloniex_bot -v "$(pwd)":/app poloniex-bot`，否则容器内无代码无法运行。

---

## 六、Redis 数据查看

Compose 启动后，交易记录会写入 Redis：

- 列表键：`poloniex_simulate:trades`（每笔交易 JSON 追加）
- 最近一笔：`poloniex_simulate:last_trade`

进入 Redis 容器查看示例：

```bash
docker-compose exec redis redis-cli
> LRANGE poloniex_simulate:trades 0 -1
> GET poloniex_simulate:last_trade
```

---

## 七、常见问题

- **容器启动后立刻退出**：看日志 `docker-compose logs bot`，多为依赖或 `config` 报错；确认 `requirements.txt` 已安装、未挂载错误配置文件。
- **收不到 Telegram**：在 config.py 中检查 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID` 是否已填写，且 Bot 已加入目标群/频道。
- **连不上 Redis**：Compose 下请在 config.py 中把 `REDIS_URL` 设为 `redis://redis:6379/0`；单容器连本机 Redis 可设为 `redis://host.docker.internal:6379/0`（Docker Desktop）。

---

## 八、目录与文件一览

```
poloniex_futures_bot/
├── Dockerfile          # 仅装依赖，不拷贝代码
├── docker-compose.yml  # Bot + Redis，挂载 .:/app
├── DOCKER.md           # 本说明
├── config.py           # 配置（key/token/Redis 等直接写在此文件）
├── main.py
└── ...
```

构建与运行均需在包含 `Dockerfile` 和 `docker-compose.yml` 的目录下执行。
