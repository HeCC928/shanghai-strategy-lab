"""Daily event loop: yesterday's decisions execute before today's close is known."""
from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

import numpy as np
import pandas as pd

from lab.config import Config
from lab.data import Snapshot
from lab.fees import costs, FEE_SCHEDULE
from lab.strategies import compute_features, rank_candidates
from lab.shares import ShareBook, sell_lot_size, strict_data_issues
from lab.risk import risk_history
import json


@dataclass
class Result:
    config: Config
    manifest: dict
    equity: pd.DataFrame
    positions: pd.DataFrame
    decisions: pd.DataFrame
    orders: pd.DataFrame
    fills: pd.DataFrame
    plans: pd.DataFrame
    metrics: dict = field(default_factory=dict)
    timings: dict = field(default_factory=dict)
    benchmarks: pd.DataFrame = field(default_factory=pd.DataFrame)
    benchmark_metrics: dict = field(default_factory=dict)
    corporate_events: pd.DataFrame = field(default_factory=pd.DataFrame)
    closed_lots: pd.DataFrame = field(default_factory=pd.DataFrame)
    risk_states: pd.DataFrame = field(default_factory=pd.DataFrame)
    windows: list = field(default_factory=list)
    selection_trials: pd.DataFrame = field(default_factory=pd.DataFrame)


