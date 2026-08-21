# -*- coding: utf-8 -*-
"""
多策略可选：EMA 交叉 / MACD / RSI / 组合(趋势+RSI 过滤) / freqtrade 风格(technical)。
统一接口 compute_signal() -> (direction, sl, tp, rationale, signal_quality)；config.STRATEGY 选择策略。
增强版：信号质量评分、趋势过滤、防假突破。
"""
from typing import Dict, List, Tuple, Optional

import config_bootstrap  # noqa: F401

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
    MTF_HTF_INTERVAL,
    MTF_HTF_LIMIT,
    MTF_LTF_INTERVAL,
    MTF_LTF_LIMIT,
    MTF_HTF_EMA_FAST,
    MTF_HTF_EMA_SLOW,
    MTF_LTF_EMA_FAST,
    MTF_LTF_EMA_SLOW,
    MTF_RSI_PERIOD,
    MTF_RSI_LONG_MAX,
    MTF_RSI_SHORT_MIN,
    MTF_VOL_MA_PERIOD,
    MTF_VOL_MULT,
    MTF_ATR_SL_MULT,
    MTF_ATR_TP_MULT,
    AUTO_ADX_PERIOD,
    AUTO_ADX_TREND_THRESHOLD,
    AUTO_ADX_STRONG_TREND,
    AUTO_ATR_LOOKBACK,
    AUTO_ATR_HIGH_PERCENTILE,
    AUTO_RSI_EXTREME_LOW,
    AUTO_RSI_EXTREME_HIGH,
    AUTO_STRATEGY_STRONG_TREND,
    AUTO_STRATEGY_TREND,
    AUTO_STRATEGY_RANGING,
    AUTO_STRATEGY_HIGH_VOLATILITY,
    AUTO_STRATEGY_EXTREME,
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

    records = fetch_exchanges(CONSENSUS_EXCHANGES, CONSENSUS_MOMENTUM_MINUTES, parallel=True)
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


# ---------- 多时间框架 MTF：高周期趋势 + 低周期入场 + 成交量/RSI/MACD 实时确认 ----------
def _vol_ma(amounts: List[float], period: int) -> List[float]:
    """成交量（额）简单移动平均。"""
    n = len(amounts)
    out = [0.0] * n
    for i in range(n):
        start = max(0, i - period + 1)
        out[i] = sum(amounts[start : i + 1]) / (i - start + 1)
    return out


