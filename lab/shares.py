"""Real-share lots, T+1 availability, dividend receivables and bonus shares."""
from dataclasses import dataclass
import math

import pandas as pd
from lab.fees import FEE_SCHEDULE


def strict_data_issues(snapshot, config):
    issues = []
    b = snapshot.bars[(snapshot.bars.date >= str(config.start)) & (snapshot.bars.date <= str(config.end))]
    for col in ("is_st", "is_suspended", "no_price_limit"):
        if col not in b or b[col].isna().any():
            issues.append(f"缺少完整历史状态：{col}")
    if "no_price_limit" in b:
        limited = b[~b.no_price_limit.fillna(False).astype(bool)]
        for col in ("limit_up", "limit_down"):
            if col not in limited or limited[col].isna().any() or (limited[col] <= 0).any():
                issues.append(f"缺少当日有效限制价格：{col}")
    coverage = snapshot.manifest.get("corporate_action_coverage", {})
    exits=snapshot.manifest.get("exit_records",[])
    for ins in snapshot.instruments.itertuples():
        delisted=getattr(ins,"delist_date",None)
        if pd.notna(delisted) and delisted and str(delisted)<=str(config.end):
            matched=[x for x in exits if x.get("symbol")==ins.symbol]
            if len(matched)!=1:
                issues.append(f"{ins.symbol}缺少唯一且明确的退市现金回收记录")
            elif not (matched[0].get("source") and matched[0].get("known_at") and matched[0].get("recovery_date","")>=str(delisted)
                      and str(matched[0]["known_at"])<=str(matched[0].get("recovery_date",""))
                      and isinstance(matched[0].get("net_cash_per_share"),(int,float)) and math.isfinite(matched[0]["net_cash_per_share"]) and matched[0]["net_cash_per_share"]>=0):
                issues.append(f"{ins.symbol}现金回收记录无效")
    for symbol in snapshot.instruments.symbol:
        proof = coverage.get(symbol, {})
        if not (proof.get("from", "9999") <= str(config.start) and proof.get("to", "") >= str(config.end)
                and proof.get("source") and proof.get("reviewed_at") and proof.get("complete") is True):
            issues.append(f"{symbol}缺少已核验公司行动覆盖声明")
    a = snapshot.actions
    if not a.empty:
        required = {"event_id", "symbol", "record_date", "ex_date", "pay_date", "cash_per_share", "share_multiplier", "share_trade_date", "source"}
        if not required.issubset(a):
            issues.append("公司行动字段不完整")
        else:
            if a.event_id.duplicated().any(): issues.append("公司行动ID重复")
            if not set(a.symbol).issubset(snapshot.instruments.symbol): issues.append("公司行动证券不在股票池")
            for row in a.itertuples():
                if row.ex_date not in snapshot.calendar or row.record_date not in snapshot.calendar:
                    issues.append(f"{row.event_id}登记或除权日不在交易日历")
                    continue
                if snapshot.calendar.index(row.ex_date)-snapshot.calendar.index(row.record_date) != 1:
                    issues.append(f"{row.event_id}登记与除权日期关系需人工核对")
                if row.pay_date < row.ex_date or row.share_trade_date < row.ex_date:
                    issues.append(f"{row.event_id}到账或股份可售日期早于除权日")
                if not math.isfinite(row.cash_per_share) or row.cash_per_share < 0 or not math.isfinite(row.share_multiplier) or row.share_multiplier < 1:
                    issues.append(f"{row.event_id}暂不支持配股、合股或无效事件")
                if not isinstance(row.source,str) or not row.source.strip(): issues.append(f"{row.event_id}缺少事件来源")
    if str(config.start) < FEE_SCHEDULE["coverage_start"] or str(config.end) > FEE_SCHEDULE["coverage_end"]:
        issues.append("真实股数模式超出已核验费用日期范围：" + FEE_SCHEDULE["scope"])
    return issues


@dataclass
class Lot:
    symbol: str
    quantity: float
    bought_on: str
    available_on: str
    cost_per_share: float
    income_per_share: float = 0.


