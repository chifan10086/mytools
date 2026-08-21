# -*- coding: utf-8 -*-
"""
多交易所 BTC 永续公开数据（基于 ccxt）：24h 成交额、最新价、资金费率、未平仓量、短周期动量。
仅用公开 API，无需鉴权；用于 consensus 策略的 pressure 与 volume 权重。

支持交易所：binance, bybit, okx, bitget, gate, htx, kucoin, mexc
在 config 的 CONSENSUS_EXCHANGES / DECISION_JOURNAL_EXCHANGES 里填别名即可。
国内等网络环境若 binance/bybit 等超时，可在 config 设置 CCXT_PROXY（http/https/socks5 URL）。
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import ccxt

logger = logging.getLogger(__name__)

_TIMEOUT_MS = 10_000
_SYMBOL = "BTC/USDT:USDT"

# 别名 → ccxt 类名（永续合约需要特定子类的交易所）
# gate：ccxt 现用 gate；4.5 中后期已移除 gateio 别名，旧版再回退
_ALIAS: Dict[str, str] = {
    "binance": "binanceusdm",
    "huobi": "htx",
    "kucoin": "kucoinfutures",
    "gateio": "gate",
}

_exchange_cache: Dict[tuple, ccxt.Exchange] = {}


def _get_proxy() -> Optional[str]:
    """从 config 读取代理地址，支持 http/https/socks5。"""
    try:
        import config as _c
        p = getattr(_c, "CCXT_PROXY", None)
        if p is None:
            return None
        s = str(p).strip()
        return s or None
    except Exception:
        return None


def _get_exchange(name: str) -> Optional[ccxt.Exchange]:
    ccxt_id = _ALIAS.get(name, name)
    proxy = _get_proxy()
    cache_key = (ccxt_id, proxy or "")
    if cache_key in _exchange_cache:
        return _exchange_cache[cache_key]
    cls = getattr(ccxt, ccxt_id, None)
    if cls is None and ccxt_id == "gate":
        cls = getattr(ccxt, "gateio", None)
    if cls is None:
        logger.warning("ccxt 不支持交易所: %s (ccxt_id=%s)", name, ccxt_id)
        return None
    opts: Dict[str, Any] = {
        "enableRateLimit": True,
        "timeout": _TIMEOUT_MS,
        "options": {"defaultType": "swap"},
    }
    if proxy:
        if proxy.lower().startswith("socks"):
            opts["socksProxy"] = proxy
        elif proxy.lower().startswith("http"):
            opts["httpProxy"] = proxy
            opts["httpsProxy"] = proxy
    ex = cls(opts)
    _exchange_cache[cache_key] = ex
    return ex


def _fetch_one(name: str, momentum_minutes: int) -> Optional[Dict[str, Any]]:
    """拉取单个交易所的 ticker + funding + OI + 短周期动量。"""
    ex = _get_exchange(name)
    if ex is None:
        return None
    try:
        ticker = ex.fetch_ticker(_SYMBOL)
    except Exception as e:
        logger.debug("fetch_ticker %s 失败: %s", name, e)
        return None

    price = float(ticker.get("last") or 0)
    if price <= 0:
        return None
    exid = getattr(ex, "id", "") or ""
    volume_24h = float(ticker.get("quoteVolume") or 0)
    if volume_24h <= 0:
        info = ticker.get("info") or {}
        if exid == "okx" and isinstance(info, dict):
            # OKX 永续 ticker 常无 quoteVolume；volCcy24h 为标的成交量（BTC），乘价得约 USDT 成交额
            vc = float(info.get("volCcy24h") or 0)
            if vc > 0:
                volume_24h = vc * price
    if volume_24h <= 0:
        base_vol = float(ticker.get("baseVolume") or 0)
        if base_vol > 0 and exid != "okx":
            volume_24h = base_vol * price

    funding = 0.0
    try:
        fr = ex.fetch_funding_rate(_SYMBOL)
        funding = float(fr.get("fundingRate") or 0)
    except Exception:
        pass

    oi_val = 0.0
    try:
        if hasattr(ex, "fetch_open_interest"):
            oi_data = ex.fetch_open_interest(_SYMBOL)
            oi_val = float(
                oi_data.get("openInterestValue")
                or oi_data.get("openInterestAmount", 0)
                or 0
            )
    except Exception:
        pass

    momentum = 0.0
    try:
        tf = "5m" if momentum_minutes >= 5 else "1m"
        ohlcv = ex.fetch_ohlcv(_SYMBOL, timeframe=tf, limit=3)
        if ohlcv and len(ohlcv) >= 2:
            old_c = float(ohlcv[0][4])
            new_c = float(ohlcv[-1][4])
            if old_c > 0:
                momentum = (new_c - old_c) / old_c
    except Exception:
        pass

    return {
        "exchange": name,
        "volume_24h": volume_24h,
        "price": price,
        "funding_rate": funding,
        "open_interest": oi_val,
        "momentum": momentum,
    }


def fetch_exchanges(
    exchange_ids: List[str],
    momentum_minutes: int = 5,
    parallel: bool = False,
) -> List[Dict[str, Any]]:
    """
    拉取各交易所数据，返回列表，每项含 volume_24h, price, funding_rate, open_interest, momentum。
    parallel=True 时各所并行请求（推荐用于决策日志等非热路径）。
    """
    ids = [(ex or "").strip().lower() for ex in exchange_ids]
    ids = [e for e in ids if e]

    out: List[Dict[str, Any]] = []
    if parallel and len(ids) > 1:
        with ThreadPoolExecutor(max_workers=min(10, len(ids))) as pool:
            futs = {pool.submit(_fetch_one, eid, momentum_minutes): eid for eid in ids}
            for fut in as_completed(futs):
                try:
                    row = fut.result()
                    if row:
                        out.append(row)
                except Exception:
                    pass
        out.sort(key=lambda r: r.get("exchange", ""))
    else:
        for eid in ids:
            row = _fetch_one(eid, momentum_minutes)
            if row:
                out.append(row)
    return out


def volume_weights(records: List[Dict[str, Any]]) -> List[float]:
    """按 24h 成交额计算权重（归一化）。"""
    total = sum(r.get("volume_24h", 0) or 0 for r in records)
    if total <= 0:
        n = len(records)
        return [1.0 / n] * n if n else []
    return [(r.get("volume_24h", 0) or 0) / total for r in records]


def global_pressure(
    records: List[Dict[str, Any]],
    weights: List[float],
    a: float,
    b: float,
    c: float,
    oi_change_list: Optional[List[float]] = None,
) -> float:
    """
    pressure_i = a * momentum + b * oi_change - c * funding_rate
    global_pressure = Σ(weight_i * pressure_i)
    """
    if not records or len(weights) != len(records):
        return 0.0
    oi_changes = oi_change_list or []
    total = 0.0
    for i, r in enumerate(records):
        m = r.get("momentum", 0) or 0
        f = r.get("funding_rate", 0) or 0
        oi_ch = oi_changes[i] if i < len(oi_changes) else 0.0
        total += weights[i] * (a * m + b * oi_ch - c * f)
    return total
