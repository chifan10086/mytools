# -*- coding: utf-8 -*-
"""
文件缓存模块。
参考 crypto_news_pipeline 的 check_cache 节点思路，
但用本地 JSON 文件替代 MongoDB，减少外部依赖。
"""
import json
import logging
import os
from typing import Set

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_PATH = "logs/news_cache.json"


class NewsCache:
    """基于 JSON 文件的新闻 ID 缓存，防止重复处理。"""

    def __init__(self, cache_path: str = ""):
        self._path = cache_path or _DEFAULT_CACHE_PATH
        self._ids: Set[str] = set()
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._ids = set(data)
            logger.debug("缓存加载完成：%d 条", len(self._ids))
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("缓存文件加载失败: %s", e)

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(list(self._ids), f)
        except IOError as e:
            logger.error("缓存文件保存失败: %s", e)

    def contains(self, news_id: str) -> bool:
        return news_id in self._ids

    def add(self, news_id: str) -> None:
        self._ids.add(news_id)

    def add_batch(self, news_ids) -> None:
        self._ids.update(news_ids)
        self._save()

    def size(self) -> int:
        return len(self._ids)

    def trim(self, max_size: int = 5000) -> None:
        """限制缓存大小，移除最早添加的条目（近似 FIFO）。"""
        if len(self._ids) > max_size:
            excess = len(self._ids) - max_size
            ids_list = list(self._ids)
            self._ids = set(ids_list[excess:])
            self._save()
