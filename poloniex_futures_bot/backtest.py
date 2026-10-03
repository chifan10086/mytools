# -*- coding: utf-8 -*-
"""
用币安 BTC 永续历史 K 线回放「当前 config」：strategy.compute_signal + main.py 的离场与风控逻辑。
改参数前后各跑一次，看样本内/样本外是否同向，再决定上线。

    python3 backtest.py                       # 最近 120 天，2026-09-01 前后分成样本内/外
    python3 backtest.py --days 90 --split 2026-08-15
    python3 backtest.py --exchanges binance,bybit,okx,bitget,gate   # 同一配置在多家 K 线上各跑一遍，看结论是否一致
    python3 backtest.py --consensus           # 按 config.KLINE_SOURCES 合成共识 K 线回放（与实盘数据路径一致）

约定：信号只在已收盘 K 线上计算（同 SIGNAL_ON_CLOSED_BARS=True），在该根收盘价成交；
止损/止盈按下一根起的高低点判定，同根同时触及按止损算（偏保守）；浮盈保护与最大持仓按收盘价判定；
手续费双边 Taker，不计资金费；盘口 / 多所压力 / 新闻门禁无法回放，按放行处理。
"""
import argparse
import collections
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import config_bootstrap  # noqa: F401
import config as cfg
import risk_manager
from entry_gates import passes_entry_gates, will_open_or_reverse
from exchange import position_size_by_risk
from multi_exchange import _INTERVAL_TO_TF, _SYMBOL, _get_exchange, merge_consensus_klines
from strategy import compute_signal

_TF_SEC = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400}


class _Clock:
    """让 RiskManager 用回放时间而不是墙上时钟。"""

    t = 0.0

    def time(self) -> float:
        return self.t


def fetch_history(days: int, exchange: str = "binance") -> List[List[float]]:
    ex = _get_exchange(exchange)
    if ex is None:
        sys.exit(f"ccxt 不支持交易所 {exchange}")
    tf = _INTERVAL_TO_TF.get(str(cfg.KLINE_INTERVAL).upper(), "5m")
    step = _TF_SEC[tf] * 1000
    since = int((time.time() - days * 86400) * 1000)
    out: List[List[float]] = []
    while True:
        rows = ex.fetch_ohlcv(_SYMBOL, timeframe=tf, since=since, limit=1000)
        if not rows:
            break
        out.extend(rows)
        if len(rows) < 2 or rows[-1][0] + step > time.time() * 1000 or rows[-1][0] + step <= since:
            break
        since = rows[-1][0] + step
    seen = set()
    uniq = [r for r in out if not (r[0] in seen or seen.add(r[0]))]
    # 最后一根通常未收盘，丢掉
    if uniq and uniq[-1][0] + step > time.time() * 1000:
        uniq.pop()
    return uniq


