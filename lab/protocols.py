"""Calendar-month research protocols; all cutoffs are explicit."""
from datetime import date
from typing import Literal
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator


class WalkForwardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    start: date = date(2025, 7, 1)
    end: date = date(2026, 6, 30)
    train_months: int = Field(12, ge=3, le=36)
    validation_months: int = Field(3, ge=1, le=12)
    shortlist: int = Field(5, ge=1, le=20)
    max_drawdown: float = Field(.25, gt=0, le=1)
    target_period_optimized: bool = True
    selection: Literal["rank_50_30_20"] = "rank_50_30_20"

    @model_validator(mode="after")
    def complete_months(self):
        if self.start.day != 1 or self.end != pd.Timestamp(self.end).to_period("M").end_time.date() or self.end <= self.start:
            raise ValueError("Rolling evaluation requires complete calendar months in increasing order")
        return self

    def windows(self, calendar):
        result = []
        for month in pd.period_range(self.start, self.end, freq="M"):
            replay_start, replay_end = str(month.start_time.date()), str(month.end_time.date())
            past = [d for d in calendar if d < replay_start]
            sessions = [d for d in calendar if replay_start <= d <= replay_end]
            if not past or not sessions:
                raise ValueError(f"No complete calendar coverage for {month}")
            val_first = month - self.validation_months
            train_first = val_first - self.train_months
            result.append({"month": str(month), "train_start": str(train_first.start_time.date()),
                           "train_end": str((val_first - 1).end_time.date()),
                           "validation_start": str(val_first.start_time.date()),
                           "validation_end": str((month - 1).end_time.date()),
                           "signal_date": past[-1], "replay_start": replay_start,
                           "replay_end": replay_end, "first_session": sessions[0], "last_session": sessions[-1]})
        return result
