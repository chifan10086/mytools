# -*- coding: utf-8 -*-
"""
Poloniex Futures V3 REST 客户端：鉴权签名 + 限频重试
"""
import hashlib
import hmac
import base64
import time
import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional, Dict, Any, List

from config import (
    API_KEY,
    API_SECRET,
    BASE_URL,
    RECV_WINDOW_MS,
    REQUEST_TIMEOUT,
    RATE_LIMIT_RETRY,
    RATE_LIMIT_BACKOFF,
)


def _sign(method: str, path: str, params: Dict[str, str], body_str: Optional[str] = None) -> tuple:
    """生成 HMAC-SHA256 签名。GET 用 params；POST/DELETE 带 body 时用 requestBody&signTimestamp。"""
    ts = str(int(time.time() * 1000))
    if body_str is not None:
        # POST/DELETE: requestBody={...}&signTimestamp=ts
        sign_str = f"requestBody={body_str}&signTimestamp={ts}"
    else:
        params = dict(params)
        params["signTimestamp"] = ts
        sign_str = "&".join(f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted(params.items()))
    req_str = f"{method}\n{path}\n{sign_str}"
    sig = hmac.new(
        API_SECRET.encode("utf-8"),
        req_str.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(sig).decode("utf-8"), ts


def _request(
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
    signed: bool = False,
) -> Dict[str, Any]:
    """发 HTTP 请求，带限频重试。path 如 /v3/market/candles，params 为 query。"""
    url = BASE_URL.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    else:
        params = {}

    last_err = None
    for attempt in range(RATE_LIMIT_RETRY + 1):
        try:
            req = urllib.request.Request(url, method=method)
            req.add_header("User-Agent", "PoloniexBot/1.0 (Python)")
            data = None
            if body is not None:
                data = json.dumps(body).encode("utf-8")
                req.add_header("Content-Type", "application/json")
                req.data = data

            if signed:
                body_str = None
                if method in ("POST", "DELETE") and body is not None:
                    body_str = json.dumps(body, separators=(",", ":"))
                signature, ts = _sign(method, path, {k: str(v) for k, v in params.items()}, body_str)
                req.add_header("key", API_KEY)
                req.add_header("signTimestamp", ts)
                req.add_header("signature", signature)
                req.add_header("signatureMethod", "HmacSHA256")
                req.add_header("signatureVersion", "1")
                req.add_header("recvWindow", str(RECV_WINDOW_MS))

            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8")
                out = json.loads(raw) if raw else {}
                if out.get("code") != 200 and out.get("code") is not None:
                    raise RuntimeError(f"API error: {out}")
                return out
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429 or e.code >= 500:
                time.sleep(RATE_LIMIT_BACKOFF * (attempt + 1))
                continue
            raw = e.read().decode("utf-8") if e.fp else ""
            try:
                err_body = json.loads(raw)
            except Exception:
                err_body = raw
            raise RuntimeError(f"HTTP {e.code}: {err_body}")
        except Exception as e:
            last_err = e
            if attempt < RATE_LIMIT_RETRY:
                time.sleep(RATE_LIMIT_BACKOFF * (attempt + 1))
                continue
            raise
    if last_err:
        raise last_err
    return {}


def get_market_funding_rate(symbol: str) -> Optional[Dict[str, Any]]:
    """
    当前资金费率（公开接口）。正费率通常表示多方向空方支付。
    返回 data 字典（含 fR 等）或 None。
    """
    try:
        r = _request("GET", "/v3/market/fundingRate", params={"symbol": symbol}, signed=False)
        data = r.get("data")
        if isinstance(data, dict) and data:
            return data
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
    except Exception:
        pass
    return None


def get_klines(symbol: str, interval: str, limit: int = 100, s_time: Optional[int] = None, e_time: Optional[int] = None) -> List[List]:
    """获取 K 线。返回 list of [l, h, o, c, amt, qty, tC, sT, cT]。"""
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    if s_time is not None:
        params["sTime"] = s_time
    if e_time is not None:
        params["eTime"] = e_time
    r = _request("GET", "/v3/market/candles", params=params, signed=False)
    return r.get("data") or []


def get_account_balance() -> Dict[str, Any]:
    """账户权益。"""
    r = _request("GET", "/v3/account/balance", signed=True)
    return r.get("data") or {}


def get_positions(symbol: Optional[str] = None) -> List[Dict]:
    """当前持仓。"""
    params = {} if symbol is None else {"symbol": symbol}
    r = _request("GET", "/v3/trade/position/opens", params=params, signed=True)
    return r.get("data") or []


def place_order(
    symbol: str,
    side: str,
    pos_side: str,
    order_type: str,
    sz: str,
    mgn_mode: str = "CROSS",
    px: Optional[str] = None,
    reduce_only: bool = False,
    cl_ord_id: Optional[str] = None,
) -> Dict[str, Any]:
    """下单。side=BUY/SELL, pos_side=LONG/SHORT, order_type=MARKET/LIMIT, sz 为张数。"""
    body = {
        "symbol": symbol,
        "side": side.upper(),
        "mgnMode": mgn_mode,
        "posSide": pos_side.upper(),
        "type": order_type.upper(),
        "sz": str(sz),
        "reduceOnly": reduce_only,
    }
    if px is not None:
        body["px"] = str(px)
    if cl_ord_id:
        body["clOrdId"] = cl_ord_id
    r = _request("POST", "/v3/trade/order", body=body, signed=True)
    return r.get("data") or r


def close_position_at_market(symbol: str, pos_side: str, sz: str) -> Dict[str, Any]:
    """市价平仓。"""
    body = {"symbol": symbol, "posSide": pos_side.upper(), "sz": str(sz)}
    r = _request("POST", "/v3/trade/position", body=body, signed=True)
    return r.get("data") or r
