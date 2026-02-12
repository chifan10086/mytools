# -*- coding: utf-8 -*-
"""
多策略可选：EMA 交叉 / MACD / RSI / 组合(趋势+RSI 过滤)。
统一接口 compute_signal() -> (direction, sl, tp)；config.STRATEGY 选择策略。
"""
from typing import List, Tuple, Optional

from config import (
    STRATEGY,
    EMA_FAST,
    EMA_SLOW,
    EMA_HF_FAST,
    EMA_HF_SLOW,
    ATR_PERIOD,
    ATR_FILTER_MULT,
    STOP_LOSS_RATIO,
    TAKE_PROFIT_RATIO,
    MACD_FAST,
    MACD_SLOW,
    MACD_SIGNAL,
    MACD_ATR_FILTER,
    RSI_PERIOD,
    RSI_OVERSOLD,
    RSI_OVERBOUGHT,
    RSI_NEUTRAL_LOW,
    RSI_NEUTRAL_HIGH,
)


def _ema(series: List[float], period: int) -> List[float]:
    out: List[float] = []
    k = 2.0 / (period + 1)
    for i, x in enumerate(series):
        if i == 0:
            out.append(x)
        else:
            out.append(k * x + (1 - k) * out[-1])
    return out


def _atr(high: List[float], low: List[float], close: List[float], period: int) -> List[float]:
    n = len(close)
    atr: List[float] = [0.0] * n
    tr: List[float] = [0.0] * n
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    if n >= period:
        atr[period - 1] = sum(tr[1 : period + 1]) / period
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def _rsi(close: List[float], period: int) -> List[Optional[float]]:
    n = len(close)
    out: List[Optional[float]] = [None] * n
    for i in range(period, n):
        gains, losses = 0.0, 0.0
        for j in range(i - period + 1, i + 1):
            chg = close[j] - close[j - 1]
            if chg > 0:
                gains += chg
            else:
                losses -= chg
        avg_gain = gains / period
        avg_loss = losses / period
        if avg_loss <= 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - (100.0 / (1 + rs))
    return out


def _macd(
    close: List[float], fast: int, slow: int, signal_period: int
) -> Tuple[List[float], List[float], List[float]]:
    """返回 (macd_line, signal_line, histogram)。长度与 close 相同，前段为 0。"""
    n = len(close)
    ema_f = _ema(close, fast)
    ema_s = _ema(close, slow)
    macd_line = [ema_f[i] - ema_s[i] for i in range(n)]
    signal_line: List[float] = [0.0] * n
    k = 2.0 / (signal_period + 1)
    start = slow - 1
    end_signal = start + signal_period
    if end_signal <= n:
        signal_line[end_signal - 1] = sum(macd_line[start:end_signal]) / signal_period
        for i in range(end_signal, n):
            signal_line[i] = k * macd_line[i] + (1 - k) * signal_line[i - 1]
    histogram = [macd_line[i] - signal_line[i] for i in range(n)]
    return macd_line, signal_line, histogram


def parse_klines(data: List[List]) -> Tuple[List[float], List[float], List[float], List[float], List[int]]:
    """data 每项为 [l, h, o, c, amt, qty, tC, sT, cT]。返回 o,h,l,c,times。"""
    o, h, l, c, t = [], [], [], [], []
    for row in data:
        if len(row) >= 9:
            l.append(float(row[0]))
            h.append(float(row[1]))
            o.append(float(row[2]))
            c.append(float(row[3]))
            t.append(int(row[7]))
    return o, h, l, c, t


def _sl_tp_long(price: float) -> Tuple[float, float]:
    return price * (1 - STOP_LOSS_RATIO), price * (1 + TAKE_PROFIT_RATIO)


def _sl_tp_short(price: float) -> Tuple[float, float]:
    return price * (1 + STOP_LOSS_RATIO), price * (1 - TAKE_PROFIT_RATIO)


