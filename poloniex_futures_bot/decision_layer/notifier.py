# -*- coding: utf-8 -*-
"""
Telegram 新闻推送模块。
参考 crypto_news_pipeline/src/nodes/telegram_notifier.py 和 src/utils/helpers.py，
将高影响力新闻实时推送到 Telegram。
"""
import logging
from typing import List

from decision_layer.models import ProcessedNewsItem, Sentiment, Importance

logger = logging.getLogger(__name__)

_SENTIMENT_EMOJI = {
    Sentiment.POSITIVE: "🟢",
    Sentiment.NEGATIVE: "🔴",
    Sentiment.NEUTRAL: "🟡",
}

_IMPORTANCE_EMOJI = {
    Importance.HIGH: "🔥",
    Importance.MEDIUM: "⚡",
    Importance.LOW: "💡",
}


def _build_news_message(news: ProcessedNewsItem) -> str:
    """构建单条新闻的 Telegram 消息。"""
    sent_emoji = _SENTIMENT_EMOJI.get(news.sentiment, "⚪")
    imp_emoji = _IMPORTANCE_EMOJI.get(news.importance, "📊")
    sent_cn = {"POSITIVE": "看多", "NEGATIVE": "看空", "NEUTRAL": "中性"}.get(news.sentiment.value, "中性")
    imp_cn = {"HIGH": "高", "MEDIUM": "中", "LOW": "低"}.get(news.importance.value, "低")

    text = news.text[:200] + "..." if len(news.text) > 200 else news.text

    parts = [
        f"📰 {news.title}",
        "",
        f"{text}",
        "",
        f"{sent_emoji} 情绪: {sent_cn} ({news.sentiment_score:+.2f})",
        f"{imp_emoji} 重要性: {imp_cn}",
        f"📡 来源: {news.source_name}",
    ]

    if news.news_url:
        parts.append(f"🔗 {news.news_url}")

    parts.append("─────────────────")
    return "\n".join(parts)


def _build_summary_message(news_list: List[ProcessedNewsItem], score_val: float) -> str:
    """构建批量新闻汇总消息。"""
    bullish = sum(1 for n in news_list if n.sentiment == Sentiment.POSITIVE)
    bearish = sum(1 for n in news_list if n.sentiment == Sentiment.NEGATIVE)
    neutral = sum(1 for n in news_list if n.sentiment == Sentiment.NEUTRAL)
    high = sum(1 for n in news_list if n.importance == Importance.HIGH)

    if score_val >= 0.3:
        bias = "偏多 📈"
    elif score_val <= -0.3:
        bias = "偏空 📉"
    else:
        bias = "中性 ➡️"

    return (
        f"╔═══════════════════╗\n"
        f"║  📊 新闻情绪汇总   ║\n"
        f"╚═══════════════════╝\n"
        f"处理新闻: {len(news_list)} 条\n"
        f"🟢 看多: {bullish} | 🔴 看空: {bearish} | 🟡 中性: {neutral}\n"
        f"🔥 高影响: {high} 条\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"综合评分: {score_val:+.3f} ({bias})\n"
        f"━━━━━━━━━━━━━━━━"
    )


def notify_important_news(
    news_list: List[ProcessedNewsItem],
    aggregate_score: float,
    send_fn,
    min_importance: Importance = Importance.MEDIUM,
    send_summary: bool = True,
) -> int:
    """
    推送重要新闻到 Telegram。

    Args:
        news_list: 处理过的新闻列表
        aggregate_score: 当前聚合评分
        send_fn: 发送 Telegram 的函数（接受 str 参数）
        min_importance: 最低推送重要性
        send_summary: 是否发送汇总消息

    Returns:
        实际发送的消息数
    """
    if not news_list:
        return 0

    importance_order = [Importance.HIGH, Importance.MEDIUM, Importance.LOW]
    min_idx = importance_order.index(min_importance)
    allowed = set(importance_order[: min_idx + 1])

    sent = 0

    # 先发汇总
    if send_summary:
        try:
            summary = _build_summary_message(news_list, aggregate_score)
            send_fn(summary)
            sent += 1
        except Exception as e:
            logger.error("发送汇总消息失败: %s", e)

    # 逐条发送符合重要性阈值的新闻
    for news in news_list:
        if news.importance not in allowed:
            continue
        if not news.is_market_relevant:
            continue
        try:
            msg = _build_news_message(news)
            send_fn(msg)
            sent += 1
        except Exception as e:
            logger.error("推送新闻失败 [%s]: %s", news.id[:8], e)

    if sent > 0:
        logger.info("Telegram 推送完成：%d 条消息", sent)
    return sent
