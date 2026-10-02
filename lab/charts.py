import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from lab.metrics import monthly_returns

PALETTE = ["#2563EB", "#8B5CF6", "#EA8C28", "#149D92"]


def style(fig, height=440):
    fig.update_layout(template="plotly_white", height=height, font=dict(family="Microsoft YaHei, Arial", size=13, color="#17202A"),
                      margin=dict(l=35, r=20, t=40, b=35), legend=dict(orientation="h", y=1.13),
                      hovermode="x unified", paper_bgcolor="white", plot_bgcolor="white")
    return fig


def equity_chart(r, gross=False):
    e = r.equity
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.72, .28], vertical_spacing=.08)
    fig.add_trace(go.Scatter(x=e.date, y=e.equity/r.config.capital, name="扣费后净值", line=dict(color=PALETTE[0])), row=1, col=1)
    for key, name, color in [("buy_hold", "同池买入持有", "#667085"), ("equal_weight", "同池等权调仓", "#9CA8BC"),("market","上证综指（价格指数）","#B9A888")]:
        if key in r.benchmarks:
            fig.add_trace(go.Scatter(x=r.benchmarks.date,y=r.benchmarks[key]/r.config.capital,name=name,line=dict(color=color,dash="dash")),row=1,col=1)
    if gross:
        fig.add_trace(go.Scatter(x=e.date, y=e.gross_equity/r.config.capital, name="同路径归还显式费用", line=dict(color="#8B5CF6", dash="dot")), row=1, col=1)
    if not r.decisions.empty:
        dates = sorted(set(r.decisions.signal_date) & set(e.date))
        points = e.set_index("date").loc[dates]
        fig.add_trace(go.Scatter(x=dates, y=points.equity/r.config.capital, mode="markers", name="选日期查决策",
                                marker=dict(size=3, color=PALETTE[0]), customdata=dates), row=1, col=1)
    fig.add_trace(go.Scatter(x=e.date, y=e.equity/e.equity.cummax()-1, name="回撤", fill="tozeroy", line=dict(color="#8291AA")), row=2, col=1)
    fig.update_yaxes(title="净值", row=1, col=1)
    fig.update_yaxes(title="回撤", tickformat=".0%", row=2, col=1)
    fig.update_layout(clickmode="event+select")
    if r.metrics.get("max_drawdown",0)<0:
        fig.add_vrect(x0=r.metrics["drawdown_peak"],x1=r.metrics["drawdown_trough"],fillcolor="#E4A853",opacity=.08,line_width=0,row="all",col=1)
    return style(fig, 530)


def candle_chart(snapshot, r, symbol, signal_date=None):
    b = snapshot.bars[snapshot.bars.symbol == symbol].copy()
    for window in (20,60):
        b[f"chart_ma{window}"]=b.adj_close.rolling(window).mean()*b.raw_close/b.adj_close
    b = b[(b.date >= str(r.config.start)) & (b.date <= str(r.config.end))]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.75, .25], vertical_spacing=.04)
    fig.add_trace(go.Candlestick(x=b.date, open=b.raw_open, high=b.raw_high, low=b.raw_low, close=b.raw_close,
                                 increasing_line_color="#D94A4A", decreasing_line_color="#1A9968", name="原始价格"), row=1, col=1)
    for window,color in [(20,"#EA8C28"),(60,"#8B5CF6")]:
        fig.add_trace(go.Scatter(x=b.date,y=b[f"chart_ma{window}"],name=f"调整MA{window}映射",line=dict(color=color,width=1)),row=1,col=1)
    if signal_date:
        fig.add_vline(x=signal_date,line_dash="dot",line_color="#2563EB")
    # Convert adjusted execution prices to raw chart coordinates on that date.
    fills = r.fills[r.fills.symbol == symbol]
    for side, color, shape in [("buy", "#D94A4A", "triangle-up"), ("sell", "#1A9968", "triangle-down")]:
        f = fills[fills.side == side].merge(b[["date", "raw_open", "adj_open"]], on="date") if len(fills) else pd.DataFrame()
        if len(f):
            price = f.price*f.raw_open/f.adj_open if r.config.mode == "research" else f.price
            fig.add_trace(go.Scatter(x=f.date, y=price, mode="markers", name="买入" if side=="buy" else "卖出",
                                    customdata=f.order_id, marker=dict(color=color, size=11, symbol=shape)), row=1, col=1)
    fig.add_trace(go.Bar(x=b.date, y=b.volume, marker_color="#B6C9EB", name="成交量（股）"), row=2, col=1)
    fig.update_layout(xaxis_rangeslider_visible=False, clickmode="event+select")
    fig.update_yaxes(title="原始价格（元）", row=1, col=1)
    return style(fig, 510)


def heatmap(r):
    table = monthly_returns(r.equity).pivot(index="year", columns="month", values="return").reindex(columns=range(1,13))
    fig = go.Figure(go.Heatmap(z=table.values, x=[str(x) for x in table.columns], y=[str(x) for x in table.index],
                              text=table.map(lambda x: "" if pd.isna(x) else f"{x:.1%}").values, texttemplate="%{text}",
                              colorscale=[[0,"#1A9968"],[.5,"#F6F8FB"],[1,"#D94A4A"]], zmid=0, colorbar=dict(tickformat=".0%")))
    cells=[(str(month),str(year)) for year in table.index for month in table.columns if pd.notna(table.loc[year,month])]
    fig.add_trace(go.Scatter(x=[x for x,y in cells],y=[y for x,y in cells],mode="markers",marker=dict(size=26,color="rgba(0,0,0,0.01)"),showlegend=False,hovertemplate="%{y}年%{x}月 · 点击筛选<extra></extra>"))
    fig.update_layout(clickmode="event+select")
    return style(fig, max(250, len(table)*45+100)).update_layout(hovermode="closest")
