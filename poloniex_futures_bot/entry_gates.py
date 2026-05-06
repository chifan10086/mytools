# -*- coding: utf-8 -*-
"""
开仓 / 反手前的可选门禁（信号质量、多所 global_pressure 与方向一致）。
依据 decision_journal 复盘：边际 signal_quality（≈0.30–0.35）成交易连亏；pressure 与方向一致时样本更合理。
"""
from typing import Any, Dict, Optional, Tuple

import config_bootstrap  # noqa: F401

import config as cfg


def _f(name: str, default: float) -> float:
    try:
        return float(getattr(cfg, name, default))
    except (TypeError, ValueError):
        return default


def _b(name: str, default: bool) -> bool:
    v = getattr(cfg, name, default)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)


def _i(name: str, default: int) -> int:
    try:
        return int(getattr(cfg, name, default))
    except (TypeError, ValueError):
        return default


def passes_entry_gates(
    direction: int,
    signal_quality: Optional[float],
    pos_side: Optional[str],
    cross_exchange: Optional[Dict[str, Any]],
) -> Tuple[bool, str]:
    """
    direction: -1 做空 / 1 做多 / 0 无信号
    pos_side: None | LONG | SHORT — 用于反手时使用更严的 MIN_SIGNAL_QUALITY_REVERSE
    """
    if direction == 0:
        return True, ""

    min_sq = _f("ENTRY_MIN_SIGNAL_QUALITY", 0.0)
    min_sq_rev = _f("ENTRY_MIN_SIGNAL_QUALITY_REVERSE", 0.0)
    if min_sq_rev <= 0:
        min_sq_rev = min_sq

    is_reverse = bool(pos_side) and (
        (pos_side == "LONG" and direction == -1) or (pos_side == "SHORT" and direction == 1)
    )
    thresh = min_sq_rev if is_reverse else min_sq

    sq = float(signal_quality) if signal_quality is not None else 0.0
    if thresh > 0 and sq + 1e-12 < thresh:
        return False, f"signal_quality {sq:.2f} < {thresh:.2f}"

    if not _b("ENTRY_REQUIRE_CROSS_PRESSURE_ALIGN", False):
        return True, ""

    fail_open = _b("ENTRY_CROSS_PRESSURE_FAIL_OPEN", True)
    min_align = _f("ENTRY_CROSS_PRESSURE_MIN_ALIGN", 0.0)
    min_ex_ok = _i("ENTRY_CROSS_MIN_EXCHANGES_OK", 4)

    if not isinstance(cross_exchange, dict):
        return (True, "") if fail_open else (False, "no_cross_exchange_snapshot")

    gp = cross_exchange.get("global_pressure")
    ex_ok = cross_exchange.get("exchanges_ok") or []
    n_ok = len(ex_ok) if isinstance(ex_ok, list) else 0

    if gp is None:
        return (True, "") if fail_open else (False, "global_pressure_missing")

    if n_ok < min_ex_ok:
        return (True, "") if fail_open else (False, f"exchanges_ok {n_ok} < {min_ex_ok}")

    gp_f = float(gp)
    # 做多需要 pressure 为正且足够大；做空为负且 |gp| 足够大
    aligned = direction * gp_f >= min_align
    if not aligned:
        return False, f"pressure 未同向: direction={direction} global_pressure={gp_f:.6f} 需要 direction*gp >= {min_align}"

    return True, ""


def will_open_or_reverse(direction: int, pos_side: Optional[str]) -> bool:
    if direction == 0:
        return False
    if pos_side == "LONG" and direction == -1:
        return True
    if pos_side == "SHORT" and direction == 1:
        return True
    if not pos_side and direction in (1, -1):
        return True
    return False
