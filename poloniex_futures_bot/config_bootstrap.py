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
    "FT_REQUIRE_HIST_MOMENTUM": True,
    "FUTURES_TAKER_FEE_RATE": 0.0005,
    "FUNDING_SETTLEMENT_SECONDS": 28800,
    "USE_API_FUNDING_RATE": True,
    "FUNDING_RATE_FALLBACK": 0.0,
    "HOURLY_REPORT_INTERVAL_SEC": 3600,
    "MTF_HTF_INTERVAL": "MINUTE_15",
    "MTF_HTF_LIMIT": 200,
    "MTF_LTF_INTERVAL": "MINUTE_1",
    "MTF_LTF_LIMIT": 100,
    "MTF_HTF_EMA_FAST": 50,
    "MTF_HTF_EMA_SLOW": 200,
    "MTF_LTF_EMA_FAST": 9,
    "MTF_LTF_EMA_SLOW": 21,
    "MTF_RSI_PERIOD": 14,
    "MTF_RSI_LONG_MAX": 70,
    "MTF_RSI_SHORT_MIN": 30,
    "MTF_VOL_MA_PERIOD": 20,
    "MTF_VOL_MULT": 1.2,
    "MTF_ATR_SL_MULT": 2.0,
    "MTF_ATR_TP_MULT": 3.0,
    "AUTO_ADX_PERIOD": 14,
    "AUTO_ADX_TREND_THRESHOLD": 25,
    "AUTO_ADX_STRONG_TREND": 40,
    "AUTO_ATR_LOOKBACK": 50,
    "AUTO_ATR_HIGH_PERCENTILE": 75,
    "AUTO_RSI_EXTREME_LOW": 20,
    "AUTO_RSI_EXTREME_HIGH": 80,
    "AUTO_STRATEGY_STRONG_TREND": "mtf",
    "AUTO_STRATEGY_TREND": "composite",
    "AUTO_STRATEGY_RANGING": "rsi",
    "AUTO_STRATEGY_HIGH_VOLATILITY": "macd",
    "AUTO_STRATEGY_EXTREME": "rsi",
    "DECISION_JOURNAL_ENABLED": True,
    "DECISION_JOURNAL_PATH": "logs/decision_journal.jsonl",
    "DECISION_JOURNAL_EXCHANGES": ["binance", "bybit", "okx", "bitget", "gate", "htx", "kucoin", "mexc"],
    "DECISION_JOURNAL_PARALLEL": True,
    "CCXT_PROXY": "",
}

for _name, _val in _DEFAULTS.items():
    if not hasattr(_cfg, _name):
        setattr(_cfg, _name, _val)