def run_backtest(c: Config, snapshot: Snapshot, progress: Callable | None = None,
                 parameter_schedule: list | None = None, feature_cache: dict | None = None) -> Result:
    start_clock = perf_counter()
    original_config = c
    snapshot.validate()
    dates = snapshot.check_range(c.start, c.end)
    if c.mode=="research" and "delist_date" in snapshot.instruments:
        retired=snapshot.instruments.delist_date.dropna()
        if ((retired!="") & (retired<=str(c.end))).any():
            raise ValueError("含退市的区间请提供现金回收记录并使用真实股数模式；不能用最后价格冒充卖出收入")
    if c.mode == "shares":
        issues = strict_data_issues(snapshot, c)
        if issues:
            raise ValueError("真实股数模式数据验收未通过：" + "；".join(issues))
    schedule = parameter_schedule or []
    allowed = {"top_n", "max_weight", "momentum_window", "vol_window", "low_vol_window", "short_ma", "long_ma",
               "breakout_window", "amount_multiple", "reversal_window", "threshold_ma", "entry_threshold", "exit_threshold",
               "exposure", "market_filter", "market_ma", "defensive_exposure", "volatility_control", "target_volatility"}
    if schedule != sorted(schedule, key=lambda x:x["signal_date"]) or len({x["signal_date"] for x in schedule}) != len(schedule):
        raise ValueError("Parameter schedule must contain unique, increasing signal dates")
    for entry in schedule:
        if set(entry["params"]) - allowed or entry["signal_date"] not in snapshot.calendar:
            raise ValueError("Invalid scheduled parameters or signal date")
    config_by_date = {x["signal_date"]: Config(**{**c.model_dump(), **x["params"]}) for x in schedule}
    def get_features(config):
        key = json.dumps(config.model_dump(mode="json", exclude={"start", "end", "capital"}), sort_keys=True)
        if feature_cache is not None and key in feature_cache:
            return feature_cache[key]
        frame = compute_features(snapshot, config)
        if feature_cache is not None:
            if len(feature_cache) >= 12:
                feature_cache.pop(next(iter(feature_cache)))
            feature_cache[key] = frame
        return frame
    versions = [(snapshot.calendar[0], c)]
    for day, config in config_by_date.items():
        if day == versions[0][0]: versions[0] = (day, config)
        else: versions.append((day, config))
    pieces, risk_pieces = [], []
    for index, (day, config) in enumerate(versions):
        end = versions[index+1][0] if index+1 < len(versions) else "9999-12-31"
        f = get_features(config)
        pieces.append(f[(f.date >= day) & (f.date < end)])
        risk = risk_history(snapshot, config)
        risk_pieces.append(risk[(risk.date >= day) & (risk.date < end)])
    features = pd.concat(pieces, ignore_index=True)
    risk_frame = pd.concat(risk_pieces, ignore_index=True)
    risk_by_day = risk_frame.set_index("date").target_exposure.to_dict()
    by_day = {d: g.set_index("symbol", drop=False) for d, g in features.groupby("date")}
    feature_seconds = perf_counter() - start_clock
    cal = snapshot.calendar
    indices = {d: i for i, d in enumerate(cal)}
    first_i = indices[dates[0]]
    pre = cal[first_i-1] if first_i else dates[0]
    book = ShareBook(snapshot.instruments.symbol, cal, snapshot.actions) if c.mode=="shares" else None
    qty = book.quantities if book else {s: 0. for s in snapshot.instruments.symbol}
    price_prefix = "raw" if book else "adj"
    marks = {s: 0. for s in qty}
    cash = c.capital
    nav = c.capital
    total_fees = 0.
    plans, active, exits, pending = [], {}, {}, []
    orders, fills, decisions, positions = [], [], [], []
    equity = [{"date": pre, "equity": nav, "cash": cash, "receivable": 0., "fees": 0., "gross_equity": nav, "initial": True}]
    plan_seq = 0
    has_hold_target = False
    exit_events=snapshot.manifest.get("exit_records",[])
    recovered=set()

    def cancel_plan(symbol, reason, day):
        if symbol in active:
            p = active.pop(symbol)
            p.update(status=reason, closed_at=day)

    def new_plan(symbol, budget, day):
        nonlocal plan_seq
        if budget <= .000001:
            return
        plan_seq += 1
        p = {"plan_id": f"P{plan_seq:06d}", "symbol": symbol, "signal_date": day,
             "budget": budget, "spent": 0., "stage": 0, "attempts": 0,
             "next_index": indices[day], "expires_index": indices[day] + c.plan_lifetime,
             "status": "active", "closed_at": ""}
        plans.append(p)
        active[symbol] = p

    def decide(day, force=False):
        nonlocal pending, has_hold_target, c
        if day in config_by_date:
            c = config_by_date[day]
            force = True
        if day not in by_day:
            return
        i = indices[day]
        dayf = by_day[day]
        exposure = float(risk_by_day.get(day, 0.))
        invested = sum(qty[s] * marks[s] for s in qty)
        # Exposure reductions operate on existing positions, not on a reset portfolio.
        if invested > nav * exposure + .01 and exposure < 1:
            ratio = max(0., nav * exposure / invested)
            for s, q in qty.items():
                if q > 1e-9:
                    cancel_plan(s, "Risk allocation reduced", day)
                    reduction = q * (1-ratio)
                    previous = exits.get(s, {}).get("quantity", 0.)
                    exits[s] = {"signal_date": day, "quantity": max(previous, reduction), "reason": "Risk exposure limit"}
        if exposure == 0:
            for s in list(active): cancel_plan(s, "Cash allocation selected", day)
        for s in list(active):
            if i > active[s]["expires_index"]:
                cancel_plan(s, "计划到期", day)
        next_day = cal[i+1] if i+1 < len(cal) else None
        if c.rebalance == "monthly":
            scheduled = next_day is not None and day[:7] != next_day[:7]
        elif c.rebalance == "weekly":
            scheduled = next_day is not None and pd.Timestamp(day).isocalendar()[:2] != pd.Timestamp(next_day).isocalendar()[:2]
        else:
            scheduled = (i - first_i + 1) % 20 == 0
        choose = c.strategy == "threshold" or force or scheduled
        if c.strategy == "buy_hold" and has_hold_target:
            choose = False
        if choose:
            ranking = rank_candidates(dayf.reset_index(drop=True))
            ranking["target_weight"] = 0.
            if c.strategy == "threshold":
                for s in set(active) | {s for s, q in qty.items() if q > 1e-9}:
                    if s in dayf.index and dayf.loc[s, "deviation"] < c.exit_threshold:
                        cancel_plan(s, "退出条件触发", day)
                        if qty[s] > 1e-9:
                            exits[s] = {"signal_date": day, "quantity": qty[s], "reason": "跌破退出阈值"}
                occupied = set(active) | {s for s, q in qty.items() if q > 1e-9}
                for row in ranking[["symbol","qualified","cross_up"]].itertuples(index=False):
                    if exposure > 0 and row.qualified and row.cross_up and row.symbol not in occupied and row.symbol not in exits and len(occupied) < c.top_n:
                        new_plan(row.symbol, nav * c.target_weight * exposure, day)
                        occupied.add(row.symbol)
                ranking.loc[ranking.symbol.isin(occupied), "target_weight"] = c.target_weight * exposure
            else:
                eligible = ranking[ranking.qualified]
                selected = eligible if c.strategy in ("buy_hold", "equal_weight") else eligible.head(c.top_n)
                weight = min(c.max_weight, 1 / len(selected)) if len(selected) and c.strategy in ("buy_hold", "equal_weight") else c.target_weight
                weight *= exposure
                targets = {s: nav * weight for s in selected.symbol}
                ranking.loc[ranking.symbol.isin(targets), "target_weight"] = weight
                for s in list(active):
                    if s not in targets:
                        cancel_plan(s, "新目标移除", day)
                for s, q in qty.items():
                    value = q * marks[s]
                    target = targets.get(s, 0.)
                    if value > target + .01:
                        cancel_plan(s, "目标减仓", day)
                        exits[s] = {"signal_date": day, "quantity": (value-target)/marks[s], "reason": "调仓目标减仓"}
                for s, target in targets.items():
                    remaining = max(0., target - qty[s]*marks[s])
                    if s in active:
                        p = active[s]
                        p["budget"] = min(p["budget"], p["spent"] + remaining)
                    elif remaining > .01 and s not in exits:
                        new_plan(s, remaining, day)
                has_hold_target = True
            ranking["signal_date"] = day
            ranking["execution_date"] = next_day
            ranking.loc[ranking.qualified & (ranking.target_weight == 0), "reason"] = "满足条件但未入选／未发生入场上穿／持仓名额不足"
            keep = ["symbol", "signal_date", "execution_date", "score", "rank", "qualified", "reason", "target_weight",
                    "momentum", "volatility", "low_volatility", "deviation", "cross_up", "amount_ratio", "breakout", "reversal", "avg_amount"]
            decisions.extend(ranking[keep].to_dict("records"))
        pending = []
        for s, intent in sorted(exits.items()):
            pending.append({"symbol": s, "side": "sell", "signal_date": day, "origin_signal_date": intent["signal_date"],
                            "quantity": min(qty[s], intent["quantity"]), "budget": 0., "reason": intent["reason"], "plan_id": "", "stage": 0})
        for s, p in sorted(active.items(), key=lambda item: item[1]["plan_id"]):
            if s in exits or i < p["next_index"] or s not in dayf.index:
                continue
            if not dayf.loc[s, "qualified"]:
                continue
            room = max(0., nav*c.max_weight - qty[s]*marks[s])
            if exposure < 1:
                planned_buys = sum(x["budget"] for x in pending if x["side"] == "buy")
                room = min(room, max(0., nav*exposure - invested - planned_buys))
            budget = min(p["budget"] * c.fractions[p["stage"]], p["budget"]-p["spent"], room)
            if budget <= .01:
                continue
            pending.append({"symbol": s, "side": "buy", "signal_date": day, "origin_signal_date": p["signal_date"],
                            "quantity": 0., "budget": budget, "reason": "分批条件复查通过", "plan_id": p["plan_id"], "stage": p["stage"]+1})

    if pre < dates[0] and pre in by_day:
        marks.update(by_day[pre][f"{price_prefix}_close"].to_dict())
        decide(pre, force=True)
    for step, day in enumerate(dates):
        f = by_day[day] if day in by_day else pd.DataFrame()
        if book:
            old_quantities = qty.copy()
            cash += book.open_day(day)
            # Existing sell intents preserve their fraction after bonus shares.
            for s in exits:
                if old_quantities[s]>0 and qty[s] != old_quantities[s]:
                    ratio=qty[s]/old_quantities[s]
                    exits[s]["quantity"] *= ratio
                    for intent in pending:
                        if intent["symbol"]==s and intent["side"]=="sell": intent["quantity"] *= ratio
            for event in exit_events:
                s=event["symbol"]
                if s not in recovered and event["recovery_date"]<=day:
                    cash += book.recover(s,event["net_cash_per_share"],day)
                    cancel_plan(s,"有记录的退出现金回收",day)
                    exits.pop(s,None)
                    pending=[p for p in pending if p["symbol"]!=s]
                    recovered.add(s)
        day_budget = nav * c.daily_buy_cap
        for intent in pending:
            s, side = intent["symbol"], intent["side"]
            order = {**intent, "order_id": f"O{len(orders)+1:07d}", "date": day, "status": "rejected", "reject_reason": "",
                     "filled_quantity": 0., "filled_amount": 0.}
            orders.append(order)
            reason = ""
            row = f.loc[s] if s in f.index else None
            if row is None:
                reason = "无当日行情"
            elif pd.notna(row.get("is_suspended")) and bool(row.get("is_suspended")):
                reason = "停牌"
            elif side == "buy" and pd.notna(row.get("limit_up")) and row.raw_open >= row.limit_up - 1e-8:
                reason = "开盘涨停"
            elif side == "sell" and pd.notna(row.get("limit_down")) and row.raw_open <= row.limit_down + 1e-8:
                reason = "开盘跌停"
            amount, q = 0., 0.
            if not reason:
                reference_price = float(row[f"{price_prefix}_open"])
                price = reference_price * (1 + (1 if side == "buy" else -1)*c.slippage_bps/10000)
                if book:
                    price=float(Decimal(str(price)).quantize(Decimal("0.01"),rounding=ROUND_CEILING if side=="buy" else ROUND_FLOOR))
                capacity = float(row.prior_avg_amount) * c.participation if pd.notna(row.prior_avg_amount) else 0.
                if side == "buy":
                    amount = min(intent["budget"], day_budget, capacity, cash/(1+c.commission))
                    q = max(0., amount/price)
                    if book:
                        q = (q//100)*100
                        while q>0 and q*price+costs(q*price,side,day,c)["fees"]>cash+1e-8:
                            q -= 100
                        amount = q*price
                else:
                    q = min(intent["quantity"], qty[s], capacity/price)
                    if book:
                        q = sell_lot_size(q,book.available(s,day))
                    amount = q * price
                raw_execution = float(row.raw_open)*(price/reference_price)
                if side=="buy" and pd.notna(row.get("limit_up")) and raw_execution>row.limit_up+1e-8:
                    q=0.
                    reason="滑点后价格超过涨停限制"
                if side=="sell" and pd.notna(row.get("limit_down")) and raw_execution<row.limit_down-1e-8:
                    q=0.
                    reason="滑点后价格低于跌停限制"
                if q <= 1e-9:
                    if not reason:
                        if capacity<=1e-9:reason="历史成交额容量不足"
                        elif side=="buy" and day_budget<=1e-9:reason="单日新增买入额度用尽"
                        elif side=="buy" and cash<=1e-9:reason="现金不足"
                        elif side=="buy" and book and cash<100*price+costs(100*price,side,day,c)["fees"]:reason="现金不足以支付一手及费用"
                        elif side=="buy" and book:reason="本批预算或容量不足一手"
                        elif side=="sell" and book and book.available(s,day)<=1e-9:reason="T+1或股份到账限制，无可售股数"
                        elif side=="sell" and book:reason="减仓预算或容量不足合法卖出单位"
                        else:reason="可执行预算不足"
                else:
                    fee = costs(amount, side, day, c)
                    cash += (-amount if side == "buy" else amount) - fee["fees"]
                    if book:
                        (book.buy if side=="buy" else book.sell)(s,q,price,fee["fees"],day)
                    else:
                        qty[s] += q if side == "buy" else -q
                    total_fees += fee["fees"]
                    order.update(status="filled", filled_quantity=q, filled_amount=amount)
                    fills.append({**intent, "order_id": order["order_id"], "date": day,
                                  "quantity": q, "price": price, "reference_price": reference_price, "amount": amount,
                                  **fee, "slippage_loss": q*abs(price-reference_price)})
                    if side == "buy":
                        day_budget -= amount
                    else:
                        exits[s]["quantity"] -= q
                        if exits[s]["quantity"] < 1e-9 or qty[s] < 1e-9:
                            exits.pop(s, None)
            if reason:
                order["reject_reason"] = reason
            if side == "buy" and s in active:
                p = active[s]
                p["attempts"] += 1
                if not reason:
                    p["spent"] += amount
                    p["stage"] += 1
                    p["attempts"] = 0
                    p["next_index"] = indices[day] + c.tranche_gap
                    if p["stage"] == len(c.fractions):
                        cancel_plan(s, "completed", day)
                elif p["attempts"] >= c.max_attempts:
                    cancel_plan(s, "超过尝试次数", day)
        if cash < -1e-6:
            raise AssertionError("现金账本出现负数")
        if not f.empty: marks.update(f[f"{price_prefix}_close"].to_dict())
        receivable = book.receivable if book else 0.
        nav = cash + receivable + sum(qty[s]*marks[s] for s in qty)
        equity.append({"date": day, "equity": nav, "cash": cash, "receivable": receivable, "fees": total_fees,
                       "gross_equity": nav + total_fees, "initial": False})
        for s, q in qty.items():
            if q > 1e-9:
                positions.append({"date": day, "symbol": s, "quantity": q, "mark": marks[s],
                                  "value": q*marks[s], "weight": q*marks[s]/nav,
                                  "sellable_quantity":book.available(s,day) if book else q})
        if book: book.close_day(day)
        decide(day)
        if progress and (step % 20 == 0 or step == len(dates)-1):
            progress((step+1)/len(dates), f"逐日记账 {day}")
    frames = lambda rows, columns: pd.DataFrame(rows) if rows else pd.DataFrame(columns=columns)
    mode_limit = "真实股数模式：按原始价与实际股数记账；股息按导入的每股现金数计入，未自动估算个人差异化红利税；不模拟盘中排队" if book else "研究模式：虚拟分数份额；不含整手、最低佣金、真实股息到账；未验证状态不代表可成交"
    if book:
        mode_limit += "；成交价按不利方向取0.01元价格档，分项费用按分四舍五入"
    if exit_events:
        mode_limit += "；退市后按最后可用价格估值直至有记录的现金回收，该估值不代表可成交价格"
    result = Result(original_config, {**snapshot.manifest, "snapshot_id": snapshot.digest(), "mode": c.mode, "fee_schedule":FEE_SCHEDULE,
                       "limitations": snapshot.manifest.get("limitations", []) + [mode_limit, "成本前曲线为同一路径归还显式费用，不是零成本重跑"]},
                    pd.DataFrame(equity), frames(positions, ["date", "symbol", "quantity", "value", "weight"]),
                    frames(decisions, ["signal_date", "symbol", "score", "rank", "reason", "target_weight"]),
                    frames(orders, ["date", "symbol", "side", "status", "reject_reason"]),
                    frames(fills, ["date", "symbol", "side", "quantity", "amount", "fees", "commission", "stamp_tax", "transfer_fee", "slippage_loss"]),
                    frames(plans, ["plan_id", "symbol", "status"]),
                    timings={"features_seconds": feature_seconds, "total_seconds": perf_counter()-start_clock})
    result.risk_states = risk_frame[(risk_frame.date >= pre) & (risk_frame.date <= dates[-1])].reset_index(drop=True)
    if schedule:
        result.manifest["parameter_schedule"] = schedule
    if book:
        result.corporate_events = pd.DataFrame(book.events)
        result.closed_lots = pd.DataFrame(book.realized)
    from lab.metrics import calculate_metrics
    result.metrics = calculate_metrics(result)
    if book:
        result.metrics["unrealized_pnl"] = sum(lot.quantity*(marks[lot.symbol]-lot.cost_per_share+lot.income_per_share) for lot in book.lots if lot.quantity>1e-8)
    return result
