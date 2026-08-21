# -*- coding: utf-8 -*-
"""
每笔交易一条的生命周期日志（logs/trades.jsonl），供事后归因与参数标定。
与 decision_journal 的逐轮快照分离：体积小、可长期保留；写入失败不影响交易。

mfe/mae（最大有利/不利偏移）按主循环轮询频率采样标价，
分辨率受轮询间隔限制，不含轮询间隙内的穿刺，记录 excursion_samples 以便判断。
"""
import json
import logging
import os
import time
from typing import Any, Dict, Optional

import config_bootstrap  # noqa: F401

import config as _cfg

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    return bool(getattr(_cfg, "TRADE_JOURNAL_ENABLED", True))


def _path() -> str:
    return str(getattr(_cfg, "TRADE_JOURNAL_PATH", "logs/trades.jsonl") or "logs/trades.jsonl")


def _append(record: Dict[str, Any]) -> None:
    path = _path()
    try:
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception as e:
        logger.warning("交易日志写入失败 %s: %s", path, e)


class TradeRecorder:
    """open_trade() 记录入场上下文 → update() 每轮刷新浮动极值 → close_trade() 落盘。"""

    def __init__(self) -> None:
        self._entry: Optional[Dict[str, Any]] = None
        self._best: float = 0.0
        self._worst: float = 0.0
        self._samples: int = 0
        self._fees_at_entry: float = 0.0
        self._funding_at_entry: float = 0.0
        self._seq: int = 0

    def open_trade(
        self,
        side: str,
        price: float,
        size: float,
        sl: Optional[float],
        tp: Optional[float],
        equity: float,
        context: Optional[Dict[str, Any]] = None,
        fees_paid: float = 0.0,
        funding_cashflow: float = 0.0,
    ) -> None:
        if price <= 0:
            self._entry = None
            return
        self._seq += 1
        now = time.time()
        entry: Dict[str, Any] = {
            "trade_id": f"{int(now)}-{self._seq}",
            "side": side,
            "entry_ts": round(now, 3),
            "entry_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "entry_price": round(price, 4),
            "size": round(size, 8),
            "notional": round(size * price, 4),
            "stop_loss": None if sl is None else round(sl, 4),
            "take_profit": None if tp is None else round(tp, 4),
            "equity_at_entry": round(equity, 4),
        }
        if context:
            entry.update(context)
        self._entry = entry
        self._best = price
        self._worst = price
        self._samples = 1
        self._fees_at_entry = fees_paid
        self._funding_at_entry = funding_cashflow

    def update(self, price: float) -> None:
        """主循环每轮调用；仅在持仓期间累积浮动极值。"""
        if self._entry is None or price <= 0:
            return
        self._best = max(self._best, price)
        self._worst = min(self._worst, price)
        self._samples += 1

    def close_trade(
        self,
        price: float,
        reason: str,
        pnl: float,
        equity_after: float,
        fees_paid: float = 0.0,
        funding_cashflow: float = 0.0,
    ) -> None:
        entry = self._entry
        self._entry = None
        if entry is None or not _enabled():
            return

        now = time.time()
        entry_px = float(entry["entry_price"])
        long_side = entry["side"] == "LONG"
        if long_side:
            mfe = (self._best - entry_px) / entry_px
            mae = (self._worst - entry_px) / entry_px
        else:
            mfe = (entry_px - self._worst) / entry_px
            mae = (entry_px - self._best) / entry_px
        move = (price - entry_px) / entry_px * (1.0 if long_side else -1.0)
        equity_at_entry = float(entry.get("equity_at_entry") or 0.0)

        record = dict(entry)
        record.update(
            {
                "exit_ts": round(now, 3),
                "exit_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                "exit_price": round(price, 4),
                "exit_reason": reason,
                "hold_sec": int(now - float(entry["entry_ts"])),
                "realized_pnl": round(pnl, 6),
                "return_on_equity": round(pnl / equity_at_entry, 8) if equity_at_entry > 0 else None,
                "price_move_ratio": round(move, 8),
                "fees": round(fees_paid - self._fees_at_entry, 6),
                "funding": round(funding_cashflow - self._funding_at_entry, 6),
                "equity_after": round(equity_after, 4),
                "mfe_ratio": round(mfe, 8),
                "mae_ratio": round(mae, 8),
                "excursion_samples": self._samples,
            }
        )
        _append(record)
