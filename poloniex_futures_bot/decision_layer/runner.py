# -*- coding: utf-8 -*-
"""
Decision Layer 后台运行器。
以守护线程定时运行新闻采集 → 缓存过滤 → 情绪分析 → 评分更新 → 推送。
"""
import time
import logging
import threading
from typing import Optional

from decision_layer.news_fetcher import fetch_crypto_news
from decision_layer.cache import NewsCache
from decision_layer.sentiment import analyze_sentiment_batch
from decision_layer.scorer import update_score, get_current_score, SentimentScore
from decision_layer.notifier import notify_important_news
from decision_layer.models import Importance

logger = logging.getLogger(__name__)


class DecisionLayerRunner:
    """
    Decision Layer 后台运行器。

    在独立守护线程中按 interval_sec 定时执行：
    1. 拉取新闻
    2. 缓存去重
    3. LLM 情绪分析
    4. 更新全局评分
    5. 推送重要新闻到 Telegram
    """

    def __init__(
        self,
        news_api_key: str = "",
        news_api_url: str = "",
        openai_api_key: str = "",
        openai_model: str = "gpt-4o-mini",
        interval_sec: int = 60,
        telegram_send_fn=None,
        telegram_min_importance: str = "MEDIUM",
        cache_path: str = "",
        enabled: bool = True,
    ):
        self._news_api_key = news_api_key
        self._news_api_url = news_api_url
        self._openai_api_key = openai_api_key
        self._openai_model = openai_model
        self._interval_sec = max(30, interval_sec)
        self._telegram_send_fn = telegram_send_fn
        self._min_importance = Importance[telegram_min_importance.upper()] if telegram_min_importance else Importance.MEDIUM
        self._cache = NewsCache(cache_path)
        self._enabled = enabled
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._run_count = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def run_count(self) -> int:
        return self._run_count

    def start(self) -> None:
        """启动后台线程。"""
        if not self._enabled:
            logger.info("Decision Layer 已禁用，不启动")
            return
        if not self._news_api_key:
            logger.warning("Decision Layer: 新闻 API Key 未配置，不启动")
            self._enabled = False
            return
        if not self._openai_api_key:
            logger.warning("Decision Layer: OpenAI API Key 未配置，情绪分析将跳过")

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="DecisionLayer", daemon=True)
        self._thread.start()
        logger.info(
            "Decision Layer 启动: 间隔 %ds | 模型 %s | 推送阈值 %s",
            self._interval_sec, self._openai_model, self._min_importance.value,
        )

    def stop(self) -> None:
        """停止后台线程。"""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        logger.info("Decision Layer 已停止")

    def run_once(self) -> SentimentScore:
        """手动执行一次完整流水线（供测试或同步调用）。"""
        return self._pipeline()

    def _loop(self) -> None:
        """后台循环主体。"""
        # 首次启动延迟 5 秒，等主循环先就绪
        time.sleep(5)
        while not self._stop_event.is_set():
            try:
                self._pipeline()
            except Exception as e:
                logger.exception("Decision Layer 管道执行异常: %s", e)
            self._stop_event.wait(self._interval_sec)

    def _pipeline(self) -> SentimentScore:
        """单次执行：采集 → 去重 → 分析 → 评分 → 推送。"""
        self._run_count += 1
        logger.debug("Decision Layer 第 %d 次执行...", self._run_count)

        # 1. 采集新闻
        raw_news = fetch_crypto_news(self._news_api_key, self._news_api_url)
        if not raw_news:
            logger.debug("无新闻数据")
            return get_current_score()

        # 2. 缓存去重
        unseen = [n for n in raw_news if not self._cache.contains(n.id)]
        cache_hit = len(raw_news) - len(unseen)
        if cache_hit > 0:
            logger.debug("缓存命中 %d 条，新增 %d 条", cache_hit, len(unseen))
        if not unseen:
            return get_current_score()

        # 3. 情绪分析
        processed = analyze_sentiment_batch(
            unseen,
            openai_api_key=self._openai_api_key,
            model_name=self._openai_model,
        )

        # 4. 更新缓存
        if processed:
            self._cache.add_batch([n.id for n in processed])
            self._cache.trim(max_size=3000)

        # 5. 更新全局评分
        score = update_score(processed)

        # 6. Telegram 推送
        if self._telegram_send_fn and processed:
            notify_important_news(
                processed,
                aggregate_score=score.score,
                send_fn=self._telegram_send_fn,
                min_importance=self._min_importance,
                send_summary=True,
            )

        return score
