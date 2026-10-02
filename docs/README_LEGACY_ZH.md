# 沪A策略研究室

本地中文策略研究工具。实现五种策略、分批建仓、五个操作页面、后台回测与下载、缓存、CSV导入、基准对比和实验导出。支持复权收益研究账本与受数据完整性约束的真实股数账本。当前验收进度见`docs/EXECUTION_CHECKLIST.md`。

## 启动

Windows PowerShell，在本项目目录执行：

```powershell
& 'D:/anaconda/envs/FinRL/python.exe' -m pip install -e '.[test]'
& 'D:/anaconda/envs/FinRL/python.exe' -m streamlit run app.py
```

依赖已安装后，也可在PowerShell执行`./start.ps1`一键启动。默认使用上述FinRL解释器；其他机器可传入`-PythonPath`。

浏览器打开 http://localhost:8501 。其他机器使用Python 3.10–3.12，创建环境后执行 `python -m pip install -e '.[test]'` 和 `python -m streamlit run app.py`。

复现本机已验证的Windows/Python3.10依赖组合，可先安装`requirements-lock.txt`。它只锁定本项目依赖，不导出整个FinRL环境。

## 第一次使用

1. 研究工作台点击“创建离线演示数据”，得到明确标注的合成样本；或前往“数据与实验”下载真实行情。
2. 选择股票池、策略、日期、资金与分批参数，点击“运行回测并保存实验”。
3. 回测结果查看净值、回撤、月收益、持仓与费用；点击决策点后到交易复盘查看对应日期。
4. 交易复盘选择信号日期和股票，查看筛选原因、次日订单、成交和分批计划。
5. 修改参数再运行会保存一个新实验，在策略对比选择最多4个实验。
6. 回测结果导出ZIP，包括配置、指标、净值、持仓、交易、订单、决策、计划、数据说明与独立HTML报告。

本地数据在`storage/`，不默认提交到GitHub。下载中断保留成功缓存，重新下载复用；失败不会创建“完整”快照。

## 命令行

```powershell
& 'D:/anaconda/envs/FinRL/python.exe' -m lab.cli demo
& 'D:/anaconda/envs/FinRL/python.exe' -m lab.cli download --count 100
& 'D:/anaconda/envs/FinRL/python.exe' -m lab.cli run storage/snapshots/<快照ID> --strategy momentum
& 'D:/anaconda/envs/FinRL/python.exe' -m pytest -q
```

## 规则

- S0：调整收盘价相对20日均线的偏离上穿2%入场，跌破-2%退出；指标持续高于2%不重复创建第一批。
- S1：60日动量/20日日收益标准差，要求正动量且价格>MA20>MA60。
- S2：60日日收益年化波动由低到高选择。
- S3：突破此前20日收盘高点，且当日成交额/此前20日均额至少1.5。
- S4：过去5日下跌、当前调整收盘价高于MA60，按短期跌幅排序。
- S1–S4按月末/周末/20交易日形成目标；S0每日检查。所有信号最早下一交易日开盘执行。
- 默认分40%/30%/30%三批，相邻批次成交后等待至少5个交易日再收盘检查；次日执行。单日新增买入默认不超过前一收盘净值20%。
- 日线成交是模型假设，已知停牌不成交、已知开盘涨停不买或跌停不卖。状态未知会保留限制说明。
- 研究模式使用调整价格与虚拟分数份额，比例佣金和卖出印花税、滑点进入账本；不套用真实100股整手或5元最低佣金。滑点已经进入成交价，不二次扣除。
- 成本前曲线为同一成交路径归还显式费用，没有重新投入返还费用，不能当成零成本策略重跑。

## 标准CSV

行情列：`symbol,date,raw_open,raw_high,raw_low,raw_close,adj_open,adj_high,adj_low,adj_close,volume,amount`；代码字符串，日期YYYY-MM-DD，成交量为股、成交额为元。可增加`is_st,is_suspended,limit_up,limit_down`，未知留空。

证券列：`symbol,name,exchange,board,list_date`；本项目仅接受`exchange=SSE,board=MAIN_A`。用户须依据证券基本信息验证类型。

日历：`date`一列，完整且排序的交易日。行情内部缺口不能按零收益填充；只有来源证实的停牌可沿用估值价。

## 数据与限制

免费AKShare（东方财富行情）为首选，BaoStock提供备用与状态字段，均需网络可达。本地下载验证不能保证未来接口一直可用。程序不需要付费AI调用或券商账户。

本机已实测：AKShare短区间成功、长区间出现断连；BaoStock完成100股198,400条真实日线与指数下载。当前建议下载时选择BaoStock，或命令行增加`--source baostock`。暂无需购买API订阅。

默认池来自下载时存续的沪A主板股票，按代码选择，存在幸存者及事后选择偏差。不能把固定观察池结果称为历史全沪A无偏收益。合成演示从不作为真实研究报告。

历史ST、涨跌停、分红到账、送转和退市回收信息需要分别验证；免费行情快照尚未补齐全部事件，因此不能直接开启严格真实股数标记。导入完整且有核验依据的事件与状态后，可使用原始价格、整手、最低佣金、T+1及公司行动账本。字段和边界见`docs/DATA_DICTIONARY.md`。收益目标不作为软件测试通过条件。

上证综指是价格指数参考，不是与含分红策略完全同口径的可投资基准。参数网格固定使用2022年验证集；默认全区间报告是回顾性探索，不宣称前瞻实盘成绩。

规划与实时验收记录分别见`IMPLEMENTATION_PLAN_V2.md`及`docs/EXECUTION_CHECKLIST.md`。

### 严格股数CSV教学样本

`examples/strict_synthetic/`提供行情、证券、日历、公司行动及核验声明的完整CSV/JSON样本。它们全部为合成教学数据，可在CSV导入页导入，再使用同目录config.yaml的参数运行。样本展示900股、最低佣金、每股1元现金和1送1的入账过程；不是实际证券事件。运行`python scripts/build_csv_example.py`可重新生成样本及完整报告。

最大回撤卡片显示正的损失比例；导出的`max_drawdown`保留负的水下收益口径。`unrealized_pnl`按期末剩余FIFO批次估值，真实股数模式包括分摊股息收入，不扣假设期末卖出费用。后台任务状态保存在`storage/jobs/jobs.sqlite`，JSON保留为诊断副本。

## 报告与验证

完整验收记录见[验证说明](docs/VALIDATION.md)。五策略实际报告目录及指标在[计算结果清单](docs/evidence/computed_reports.csv)，对应`storage/runs/`中均有`report.html`和`export.zip`。这些由本机真实行情计算的文件用于本地研究，不默认上传GitHub。

![100股阈值策略工作台](docs/screenshots/workbench-100-stock.png)

![真实回测结果](docs/screenshots/results-1440.png)
