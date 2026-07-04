# -*- coding: utf-8 -*-
"""
Decision Layer - 币圈新闻情绪决策层

基于 crypto_news_pipeline 思路，为 Freqtrade dry-run 提供外部情绪评分。
职责：采集币圈新闻 → 情绪分析 → 输出交易前置评分 → Telegram 推送重要新闻。
"""
from decision_layer.scorer import get_current_score, SentimentScore
from decision_layer.runner import DecisionLayerRunner

__all__ = ["get_current_score", "SentimentScore", "DecisionLayerRunner"]
