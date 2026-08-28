# -*- coding: utf-8 -*-
"""
开仓 / 反手前的可选门禁（信号质量、多所 global_pressure 与方向一致、新闻情绪）。
依据 decision_journal 复盘：边际 signal_quality（≈0.30–0.35）成交易连亏；pressure 与方向一致时样本更合理。
新增：decision_layer 新闻情绪评分门禁。
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


def _check_decision_layer_gate(direction: int) -> Tuple[bool, str]:
    """
    Decision Layer 新闻情绪门禁。
    做多时若情绪过于看空则阻止，做空时若情绪过于看多则阻止。
    """
    if not _b("DECISION_LAYER_GATE_ENABLED", False):
        return True, ""

    try:
        from decision_layer.scorer import get_current_score
    except ImportError:
        return True, ""

    score = get_current_score()
    if score.stale:
        return True, ""

    min_conf = _f("DECISION_LAYER_GATE_MIN_CONFIDENCE", 0.3)
    if score.confidence < min_conf:
        return True, ""

    if direction == 1:
        long_min = _f("DECISION_LAYER_GATE_LONG_MIN_SCORE", -0.4)
        if score.score < long_min:
            return False, (
                f"新闻情绪偏空({score.score:+.3f} < {long_min:+.2f})，"
                f"阻止做多 [置信度{score.confidence:.2f} 多{score.bullish_count}/空{score.bearish_count}]"
            )
    elif direction == -1:
        short_max = _f("DECISION_LAYER_GATE_SHORT_MAX_SCORE", 0.4)
        if score.score > short_max:
            return False, (
                f"新闻情绪偏多({score.score:+.3f} > {short_max:+.2f})，"
                f"阻止做空 [置信度{score.confidence:.2f} 多{score.bullish_count}/空{score.bearish_count}]"
            )

    return True, ""


def _venue_agrees(direction: int, imb: float, min_imb: float) -> bool:
    if direction == 1:
        return imb >= min_imb
    if direction == -1:
        return imb <= -min_imb
    return False


def _check_book_gate(direction: int, order_book: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
    if not _b("ENTRY_REQUIRE_BOOK_ALIGN", False):
        return True, ""
    fail_open = _b("ENTRY_BOOK_FAIL_OPEN", True)
    min_imb = _f("ENTRY_BOOK_MIN_IMBALANCE", 0.08)
    if not isinstance(order_book, dict):
        return (True, "") if fail_open else (False, "order_book_missing")

    venues = order_book.get("venues")
    if isinstance(venues, list) and venues:
        agrees = 0
        n = 0
        for v in venues:
            if not isinstance(v, dict) or v.get("imbalance") is None:
                continue
            n += 1
            if _venue_agrees(direction, float(v["imbalance"]), min_imb):
                agrees += 1
        if n == 0:
            return (True, "") if fail_open else (False, "order_book_missing")
        need = 2 if n >= 2 else 1
        if agrees < need:
            return False, f"盘口未多数同向 {agrees}/{n} < {need}"
        return True, ""

    if order_book.get("imbalance") is None:
        return (True, "") if fail_open else (False, "order_book_missing")
    imb = float(order_book["imbalance"])
    if not _venue_agrees(direction, imb, min_imb):
        side = "偏空" if direction == 1 else "偏多"
        return False, f"盘口{side} imbalance={imb:.3f}"
    return True, ""


def passes_entry_gates(
    direction: int,
    signal_quality: Optional[float],
    pos_side: Optional[str],
    cross_exchange: Optional[Dict[str, Any]],
    order_book: Optional[Dict[str, Any]] = None,
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

    # Decision Layer 新闻情绪门禁
    dl_ok, dl_reason = _check_decision_layer_gate(direction)
    if not dl_ok:
        return False, dl_reason

    book_ok, book_reason = _check_book_gate(direction, order_book)
    if not book_ok:
        return False, book_reason

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
    # 弱压力当噪声放行；只拦明显反向（旧逻辑要求必须同向超过 0.0006，5m 上几乎开不成）
    if direction * gp_f >= 0:
        return True, ""
    if abs(gp_f) < min_align:
        return True, ""
    return False, (
        f"pressure 明显反向: direction={direction} global_pressure={gp_f:.6f} "
        f"|gp| >= {min_align}"
    )


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