# ---------- EMA 交叉 ----------
def _compute_ema_cross(
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[int, Optional[float], Optional[float]]:
    n = len(closes)
    if n < EMA_SLOW + ATR_PERIOD:
        return 0, None, None
    ema_f = _ema(closes, EMA_FAST)
    ema_s = _ema(closes, EMA_SLOW)
    atr = _atr(highs, lows, closes, ATR_PERIOD)
    i = n - 1
    atr_val = atr[i]
    if atr_val <= 0:
        return 0, None, None
    price = closes[i]
    dist_fast = abs(price - ema_f[i])
    dist_slow = abs(price - ema_s[i])
    if dist_fast < ATR_FILTER_MULT * atr_val or dist_slow < ATR_FILTER_MULT * atr_val:
        return 0, None, None
    if ema_f[i] > ema_s[i] and (i == 0 or ema_f[i - 1] <= ema_s[i - 1]):
        sl, tp = _sl_tp_long(price)
        return 1, sl, tp
    if ema_f[i] < ema_s[i] and (i == 0 or ema_f[i - 1] >= ema_s[i - 1]):
        sl, tp = _sl_tp_short(price)
        return -1, sl, tp
    return 0, None, None


# ---------- MACD ----------
def _compute_macd(
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[int, Optional[float], Optional[float]]:
    n = len(closes)
    need = MACD_SLOW + MACD_SIGNAL
    if n < need:
        return 0, None, None
    macd_line, signal_line, histogram = _macd(closes, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
    i = n - 1
    price = closes[i]
    if MACD_ATR_FILTER and n >= need + ATR_PERIOD:
        atr = _atr(highs, lows, closes, ATR_PERIOD)
        atr_val = atr[i]
        if atr_val > 0 and abs(histogram[i]) < ATR_FILTER_MULT * atr_val:
            return 0, None, None
    # 上穿：前一根 MACD <= signal，当前 MACD > signal -> 多
    if histogram[i] > 0 and (i == 0 or histogram[i - 1] <= 0):
        sl, tp = _sl_tp_long(price)
        return 1, sl, tp
    if histogram[i] < 0 and (i == 0 or histogram[i - 1] >= 0):
        sl, tp = _sl_tp_short(price)
        return -1, sl, tp
    return 0, None, None


# ---------- RSI ----------
def _compute_rsi(closes: List[float]) -> Tuple[int, Optional[float], Optional[float]]:
    n = len(closes)
    if n < RSI_PERIOD + 1:
        return 0, None, None
    rsi_series = _rsi(closes, RSI_PERIOD)
    i = n - 1
    r = rsi_series[i]
    if r is None:
        return 0, None, None
    price = closes[i]
    if r < RSI_OVERSOLD:
        sl, tp = _sl_tp_long(price)
        return 1, sl, tp
    if r > RSI_OVERBOUGHT:
        sl, tp = _sl_tp_short(price)
        return -1, sl, tp
    return 0, None, None


# ---------- 高频：快均线 5/20，不做 ATR 过滤，信号多、不蹲守 ----------
def _compute_hf(
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[int, Optional[float], Optional[float]]:
    n = len(closes)
    if n < EMA_HF_SLOW + 1:
        return 0, None, None
    ema_f = _ema(closes, EMA_HF_FAST)
    ema_s = _ema(closes, EMA_HF_SLOW)
    i = n - 1
    price = closes[i]
    if ema_f[i] > ema_s[i] and (i == 0 or ema_f[i - 1] <= ema_s[i - 1]):
        sl, tp = _sl_tp_long(price)
        return 1, sl, tp
    if ema_f[i] < ema_s[i] and (i == 0 or ema_f[i - 1] >= ema_s[i - 1]):
        sl, tp = _sl_tp_short(price)
        return -1, sl, tp
    return 0, None, None


# ---------- 组合：EMA 趋势 + RSI 过滤（避免超买追多、超卖追空）----------
def _compute_composite(
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[int, Optional[float], Optional[float]]:
    direction, sl, tp = _compute_ema_cross(highs, lows, closes)
    if direction == 0:
        return 0, None, None
    n = len(closes)
    if n < RSI_PERIOD + 1:
        return direction, sl, tp
    rsi_series = _rsi(closes, RSI_PERIOD)
    r = rsi_series[n - 1]
    if r is None:
        return direction, sl, tp
    if direction == 1 and r > RSI_NEUTRAL_HIGH:
        return 0, None, None  # 做多信号但 RSI 已偏高，不追
    if direction == -1 and r < RSI_NEUTRAL_LOW:
        return 0, None, None  # 做空信号但 RSI 已偏低，不追
    return direction, sl, tp


def compute_signal(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[int, Optional[float], Optional[float]]:
    """
    返回 (direction, stop_loss_price, take_profit_price)。
    direction: 1=多, -1=空, 0=无。
    由 config.STRATEGY 选择：hf | ema_cross | macd | rsi | composite。
    """
    s = (STRATEGY or "ema_cross").strip().lower()
    if s == "hf":
        return _compute_hf(highs, lows, closes)
    if s == "macd":
        return _compute_macd(highs, lows, closes)
    if s == "rsi":
        return _compute_rsi(closes)
    if s == "composite":
        return _compute_composite(highs, lows, closes)
    return _compute_ema_cross(highs, lows, closes)


def check_stop_loss_take_profit(
    side: str,
    entry_price: float,
    current_price: float,
    stop_loss_ratio: float = STOP_LOSS_RATIO,
    take_profit_ratio: float = TAKE_PROFIT_RATIO,
) -> Optional[str]:
    """返回 "stop_loss" / "take_profit" / None。"""
    if side.upper() == "LONG":
        if current_price <= entry_price * (1 - stop_loss_ratio):
            return "stop_loss"
        if current_price >= entry_price * (1 + take_profit_ratio):
            return "take_profit"
    else:
        if current_price >= entry_price * (1 + stop_loss_ratio):
            return "stop_loss"
        if current_price <= entry_price * (1 - take_profit_ratio):
            return "take_profit"
    return None
