"""Explicit costs. Slippage is in the execution price, never deducted again."""
from lab.config import Config
from pathlib import Path
import yaml
from decimal import Decimal, ROUND_HALF_UP

FEE_SCHEDULE=yaml.safe_load((Path(__file__).parent/"resources"/"fees.yaml").read_text(encoding="utf-8"))


def costs(amount: float, side: str, day: str, c: Config) -> dict:
    commission = amount * c.commission
    if c.mode == "shares" and amount > 0:
        commission = max(commission, c.minimum_commission)
    applicable=[row for row in FEE_SCHEDULE["rates"] if row["effective_from"]<=day]
    if not applicable: raise ValueError("历史费用表未覆盖2018年之前的成交")
    rate=applicable[-1]
    stamp = amount * rate["sell_stamp"] if side == "sell" else 0.
    transfer = amount * rate["transfer_both_sides"] if c.mode == "shares" else 0.
    if c.mode=="shares":
        rounded=lambda value:float(Decimal(str(value)).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))
        commission,stamp,transfer=map(rounded,(commission,stamp,transfer))
    return {"commission": commission, "stamp_tax": stamp, "transfer_fee": transfer,
            "fees": commission + stamp + transfer}
