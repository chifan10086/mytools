# -*- coding: utf-8 -*-
"""
多策略可选：EMA 交叉 / MACD / RSI / 组合(趋势+RSI 过滤) / freqtrade 风格(technical)。
统一接口 compute_signal() -> (direction, sl, tp, rationale)；config.STRATEGY 选择策略。
"""
from typing import List, Tuple, Optional

from config import (
    STRATEGY,
    FREQTRADE_CONFIRM,
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
    CONSENSUS_EXCHANGES,
    CONSENSUS_A,
    CONSENSUS_B,
    CONSENSUS_C,
    CONSENSUS_THRESHOLD_LONG,
    CONSENSUS_THRESHOLD_SHORT,
    CONSENSUS_MOMENTUM_MINUTES,
)
from freqtrade_advisory import compute_freqtrade_signal


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
) -> Tuple[int, Optional[float], Optional[float], str]:
    n = len(closes)
    if n < EMA_SLOW + ATR_PERIOD:
        return 0, None, None, f"【EMA交叉】K线不足(需≥{EMA_SLOW + ATR_PERIOD})"
    ema_f = _ema(closes, EMA_FAST)
    ema_s = _ema(closes, EMA_SLOW)
    atr = _atr(highs, lows, closes, ATR_PERIOD)
    i = n - 1
    atr_val = atr[i]
    if atr_val <= 0:
        return 0, None, None, "【EMA交叉】ATR 无效"
    price = closes[i]
    dist_fast = abs(price - ema_f[i])
    dist_slow = abs(price - ema_s[i])
    if dist_fast < ATR_FILTER_MULT * atr_val or dist_slow < ATR_FILTER_MULT * atr_val:
        return (
            0,
            None,
            None,
            f"【EMA交叉】价距 EMA 未过 ATR 过滤 (ATR={atr_val:.2f})",
        )
    snap = f"【EMA交叉】收盘={price:.2f} EMA{EMA_FAST}={ema_f[i]:.2f} EMA{EMA_SLOW}={ema_s[i]:.2f}"
    if ema_f[i] > ema_s[i] and (i == 0 or ema_f[i - 1] <= ema_s[i - 1]):
        sl, tp = _sl_tp_long(price)
        return 1, sl, tp, snap + " → 金叉做多"
    if ema_f[i] < ema_s[i] and (i == 0 or ema_f[i - 1] >= ema_s[i - 1]):
        sl, tp = _sl_tp_short(price)
        return -1, sl, tp, snap + " → 死叉做空"
    return 0, None, None, snap + " → 无交叉"