def _compute_mtf(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[int, Optional[float], Optional[float], str]:
    """
    多时间框架策略：
    1) 拉取 15 分钟 K 线 → EMA50/200 定大趋势 + MACD 柱确认动量方向
    2) 用传入的 1 分钟 K 线 → EMA9/21 找精确入场
    3) RSI 防追高杀跌；成交量 > 均量倍数确认信号强度
    4) ATR 动态止损止盈
    """
    from exchange import fetch_klines_mtf

    lines: List[str] = ["【MTF 多时间框架】"]

    # ---- 高周期（15 分钟）趋势判定 ----
    htf_raw = fetch_klines_mtf(MTF_HTF_INTERVAL, MTF_HTF_LIMIT)
    if not htf_raw:
        return 0, None, None, "【MTF】高周期 K 线拉取失败"
    htf_o, htf_h, htf_l, htf_c, _ = parse_klines(htf_raw)
    htf_n = len(htf_c)
    need_htf = MTF_HTF_EMA_SLOW + MACD_SLOW + MACD_SIGNAL
    if htf_n < need_htf:
        return 0, None, None, f"【MTF】高周期 K 线不足(需≥{need_htf}，当前{htf_n})"

    htf_ema_f = _ema(htf_c, MTF_HTF_EMA_FAST)
    htf_ema_s = _ema(htf_c, MTF_HTF_EMA_SLOW)
    htf_macd, htf_signal, htf_hist = _macd(htf_c, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
    htf_rsi = _rsi(htf_c, MTF_RSI_PERIOD)

    hi = htf_n - 1
    htf_price = htf_c[hi]
    htf_ef, htf_es = htf_ema_f[hi], htf_ema_s[hi]
    htf_h_val = htf_hist[hi]
    htf_rsi_val = htf_rsi[hi]

    htf_trend = 0
    if htf_ef > htf_es:
        htf_trend = 1
    elif htf_ef < htf_es:
        htf_trend = -1

    htf_macd_confirm = (htf_trend == 1 and htf_h_val > 0) or (htf_trend == -1 and htf_h_val < 0)

    lines.append(
        f"高周期({MTF_HTF_INTERVAL})：收盘={htf_price:.2f} "
        f"EMA{MTF_HTF_EMA_FAST}={htf_ef:.2f} EMA{MTF_HTF_EMA_SLOW}={htf_es:.2f} "
        f"趋势={'多' if htf_trend == 1 else '空' if htf_trend == -1 else '震荡'}"
    )
    lines.append(
        f"  MACD柱={htf_h_val:.4f} {'确认' if htf_macd_confirm else '未确认'}动量 | "
        f"RSI={htf_rsi_val:.1f}" if htf_rsi_val is not None else f"  MACD柱={htf_h_val:.4f} | RSI=N/A"
    )

    if htf_trend == 0:
        lines.append("→ 高周期无明确趋势，不开仓")
        return 0, None, None, "\n".join(lines)

    if not htf_macd_confirm:
        lines.append("→ 高周期 MACD 柱未确认趋势动量，不开仓")
        return 0, None, None, "\n".join(lines)

    # ---- 低周期（1 分钟，使用传入数据）入场信号 ----
    ltf_n = len(closes)
    ltf_need = max(MTF_LTF_EMA_SLOW + 1, MTF_RSI_PERIOD + 1, MTF_VOL_MA_PERIOD + 1, ATR_PERIOD + 1)
    if ltf_n < ltf_need:
        lines.append(f"低周期 K 线不足(需≥{ltf_need}，当前{ltf_n})")
        return 0, None, None, "\n".join(lines)

    ltf_ema_f = _ema(closes, MTF_LTF_EMA_FAST)
    ltf_ema_s = _ema(closes, MTF_LTF_EMA_SLOW)
    ltf_rsi = _rsi(closes, MTF_RSI_PERIOD)
    ltf_atr = _atr(highs, lows, closes, ATR_PERIOD)

    li = ltf_n - 1
    ltf_price = closes[li]
    ltf_ef, ltf_es = ltf_ema_f[li], ltf_ema_s[li]
    ltf_rsi_val = ltf_rsi[li]
    ltf_atr_val = ltf_atr[li]

    ltf_cross_up = ltf_ef > ltf_es and (li == 0 or ltf_ema_f[li - 1] <= ltf_ema_s[li - 1])
    ltf_cross_dn = ltf_ef < ltf_es and (li == 0 or ltf_ema_f[li - 1] >= ltf_ema_s[li - 1])
    ltf_trend_align = (htf_trend == 1 and ltf_ef > ltf_es) or (htf_trend == -1 and ltf_ef < ltf_es)

    lines.append(
        f"低周期({MTF_LTF_INTERVAL})：收盘={ltf_price:.2f} "
        f"EMA{MTF_LTF_EMA_FAST}={ltf_ef:.2f} EMA{MTF_LTF_EMA_SLOW}={ltf_es:.2f} "
        f"ATR={ltf_atr_val:.2f}"
    )

    # ---- 成交量确认 ----
    vol_ok = True
    vol_info = ""
    if ltf_n >= 9 and len(opens) == ltf_n:
        amounts = [abs(closes[j] - opens[j]) * (highs[j] - lows[j] + 1) for j in range(ltf_n)]
        vol_series = _vol_ma(amounts, MTF_VOL_MA_PERIOD)
        cur_vol = amounts[li]
        avg_vol = vol_series[li]
        vol_ok = cur_vol >= avg_vol * MTF_VOL_MULT
        vol_info = f"成交活跃度={cur_vol:.2f} 均值={avg_vol:.2f} ×{MTF_VOL_MULT} {'✓' if vol_ok else '✗'}"
    lines.append(f"  {vol_info}" if vol_info else "  成交量数据不足，跳过量能过滤")

    # ---- RSI 过滤 ----
    rsi_ok = True
    if ltf_rsi_val is not None:
        if htf_trend == 1 and ltf_rsi_val > MTF_RSI_LONG_MAX:
            rsi_ok = False
        if htf_trend == -1 and ltf_rsi_val < MTF_RSI_SHORT_MIN:
            rsi_ok = False
        lines.append(
            f"  RSI({MTF_RSI_PERIOD})={ltf_rsi_val:.1f} "
            f"{'✓' if rsi_ok else '✗ 过滤'}"
        )
    else:
        lines.append("  RSI=N/A")

    # ---- 综合判定 ----
    has_entry_signal = ltf_cross_up if htf_trend == 1 else ltf_cross_dn if htf_trend == -1 else False
    trend_aligned = ltf_trend_align

    if has_entry_signal:
        lines.append(f"  入场信号：{'金叉' if htf_trend == 1 else '死叉'}交叉 ✓")
    elif trend_aligned:
        lines.append(f"  无交叉但低周期趋势同向（顺势入场）")
        has_entry_signal = True
    else:
        lines.append("  低周期未与高周期趋势对齐，不开仓")
        return 0, None, None, "\n".join(lines)

    if not rsi_ok:
        lines.append("→ RSI 过滤，不开仓")
        return 0, None, None, "\n".join(lines)

    if not vol_ok:
        lines.append("→ 成交量不足，不开仓")
        return 0, None, None, "\n".join(lines)

    # ---- 动态止损止盈（基于 ATR）----
    if ltf_atr_val > 0:
        sl_dist = ltf_atr_val * MTF_ATR_SL_MULT
        tp_dist = ltf_atr_val * MTF_ATR_TP_MULT
    else:
        sl_dist = ltf_price * STOP_LOSS_RATIO
        tp_dist = ltf_price * TAKE_PROFIT_RATIO

    if htf_trend == 1:
        sl = ltf_price - sl_dist
        tp = ltf_price + tp_dist
        lines.append(f"→ 做多 | SL={sl:.2f}(ATR×{MTF_ATR_SL_MULT}) TP={tp:.2f}(ATR×{MTF_ATR_TP_MULT})")
        return 1, sl, tp, "\n".join(lines)
    else:
        sl = ltf_price + sl_dist
        tp = ltf_price - tp_dist
        lines.append(f"→ 做空 | SL={sl:.2f}(ATR×{MTF_ATR_SL_MULT}) TP={tp:.2f}(ATR×{MTF_ATR_TP_MULT})")
        return -1, sl, tp, "\n".join(lines)


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


# ---------- 自动策略选择 auto：实时市场分类 → 自动分发最佳子策略 ----------
def _adx(
    highs: List[float], lows: List[float], closes: List[float], period: int
) -> List[float]:
    """Average Directional Index，衡量趋势强度，不区分方向。"""
    n = len(closes)
    adx_out = [0.0] * n
    if n < period * 2:
        return adx_out

    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    tr = [0.0] * n
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        dn = lows[i - 1] - lows[i]
        plus_dm[i] = up if (up > dn and up > 0) else 0.0
        minus_dm[i] = dn if (dn > up and dn > 0) else 0.0
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    smoothed_tr = [0.0] * n
    smoothed_plus = [0.0] * n
    smoothed_minus = [0.0] * n
    smoothed_tr[period] = sum(tr[1 : period + 1])
    smoothed_plus[period] = sum(plus_dm[1 : period + 1])
    smoothed_minus[period] = sum(minus_dm[1 : period + 1])
    for i in range(period + 1, n):
        smoothed_tr[i] = smoothed_tr[i - 1] - smoothed_tr[i - 1] / period + tr[i]
        smoothed_plus[i] = smoothed_plus[i - 1] - smoothed_plus[i - 1] / period + plus_dm[i]
        smoothed_minus[i] = smoothed_minus[i - 1] - smoothed_minus[i - 1] / period + minus_dm[i]

    dx = [0.0] * n
    for i in range(period, n):
        if smoothed_tr[i] == 0:
            continue
        di_plus = 100.0 * smoothed_plus[i] / smoothed_tr[i]
        di_minus = 100.0 * smoothed_minus[i] / smoothed_tr[i]
        di_sum = di_plus + di_minus
        dx[i] = 100.0 * abs(di_plus - di_minus) / di_sum if di_sum > 0 else 0.0

    first_adx_idx = period * 2 - 1
    if first_adx_idx < n:
        adx_out[first_adx_idx] = sum(dx[period : first_adx_idx + 1]) / period
        for i in range(first_adx_idx + 1, n):
            adx_out[i] = (adx_out[i - 1] * (period - 1) + dx[i]) / period

    return adx_out


def _classify_market(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[str, str]:
    """
    分析当前市场状态，返回 (regime, detail_text)。
    regime: "strong_trend" | "trend" | "ranging" | "high_volatility" | "extreme"
    """
    n = len(closes)
    detail: List[str] = ["【自动策略·市场诊断】"]

    adx_val = 0.0
    if n >= AUTO_ADX_PERIOD * 2:
        adx_series = _adx(highs, lows, closes, AUTO_ADX_PERIOD)
        adx_val = adx_series[n - 1]
    detail.append(f"ADX({AUTO_ADX_PERIOD})={adx_val:.1f}")

    atr_series = _atr(highs, lows, closes, ATR_PERIOD)
    atr_val = atr_series[n - 1] if n > ATR_PERIOD else 0.0
    price = closes[n - 1]
    atr_pct = (atr_val / price * 100) if price > 0 else 0.0

    lookback = min(AUTO_ATR_LOOKBACK, n)
    atr_window = [atr_series[n - 1 - j] for j in range(lookback) if atr_series[n - 1 - j] > 0]
    atr_percentile = 50.0
    if atr_window and atr_val > 0:
        below = sum(1 for v in atr_window if v <= atr_val)
        atr_percentile = below / len(atr_window) * 100.0
    detail.append(f"ATR={atr_val:.2f}({atr_pct:.3f}%) 百分位={atr_percentile:.0f}%")

    rsi_series = _rsi(closes, RSI_PERIOD)
    rsi_val = rsi_series[n - 1] if n > RSI_PERIOD and rsi_series[n - 1] is not None else 50.0
    detail.append(f"RSI({RSI_PERIOD})={rsi_val:.1f}")

    if rsi_val is not None and (rsi_val < AUTO_RSI_EXTREME_LOW or rsi_val > AUTO_RSI_EXTREME_HIGH):
        regime = "extreme"
        detail.append(f"→ 极端行情 (RSI {'超卖' if rsi_val < AUTO_RSI_EXTREME_LOW else '超买'})")
    elif adx_val >= AUTO_ADX_STRONG_TREND:
        regime = "strong_trend"
        detail.append(f"→ 强趋势 (ADX>{AUTO_ADX_STRONG_TREND})")
    elif adx_val >= AUTO_ADX_TREND_THRESHOLD:
        if atr_percentile >= AUTO_ATR_HIGH_PERCENTILE:
            regime = "high_volatility"
            detail.append(f"→ 趋势+高波动 (ADX>{AUTO_ADX_TREND_THRESHOLD}, ATR百分位>{AUTO_ATR_HIGH_PERCENTILE})")
        else:
            regime = "trend"
            detail.append(f"→ 普通趋势 (ADX>{AUTO_ADX_TREND_THRESHOLD})")
    else:
        if atr_percentile >= AUTO_ATR_HIGH_PERCENTILE:
            regime = "high_volatility"
            detail.append(f"→ 高波动震荡 (ADX<{AUTO_ADX_TREND_THRESHOLD}, ATR百分位>{AUTO_ATR_HIGH_PERCENTILE})")
        else:
            regime = "ranging"
            detail.append(f"→ 震荡 (ADX<{AUTO_ADX_TREND_THRESHOLD})")

    return regime, "\n".join(detail)


_REGIME_TO_STRATEGY = {
    "strong_trend": "AUTO_STRATEGY_STRONG_TREND",
    "trend": "AUTO_STRATEGY_TREND",
    "ranging": "AUTO_STRATEGY_RANGING",
    "high_volatility": "AUTO_STRATEGY_HIGH_VOLATILITY",
    "extreme": "AUTO_STRATEGY_EXTREME",
}


def _compute_auto(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[int, Optional[float], Optional[float], str]:
    """自动策略：先诊断市场状态，再分发到最匹配的子策略。"""
    import config as _cfg

    n = len(closes)
    if n < AUTO_ADX_PERIOD * 2 + ATR_PERIOD:
        return 0, None, None, f"【Auto】K线不足(需≥{AUTO_ADX_PERIOD * 2 + ATR_PERIOD}，当前{n})"

    regime, diag_text = _classify_market(opens, highs, lows, closes)

    config_key = _REGIME_TO_STRATEGY[regime]
    chosen = getattr(_cfg, config_key, "composite")

    diag_text += f"\n选用策略: {chosen}"

    d, sl, tp, sub_rationale = _dispatch_strategy(chosen, opens, highs, lows, closes)

    full_rationale = diag_text + "\n---\n" + sub_rationale
    return d, sl, tp, full_rationale


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
    if s == "mtf":
        return _compute_mtf(opens, highs, lows, closes)
    return _compute_ema_cross(highs, lows, closes)


def _calculate_signal_quality(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
    direction: int,
) -> Tuple[float, Dict[str, float]]:
    """
    计算信号质量评分 (0-1)，综合考虑：
    1. 趋势强度 (ADX)
    2. 成交量确认
    3. 价格动量
    4. 波动率适中性
    返回 (总分, 各维度得分)。分项之和即总分，便于事后标定权重与阈值。
    """
    parts: Dict[str, float] = {
        "adx": 0.0,
        "volume": 0.0,
        "momentum": 0.0,
        "volatility": 0.0,
        "fallback": 0.0,
    }
    if direction == 0:
        return 0.0, parts

    n = len(closes)
    if n < 50:
        parts["fallback"] = 0.5
        return 0.5, parts

    # 1. ADX 趋势强度 (0-0.3分)
    if n >= AUTO_ADX_PERIOD * 2:
        adx_series = _adx(highs, lows, closes, AUTO_ADX_PERIOD)
        adx_val = adx_series[n - 1]
        if adx_val >= 40:
            parts["adx"] = 0.3
        elif adx_val >= 25:
            parts["adx"] = 0.2
        elif adx_val >= 20:
            parts["adx"] = 0.1

    # 2. 成交量确认 (0-0.25分)
    if len(opens) == n:
        amounts = [abs(closes[j] - opens[j]) * (highs[j] - lows[j] + 1) for j in range(n)]
        if n >= 20:
            recent_vol = sum(amounts[-5:]) / 5
            avg_vol = sum(amounts[-20:]) / 20
            if recent_vol > avg_vol * 1.5:
                parts["volume"] = 0.25
            elif recent_vol > avg_vol * 1.2:
                parts["volume"] = 0.15
            elif recent_vol > avg_vol:
                parts["volume"] = 0.05

    # 3. 价格动量 (0-0.25分)
    if n >= 10:
        momentum = (closes[-1] - closes[-10]) / closes[-10] if closes[-10] > 0 else 0
        if direction == 1 and momentum > 0.02:
            parts["momentum"] = 0.25
        elif direction == 1 and momentum > 0.01:
            parts["momentum"] = 0.15
        elif direction == -1 and momentum < -0.02:
            parts["momentum"] = 0.25
        elif direction == -1 and momentum < -0.01:
            parts["momentum"] = 0.15

    # 4. 波动率适中 (0-0.2分) - 太高或太低都不好
    atr_series = _atr(highs, lows, closes, ATR_PERIOD)
    atr_val = atr_series[n - 1] if n > ATR_PERIOD else 0
    price = closes[n - 1]
    atr_pct = (atr_val / price * 100) if price > 0 else 0
    if 0.5 <= atr_pct <= 3.0:
        parts["volatility"] = 0.2
    elif 0.3 <= atr_pct <= 4.0:
        parts["volatility"] = 0.1

    return min(sum(parts.values()), 1.0), parts


def _check_trend_filter(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    direction: int,
) -> Tuple[bool, str]:
    """
    趋势过滤：防止逆势交易和假突破
    返回 (是否通过, 说明)
    """
    n = len(closes)
    if n < 50 or direction == 0:
        return True, ""
    
    # 检查长期趋势 (EMA 50)
    ema_50 = _ema(closes, 50)
    price = closes[-1]
    
    # 多头信号但价格远低于 EMA50
    if direction == 1 and price < ema_50[-1] * 0.98:
        return False, f"价格 {price:.2f} 低于 EMA50 {ema_50[-1]:.2f}，逆势做多风险高"
    
    # 空头信号但价格远高于 EMA50
    if direction == -1 and price > ema_50[-1] * 1.02:
        return False, f"价格 {price:.2f} 高于 EMA50 {ema_50[-1]:.2f}，逆势做空风险高"
    
    # 检查假突破：价格刚突破但立即回落
    if n >= 3:
        if direction == 1:
            # 检查是否刚突破阻力位但回落
            recent_high = max(highs[-10:-1]) if n >= 10 else max(highs[:-1])
            if closes[-1] > recent_high and closes[-1] < highs[-1] * 0.998:
                return False, "疑似假突破：突破后立即回落"
        elif direction == -1:
            # 检查是否刚跌破支撑位但反弹
            recent_low = min(lows[-10:-1]) if n >= 10 else min(lows[:-1])
            if closes[-1] < recent_low and closes[-1] > lows[-1] * 1.002:
                return False, "疑似假突破：跌破后立即反弹"
    
    return True, "趋势过滤通过"


def compute_signal(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[int, Optional[float], Optional[float], str, Optional[float], Dict[str, float]]:
    """
    返回 (direction, stop_loss_price, take_profit_price, rationale, signal_quality, quality_parts)。
    direction: 1=多, -1=空, 0=无。
    signal_quality: 0-1 信号质量评分；quality_parts: 各维度得分明细
    STRATEGY: auto | hf | ema_cross | macd | rsi | composite | consensus | mtf | freqtrade
    FREQTRADE_CONFIRM=True 时主策略须与 freqtrade 风格同向才出信号。
    """
    s = (STRATEGY or "ema_cross").strip().lower()
    if s == "freqtrade":
        bd, bsl, btp, br = compute_freqtrade_signal(opens, highs, lows, closes)
        quality, quality_parts = _calculate_signal_quality(opens, highs, lows, closes, bd)
        return bd, bsl, btp, br, quality, quality_parts

    if s == "auto":
        bd, bsl, btp, br = _compute_auto(opens, highs, lows, closes)
    else:
        bd, bsl, btp, br = _dispatch_strategy(s, opens, highs, lows, closes)

    # 趋势过滤
    if bd != 0:
        trend_ok, trend_msg = _check_trend_filter(highs, lows, closes, bd)
        if not trend_ok:
            quality, quality_parts = _calculate_signal_quality(opens, highs, lows, closes, 0)
            return 0, None, None, br + f"\n\n【趋势过滤】{trend_msg}", quality, quality_parts
        br += f"\n【趋势过滤】{trend_msg}"

    # 计算信号质量
    quality, quality_parts = _calculate_signal_quality(opens, highs, lows, closes, bd)

    # 低质量信号过滤
    if bd != 0 and quality < 0.3:
        return (
            0,
            None,
            None,
            br + f"\n\n【信号质量过滤】质量评分 {quality:.2f} < 0.3，信号太弱",
            quality,
            quality_parts,
        )

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
                quality,
                quality_parts,
            )
        if bd in (1, -1) and fd == bd:
            sl = bsl if bsl is not None else fsl
            tp = btp if btp is not None else ftp
            return (
                bd,
                sl,
                tp,
                "【主策略 + Freqtrade 一致】\n" + br + "\n---\n" + fr,
                quality,
                quality_parts,
            )
        return (
            0,
            None,
            None,
            "【无开仓信号】\n主策略:\n" + br + "\n---\nFreqtrade:\n" + fr,
            quality,
            quality_parts,
        )

    return bd, bsl, btp, br, quality, quality_parts


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
