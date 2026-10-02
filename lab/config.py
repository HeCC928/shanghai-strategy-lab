from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


STRATEGIES = {
    "threshold": "S0 简单阈值", "momentum": "S1 动量趋势",
    "low_vol": "S2 低波动", "breakout": "S3 放量突破", "reversal": "S4 短期反转",
}


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False, validate_default=True)
    strategy: Literal["threshold", "momentum", "low_vol", "breakout", "reversal", "buy_hold", "equal_weight"] = "threshold"
    start: date = date(2018, 1, 1)
    end: date = date(2025, 2, 28)
    capital: float = Field(1_000_000, gt=0)
    mode: Literal["research", "shares"] = "research"
    top_n: int = Field(10, ge=1, le=2000)
    max_weight: float = Field(.1, gt=0, le=1)
    rebalance: Literal["monthly", "weekly", "20d"] = "monthly"
    min_history: int = Field(120, ge=1)
    min_amount: float = Field(20_000_000, ge=0)
    exclude_st: bool = False
    momentum_window: int = Field(60, ge=2, le=250)
    vol_window: int = Field(20, ge=2, le=250)
    low_vol_window: int = Field(60, ge=2, le=250)
    short_ma: int = Field(20, ge=2, le=250)
    long_ma: int = Field(60, ge=3, le=500)
    breakout_window: int = Field(20, ge=2, le=250)
    amount_multiple: float = Field(1.5, gt=0)
    reversal_window: int = Field(5, ge=1, le=60)
    threshold_ma: int = Field(20, ge=2, le=250)
    entry_threshold: float = .02
    exit_threshold: float = -.02
    staging: bool = True
    tranche_weights: tuple[float, ...] = (.4, .3, .3)
    tranche_gap: int = Field(5, ge=1, le=100)
    plan_lifetime: int = Field(20, ge=1, le=250)
    max_attempts: int = Field(3, ge=1, le=20)
    daily_buy_cap: float = Field(.2, gt=0, le=1)
    participation: float = Field(.01, gt=0, le=1)
    commission: float = Field(.0003, ge=0, le=.1)
    minimum_commission: float = Field(5, ge=0)
    slippage_bps: float = Field(5, ge=0, le=500)
    risk_free: float = Field(0, ge=0, le=.5)
    exposure: float = Field(1., ge=0, le=1)
    market_filter: bool = False
    market_ma: int = Field(60, ge=20, le=250)
    defensive_exposure: float = Field(.25, ge=0, le=1)
    volatility_control: bool = False
    target_volatility: float = Field(.15, gt=0, le=1)

    @model_validator(mode="after")
    def valid(self):
        if self.end <= self.start:
            raise ValueError("结束日期必须晚于开始日期")
        if self.short_ma >= self.long_ma:
            raise ValueError("短均线窗口必须小于长均线窗口")
        if self.exit_threshold >= self.entry_threshold:
            raise ValueError("退出阈值必须小于入场阈值")
        if not self.tranche_weights or any(x <= 0 for x in self.tranche_weights) or abs(sum(self.tranche_weights)-1) > 1e-8:
            raise ValueError("分批比例必须为正且合计100%")
        return self

    @property
    def fractions(self):
        return self.tranche_weights if self.staging else (1.,)

    @property
    def target_weight(self):
        return min(1 / self.top_n, self.max_weight)
