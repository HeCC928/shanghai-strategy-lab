"""Run with: python -m streamlit run app.py"""
from datetime import date
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lab.charts import PALETTE, candle_chart, equity_chart, heatmap, style
from lab.config import Config, STRATEGIES
from lab.data import Snapshot
from lab.demo import synthetic_snapshot
from lab.research import run_experiment
from lab.store import list_runs, load_result, save_result
from lab.shares import strict_data_issues
from lab.jobs import start_job,read_job,cancel_job,running_jobs
from lab.explanations import explain_decision,localized,METRIC_LABELS

st.set_page_config(page_title="沪A策略研究室", page_icon="📈", layout="wide")
st.markdown("""<style>
.block-container{padding-top:2rem;max-width:1480px} h1{font-size:28px!important;letter-spacing:.02em}
div[data-testid="stMetric"]{background:white;border:1px solid #E3E8F0;border-radius:10px;padding:15px}
div[data-testid="stMetricValue"]{font-size:24px} [data-testid="stSidebar"]{border-right:1px solid #E3E8F0}
</style>""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def get_snapshot(path, schema_version=2):
    return Snapshot.load(path)


@st.cache_data(show_spinner=False)
def get_result(path, schema_version=2):
    return load_result(path)


def snapshots():
    items = {}
    for p in sorted(Path("storage/snapshots").glob("*/manifest.json")):
        m = json.loads(p.read_text(encoding="utf-8"))
        items[str(p.parent)] = m.get("label", p.parent.name)+" · "+p.parent.name[:6]
    return items


def select_run(path):
    st.session_state["result_path"] = str(path)
    st.session_state.pop("review_date", None)
    st.session_state.pop("review_symbol", None)


def current():
    if not st.session_state.get("result_path"):
        st.info("先在研究工作台运行一次回测，或从数据与实验页加载已保存实验。")
        return None
    return get_result(st.session_state.result_path)


def parameter_choice(label,options,current):
    return st.selectbox(label,options,index=options.index(current) if current in options else 0)


def metrics(r, compact=False):
    labels = [("累计收益", "total_return", ".2%"), ("年化收益", "cagr", ".2%"),
              ("Sharpe", "sharpe", ".2f"), ("最大回撤", "max_drawdown", ".2%"),
              ("费用（元）", "fees", ",.0f"), ("成交笔数", "fills", ",d")]
    if not compact:
        labels[-1] = ("年化超额", "annual_excess", ".2f")
    columns = st.columns(3)+st.columns(3) if compact else st.columns(6)
    for col, (label, key, fmt) in zip(columns, labels):
        value = r.metrics.get(key)
        if key == "annual_excess" and value is not None: value *= 100
        if key == "max_drawdown" and value is not None: value = abs(value)
        col.metric(label, "N/A" if value is None else format(value, fmt),help="相对同池买入持有的CAGR差，单位：百分点。" if key=="annual_excess" else None)


st.sidebar.markdown("### 沪A策略研究室")
st.sidebar.caption("SHANGHAI STRATEGY LAB")
page = st.sidebar.radio("研究导航", ["研究工作台", "回测结果", "交易复盘", "策略对比", "数据与实验"], label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.caption("日频 · 收盘形成信号 · 次日开盘执行")
st.sidebar.caption("本地研究工具 / 不连接真实委托")
if st.session_state.get("result_path"):
    st.sidebar.success("已加载实验")
    st.sidebar.caption(Path(st.session_state.result_path).name)

st.title(page)

jobs=running_jobs()
active_jobs=[x for x in jobs if x["state"] in ("queued","running","cancelling")]
busy=bool(active_jobs)
if busy and not st.session_state.get("active_job"):
    st.session_state.active_job=active_jobs[0]["path"]


@st.fragment(run_every="2s")
def job_panel():
    path=st.session_state.get("active_job")
    if not path: return
    job=read_job(path)
    if job["state"] in ("queued","running","cancelling"):
        st.progress(job.get("progress",0.),text=job.get("message","处理中"))
        st.caption("任务在后台运行，可切换页面查看已有实验。")
        if st.button("取消当前任务",key="cancel_job"):
            cancel_job(path)
            st.info("已请求取消，当前数据请求结束后停止；不会删除成功缓存。")
    elif job["state"]=="completed":
        st.success("本次任务已完成并保存。")
        if st.session_state.get("consumed_job")!=path:
            st.session_state.consumed_job=path
            if job["kind"]=="run": select_run(job["output"])
            elif job["kind"]=="sensitivity": st.session_state.sensitivity_path=job["output"]
            st.rerun()
    else:
        st.error("本次任务"+job["state"]+"："+job.get("message",""))


job_panel()

if page == "研究工作台":
    st.caption("把投资想法写成规则，用同一套数据和账本检验。")
    catalog = snapshots()
    if not catalog:
        st.info("还没有本地数据。可先创建离线合成演示，或前往数据与实验下载真实日线。")
        if st.button("创建离线演示数据", type="primary"):
            with st.spinner("生成清楚标注的合成行情样本…"):
                synthetic_snapshot().save()
            st.rerun()
    else:
        draft=Config(**st.session_state.get("draft_config",{}))
        left, right = st.columns([1, 1.7], gap="large")
        with left:
            source_options=list(catalog)
            previous_source=st.session_state.get("draft_source",source_options[0])
            source_path = st.selectbox("股票池 / 数据快照", source_options,index=source_options.index(previous_source) if previous_source in source_options else 0, format_func=catalog.get)
            s = get_snapshot(source_path)
            strategy = st.selectbox("选股策略", list(STRATEGIES),index=list(STRATEGIES).index(draft.strategy) if draft.strategy in STRATEGIES else 0, format_func=STRATEGIES.get)
            mode = st.selectbox("记账模式",["research","shares"],index=0 if draft.mode=="research" else 1,format_func=lambda x:"复权收益研究模式" if x=="research" else "真实股数模式（需数据验收）")
            a, b = st.columns(2)
            begin = a.date_input("开始日期", draft.start)
            end = b.date_input("结束日期", draft.end)
            capital = st.number_input("初始资金（元）", min_value=1000., value=float(draft.capital), step=10000.)
            a, b = st.columns(2)
            top_n = a.selectbox("最多持有", [5,10,15,20], index=[5,10,15,20].index(draft.top_n) if draft.top_n in [5,10,15,20] else 1)
            max_weight = b.number_input("单票权重上限（%）", 1.,100.,draft.max_weight*100,1.)/100
            rebalance = st.selectbox("选股更新周期（阈值策略每日检查）", ["monthly","weekly","20d"],index=["monthly","weekly","20d"].index(draft.rebalance), format_func=lambda x:{"monthly":"自然月末","weekly":"每周末","20d":"每20个交易日"}[x])
            staging = st.toggle("分三批建仓：40% / 30% / 30%", value=draft.staging)
            tranche_gap = st.number_input("相邻批次至少间隔（交易日）", 1,100,draft.tranche_gap)
            params = {}
            with st.expander("策略参数", expanded=True):
                if strategy == "threshold":
                    params["threshold_ma"] = st.number_input("均线窗口", 2,250,draft.threshold_ma)
                    params["entry_threshold"] = st.number_input("上穿入场线（%）", value=draft.entry_threshold*100, step=.5)/100
                    params["exit_threshold"] = st.number_input("跌破退出线（%）", value=draft.exit_threshold*100, step=.5)/100
                elif strategy == "momentum":
                    params["momentum_window"] = parameter_choice("动量窗口", [20,40,60,120],draft.momentum_window)
                    params["vol_window"] = parameter_choice("波动窗口", [20,40,60],draft.vol_window)
                    params["short_ma"] = parameter_choice("短均线", [10,20,30],draft.short_ma)
                    params["long_ma"] = parameter_choice("长均线", [40,60,120],draft.long_ma)
                elif strategy == "low_vol":
                    params["low_vol_window"] = parameter_choice("低波动窗口", [20,60,120],draft.low_vol_window)
                elif strategy == "breakout":
                    params["breakout_window"] = parameter_choice("突破窗口（不含当天）", [20,40,60],draft.breakout_window)
                    params["amount_multiple"] = parameter_choice("成交额倍数", [1.2,1.5,2.],draft.amount_multiple)
                elif strategy == "reversal":
                    params["reversal_window"] = parameter_choice("反转窗口", [3,5,10],draft.reversal_window)
                    params["long_ma"] = parameter_choice("趋势均线", [40,60,120],draft.long_ma)
            with st.expander("资金、成本与数据过滤"):
                params["daily_buy_cap"] = st.number_input("单日买入上限（净值%）",1.,100.,draft.daily_buy_cap*100)/100
                params["commission"] = st.number_input("佣金率（%）",0.,1.,draft.commission*100,format="%.3f")/100
                params["minimum_commission"] = st.number_input("每笔最低佣金（元，仅真实股数模式）",0.,1000.,float(draft.minimum_commission))
                params["slippage_bps"] = st.selectbox("单边滑点（基点）",[0,5,10,20],index=[0,5,10,20].index(draft.slippage_bps) if draft.slippage_bps in [0,5,10,20] else 1)
                params["min_amount"] = st.number_input("20日平均成交额下限（万元）",0.,100000.,draft.min_amount/10000)*10000
                params["min_history"] = st.number_input("最少上市及行情交易日",20,500,max(20,draft.min_history))
                params["exclude_st"] = st.checkbox("排除历史ST（要求状态完整）",value=draft.exclude_st)
                params["plan_lifetime"] = st.number_input("建仓计划有效交易日",1,250,draft.plan_lifetime)
                params["max_attempts"] = st.number_input("每批最多尝试执行次数",1,20,draft.max_attempts)
                params["risk_free"] = st.number_input("年无风险收益率（%）",0.,50.,float(draft.risk_free*100))/100
                params["participation"] = st.number_input("单笔占历史平均成交额上限（%）",.1,100.,draft.participation*100)/100
            try:
                config = Config(**{**draft.model_dump(),**params,"strategy":strategy,"mode":mode,"start":begin,"end":end,"capital":capital,"top_n":top_n,"max_weight":max_weight,
                                "rebalance":rebalance,"staging":staging,"tranche_gap":tranche_gap})
                st.session_state.draft_config=config.model_dump(mode="json")
                st.session_state.draft_source=source_path
            except ValueError as exc:
                config = None
                st.error(str(exc))
            run_clicked = st.button("运行回测并保存实验", type="primary", disabled=config is None or busy, width="stretch")
        with right:
            st.subheader("本次研究设置")
            st.info(s.manifest.get("label", "数据快照"))
            st.write(f"**{len(s.instruments)}只股票** · {s.bars.date.min()} — {s.bars.date.max()} · {len(s.bars):,}条日线")
            explanations = {
                "threshold":"收盘价相对均线的偏离上穿入场线时创建计划；条件持续成立才继续加仓，跌破退出线则停止买入并退出。",
                "momentum":"选择上涨趋势中，近期收益相对于波动更强的股票。",
                "low_vol":"按历史收益波动从低到高选择，观察是否改善组合回撤。",
                "breakout":"寻找收盘价突破此前高点、且成交额放大的股票；没有候选时保留现金。",
                "reversal":"选择中期趋势仍在、近期出现回落的股票，检验短期反弹假设。"}
            st.write(explanations[strategy])
            if staging:
                st.write(f"**建仓节奏：** 40% → 等待至少{tranche_gap}个交易日并复查 → 30% → 再复查 → 30%。")
            if mode=="research":
                st.caption("复权收益研究模式：分数份额、比例佣金及卖出印花税；不模拟整手与真实分红到账。")
            elif config:
                issues=strict_data_issues(s,config)
                if issues:
                    st.warning("该快照尚不能执行真实股数回测，需补齐以下数据。研究模式仍可使用。")
                    with st.expander("数据验收缺口",expanded=True):
                        for issue in issues: st.write("• "+issue)
                else: st.success("真实股数数据结构与覆盖声明通过。原始价、整手、T+1、分红和送转进入账本。")
            if top_n*max_weight < 1:
                st.info(f"最多目标投入{min(1,top_n*max_weight):.0%}，其余保留现金；候选不足还会增加现金比例。")
            if st.session_state.get("result_path"):
                old = current()
                if config and (old.config != config or old.manifest["snapshot_id"] != s.digest()):
                    st.warning("参数已修改，已有结果尚未更新。点击运行后创建新实验。")
                else:
                    st.success("当前参数与已保存实验一致。")
                metrics(old,compact=True)
                st.plotly_chart(equity_chart(old), width="stretch", key="work_preview")
            else:
                st.dataframe(s.instruments[["symbol","name","list_date"]].rename(columns={"symbol":"代码","name":"名称","list_date":"上市日期"}), hide_index=True, width="stretch")
            with st.expander("数据与研究限制"):
                for line in s.manifest.get("limitations",[]): st.write("• "+line)
        if run_clicked:
            try:
                st.session_state.active_job=start_job("run",{"config":config.model_dump(mode="json"),"snapshot":str(Path(source_path).resolve()),"output_root":str(Path("storage").resolve())})
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

elif page == "回测结果":
    r = current()
    if r:
        st.caption(f"{STRATEGIES.get(r.config.strategy,r.config.strategy)} · {r.config.start} — {r.config.end} · {r.manifest.get('label','')} · 已保存实验")
        metrics(r)
        with st.expander("筛选图表日期／另算区间绩效"):
            a_range,b_range=st.columns(2)
            range_start=a_range.date_input("图表起日",r.config.start,key="chart_start_"+st.session_state.result_path)
            range_end=b_range.date_input("图表止日",r.config.end,key="chart_end_"+st.session_state.result_path)
            if st.button("计算所选区间绩效"):
                try:
                    from lab.metrics import period_metrics
                    st.json(period_metrics(r.equity,range_start,range_end,r.config.risk_free))
                except ValueError as exc:st.warning(str(exc))
            st.caption("上方指标始终对应完整实验；区间收益从首个选中交易日前一收盘净值起算。缩放图表不会改变全期结果。")
        gross = st.checkbox("叠加同一路径的成本前曲线（只归还显式费用）")
        result_figure=equity_chart(r,gross)
        if range_start<=range_end:result_figure.update_xaxes(range=[str(range_start),str(range_end)])
        event = st.plotly_chart(result_figure, width="stretch",on_select="rerun",selection_mode="points",key="result_equity")
        points = event.selection.points
        if points:
            chosen = str(points[-1].get("x",""))[:10]
            st.session_state["selected_signal_date"] = chosen
            st.info(f"已选择 {chosen}；交易复盘页将使用该日期附近的决策。")
        if r.fills.empty: st.info("本实验没有成交；可查看过滤原因，不会填造胜率。")
        a,b,c,d = st.tabs(["月度与年度收益","持仓与现金","交易与费用","详细指标"])
        with a:
            monthly=st.plotly_chart(heatmap(r),width="stretch",on_select="rerun",key="monthly_heatmap")
            if monthly.selection.points:
                point=monthly.selection.points[-1]
                if "x" in point and "y" in point:
                    prefix=f"{str(point['y'])[:4]}-{int(point['x']):02d}"
                    st.caption(f"{prefix} 成交记录")
                    st.dataframe(r.fills[r.fills.date.str.startswith(prefix)],hide_index=True,width="stretch")
                    st.caption(f"{prefix} 持仓记录")
                    st.dataframe(localized(r.positions[r.positions.date.str.startswith(prefix)]),hide_index=True,width="stretch")
            yearly=go.Figure()
            frames=[("策略",r.equity.set_index("date").equity)]
            frames += [(label,r.benchmarks.set_index("date")[key]) for key,label in [("buy_hold","同池买入持有"),("equal_weight","同池等权调仓")] if key in r.benchmarks]
            for label,series in frames:
                returns=series.pct_change(fill_method=None).dropna()
                annual=(1+returns).groupby(pd.to_datetime(returns.index).year).prod()-1
                yearly.add_bar(x=annual.index.astype(str),y=annual.values,name=label)
            yearly.update_yaxes(tickformat=".0%",title="年度复合收益")
            st.plotly_chart(style(yearly,330),width="stretch")
        with b:
            if len(r.positions):
                p = r.positions.pivot(index="date",columns="symbol",values="weight").fillna(0)
                p = p.reindex(r.equity.loc[~r.equity.initial,"date"],fill_value=0)
                fig = go.Figure()
                if len(p.columns)>20:
                    main=p.mean().nlargest(10).index.tolist()
                    p["其他"]=p.drop(columns=main).sum(axis=1)
                    p=p[main+["其他"]]
                for symbol in p.columns:
                    fig.add_scatter(x=p.index,y=p[symbol],name=symbol,stackgroup="weights")
                fig.add_scatter(x=r.equity.date,y=r.equity.cash/r.equity.equity,name="现金",stackgroup="weights",line_color="#D9E1EB")
                if r.equity.receivable.max()>0:
                    fig.add_scatter(x=r.equity.date,y=r.equity.receivable/r.equity.equity,name="应收股息",stackgroup="weights",line_color="#D4B5F3")
                fig.update_yaxes(tickformat=".0%")
                st.plotly_chart(style(fig),width="stretch")
            st.dataframe(localized(r.positions),hide_index=True,width="stretch")
        with c:
            if len(r.fills):
                labels={"commission":"佣金","stamp_tax":"印花税","transfer_fee":"过户费","slippage_loss":"估计滑点（已计入价格）"}
                costs=pd.DataFrame({"项目":list(labels.values()),"金额（元）":[r.fills[k].sum() for k in labels]})
                st.dataframe(costs,hide_index=True)
            st.dataframe(localized(r.fills),hide_index=True,width="stretch")
            if not r.corporate_events.empty:
                st.subheader("公司行动入账")
                st.dataframe(r.corporate_events,hide_index=True,width="stretch")
        with d:
            st.json(r.metrics)
            st.json(r.timings)
            if r.benchmark_metrics:
                st.json(r.benchmark_metrics)
            if r.metrics["short_period"]: st.caption("不足一年，年化数值可能被短区间放大。")
        st.download_button("导出报告与全部结果 ZIP",Path(st.session_state.result_path,"export.zip").read_bytes(),file_name="strategy_report.zip",mime="application/zip",type="primary")

elif page == "交易复盘":
    r=current()
    if r:
        signal_dates=sorted(r.decisions.signal_date.unique())
        if signal_dates:
            default=st.session_state.get("selected_signal_date",signal_dates[0])
            index=min(range(len(signal_dates)),key=lambda i:abs((pd.Timestamp(signal_dates[i])-pd.Timestamp(default)).days))
            day=st.selectbox("信号日期（收盘）",signal_dates,index=index,key="review_date")
            ranks=r.decisions[r.decisions.signal_date==day].reset_index(drop=True)
            st.caption(f"下一交易日执行：{ranks.execution_date.iloc[0]}。排名表示信号日情况，不能代表已成交。")
            valid=ranks[ranks.score.notna()].head(20)
            if len(valid):
                rank_plot=go.Figure(go.Bar(x=valid.score,y=valid.symbol,orientation="h",marker_color=[PALETTE[0] if x>0 else "#C2CBD9" for x in valid.target_weight],customdata=valid.symbol))
                rank_plot.update_yaxes(autorange="reversed",type="category")
                rank_plot.update_layout(clickmode="event+select")
                ranking_event=st.plotly_chart(style(rank_plot,330),width="stretch",on_select="rerun",key=f"ranking_{day}")
            else: ranking_event=None
            selection=st.dataframe(localized(ranks),hide_index=True,width="stretch",on_select="rerun",selection_mode="single-row",key="rank_table")
            symbols=ranks.symbol.tolist()
            picked=st.session_state.get("review_symbol",symbols[0])
            if picked not in symbols: picked=symbols[0]
            table_token=(r.manifest.get("run_id"),day,tuple(selection.selection.rows))
            if selection.selection.rows and st.session_state.get("last_rank_table")!=table_token:
                picked=symbols[selection.selection.rows[0]]
                st.session_state.last_rank_table=table_token
            if ranking_event and ranking_event.selection.points:
                selected_symbol=ranking_event.selection.points[-1].get("customdata")
                bar_token=(r.manifest.get("run_id"),day,selected_symbol)
                if selected_symbol in symbols and st.session_state.get("last_rank_bar")!=bar_token:
                    picked=selected_symbol
                    st.session_state.last_rank_bar=bar_token
            symbol=st.selectbox("查看股票",symbols,index=symbols.index(picked),key=f"symbol_{day}_{picked}")
            st.session_state.review_symbol=symbol
            st.info(explain_decision(ranks[ranks.symbol==symbol].iloc[0],r.config))
            snapshot_path=Path("storage/snapshots")/r.manifest["snapshot_id"][:16]
            if snapshot_path.exists():
                s=get_snapshot(str(snapshot_path))
                st.caption("均线先在调整价格上计算，再按当日比例映射到原始价格；虚线标记所选信号日。")
                event=st.plotly_chart(candle_chart(s,r,symbol,day),width="stretch",on_select="rerun",selection_mode="points",key=f"candle_{symbol}")
                if event.selection.points:
                    order_id=event.selection.points[-1].get("customdata")
                    if order_id and "order_id" in r.fills: st.dataframe(r.fills[r.fills.order_id==order_id],hide_index=True)
            else: st.warning("原始快照不在本机；可查看已保存交易，但不能重建K线。")
            a,b,c=st.tabs(["为什么买／为什么没买","成交明细","分批计划"])
            with a:
                st.dataframe(localized(ranks[ranks.symbol==symbol]),hide_index=True,width="stretch")
                st.dataframe(localized(r.orders[(r.orders.symbol==symbol)&(r.orders.signal_date==day)] if len(r.orders) else r.orders),hide_index=True,width="stretch")
            with b: st.dataframe(localized(r.fills[r.fills.symbol==symbol]),hide_index=True,width="stretch")
            with c: st.dataframe(localized(r.plans[r.plans.symbol==symbol]),hide_index=True,width="stretch")
        else: st.info("没有可用决策记录。请检查历史长度。")

elif page == "策略对比":
    runs=list_runs()
    if runs.empty: st.info("先保存两个以上实验，再比较策略或参数。")
    else:
        options=runs.run_id.tolist()
        labels={row.run_id:f"{STRATEGIES.get(row.strategy,row.strategy)} · {row.start}~{row.end} · {row.run_id}" for row in runs.itertuples()}
        comparison_default=[x for x in st.session_state.get("comparison_saved",options[:min(2,len(options))]) if x in options]
        selected=st.multiselect("选择最多4个已保存实验",options,default=comparison_default,format_func=labels.get,max_selections=4,key="compare_selection")
        st.session_state.comparison_saved=selected
        compare=[get_result(str(Path("storage/runs")/x)) for x in selected]
        fig=go.Figure()
        for i,r in enumerate(compare):
            fig.add_scatter(x=r.equity.date,y=r.equity.equity/r.config.capital,name=f"{i+1} {STRATEGIES.get(r.config.strategy,r.config.strategy)}",line_color=PALETTE[i])
        if compare:
            st.plotly_chart(style(fig),width="stretch")
            st.dataframe(pd.DataFrame([{**r.metrics,"实验":selected[i]} for i,r in enumerate(compare)]).rename(columns=METRIC_LABELS),hide_index=True,width="stretch")
            with st.expander("各实验年度收益拆解"):
                annual_chart=go.Figure()
                for i,r in enumerate(compare):
                    ret=r.equity.set_index(pd.to_datetime(r.equity.date)).equity.pct_change(fill_method=None).dropna()
                    annual=(1+ret).groupby(ret.index.year).prod()-1
                    annual_chart.add_bar(x=annual.index.astype(str),y=annual.values,name=f"{i+1} {STRATEGIES.get(r.config.strategy,r.config.strategy)}",marker_color=PALETTE[i])
                annual_chart.update_yaxes(tickformat=".0%")
                st.plotly_chart(style(annual_chart,330),width="stretch")
            settings=pd.DataFrame([{**r.config.model_dump(mode="json"),"snapshot_id":r.manifest["snapshot_id"]} for r in compare],index=[f"实验{i+1}" for i in range(len(compare))]).T
            st.subheader("配置差异")
            differences=settings[settings.astype(str).nunique(axis=1)>1]
            if len(differences):
                st.warning("存在以下配置或数据差异；解释结果时需要同时考虑。")
                st.dataframe(differences,width="stretch")
            else: st.success("配置与数据一致。")
            with st.expander("参数敏感性（当前实验区间）"):
                st.caption("只对第一个选中实验做3×3有限网格，保留原成本与股票池；不会搜索2023–2025留出集的最优参数。")
                first=compare[0]
                snapshot_path=Path("storage/snapshots")/first.manifest["snapshot_id"][:16]
                if st.button("运行验证集参数网格",disabled=busy or not snapshot_path.exists()):
                    try:
                        st.session_state.active_job=start_job("sensitivity",{"config":first.config.model_dump(mode="json"),"snapshot":str(snapshot_path.resolve())})
                        st.rerun()
                    except Exception as exc:st.error(str(exc))
                grid_path=st.session_state.get("sensitivity_path")
                if grid_path and Path(grid_path).exists():
                    from lab.sensitivity import GRIDS
                    request=json.loads((Path(grid_path).parent/"request.json").read_text(encoding="utf-8"))
                    grid_config=Config(**request["payload"]["config"])
                    st.caption("已计算网格对应："+STRATEGIES[grid_config.strategy]+"；改变选择不会重算旧网格。")
                    grid=pd.read_csv(grid_path)
                    x,_,y,_=GRIDS[grid_config.strategy]
                    pivot=grid.pivot(index=y,columns=x,values="sharpe")
                    figure=go.Figure(go.Heatmap(x=pivot.columns,y=pivot.index,z=pivot.values,text=pivot.round(2).values,texttemplate="%{text}",colorbar=dict(title="Sharpe")))
                    figure.add_scatter(x=grid[x],y=grid[y],mode="markers",marker=dict(size=35,color="rgba(0,0,0,0.01)"),customdata=grid.index,showlegend=False,hovertemplate=f"{x}=%{{x}}<br>{y}=%{{y}}<extra></extra>")
                    figure.update_layout(clickmode="event+select")
                    figure.update_xaxes(title=x,type="category")
                    figure.update_yaxes(title=y,type="category")
                    picked_grid=st.plotly_chart(style(figure,320).update_layout(hovermode="closest"),width="stretch",on_select="rerun",key="parameter_grid_"+str(grid_path))
                    st.dataframe(grid,hide_index=True,width="stretch")
                    grid_key="grid_choice_"+str(grid_path)
                    if picked_grid.selection.points:
                        grid_pick=picked_grid.selection.points[-1].get("customdata")
                        grid_token=(str(grid_path),grid_pick)
                        if grid_pick is not None and st.session_state.get("last_grid_point")!=grid_token:
                            st.session_state[grid_key]=int(grid_pick)
                            st.session_state.last_grid_point=grid_token
                    row=st.selectbox("选择一组参数用于新实验",range(len(grid)),key=grid_key,format_func=lambda i:f"{x}={grid.iloc[i][x]}, {y}={grid.iloc[i][y]}")
                    if st.button("保存该组参数的验证集实验",disabled=busy):
                        params={**grid_config.model_dump(mode="json"),x:float(grid.iloc[row][x]),y:float(grid.iloc[row][y])}
                        st.session_state.active_job=start_job("run",{"config":Config(**params).model_dump(mode="json"),"snapshot":request["payload"]["snapshot"],"output_root":str(Path("storage").resolve())})
                        st.rerun()

elif page == "数据与实验":
    data_tab, import_tab, history_tab = st.tabs(["数据下载与缓存","CSV导入","实验历史"])
    with data_tab:
        catalog=snapshots()
        if catalog:
            st.dataframe(pd.DataFrame([{"快照":Path(p).name,"说明":label} for p,label in catalog.items()]),hide_index=True,width="stretch")
            inspect_path=st.selectbox("检查数据覆盖",list(catalog),format_func=catalog.get)
            inspect=get_snapshot(inspect_path)
            st.dataframe(inspect.coverage_report(),hide_index=True,width="stretch")
            with st.expander("来源、数据版本及完整性说明"):st.json(inspect.manifest)
        with st.expander("下载真实沪A日线",expanded=not bool(catalog)):
            st.caption("免费接口。默认按代码选取当前存续主板股票，属于固定观察池，存在幸存者偏差。下载后回测无需联网。")
            provider=st.selectbox("数据来源",["akshare","baostock"])
            stock_text=st.text_area("自选代码（逗号分隔，留空按代码选取）",placeholder="600000,600004,600009")
            count=st.number_input("留空时下载股票数量",1,1000,100)
            a,b=st.columns(2)
            ds=a.date_input("下载起日（含指标预热）",date(2017,1,1))
            de=b.date_input("下载止日",date(2025,3,7))
            if st.button("下载并验证数据",type="primary",disabled=busy):
                try:
                    symbols=[x.strip() for x in stock_text.replace("，",",").split(",") if x.strip()]
                    st.session_state.active_job=start_job("download",{"symbols":symbols or None,"count":count,"start":str(ds),"end":str(de),"source":provider})
                    st.rerun()
                except Exception as exc: st.error(str(exc))
        if st.button("创建或恢复离线合成演示"):
            synthetic_snapshot().save()
            st.success("合成演示数据已就绪，前往研究工作台运行。")
        report=Path("storage/downloads/last_download_report.json")
        if report.exists():
            with st.expander("最近下载覆盖与失败记录"):st.json(json.loads(report.read_text(encoding="utf-8")))
    with import_tab:
        st.write("分别导入标准行情、证券信息与交易日历。字段说明见 README；校验失败不会创建快照。")
        bars_file=st.file_uploader("行情CSV",type="csv",key="bars_upload")
        meta_file=st.file_uploader("证券信息CSV",type="csv",key="meta_upload")
        cal_file=st.file_uploader("交易日历CSV（date列，仅含交易日）",type="csv",key="cal_upload")
        action_file=st.file_uploader("公司行动CSV（真实股数模式可选补充）",type="csv",key="action_upload")
        manifest_file=st.file_uploader("数据说明JSON（含逐股票公司行动覆盖核验记录）",type="json",key="manifest_upload")
        if st.button("验证并导入",disabled=not all([bars_file,meta_file,cal_file])):
            try:
                bars=pd.read_csv(bars_file,dtype={"symbol":str,"date":str})
                meta=pd.read_csv(meta_file,dtype=str)
                calendar=pd.read_csv(cal_file,dtype=str).date.tolist()
                actions=pd.read_csv(action_file,dtype={"symbol":str,"record_date":str,"ex_date":str,"pay_date":str,"share_trade_date":str}) if action_file else pd.DataFrame()
                manifest=json.load(manifest_file) if manifest_file else {}
                manifest.pop("snapshot_id",None)
                s=Snapshot(bars,meta,calendar,{**manifest,"source":"csv","label":"用户CSV固定观察池","limitations":manifest.get("limitations",[])+["用户导入，来源与历史覆盖由使用者核实"]},actions)
                path=s.save()
                st.success(f"已保存快照 {path.name}")
            except Exception as exc: st.error(str(exc))
    with history_tab:
        runs=list_runs()
        st.dataframe(runs,hide_index=True,width="stretch")
        if not runs.empty:
            choice=st.selectbox("加载已保存实验",runs.run_id)
            if st.button("加载实验"):
                select_run(Path("storage/runs")/choice)
                st.success("已加载，可前往回测结果或交易复盘。")
