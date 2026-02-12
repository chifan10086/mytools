# Docker Compose - Jenkins & MQ

## 目录结构

```
docker/
├── Jenkins/          # Jenkins 数据目录（首次运行后生成 data）
├── Mq/               # RabbitMQ 数据目录（首次运行后生成 data）
├── docker-compose.yml
└── README.md
```

## 启动

```bash
cd docker
docker-compose up -d
```

## 访问

| 服务     | 地址                    | 说明           |
|----------|-------------------------|----------------|
| Jenkins  | http://localhost:8080   | 首次需从日志取初始密码 |
| RabbitMQ | http://localhost:15672  | 默认账号 admin / admin |

## 停止

```bash
docker-compose down
```

## 修改 MQ 账号密码

编辑 `docker-compose.yml` 中 `mq` 的 `RABBITMQ_DEFAULT_USER`、`RABBITMQ_DEFAULT_PASS` 后重新 up。
