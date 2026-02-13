# -*- coding: utf-8 -*-
"""
多交易所 BTC 永续公开数据：24h 成交额、最新价、资金费率、未平仓量、短周期动量。
仅用公开 API，不鉴权；用于 consensus 策略的 pressure 与 volume 权重。
"""
import json
import time
import urllib.request
from typing import Optional, Dict, Any, List

# 统一超时
_TIMEOUT = 10
_HEADERS = {"User-Agent": "PoloniexBot/1.0 (Python)"}


def _get(url: str) -> Optional[Any]:
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _binance(momentum_minutes: int) -> Optional[Dict[str, Any]]:
    """Binance USDT 永续 BTC."""
    base = "https://fapi.binance.com"
    ticker = _get(f"{base}/fapi/v1/ticker/24hr?symbol=BTCUSDT")
    if not ticker or "quoteVolume" not in ticker:
        return None
    premium = _get(f"{base}/fapi/v1/premiumIndex?symbol=BTCUSDT")
    funding = float(premium.get("lastFundingRate", 0)) if premium else 0.0
    # 5m 动量：最近 2 根 5m K 线
    interval = "5m" if momentum_minutes >= 5 else "1m"
    limit = 3
    klines = _get(f"{base}/fapi/v1/klines?symbol=BTCUSDT&interval={interval}&limit={limit}")
    momentum = 0.0
    if klines and len(klines) >= 2:
        old_c = float(klines[0][4])
        new_c = float(klines[-1][4])
        if old_c > 0:
            momentum = (new_c - old_c) / old_c
    oi = _get(f"{base}/fapi/v1/openInterest?symbol=BTCUSDT")
    oi_val = float(oi.get("openInterest", 0) or 0) if oi else 0.0
    return {
        "volume_24h": float(ticker.get("quoteVolume", 0)),
        "price": float(ticker.get("lastPrice", 0)),
        "funding_rate": funding,
        "open_interest": oi_val,
        "momentum": momentum,
    }


def _bybit(momentum_minutes: int) -> Optional[Dict[str, Any]]:
    """Bybit 线性合约 BTCUSDT."""
    base = "https://api.bybit.com"
    ticker = _get(f"{base}/v5/market/tickers?category=linear&symbol=BTCUSDT")
    if not ticker or ticker.get("retCode") != 0:
        return None
    lst = ticker.get("result", {}).get("list") or []
    if not lst:
        return None
    t = lst[0]
    volume_24h = float(t.get("turnover24h", 0) or 0)
    price = float(t.get("lastPrice", 0) or 0)
    funding = float(t.get("fundingRate", 0) or 0)
    # K 线 5m
    interval = "5" if momentum_minutes >= 5 else "1"
    klines = _get(f"{base}/v5/market/kline?category=linear&symbol=BTCUSDT&interval={interval}&limit=3")
    momentum = 0.0
    if klines and klines.get("retCode") == 0:
        rows = (klines.get("result") or {}).get("list") or []
        if len(rows) >= 2:
            # [open, high, low, close, volume, turnover]
            old_c = float(rows[-1][4])
            new_c = float(rows[0][4])
            if old_c > 0:
                momentum = (new_c - old_c) / old_c
    oi = _get(f"{base}/v5/market/open-interest/interval?category=linear&symbol=BTCUSDT&intervalTime=5")
    oi_val = 0.0
    if oi and oi.get("retCode") == 0:
        lst_oi = (oi.get("result") or {}).get("list") or []
        if lst_oi:
            oi_val = float(lst_oi[0].get("openInterest", 0) or 0)
    return {
        "volume_24h": volume_24h,
        "price": price,
        "funding_rate": funding,
        "open_interest": oi_val,
        "momentum": momentum,
    }


