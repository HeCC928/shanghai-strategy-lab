"""Small parameter grids confined to a declared validation period."""
import itertools
import pandas as pd

from lab.config import Config
from lab.engine import run_backtest

GRIDS={
    "threshold":("threshold_ma",[10,20,30],"entry_threshold",[.01,.02,.03]),
    "momentum":("momentum_window",[20,60,120],"vol_window",[20,40,60]),
    "low_vol":("low_vol_window",[20,60,120],"top_n",[5,10,20]),
    "breakout":("breakout_window",[20,40,60],"amount_multiple",[1.2,1.5,2.]),
    "reversal":("reversal_window",[3,5,10],"long_ma",[40,60,120]),
}


def run_sensitivity(c,snapshot,progress=None):
    if c.strategy not in GRIDS: raise ValueError("该策略不支持参数网格")
    x,xs,y,ys=GRIDS[c.strategy]
    rows=[]
    for i,(vx,vy) in enumerate(itertools.product(xs,ys)):
        params={**c.model_dump(),x:vx,y:vy}
        tested=Config(**params)
        r=run_backtest(tested,snapshot)
        rows.append({x:vx,y:vy,"evaluation_start":str(c.start),"evaluation_end":str(c.end),**r.metrics})
        if progress:progress((i+1)/(len(xs)*len(ys)),f"验证集网格 {i+1}/{len(xs)*len(ys)}")
    return pd.DataFrame(rows)
