# -*- coding: utf-8 -*-
"""
数据模型：新闻条目、情绪结果。
参考 crypto_news_pipeline/src/state.py 的 Schema 设计。
"""
import datetime
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field


class Sentiment(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"


class Importance(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class NewsItem:
    """从新闻 API 获取的原始新闻条目"""
    id: str
    title: str
    text: str
    source_name: str
    news_url: str
    image_url: str
    timestamp: datetime.datetime


@dataclass
class ProcessedNewsItem:
    """经过情绪分析后的新闻条目"""
    id: str
    title: str
    text: str
    source_name: str
    news_url: str
    image_url: str
    sentiment: Sentiment
    importance: Importance
    is_market_relevant: bool
    sentiment_score: float = 0.0  # -1.0 ~ +1.0 量化分值
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