def run(rows: List[List[float]], equity0: float) -> Tuple[float, List[Dict]]:
    ts = [r[0] / 1000.0 for r in rows]
    o = [float(r[1]) for r in rows]
    h = [float(r[2]) for r in rows]
    l = [float(r[3]) for r in rows]
    c = [float(r[4]) for r in rows]
    bar_sec = ts[1] - ts[0]
    fee = float(cfg.FUTURES_TAKER_FEE_RATE)
    clock = _Clock()
    risk_manager.time = clock  # type: ignore[assignment]
    risk = risk_manager.RiskManager()

    equity = equity0
    pos = None  # dict(side, entry, size, i, peak)
    trades: List[Dict] = []
    window = int(cfg.KLINE_LIMIT)

    def close(px: float, reason: str, i: int) -> None:
        nonlocal equity, pos
        sign = 1.0 if pos["side"] == "LONG" else -1.0
        gross = pos["size"] * (px - pos["entry"]) * sign
        fee_close = pos["size"] * px * fee
        pnl = gross - fee_close
        equity += pnl
        risk.record_trade(pnl, equity)
        trades.append(
            {
                "ts": ts[pos["i"]],
                "side": pos["side"],
                "reason": reason,
                "pnl": pnl,
                "fees": fee_close + pos["fee_open"],
                "move": (px - pos["entry"]) / pos["entry"] * sign,
                "hold_bars": i - pos["i"],
                "equity": equity,
            }
        )
        pos = None

    def open_(side: str, px: float, i: int) -> None:
        nonlocal equity, pos
        size = position_size_by_risk(
            equity, px, cfg.RISK_PER_TRADE, cfg.STOP_LOSS_RATIO, fee, cfg.LEVERAGE
        ) * risk.suggest_position_scale()
        fee_open = size * px * fee
        equity -= fee_open
        pos = {"side": side, "entry": px, "size": size, "i": i, "peak": 0.0, "fee_open": fee_open}

    for i in range(window - 1, len(c)):
        clock.t = ts[i]
        if pos is not None:
            side, entry = pos["side"], pos["entry"]
            sign = 1.0 if side == "LONG" else -1.0
            sl_px = entry * (1 - sign * cfg.STOP_LOSS_RATIO)
            tp_px = entry * (1 + sign * cfg.TAKE_PROFIT_RATIO)
            hit_sl = l[i] <= sl_px if side == "LONG" else h[i] >= sl_px
            hit_tp = h[i] >= tp_px if side == "LONG" else l[i] <= tp_px
            if hit_sl:
                close(sl_px, "stop_loss", i)
            elif hit_tp:
                close(tp_px, "take_profit", i)
            if pos is not None:
                fav = (c[i] - entry) / entry * sign
                pos["peak"] = max(pos["peak"], fav)
                arm, lock = float(cfg.MAX_HOLD_ARM_RATIO), float(cfg.MAX_HOLD_LOCK_RATIO)
                if arm > lock and pos["peak"] >= arm and fav <= lock:
                    close(c[i], "profit_lock", i)
                elif cfg.MAX_HOLD_CYCLES > 0 and (i - pos["i"]) * bar_sec / 60 >= cfg.MAX_HOLD_CYCLES:
                    close(c[i], "max_hold_cycles", i)

        s = slice(i - window + 1, i + 1)
        direction, _, _, _, quality, _ = compute_signal(o[s], h[s], l[s], c[s])
        pos_side = pos["side"] if pos else None
        if not will_open_or_reverse(direction, pos_side):
            continue
        if not risk.can_trade(equity)[0]:
            continue
        if not passes_entry_gates(direction, quality, pos_side, None, None)[0]:
            continue
        if pos is not None:
            close(c[i], "reverse", i)
        open_("LONG" if direction == 1 else "SHORT", c[i], i)
    return equity, trades