def _okx(momentum_minutes: int) -> Optional[Dict[str, Any]]:
    """OKX 永续 BTC-USDT-SWAP."""
    base = "https://www.okx.com"
    ticker = _get(f"{base}/api/v5/market/ticker?instId=BTC-USDT-SWAP")
    if not ticker or ticker.get("code") != "0":
        return None
    data = (ticker.get("data") or [{}])[0]
    price = float(data.get("last", 0) or 0)
    vol_ccy = float(data.get("volCcy24h", 0) or 0)
    vol_base = float(data.get("vol24h", 0) or 0)
    volume_24h = vol_ccy if vol_ccy > 0 else (vol_base * price)
    fr = _get(f"{base}/api/v5/public/funding-rate?instId=BTC-USDT-SWAP")
    funding = 0.0
    if fr and fr.get("code") == "0" and (fr.get("data") or []):
        funding = float((fr["data"][0]).get("fundingRate", 0) or 0)
    bar = "5m" if momentum_minutes >= 5 else "1m"
    candles = _get(f"{base}/api/v5/market/candles?instId=BTC-USDT-SWAP&bar={bar}&limit=3")
    momentum = 0.0
    if candles and candles.get("code") == "0" and len(candles.get("data") or []) >= 2:
        d = candles["data"]
        old_c = float(d[-1][4])
        new_c = float(d[0][4])
        if old_c > 0:
            momentum = (new_c - old_c) / old_c
    oi = _get(f"{base}/api/v5/public/open-interest?instId=BTC-USDT-SWAP")
    oi_val = float((oi.get("data") or [{}])[0].get("oi", 0) or 0) if oi and oi.get("code") == "0" and oi.get("data") else 0.0
    return {
        "volume_24h": volume_24h,
        "price": price,
        "funding_rate": funding,
        "open_interest": oi_val,
        "momentum": momentum,
    }


def _bitget(momentum_minutes: int) -> Optional[Dict[str, Any]]:
    """Bitget 永续 BTCUSDT."""
    base = "https://api.bitget.com"
    ticker = _get(f"{base}/api/v2/mix/market/ticker?symbol=BTCUSDT&productType=usdt-futures")
    if not ticker or ticker.get("code") != "00000":
        return None
    data = (ticker.get("data") or [{}])[0]
    volume_24h = float(data.get("usdtVolume", 0) or data.get("baseVolume", 0) or 0)
    price = float(data.get("lastPr", 0) or data.get("last", 0) or 0)
    funding = float(data.get("fundingRate", 0) or 0)
    bar = "5m" if momentum_minutes >= 5 else "1m"
    candles = _get(f"{base}/api/v2/mix/market/candles?symbol=BTCUSDT&productType=usdt-futures&granularity={bar}&limit=3")
    momentum = 0.0
    if candles and candles.get("code") == "00000" and len(candles.get("data") or []) >= 2:
        d = candles["data"]
        old_c = float(d[-1][4])
        new_c = float(d[0][4])
        if old_c > 0:
            momentum = (new_c - old_c) / old_c
    oi = _get(f"{base}/api/v2/mix/market/open-interest?symbol=BTCUSDT&productType=usdt-futures")
    oi_val = float((oi.get("data") or [{}])[0].get("amount", 0) or 0) if oi and oi.get("code") == "00000" and (oi.get("data") or []) else 0.0
    return {
        "volume_24h": volume_24h,
        "price": price,
        "funding_rate": funding,
        "open_interest": oi_val,
        "momentum": momentum,
    }


# OI 变化需要上一周期缓存，这里简化为 0（仅用 momentum 与 funding）
def fetch_exchanges(
    exchange_ids: List[str],
    momentum_minutes: int = 5,
) -> List[Dict[str, Any]]:
    """
    拉取各交易所数据，返回列表，每项含 volume_24h, price, funding_rate, open_interest, momentum。
    oi_change 暂不计算（需缓存），pressure 中 b*OI_change 可视为 0。
    """
    out: List[Dict[str, Any]] = []
    fetchers = {
        "binance": _binance,
        "bybit": _bybit,
        "okx": _okx,
        "bitget": _bitget,
    }
    for ex in exchange_ids:
        ex_lower = (ex or "").strip().lower()
        if ex_lower not in fetchers:
            continue
        data = fetchers[ex_lower](momentum_minutes)
        if data and data.get("price", 0) > 0:
            data["exchange"] = ex_lower
            out.append(data)
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
    oi_change_list 若为 None 或不足则对应项按 0 处理。
    """
    if not records or len(weights) != len(records):
        return 0.0
    oi_changes = oi_change_list or []
    total = 0.0
    for i, r in enumerate(records):
        momentum = r.get("momentum", 0) or 0
        funding = r.get("funding_rate", 0) or 0
        oi_ch = oi_changes[i] if i < len(oi_changes) else 0.0
        pressure_i = a * momentum + b * oi_ch - c * funding
        total += weights[i] * pressure_i
    return total
