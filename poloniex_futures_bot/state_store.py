# -*- coding: utf-8 -*-
"""
运行状态落盘（logs/runtime_state.json）：Paper 权益与持仓、风控计数、未平仓交易的 MFE/MAE。
解决重启后 Paper 权益回到 INITIAL_EQUITY、冷静期清零、开仓行没有对应平仓行的问题。
写入失败只记 warning，不影响交易。想从零开始就删掉该文件。
"""
import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)


def load_state(path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("运行状态读取失败 %s: %s", path, e)
        return {}


def save_state(path: str, data: Dict[str, Any]) -> None:
    if not path:
        return
    try:
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except Exception as e:
        logger.warning("运行状态写入失败 %s: %s", path, e)