# ---------- MACD ----------
def _compute_macd(
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[int, Optional[float], Optional[float], str]:
    n = len(closes)
    need = MACD_SLOW + MACD_SIGNAL
    if n < need:
        return 0, None, None, f"【MACD】K线不足(需≥{need})"
    macd_line, signal_line, histogram = _macd(closes, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
    i = n - 1
    price = closes[i]
    if MACD_ATR_FILTER and n >= need + ATR_PERIOD:
        atr = _atr(highs, lows, closes, ATR_PERIOD)
        atr_val = atr[i]
        if atr_val > 0 and abs(histogram[i]) < ATR_FILTER_MULT * atr_val:
            return 0, None, None, f"【MACD】柱幅小于 ATR×{ATR_FILTER_MULT}，过滤"
    hist = histogram[i]
    hist1 = histogram[i - 1] if i > 0 else 0.0
    snap = f"【MACD】hist={hist:.6f} 前根={hist1:.6f} 收盘={price:.2f}"
    if histogram[i] > 0 and (i == 0 or histogram[i - 1] <= 0):
        sl, tp = _sl_tp_long(price)
        return 1, sl, tp, snap + " → 上穿做多"
    if histogram[i] < 0 and (i == 0 or histogram[i - 1] >= 0):
        sl, tp = _sl_tp_short(price)
        return -1, sl, tp, snap + " → 下穿做空"
    return 0, None, None, snap + " → 无信号"


# ---------- RSI ----------
def _compute_rsi(closes: List[float]) -> Tuple[int, Optional[float], Optional[float], str]:
    n = len(closes)
    if n < RSI_PERIOD + 1:
        return 0, None, None, "【RSI】K线不足"
    rsi_series = _rsi(closes, RSI_PERIOD)
    i = n - 1
    r = rsi_series[i]
    if r is None:
        return 0, None, None, "【RSI】无效"
    price = closes[i]
    snap = f"【RSI】RSI({RSI_PERIOD})={r:.1f} 收盘={price:.2f}"
    if r < RSI_OVERSOLD:
        sl, tp = _sl_tp_long(price)
        return 1, sl, tp, snap + f" <{RSI_OVERSOLD} 超卖做多"
    if r > RSI_OVERBOUGHT:
        sl, tp = _sl_tp_short(price)
        return -1, sl, tp, snap + f" >{RSI_OVERBOUGHT} 超买做空"
    return 0, None, None, snap + " → 中性"


# ---------- 高频：快均线 5/20，不做 ATR 过滤，信号多、不蹲守 ----------
def _compute_hf(
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[int, Optional[float], Optional[float], str]:
    n = len(closes)
    if n < EMA_HF_SLOW + 1:
        return 0, None, None, "【HF】K线不足"
    ema_f = _ema(closes, EMA_HF_FAST)
    ema_s = _ema(closes, EMA_HF_SLOW)
    i = n - 1
    price = closes[i]
    snap = f"【HF】收盘={price:.2f} EMA{EMA_HF_FAST}={ema_f[i]:.2f} EMA{EMA_HF_SLOW}={ema_s[i]:.2f}"
    if ema_f[i] > ema_s[i] and (i == 0 or ema_f[i - 1] <= ema_s[i - 1]):
        sl, tp = _sl_tp_long(price)
        return 1, sl, tp, snap + " → 金叉做多"
    if ema_f[i] < ema_s[i] and (i == 0 or ema_f[i - 1] >= ema_s[i - 1]):
        sl, tp = _sl_tp_short(price)
        return -1, sl, tp, snap + " → 死叉做空"
    return 0, None, None, snap + " → 无交叉"


# ---------- 多交易所共识：global_pressure = Σ(volume_weight × pressure)，pressure = a*momentum + b*OI_change - c*funding ----------
def _compute_consensus(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[int, Optional[float], Optional[float], str]:
    from multi_exchange import fetch_exchanges, volume_weights, global_pressure

    records = fetch_exchanges(CONSENSUS_EXCHANGES, CONSENSUS_MOMENTUM_MINUTES)
    if len(records) < 2:
        return 0, None, None, "【共识】交易所数据不足"
    weights = volume_weights(records)
    gp = global_pressure(records, weights, CONSENSUS_A, CONSENSUS_B, CONSENSUS_C, oi_change_list=None)
    price = closes[-1] if closes else (records[0].get("price") or 0)
    if price <= 0:
        return 0, None, None, "【共识】价格无效"
    snap = f"【共识】global_pressure={gp:.4f} 阈值多{CONSENSUS_THRESHOLD_LONG}/空{CONSENSUS_THRESHOLD_SHORT} 收盘={price:.2f}"
    if gp >= CONSENSUS_THRESHOLD_LONG:
        sl, tp = _sl_tp_long(price)
        return 1, sl, tp, snap + " → 偏多"
    if gp <= CONSENSUS_THRESHOLD_SHORT:
        sl, tp = _sl_tp_short(price)
        return -1, sl, tp, snap + " → 偏空"
    return 0, None, None, snap + " → 未过阈值"


# ---------- 组合：EMA 趋势 + RSI 过滤（避免超买追多、超卖追空）----------
def _compute_composite(
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[int, Optional[float], Optional[float], str]:
    direction, sl, tp, base_r = _compute_ema_cross(highs, lows, closes)
    if direction == 0:
        return 0, None, None, base_r
    n = len(closes)
    if n < RSI_PERIOD + 1:
        return direction, sl, tp, base_r
    rsi_series = _rsi(closes, RSI_PERIOD)
    r = rsi_series[n - 1]
    if r is None:
        return direction, sl, tp, base_r
    if direction == 1 and r > RSI_NEUTRAL_HIGH:
        return 0, None, None, base_r + f"\n【组合过滤】RSI={r:.1f}>{RSI_NEUTRAL_HIGH} 不追多"
    if direction == -1 and r < RSI_NEUTRAL_LOW:
        return 0, None, None, base_r + f"\n【组合过滤】RSI={r:.1f}<{RSI_NEUTRAL_LOW} 不追空"
    return direction, sl, tp, base_r + f"\n【组合】RSI={r:.1f} 通过"


def _dispatch_strategy(
    s: str,
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[int, Optional[float], Optional[float], str]:
    if s == "hf":
        return _compute_hf(highs, lows, closes)
    if s == "consensus":
        return _compute_consensus(opens, highs, lows, closes)
    if s == "macd":
        return _compute_macd(highs, lows, closes)
    if s == "rsi":
        return _compute_rsi(closes)
    if s == "composite":
        return _compute_composite(highs, lows, closes)
    return _compute_ema_cross(highs, lows, closes)


def compute_signal(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[int, Optional[float], Optional[float], str]:
    """
    返回 (direction, stop_loss_price, take_profit_price, rationale)。
    direction: 1=多, -1=空, 0=无。
    STRATEGY: hf | ema_cross | macd | rsi | composite | consensus | freqtrade
    FREQTRADE_CONFIRM=True 时主策略须与 freqtrade 风格同向才出信号。
    """
    s = (STRATEGY or "ema_cross").strip().lower()
    if s == "freqtrade":
        return compute_freqtrade_signal(opens, highs, lows, closes)

    bd, bsl, btp, br = _dispatch_strategy(s, opens, highs, lows, closes)

    if FREQTRADE_CONFIRM:
        fd, fsl, ftp, fr = compute_freqtrade_signal(opens, highs, lows, closes)
        if bd in (1, -1) and fd != bd:
            return (
                0,
                None,
                None,
                "【Freqtrade 共识未通过】主策略与 FT 方向不一致，不下单\n---\n主策略:\n"
                + br
                + "\n---\nFreqtrade:\n"
                + fr,
            )
        if bd in (1, -1) and fd == bd:
            sl = bsl if bsl is not None else fsl
            tp = btp if btp is not None else ftp
            return (
                bd,
                sl,
                tp,
                "【主策略 + Freqtrade 一致】\n" + br + "\n---\n" + fr,
            )
        return (
            0,
            None,
            None,
            "【无开仓信号】\n主策略:\n" + br + "\n---\nFreqtrade:\n" + fr,
        )

    return bd, bsl, btp, br


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