class ShareBook:
    def __init__(self, symbols, calendar, actions):
        self.quantities = {s: 0. for s in symbols}
        self.lots = []
        self.calendar = calendar
        self.actions = actions.to_dict("records")
        self.entitlements = {}
        self.receivables = []
        self.events = []
        self.realized = []

    @property
    def receivable(self):
        return sum(x["amount"] for x in self.receivables)

    def available(self, symbol, day):
        return sum(lot.quantity for lot in self.lots if lot.symbol==symbol and lot.available_on <= day)

    def buy(self, symbol, quantity, price, fees, day):
        if abs(quantity/100-round(quantity/100)) > 1e-8:
            raise ValueError("买入必须100股整数倍")
        i = self.calendar.index(day)
        unlock = self.calendar[i+1] if i+1<len(self.calendar) else "9999-12-31"
        self.lots.append(Lot(symbol, quantity, day, unlock, (quantity*price+fees)/quantity))
        self.quantities[symbol] += quantity

    def sell(self, symbol, quantity, price, fees, day):
        if quantity > self.available(symbol, day)+1e-8:
            raise ValueError("违反T+1或超出可售数量")
        remaining = quantity
        for lot in self.lots:
            if remaining <= 1e-8: break
            if lot.symbol != symbol or lot.available_on > day or lot.quantity <= 0: continue
            q = min(lot.quantity, remaining)
            pnl = q*(price-lot.cost_per_share+lot.income_per_share)-fees*q/quantity
            self.realized.append({"symbol":symbol,"date":day,"bought_on":lot.bought_on,"quantity":q,"pnl":pnl})
            lot.quantity -= q
            remaining -= q
        self.quantities[symbol] -= quantity

    def close_day(self, day):
        for event in self.actions:
            if event["record_date"] == day:
                self.entitlements[event["event_id"]] = [(lot,lot.quantity) for lot in self.lots if lot.symbol==event["symbol"] and lot.quantity>0]

    def recover(self,symbol,net_cash_per_share,day):
        quantity=self.quantities[symbol]
        amount=quantity*net_cash_per_share
        for lot in self.lots:
            if lot.symbol==symbol and lot.quantity>0:
                self.realized.append({"symbol":symbol,"date":day,"bought_on":lot.bought_on,"quantity":lot.quantity,
                                      "pnl":lot.quantity*(net_cash_per_share-lot.cost_per_share+lot.income_per_share)})
                lot.quantity=0.
        self.quantities[symbol]=0.
        self.events.append({"date":day,"event_id":"exit_"+symbol,"symbol":symbol,"record_quantity":quantity,"cash_recovery":amount,"source_kind":"documented_exit"})
        return amount

    def open_day(self, day):
        for event in self.actions:
            if event["ex_date"] != day: continue
            entitlements = self.entitlements.get(event["event_id"], [])
            amount = 0.
            for lot,q in entitlements:
                dividend = q*event["cash_per_share"]
                amount += dividend
                multiplier = event["share_multiplier"]
                new_shares = q*(multiplier-1)
                if abs(new_shares-round(new_shares)) > 1e-7:
                    raise ValueError("送转产生不足1股权益，需提供实际股份分配记录后才能继续严格回测")
                lot.income_per_share += event["cash_per_share"]
                if new_shares:
                    lot.cost_per_share /= multiplier
                    lot.income_per_share /= multiplier
                    self.lots.append(Lot(lot.symbol,new_shares,lot.bought_on,event["share_trade_date"],lot.cost_per_share,lot.income_per_share))
                    self.quantities[lot.symbol] += new_shares
                self.events.append({"date":day,"event_id":event["event_id"],"symbol":lot.symbol,"record_quantity":q,"cash_entitlement":dividend,"new_shares":new_shares,"pay_date":event["pay_date"]})
            if amount:
                self.receivables.append({"event_id":event["event_id"],"amount":amount,"pay_date":event["pay_date"]})
        credited = sum(x["amount"] for x in self.receivables if x["pay_date"] <= day)
        self.receivables = [x for x in self.receivables if x["pay_date"] > day]
        return credited


def sell_lot_size(wanted, available):
    """Allow a complete odd remainder exactly once, including with round lots."""
    wanted = min(wanted, available)
    odd = int(round(available)) % 100
    if wanted+1e-8 >= available:
        return float(int(round(available)))
    if odd and wanted >= odd:
        return float(int((wanted-odd)//100)*100+odd)
    return float(int(wanted//100)*100)
