# -*- coding: utf-8 -*-
"""
每轮交易循环的决策与数据 JSONL 日志，供事后复盘与多所对比分析。
与下单逻辑解耦：写入失败不影响交易；多交易所拉取可配置并行。
"""
import json
import logging
import os
import time
from typing import Any, Dict, List

import config_bootstrap  # noqa: F401

from config import (
    STRATEGY,
    SYMBOL,
    KLINE_INTERVAL,
    KLINE_LIMIT,
    CONSENSUS_A,
    CONSENSUS_B,
    CONSENSUS_C,
    CONSENSUS_MOMENTUM_MINUTES,
)
import strategy
from multi_exchange import fetch_exchanges, volume_weights, global_pressure

logger = logging.getLogger(__name__)


def _cfg_bool(name: str, default: bool) -> bool:
    import config as _c

    v = getattr(_c, name, default)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)


def _cfg_str(name: str, default: str) -> str:
    import config as _c

    v = getattr(_c, name, default)
    return str(v) if v is not None else default


def _cfg_list(name: str, default: List[str]) -> List[str]:
    import config as _c

    v = getattr(_c, name, default)
    if isinstance(v, (list, tuple)):
        return [str(x).strip().lower() for x in v if str(x).strip()]
    return list(default)


def journal_enabled() -> bool:
    return _cfg_bool("DECISION_JOURNAL_ENABLED", True)


def _poloniex_derived(
    o: List[float], h: List[float], l: List[float], c: List[float], mark: float
) -> Dict[str, Any]:
    n = len(c)
    rsi_s = strategy._rsi(c, 14)
    atr_s = strategy._atr(h, l, c, 14)
    ema20 = strategy._ema(c, 20)
    ema50 = strategy._ema(c, 50)
    rsi_v = rsi_s[-1]
    atr_v = atr_s[-1]
    atr_pct = (atr_v / mark * 100.0) if mark > 0 else 0.0
    trend = "up" if n >= 50 and ema20[-1] > ema50[-1] else "down" if n >= 50 else "na"
    return {
        "bars": n,
        "interval": KLINE_INTERVAL,
        "limit": KLINE_LIMIT,
        "last_ohlc": {"o": round(o[-1], 2), "h": round(h[-1], 2), "l": round(l[-1], 2), "c": round(c[-1], 2)},
        "closes_tail_48": [round(x, 2) for x in c[-48:]],
        "rsi14": None if rsi_v is None else round(float(rsi_v), 4),
        "atr14": round(float(atr_v), 6),
        "atr14_pct_of_mark": round(atr_pct, 6),
        "ema20": round(float(ema20[-1]), 2) if n else None,
        "ema50": round(float(ema50[-1]), 2) if n >= 50 else None,
        "ema20_vs_50": trend,
    }


def _cross_exchange_block(mark_price: float) -> Dict[str, Any]:
    ex_ids = _cfg_list(
        "DECISION_JOURNAL_EXCHANGES",
        ["binance", "bybit", "okx", "bitget", "gate"],
    )
    parallel = _cfg_bool("DECISION_JOURNAL_PARALLEL", True)
    mom = int(CONSENSUS_MOMENTUM_MINUTES)
    records = fetch_exchanges(ex_ids, mom, parallel=parallel)
    out: Dict[str, Any] = {
        "exchanges_requested": ex_ids,
        "exchanges_ok": [r.get("exchange") for r in records],
        "records": [],
        "global_pressure": None,
        "volume_weights_by_exchange": {},
        "vs_poloniex_mark_bps": {},
    }
    if not records:
        return out
    for r in records:
        ex = r.get("exchange", "?")
        px = float(r.get("price", 0) or 0)
        out["records"].append(
            {
                "exchange": ex,
                "price": px,
                "volume_24h_quote": round(float(r.get("volume_24h", 0) or 0), 2),
                "funding_rate": float(r.get("funding_rate", 0) or 0),
                "open_interest": float(r.get("open_interest", 0) or 0),
                "momentum_short": round(float(r.get("momentum", 0) or 0), 8),
            }
        )
        if mark_price > 0 and px > 0:
            out["vs_poloniex_mark_bps"][ex] = round((px - mark_price) / mark_price * 10000.0, 4)
    w = volume_weights(records)
    for i, r in enumerate(records):
        ex = r.get("exchange", "?")
        if i < len(w):
            out["volume_weights_by_exchange"][ex] = round(float(w[i]), 6)
    if len(records) >= 2:
        out["global_pressure"] = round(
            global_pressure(records, w, CONSENSUS_A, CONSENSUS_B, CONSENSUS_C, None),
            8,
        )
    return out


def append_cycle_journal(jm: Dict[str, Any], risk: Any) -> None:
    """
    jm: main 循环内累积字段，至少可有 unix_ts、abort、action 等。
    """
    if not journal_enabled():
        return
    path = _cfg_str("DECISION_JOURNAL_PATH", "logs/decision_journal.jsonl")
    record: Dict[str, Any] = {
        "unix_ts": jm.get("unix_ts", time.time()),
        "iso_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(jm.get("unix_ts", time.time()))),
        "symbol": SYMBOL,
        "strategy": (STRATEGY or "").strip().lower(),
        "action": jm.get("action", "unknown"),
        "abort": jm.get("abort"),
    }
    try:
        if risk is not None and hasattr(risk, "get_statistics"):
            record["risk_stats"] = risk.get_statistics()
        if "can_trade" in jm:
            record["risk_can_trade"] = jm["can_trade"]
            record["risk_reason"] = jm.get("risk_reason", "")
        if "mark_price" in jm:
            record["mark_price"] = jm["mark_price"]
        if "equity" in jm:
            record["equity"] = jm["equity"]
        if "pos_side" in jm:
            record["position"] = {
                "side": jm.get("pos_side"),
                "size": jm.get("pos_size"),
                "entry_price": jm.get("entry_price"),
            }
        if "direction" in jm:
            record["signal"] = {
                "direction": jm["direction"],
                "stop_loss": jm.get("sl"),
                "take_profit": jm.get("tp"),
                "signal_quality": jm.get("signal_quality"),
            }
        if "rationale" in jm:
            record["rationale"] = jm["rationale"]
        if "position_scale" in jm:
            record["position_scale"] = jm["position_scale"]
        if "funding_rate" in jm:
            record["funding_rate_used"] = jm["funding_rate"]

        o = jm.get("o")
        h = jm.get("h")
        l = jm.get("l")
        c = jm.get("c")
        mark = float(jm.get("mark_price") or 0)
        if isinstance(o, list) and isinstance(h, list) and isinstance(l, list) and isinstance(c, list) and len(c) >= 14:
            record["poloniex"] = _poloniex_derived(o, h, l, c, mark if mark > 0 else float(c[-1]))
        if mark > 0 and not jm.get("skip_cross_exchange"):
            record["cross_exchange"] = _cross_exchange_block(mark)
    except Exception as e:
        record["journal_build_error"] = str(e)
        logger.warning("决策日志组装异常: %s", e)

    try:
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        logger.warning("决策日志写入失败 %s: %s", path, e)
