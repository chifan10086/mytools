# -*- coding: utf-8 -*-
"""
旧版 config.py 未包含后续新增项时，在 import config 之后、读取新项之前执行本模块即可补齐默认值。
用法：在 from config import ... 之前写一行：import config_bootstrap  # noqa: F401
"""
import config as _cfg

_DEFAULTS = {
    "FREQTRADE_CONFIRM": False,
    "FT_EMA_SHORT": 12,
    "FT_EMA_LONG": 26,
    "FT_MACD_FAST": 12,
    "FT_MACD_SLOW": 26,
    "FT_MACD_SIGNAL": 9,
    "FT_USE_MACD_FILTER": True,
    "FT_RSI_PERIOD": 14,
    "FT_RSI_LONG_MAX": 72,
    "FT_RSI_SHORT_MIN": 28,
    "FUTURES_TAKER_FEE_RATE": 0.0005,
    "FUNDING_SETTLEMENT_SECONDS": 28800,
    "USE_API_FUNDING_RATE": True,
    "FUNDING_RATE_FALLBACK": 0.0,
    "HOURLY_REPORT_INTERVAL_SEC": 3600,
}

for _name, _val in _DEFAULTS.items():
    if not hasattr(_cfg, _name):
        setattr(_cfg, _name, _val)