def summarize(label: str, trades: List[Dict], equity0: float) -> None:
    if not trades:
        print(f"{label}: 无交易")
        return
    pnl = [t["pnl"] for t in trades]
    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p <= 0]
    pf = sum(wins) / -sum(losses) if losses and sum(losses) < 0 else float("inf")
    peak, mdd = equity0, 0.0
    for t in trades:
        peak = max(peak, t["equity"])
        mdd = max(mdd, (peak - t["equity"]) / peak)
    days = max(1.0, (trades[-1]["ts"] - trades[0]["ts"]) / 86400)
    reasons = " ".join(f"{k}={v}" for k, v in collections.Counter(t["reason"] for t in trades).most_common())
    longs = [t["pnl"] for t in trades if t["side"] == "LONG"]
    shorts = [t["pnl"] for t in trades if t["side"] == "SHORT"]
    print(
        f"{label}: n={len(trades)} ({len(trades)/days:.1f}笔/天) 收益={sum(pnl)/equity0*100:+.1f}% "
        f"胜率={len(wins)/len(trades):.0%} PF={pf:.2f} 最大回撤={mdd:.1%} 手续费={sum(t['fees'] for t in trades):.0f} "
        f"| 多 {len(longs)}笔 {sum(longs):+.0f} 空 {len(shorts)}笔 {sum(shorts):+.0f} | {reasons}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--split", default="2026-09-01", help="样本内/外分界日 (UTC)")
    ap.add_argument("--equity", type=float, default=float(cfg.INITIAL_EQUITY))
    ap.add_argument(
        "--exchanges",
        default="binance",
        help="逗号分隔的 ccxt 交易所别名（同 CONSENSUS_EXCHANGES），每家 K 线各跑一遍",
    )
    ap.add_argument("--consensus", action="store_true", help="用 config.KLINE_SOURCES 合成共识 K 线跑一遍")
    args = ap.parse_args()

    print(
        f"策略={cfg.STRATEGY} 周期={cfg.KLINE_INTERVAL} 动量≥{cfg.MOMENTUM_MIN_RATIO} "
        f"SL={cfg.STOP_LOSS_RATIO} TP={cfg.TAKE_PROFIT_RATIO} ARM={cfg.MAX_HOLD_ARM_RATIO} "
        f"MAX_HOLD={cfg.MAX_HOLD_CYCLES} minQ={cfg.ENTRY_MIN_SIGNAL_QUALITY} FT={cfg.FREQTRADE_CONFIRM}"
    )
    fmt = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
    if args.consensus:
        sources = list(getattr(cfg, "KLINE_SOURCES", None) or ["binance"])
        by_ex = {}
        for name in sources:
            try:
                by_ex[name] = fetch_history(args.days, name)
            except Exception as e:
                print(f"[{name}] K 线拉取失败: {e}")
        rows = merge_consensus_klines(by_ex, int(getattr(cfg, "KLINE_MIN_SOURCES", 1) or 1))
        rows = [[r[7], r[2], r[1], r[0], r[3], r[5]] for r in rows]  # 回到 ccxt 顺序 [ts,o,h,l,c,vol]
        print(f"\n[consensus {','.join(sorted(by_ex))}] 数据 {fmt(rows[0][0]/1000)} ~ {fmt(rows[-1][0]/1000)} 共 {len(rows)} 根")
        report(rows, args)
        return
    for name in [e.strip().lower() for e in args.exchanges.split(",") if e.strip()]:
        try:
            rows = fetch_history(args.days, name)
        except Exception as e:
            print(f"\n[{name}] K 线拉取失败: {e}")
            continue
        if len(rows) < cfg.KLINE_LIMIT + 10:
            print(f"\n[{name}] K 线不足: {len(rows)}")
            continue
        print(f"\n[{name}] 数据 {fmt(rows[0][0]/1000)} ~ {fmt(rows[-1][0]/1000)} 共 {len(rows)} 根")
        report(rows, args)


def report(rows: List[List[float]], args: argparse.Namespace) -> None:
    equity, trades = run(rows, args.equity)
    split_ts = datetime.strptime(args.split, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
    summarize("全样本", trades, args.equity)
    is_tr = [t for t in trades if t["ts"] < split_ts]
    os_tr = [t for t in trades if t["ts"] >= split_ts]
    base_os = is_tr[-1]["equity"] if is_tr else args.equity
    summarize(f"样本内 <{args.split}", is_tr, args.equity)
    summarize(f"样本外 >={args.split}", os_tr, base_os)
    by_month: Dict[str, List[Dict]] = collections.defaultdict(list)
    for t in trades:
        by_month[datetime.fromtimestamp(t["ts"], timezone.utc).strftime("%Y-%m")].append(t)
    for m in sorted(by_month):
        v = by_month[m]
        print(
            f"  {m}: n={len(v):3d} 盈亏={sum(t['pnl'] for t in v):+8.1f} "
            f"胜率={sum(1 for t in v if t['pnl'] > 0)/len(v):.0%} 多={sum(1 for t in v if t['side']=='LONG')} 空={sum(1 for t in v if t['side']=='SHORT')}"
        )
    print(f"期末权益 {equity:.2f}（期初 {args.equity:.2f}）")


if __name__ == "__main__":
    main()
