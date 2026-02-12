# Poloniex BTC 永续合约机器人 - 仅装依赖，代码由 docker-compose 挂载
FROM python:3.11-slim

WORKDIR /app

# 只安装依赖，不拷贝代码（运行时由 compose 挂载项目目录到 /app）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "-u", "main.py"]
