# -*- coding: utf-8 -*-
"""
评分模块：将多条新闻的情绪聚合为一个交易前置评分。
供 entry_gates 在开仓前查询，作为外部决策层信号。
"""
import time
import logging
import threading
from dataclasses import dataclass, field
from typing import List, Optional

from decision_layer.models import ProcessedNewsItem, Sentiment, Importance

logger = logging.getLogger(__name__)

# 重要性权重映射
_IMPORTANCE_WEIGHT = {
    Importance.HIGH: 3.0,
    Importance.MEDIUM: 1.5,
    Importance.LOW: 0.5,
}

# 新闻时效衰减半衰期（秒）：30 分钟后权重减半
_DECAY_HALF_LIFE = 1800.0


@dataclass
class SentimentScore:
    """决策层输出的聚合评分"""
    score: float = 0.0            # -1.0(极度看空) ~ +1.0(极度看多)
    confidence: float = 0.0       # 0~1，基于新闻数量和一致性
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    high_impact_count: int = 0    # HIGH importance 新闻数量
    last_update_ts: float = 0.0   # 上次更新时间戳
    stale: bool = True            # 数据是否过时

    @property
    def direction_bias(self) -> int:
        """
        返回方向偏置：
        1 = 情绪偏多，0 = 中性/不确定，-1 = 情绪偏空
        """
        if self.stale or self.confidence < 0.2:
            return 0
        if self.score >= 0.3:
            return 1
        if self.score <= -0.3:
            return -1
        return 0

    @property
    def should_block_long(self) -> bool:
        """强烈负面情绪时阻止做多"""
        return not self.stale and self.score <= -0.5 and self.confidence >= 0.4

    @property
    def should_block_short(self) -> bool:
        """强烈正面情绪时阻止做空"""
        return not self.stale and self.score >= 0.5 and self.confidence >= 0.4


# 全局单例评分，由 runner 定时更新
_current_score = SentimentScore()
_score_lock = threading.Lock()


def get_current_score() -> SentimentScore:
    """获取当前情绪评分（线程安全）。"""
    with _score_lock:
        score = SentimentScore(
            score=_current_score.score,
            confidence=_current_score.confidence,
            bullish_count=_current_score.bullish_count,
            bearish_count=_current_score.bearish_count,
            neutral_count=_current_score.neutral_count,
            high_impact_count=_current_score.high_impact_count,
            last_update_ts=_current_score.last_update_ts,
            stale=_current_score.stale,
        )
    # 超过 stale_threshold 秒未更新则标记为 stale
    if score.last_update_ts > 0 and (time.time() - score.last_update_ts > 600):
        score.stale = True
    return score


def update_score(processed_news: List[ProcessedNewsItem], stale_seconds: float = 600.0) -> SentimentScore:
    """
    根据最新一批处理过的新闻更新全局评分。

    评分逻辑：
    1. 仅计入 is_market_relevant=True 的新闻
    2. 按重要性加权
    3. 按时效指数衰减
    4. confidence 基于有效新闻数量和情绪一致性
    """
    now = time.time()
    relevant = [n for n in processed_news if n.is_market_relevant]

    if not relevant:
        with _score_lock:
            _current_score.last_update_ts = now
            _current_score.stale = True
        return get_current_score()

    weighted_sum = 0.0
    weight_total = 0.0
    bullish = 0
    bearish = 0
    neutral = 0
    high_impact = 0

    for news in relevant:
        age = max(0.0, now - news.timestamp.timestamp())
        time_weight = 0.5 ** (age / _DECAY_HALF_LIFE)
        imp_weight = _IMPORTANCE_WEIGHT.get(news.importance, 1.0)
        w = time_weight * imp_weight

        weighted_sum += news.sentiment_score * w
        weight_total += w

        if news.sentiment == Sentiment.POSITIVE:
            bullish += 1
        elif news.sentiment == Sentiment.NEGATIVE:
            bearish += 1
        else:
            neutral += 1

        if news.importance == Importance.HIGH:
            high_impact += 1

    score = weighted_sum / weight_total if weight_total > 0 else 0.0
    score = max(-1.0, min(1.0, score))

    # 置信度：基于有效新闻数量（越多越可信）和一致性
    n_total = bullish + bearish + neutral
    quantity_factor = min(1.0, n_total / 5.0)  # 5 条以上满置信

    # 一致性：如果情绪方向一致，置信度高
    if n_total > 0:
        max_direction = max(bullish, bearish, neutral)
        consistency = max_direction / n_total
    else:
        consistency = 0.0

    confidence = quantity_factor * 0.6 + consistency * 0.4
    confidence = min(1.0, confidence)

    new_score = SentimentScore(
        score=score,
        confidence=confidence,
        bullish_count=bullish,
        bearish_count=bearish,
        neutral_count=neutral,
        high_impact_count=high_impact,
        last_update_ts=now,
        stale=False,
    )

    with _score_lock:
        _current_score.score = new_score.score
        _current_score.confidence = new_score.confidence
        _current_score.bullish_count = new_score.bullish_count
        _current_score.bearish_count = new_score.bearish_count
        _current_score.neutral_count = new_score.neutral_count
        _current_score.high_impact_count = new_score.high_impact_count
        _current_score.last_update_ts = new_score.last_update_ts
        _current_score.stale = new_score.stale

    logger.info(
        "情绪评分更新: score=%.3f confidence=%.2f [多%d/空%d/中%d] 高影响%d条",
        score, confidence, bullish, bearish, neutral, high_impact,
    )
    return new_score
