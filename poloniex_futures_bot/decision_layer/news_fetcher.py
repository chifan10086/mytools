# -*- coding: utf-8 -*-
"""
新闻采集模块。
参考 crypto_news_pipeline/src/nodes/fetch_news.py，
从 cryptonews-api.com 获取最新加密货币新闻。
"""
import uuid
import logging
from typing import List
from datetime import datetime

import requests

from decision_layer.models import NewsItem

logger = logging.getLogger(__name__)


def _generate_unique_id(title: str, timestamp: datetime) -> str:
    """基于标题+时间生成确定性 UUID5，避免重复处理。"""
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    composite_key = f"{title.strip()}-{timestamp.isoformat()}"
    return str(uuid.uuid5(namespace, composite_key))


def fetch_crypto_news(api_key: str, api_url: str, timeout: int = 15) -> List[NewsItem]:
    """
    从 cryptonews-api.com 拉取最新加密货币新闻。

    Args:
        api_key: cryptonews-api.com 的 API key
        api_url: 完整的 API URL（含 section/source/items 等参数，不含 token）
        timeout: HTTP 超时秒数

    Returns:
        NewsItem 列表（可能为空）
    """
    if not api_key or not api_url:
        logger.warning("新闻 API 未配置，跳过采集")
        return []

    url = f"{api_url}&token={api_key}" if "?" in api_url else f"{api_url}?token={api_key}"

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except requests.RequestException as e:
        logger.error("新闻 API 请求失败: %s", e)
        return []
    except (ValueError, KeyError) as e:
        logger.error("新闻 API 响应解析失败: %s", e)
        return []

    news_list: List[NewsItem] = []
    for item in data:
        try:
            timestamp_str = item.get("date", "")
            timestamp = datetime.strptime(timestamp_str, "%a, %d %b %Y %H:%M:%S %z")
            news_id = _generate_unique_id(item.get("title", ""), timestamp)

            news = NewsItem(
                id=news_id,
                title=item.get("title", ""),
                text=item.get("text", ""),
                source_name=item.get("source_name", "Unknown"),
                news_url=item.get("news_url", ""),
                image_url=item.get("image_url", ""),
                timestamp=timestamp,
            )
            news_list.append(news)
        except Exception as e:
            logger.debug("解析新闻条目失败: %s", e)
            continue

    logger.info("新闻采集完成：获取 %d 条", len(news_list))
    return news_list
