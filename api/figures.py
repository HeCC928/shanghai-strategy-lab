"""Portable PNG handout rendered from the same saved daily ledger."""
import io
import os
from pathlib import Path
from threading import Lock

_render_lock = Lock()

def equity_png(run):
    with _render_lock:
        os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".runtime" / "matplotlib"))
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.ticker import PercentFormatter
        import pandas as pd
        fig = Figure(figsize=(12, 8), dpi=150, facecolor="#f7f8fc")
        FigureCanvasAgg(fig)
        m=run["metrics"]
        fig.text(.08,.945,"SHANGHAI STRATEGY LAB",fontsize=10,color="#7162c9",weight="bold")
        fig.text(.08,.895,run["case_label"],fontsize=23,color="#19233c",weight="bold")
        fig.text(.08,.855,f"{run['config']['start']} — {run['config']['end']}  |  {run['study']}",fontsize=10,color="#626c80")
        for x,label,value in [(.08,"NET RETURN",f"{m['total_return']:.1%}"),(.38,"SHARPE",f"{m['sharpe']:.2f}" if m['sharpe'] is not None else "Undefined"),(.68,"MAX DRAWDOWN",f"{abs(m['max_drawdown']):.1%}")]:
            fig.text(x,.795,label,fontsize=9,color="#626c80")
            fig.text(x,.745,value,fontsize=21,color="#19233c",weight="bold")
        ax=fig.add_axes([.08,.30,.86,.39],facecolor="white")
        dd=fig.add_axes([.08,.14,.86,.12],sharex=ax,facecolor="white")
        dates=pd.to_datetime([e["date"] for e in run["equity"]])
        ax.plot(dates,[e["nav"] for e in run["equity"]],color="#7162c9",lw=1.8,label=run["case_label"])
        if run["benchmarks"]:
            ax.plot(pd.to_datetime([e["date"] for e in run["benchmarks"]]),[e["buy_hold"]/run["config"]["capital"] for e in run["benchmarks"]],color="#a1aaba",ls="--",lw=1.5,label="Same-pool buy & hold")
        ax.set_ylabel("Net asset value")
        ax.legend(loc="upper left",frameon=False,fontsize=9)
        ax.tick_params(labelbottom=False)
        dd.fill_between(dates,[e["drawdown"] for e in run["equity"]],0,color="#d6cef0")
        dd.yaxis.set_major_formatter(PercentFormatter(1,decimals=0))
        dd.set_ylabel("Drawdown")
        for axis in (ax,dd):
            axis.grid(axis="y",color="#edf0f5")
            axis.tick_params(colors="#657086",labelsize=9)
            for spine in axis.spines.values():spine.set_visible(False)
        fig.text(.08,.065,"Retrospective research · fixed surviving-stock pool · configured costs included",fontsize=9,color="#626c80")
        note = "Fractional adjusted-price units; minimum commission, transfer fees and full corporate-action settlement omitted." if run["config"]["mode"] == "research" else "Actual-share ledger with imported corporate actions and T+1 availability; intraday queue priority is not simulated."
        fig.text(.08,.035,note,fontsize=8,color="#626c80")
        output=io.BytesIO()
        fig.savefig(output,format="png",facecolor=fig.get_facecolor())
        return output.getvalue()
