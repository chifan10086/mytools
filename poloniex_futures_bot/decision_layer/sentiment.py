# -*- coding: utf-8 -*-
"""
情绪分析模块。
参考 crypto_news_pipeline/src/nodes/sentiment_analysis.py，
使用 OpenAI API 对新闻做结构化情绪判定。
"""
import json
import logging
from typing import List, Optional

from decision_layer.models import (
    NewsItem,
    ProcessedNewsItem,
    Sentiment,
    Importance,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Senior Cryptocurrency Market Analyst specializing in real-time sentiment analysis and trading intelligence.

## Primary Objectives
1. Sentiment Classification: Evaluate news sentiment impact on BTC/crypto price (POSITIVE, NEGATIVE, NEUTRAL)
2. Importance Scoring: Assess market significance (HIGH, MEDIUM, LOW)
3. Market Relevance: Whether the news can directly impact crypto prices
4. Sentiment Score: A numeric score from -1.0 (extremely bearish) to +1.0 (extremely bullish)

## Classification Framework
- Market-Relevant: Regulatory developments, institutional movements, technical breakthroughs, exchange issues, significant partnerships, macroeconomic events affecting crypto
- Low-Value: Speculation without substance, minor influencer opinions, repetitive announcements

## Response Format (JSON only, no extra text)
{"sentiment": "POSITIVE|NEGATIVE|NEUTRAL", "importance": "HIGH|MEDIUM|LOW", "is_market_relevant": true|false, "sentiment_score": <float -1.0 to 1.0>}

Examples:
- SEC approves Bitcoin ETF → {"sentiment": "POSITIVE", "importance": "HIGH", "is_market_relevant": true, "sentiment_score": 0.9}
- Minor altcoin partnership → {"sentiment": "NEUTRAL", "importance": "LOW", "is_market_relevant": false, "sentiment_score": 0.0}
- Major exchange hacked → {"sentiment": "NEGATIVE", "importance": "HIGH", "is_market_relevant": true, "sentiment_score": -0.85}
"""

USER_PROMPT_TEMPLATE = "Analyze this crypto news article:\nTitle: {title}\nText: {text}"


def _parse_llm_response(content: str) -> Optional[dict]:
    """解析 LLM 返回的 JSON 响应。"""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end])
            except json.JSONDecodeError:
                pass
    return None


def analyze_sentiment_batch(
    news_items: List[NewsItem],
    openai_api_key: str,
    model_name: str = "gpt-4o-mini",
    timeout: int = 30,
) -> List[ProcessedNewsItem]:
    """
    批量对新闻进行情绪分析。

    Args:
        news_items: 待分析的新闻列表
        openai_api_key: OpenAI API Key
        model_name: 使用的模型（默认 gpt-4o-mini 兼顾成本与质量）
        timeout: HTTP 超时

    Returns:
        分析完成的 ProcessedNewsItem 列表
    """
    if not news_items:
        return []
    if not openai_api_key:
        logger.warning("OpenAI API Key 未配置，跳过情绪分析")
        return []

    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai 包未安装，无法进行情绪分析")
        return []

    client = OpenAI(api_key=openai_api_key, timeout=timeout)
    processed: List[ProcessedNewsItem] = []

    for item in news_items:
        try:
            user_msg = USER_PROMPT_TEMPLATE.format(title=item.title, text=item.text[:800])

            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.1,
                max_tokens=200,
            )

            content = response.choices[0].message.content or ""
            parsed = _parse_llm_response(content)

            if not parsed:
                logger.warning("LLM 响应解析失败: %s", content[:100])
                continue

            sentiment = Sentiment(parsed.get("sentiment", "NEUTRAL").upper())
            importance = Importance(parsed.get("importance", "LOW").upper())
            is_relevant = bool(parsed.get("is_market_relevant", False))
            score = float(parsed.get("sentiment_score", 0.0))
            score = max(-1.0, min(1.0, score))

            processed.append(ProcessedNewsItem(
                id=item.id,
                title=item.title,
                text=item.text,
                source_name=item.source_name,
                news_url=item.news_url,
                image_url=item.image_url,
                sentiment=sentiment,
                importance=importance,
                is_market_relevant=is_relevant,
                sentiment_score=score,
                timestamp=item.timestamp,
            ))
            logger.debug("分析完成: [%s] %s → %s %.2f", importance.value, item.title[:30], sentiment.value, score)

        except Exception as e:
            logger.error("新闻情绪分析失败 [%s]: %s", item.id[:8], e)
            continue

    logger.info("情绪分析完成：%d/%d 条", len(processed), len(news_items))
    return processed
