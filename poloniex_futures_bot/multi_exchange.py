# -*- coding: utf-8 -*-
"""
多交易所 BTC 永续公开数据（基于 ccxt）：24h 成交额、最新价、资金费率、未平仓量、短周期动量。
仅用公开 API，无需鉴权；用于 consensus 策略的 pressure 与 volume 权重。

支持交易所：binance, bybit, okx, bitget, gate, htx, kucoin, mexc
盘口深度走币安永续 / Coinbase / Kraken（美元现货），不用 Poloniex。
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

# 盘口：大所深度，不用 Poloniex。coinbase/kraken 为现货，不能走 swap 默认。
_BOOK_VENUES: Dict[str, Dict[str, Any]] = {
    "binance": {"ccxt_id": "binanceusdm", "symbol": "BTC/USDT:USDT", "default_type": "swap"},
    "coinbase": {"ccxt_id": "coinbase", "symbol": "BTC/USD", "default_type": "spot"},
    "kraken": {"ccxt_id": "kraken", "symbol": "BTC/USD", "default_type": "spot"},
    "bybit": {"ccxt_id": "bybit", "symbol": "BTC/USDT:USDT", "default_type": "swap"},
}
_book_cache: Dict[tuple, ccxt.Exchange] = {}


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


def _get_book_exchange(name: str) -> Optional[ccxt.Exchange]:
    spec = _BOOK_VENUES.get(name)
    if spec is None:
        return None
    proxy = _get_proxy()
    cache_key = (spec["ccxt_id"], spec["default_type"], proxy or "")
    if cache_key in _book_cache:
        return _book_cache[cache_key]
    cls = getattr(ccxt, spec["ccxt_id"], None)
    if cls is None:
        logger.warning("ccxt 不支持盘口交易所: %s", spec["ccxt_id"])
        return None
    opts: Dict[str, Any] = {
        "enableRateLimit": True,
        "timeout": _TIMEOUT_MS,
        "options": {"defaultType": spec["default_type"]},
    }
    if proxy:
        if proxy.lower().startswith("socks"):
            opts["socksProxy"] = proxy
        elif proxy.lower().startswith("http"):
            opts["httpProxy"] = proxy
            opts["httpsProxy"] = proxy
    ex = cls(opts)
    _book_cache[cache_key] = ex
    return ex


def _book_imbalance(levels_bid: Any, levels_ask: Any) -> Optional[Dict[str, Any]]:
    def _sz(levels: Any) -> float:
        total = 0.0
        if not isinstance(levels, list):
            return 0.0
        for lv in levels:
            if isinstance(lv, (list, tuple)) and len(lv) >= 2:
                try:
                    total += float(lv[1])
                except (TypeError, ValueError):
                    pass
        return total

    bid_sz = _sz(levels_bid)
    ask_sz = _sz(levels_ask)
    tot = bid_sz + ask_sz
    if tot <= 0:
        return None
    return {
        "bid_sz": round(bid_sz, 6),
        "ask_sz": round(ask_sz, 6),
        "imbalance": round((bid_sz - ask_sz) / tot, 6),
    }


def _fetch_one_book(name: str, limit: int) -> Optional[Dict[str, Any]]:
    spec = _BOOK_VENUES.get(name)
    ex = _get_book_exchange(name)
    if spec is None or ex is None:
        return None
    symbols = [spec["symbol"]]
    if name in ("coinbase", "kraken"):
        symbols = ["BTC/USD", "BTC/USDT"]
    book = None
    used = spec["symbol"]
    last_err: Optional[Exception] = None
    for sym in symbols:
        try:
            book = ex.fetch_order_book(sym, limit)
            used = sym
            break
        except Exception as e:
            last_err = e
            book = None
    if book is None:
        logger.debug("fetch_order_book %s 失败: %s", name, last_err)
        return None
    row = _book_imbalance(book.get("bids"), book.get("asks"))
    if row is None:
        return None
    row["exchange"] = name
    row["symbol"] = used
    return row


def snapshot_major_order_books(
    exchange_ids: Optional[List[str]] = None,
    limit: int = 20,
) -> Optional[Dict[str, Any]]:
    """
    币安 / Coinbase 等大所盘口失衡。各所先算无量纲 imbalance，再等权平均
    （不能把合约张数和现货 BTC 加在一起）。
    """
    ids = exchange_ids or ["binance", "coinbase", "kraken"]
    ids = [(e or "").strip().lower() for e in ids]
    ids = [e for e in ids if e in _BOOK_VENUES]
    if not ids:
        return None
    venues: List[Dict[str, Any]] = []
    if len(ids) > 1:
        with ThreadPoolExecutor(max_workers=min(4, len(ids))) as pool:
            futs = {pool.submit(_fetch_one_book, eid, limit): eid for eid in ids}
            for fut in as_completed(futs):
                try:
                    row = fut.result()
                    if row:
                        venues.append(row)
                except Exception:
                    pass
        venues.sort(key=lambda r: r.get("exchange", ""))
    else:
        row = _fetch_one_book(ids[0], limit)
        if row:
            venues.append(row)
    if not venues:
        logger.warning("大所盘口全部失败: %s", ids)
        return None
    imb = sum(float(v["imbalance"]) for v in venues) / len(venues)
    return {
        "imbalance": round(imb, 6),
        "venues_ok": [v["exchange"] for v in venues],
        "venues": venues,
        "levels": limit,
    }


_INTERVAL_TO_TF = {
    "MINUTE_1": "1m",
    "MINUTE_5": "5m",
    "MINUTE_15": "15m",
    "MINUTE_30": "30m",
    "HOUR_1": "1h",
    "HOUR_4": "4h",
}


def fetch_binance_klines(interval: str, limit: int) -> List[List]:
    """币安 U 本位永续 K 线，转成 Poloniex 的 [l,h,o,c,amt,qty,tC,sT,cT]。"""
    ex = _get_book_exchange("binance")
    if ex is None:
        return []
    tf = _INTERVAL_TO_TF.get((interval or "").strip().upper(), "5m")
    try:
        raw = ex.fetch_ohlcv(_SYMBOL, timeframe=tf, limit=limit)
    except Exception as e:
        logger.warning("binance K 线失败: %s", e)
        return []
    out: List[List] = []
    for row in raw or []:
        if not row or len(row) < 6:
            continue
        ts, o, h, l, c, vol = row[:6]
        ts_i = int(ts)
        o, h, l, c, vol = float(o), float(h), float(l), float(c), float(vol)
        amt = vol * c if c > 0 else 0.0
        out.append([l, h, o, c, amt, vol, 0, ts_i, ts_i])
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
