# -*- coding: utf-8 -*-
"""
使用与 freqtrade 相同的指标库 technical.qtpylib（freqtrade 依赖的 QTPyLib）生成交易倾向与可读依据。
不强制安装完整 freqtrade 包，避免与系统 Python 依赖冲突。
"""
from typing import List, Tuple, Optional

import config_bootstrap  # noqa: F401

import pandas as pd

try:
    import technical.qtpylib as qtpylib
except ImportError:  # pragma: no cover
    qtpylib = None  # type: ignore

from config import (
    FT_EMA_SHORT,
    FT_EMA_LONG,
    FT_MACD_FAST,
    FT_MACD_SLOW,
    FT_MACD_SIGNAL,
    FT_USE_MACD_FILTER,
    FT_REQUIRE_HIST_MOMENTUM,
    FT_RSI_PERIOD,
    FT_RSI_LONG_MAX,
    FT_RSI_SHORT_MIN,
    STOP_LOSS_RATIO,
    TAKE_PROFIT_RATIO,
)


def _sl_tp_long(price: float) -> Tuple[float, float]:
    return price * (1 - STOP_LOSS_RATIO), price * (1 + TAKE_PROFIT_RATIO)


def _sl_tp_short(price: float) -> Tuple[float, float]:
    return price * (1 + STOP_LOSS_RATIO), price * (1 - TAKE_PROFIT_RATIO)


def compute_freqtrade_signal(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[int, Optional[float], Optional[float], str]:
    """
    EMA(快/慢) 金叉死叉 + optional MACD 柱方向 + RSI 过滤。
    返回 (direction, sl, tp, 决策说明)。
    """
    n = len(closes)
    need = max(FT_EMA_LONG + 2, FT_MACD_SLOW + FT_MACD_SIGNAL + 2, FT_RSI_PERIOD + 2)
    if n < need:
        return 0, None, None, f"【Freqtrade风格】K线不足(需≥{need}根，当前{n})"

    if qtpylib is None:
        return 0, None, None, "【Freqtrade风格】未安装 technical 库，请 pip install -r requirements.txt"

    df = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
        }
    )
    df["ema_fast"] = df["close"].ewm(span=FT_EMA_SHORT, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=FT_EMA_LONG, adjust=False).mean()

    macd_df = qtpylib.macd(df["close"], fast=FT_MACD_FAST, slow=FT_MACD_SLOW, smooth=FT_MACD_SIGNAL)
    df["macd_hist"] = macd_df["histogram"]
    df["rsi"] = qtpylib.rsi(df["close"], window=FT_RSI_PERIOD)

    i = n - 1
    price = float(closes[i])
    ef, es = float(df["ema_fast"].iloc[i]), float(df["ema_slow"].iloc[i])
    ef1, es1 = float(df["ema_fast"].iloc[i - 1]), float(df["ema_slow"].iloc[i - 1])
    hist = float(df["macd_hist"].iloc[i])
    hist1 = float(df["macd_hist"].iloc[i - 1])
    rsi_v = float(df["rsi"].iloc[i])

    ema_bull_cross = ef > es and ef1 <= es1
    ema_bear_cross = ef < es and ef1 >= es1

    lines = [
        "【Freqtrade风格·technical.qtpylib】",
        f"收盘 {price:.2f} | EMA{FT_EMA_SHORT}={ef:.2f} EMA{FT_EMA_LONG}={es:.2f}",
        f"MACD柱 h={hist:.4f} (前根 {hist1:.4f}) | RSI({FT_RSI_PERIOD})={rsi_v:.1f}",
    ]

    if ema_bull_cross:
        if rsi_v > FT_RSI_LONG_MAX:
            lines.append(f"EMA金叉但 RSI>{FT_RSI_LONG_MAX}，过滤做多")
            return 0, None, None, "\n".join(lines)
        if FT_USE_MACD_FILTER:
            if not ((hist > 0 and hist1 <= 0) or hist > 0):
                lines.append("EMA金叉但 MACD 柱未配合多头(需柱>0或刚上穿)，过滤")
                return 0, None, None, "\n".join(lines)
        if FT_REQUIRE_HIST_MOMENTUM and hist <= hist1:
            lines.append("MACD 柱未走强(h≤h[-1])，过滤弱金叉")
            return 0, None, None, "\n".join(lines)
        sl, tp = _sl_tp_long(price)
        lines.append("结论: 做多 (EMA金叉" + ("+MACD确认" if FT_USE_MACD_FILTER else "") + ")")
        return 1, sl, tp, "\n".join(lines)

    if ema_bear_cross:
        if rsi_v < FT_RSI_SHORT_MIN:
            lines.append(f"EMA死叉但 RSI<{FT_RSI_SHORT_MIN}，过滤做空")
            return 0, None, None, "\n".join(lines)
        if FT_USE_MACD_FILTER:
            if not ((hist < 0 and hist1 >= 0) or hist < 0):
                lines.append("EMA死叉但 MACD 柱未配合空头(需柱<0或刚下穿)，过滤")
                return 0, None, None, "\n".join(lines)
        if FT_REQUIRE_HIST_MOMENTUM and hist >= hist1:
            lines.append("MACD 柱未走弱(h≥h[-1])，过滤弱死叉")
            return 0, None, None, "\n".join(lines)
        sl, tp = _sl_tp_short(price)
        lines.append("结论: 做空 (EMA死叉" + ("+MACD确认" if FT_USE_MACD_FILTER else "") + ")")
        return -1, sl, tp, "\n".join(lines)

    lines.append("结论: 无信号 (等待 EMA 交叉)")
    return 0, None, None, "\n".join(lines)


def freqtrade_trend_align(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[int, str]:
    """
    短线确认：不要求刚交叉，只要 EMA 方向与 MACD 柱同向。
    返回 (direction, 说明)。1=偏多, -1=偏空, 0=不一致。
    """
    n = len(closes)
    need = max(FT_EMA_LONG + 2, FT_MACD_SLOW + FT_MACD_SIGNAL + 2)
    if n < need:
        return 0, f"【Freqtrade同向】K线不足(需≥{need}根，当前{n})"
    if qtpylib is None:
        return 0, "【Freqtrade同向】未安装 technical 库"
    df = pd.DataFrame({"close": closes})
    ema_f = float(df["close"].ewm(span=FT_EMA_SHORT, adjust=False).mean().iloc[-1])
    ema_s = float(df["close"].ewm(span=FT_EMA_LONG, adjust=False).mean().iloc[-1])
    macd_df = qtpylib.macd(df["close"], fast=FT_MACD_FAST, slow=FT_MACD_SLOW, smooth=FT_MACD_SIGNAL)
    hist = float(macd_df["histogram"].iloc[-1])
    ema_dir = 1 if ema_f > ema_s else -1 if ema_f < ema_s else 0
    macd_dir = 1 if hist > 0 else -1 if hist < 0 else 0
    snap = f"【Freqtrade同向】EMA{FT_EMA_SHORT}={ema_f:.2f} EMA{FT_EMA_LONG}={ema_s:.2f} MACD柱={hist:.4f}"
    if ema_dir != 0 and ema_dir == macd_dir:
        return ema_dir, snap + (" → 偏多" if ema_dir == 1 else " → 偏空")
    return 0, snap + " → EMA/MACD 未同向"


def freqtrade_direction_only(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> int:
    """仅返回方向 1/-1/0，供与主策略共识。"""
    d, _, _, _ = compute_freqtrade_signal(opens, highs, lows, closes)
    return d
