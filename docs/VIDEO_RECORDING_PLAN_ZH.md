# 三分钟项目介绍视频：录制方案与英文旁白

适用项目：Shanghai A-Share Strategy Lab。方案日期：2026-09-27。

建议成片：约 3 分钟、16:9 横屏、英文界面与英文旁白，可配英文字幕。无需出镜，以实际页面录屏为主。这里提供录制设计，不包含已生成的视频文件。

## 1. 视频想让观众记住什么

这是一个把简单投资规则、可追溯的交易执行和交互式研究整合在一起的金融科技平台。

用三个可见动作支撑这个介绍：

1. 从净值和月度收益进入具体交易。
2. 展开一笔交易，看到信号、分批计划、成交和成本。
3. 对比已保存实验并打开可分享的英文研究报告。

策略收益用于给项目提供具体案例；产品展示的重点是“能操作、能解释、能保留研究证据”。

## 2. 录制前准备好的结果

以下结果已经存在。2026-09-27 核对了配置、指标及主要结果文件，无须为了录视频重新搜索参数或计算回测。

| 用途 | 实验 ID / 下拉框后缀 | Sharpe | 最大回撤 | 净收益 |
|---|---|---:|---:|---:|
| 主案例：MA30，入场 +2%，退出 −2% | `20260917T142156_a1c71212` / `a1c71212` | 1.48 | 19.3% | 32.3% |
| 单参数变化：入场改为 +2.5% | `20260917T235036_8f24a0a8` / `8f24a0a8` | 0.95 | 19.6% | 18.7% |
| 按月滚动选参案例 | `20260917T233947_eee9c020` / `eee9c020` | 1.30 | 13.7% | 23.6% |

三者均覆盖 2025-07-01 至 2026-06-30。主案例和 +2.5% 案例的已保存配置仅入场阈值不同，可用于说明参数敏感性。滚动案例用于展示研究协议，应单独解释。

### 开拍前的具体操作

1. 双击项目根目录 `Start Lab.cmd`，保持服务窗口运行。
2. 打开 `http://127.0.0.1:8765`，点击 **Featured case**。
3. 确认首页为 1.48 / 19.3% / 32.3%，没有运行中的任务或错误提示。
4. 进入 Trade Replay 预演一次：Month = `2025-07`，Stock code = `600106`，打开 `2025-07-23` 的买入。
5. 进入 Walk-Forward，确认出现 **RECORDED ROLLING EXPERIMENT**，并能切换 July / August。
6. 点击 Featured case，进入 Compare & Archive，预演勾选后缀 `8f24a0a8` 和 `eee9c020` 的实验。最多显示这三条曲线，避免画面拥挤。
7. 在另一个标签页预先打开 `http://127.0.0.1:8765/api/runs/20260917T142156_a1c71212/report/preview`。它对应精选实验，不受主页面临时切换实验影响。
8. 回到主标签页，点击 Featured case，准备录制首页。

也可直接打开 `storage/showcase/featured-report.html` 作为报告备选。应用未启动时，这份报告仍可离线查看。

## 3. 录制方式

- 建议输出 1920 × 1080、30 fps；如果屏幕或窗口更小，优先保持文字可读，不强行缩放出模糊画面。
- 浏览器以 100% 缩放开始，根据实际预览调整。不要为了把整页塞进一屏而把文字缩得过小。
- 录制前关闭无关标签、通知和书签栏，避免无关内容进入画面。
- 分成七段录，每段开始和结束各停留约两秒，剪辑时裁去多余等待。
- 推荐先录画面，再单独录旁白；中途口误时只重录当前段。
- 光标一次只指向一个重点，点击后留时间让观众阅读，不连续乱动。
- 简单切换镜头即可；最多对指标和交易抽屉做轻微放大。背景音乐可以省略。

时间表是参考。按清晰的语速录制，宁可略超过三分钟，也不要把英文旁白加速到难以理解。

## 4. 分镜、操作与可直接朗读的旁白

### 镜头 1：项目是什么（0:00–0:15）

**画面**：Overview 全景，停留数秒；鼠标不遮挡标题和指标。可添加简洁片头字幕：

`Shanghai A-Share Strategy Lab`

`Interactive FinTech Research Platform`

**英文旁白**：

> This is Shanghai A-Share Strategy Lab, an interactive research platform I built to make trading rules and their outcomes easier to understand. It brings strategy design, portfolio analysis and trade explanations into one local workspace.

### 镜头 2：结果可以追溯（0:15–0:35）

**画面**：依次指向 Sharpe、最大回撤和净值曲线，悬停一个日期点。画面保留研究期间和 target-period 标识，不必把四个指标都念一遍。

**英文旁白**：

> The featured case uses one hundred Shanghai stocks. Over July 2025 to June 2026, it recorded a Sharpe ratio of 1.48 and a maximum drawdown of 19.3 percent. This is a retrospectively selected backtest, rather than an independent holdout result.

**字幕重点**：`100 stocks · Sharpe 1.48 · Max drawdown 19.3%`。同时保留或补充较小但可读的 `Retrospective backtest`。

### 镜头 3：规则简单，建仓可控（0:35–1:05）

**画面操作**：

1. 进入 Strategy Lab，保持 Fixed parameters。
2. 依次指向 Moving-average window = 30、Entry deviation = 2.0%、Exit deviation = −2.0%。
3. 指向 Staged entry 的 40 / 30 / 30 和间隔设置。
4. 可将 Entry deviation 拖至 2.5%，停留在 **Parameters changed — run to update** 提示上。不要在这时把右侧旧曲线描述成新的结果。

**英文旁白**：

> The rule enters after the closing price crosses two percent above its thirty-session moving average, and exits below a negative two percent deviation. Positions are built in three stages: forty, thirty and thirty percent. Later purchases require another check. Parameters are editable, while saved results remain unchanged until a new experiment is run.

**录制提示**：这段演示参数可编辑即可，不点击运行按钮。后面明确展示提前算好的版本。剪辑不能造成“拖动滑块就实时完成回测”的印象。

### 镜头 4：最重要的交互——解释一笔交易（1:05–1:45）

**画面操作**：

1. 点击 Featured case 回到精选首页。
2. 点击 Monthly returns 的 July 2025，进入 Trade Replay。
3. Stock code 输入 `600106`。
4. 点击 `2025-07-23` 的买入记录。
5. 先展示 Signal / Execution 和价格标记，再缓慢滚动抽屉至 The complete entry plan。
6. 让三批实际成交日期清晰停留：July 2、July 11、July 23。

**英文旁白**：

> A monthly return is linked to the underlying executions. Here, I can inspect one stock and see the original allocation decision, the later signal check and the actual trade. This position was built across three separate dates. The panel also shows planned budgets, recorded fills, fees and slippage, making the execution process visible instead of presenting only a performance curve.

**字幕重点**：`Signal → Allocation plan → Actual fills`。

**录制提示**：本段优先保证抽屉文字可读。若一屏放不下，就分成价格图和建仓计划两个镜头；不需要快速上下滚动。后续批次不是无条件定时买入。

### 镜头 5：展示滚动研究的方法（1:45–2:15）

**画面操作**：

1. 关闭交易抽屉，进入 Walk-Forward。应用会载入配置的滚动案例。
2. 选 July 2025，指向 CALIBRATE / VALIDATE / REPLAY。
3. 点击 August，让时间窗口前移。
4. 简短展示 The selected rule 和 Why this candidate?。

**英文旁白**：

> A separate rolling experiment uses twelve months for calibration, three for validation and one for forward replay. Moving the timeline shows the information cutoff and the selected parameters for each month. Cash and holdings continue across windows. Its recorded Sharpe is 1.30; it is distinct from the fixed featured case.

**录制提示**：使用月份按钮，不依赖 Replay speed。目前速度选项没有真正改变计时。不要用此页画面配“滚动策略 Sharpe 1.48”的字幕，也不要把协议预览录成真实计算结果。

### 镜头 6：提前计算好的参数对比（2:15–2:40）

**画面操作**：

1. 点击 Featured case，进入 Compare & Archive。
2. 保留精选案例，勾选后缀 `8f24a0a8` 的 +2.5% 案例；可再勾选 `eee9c020` 的滚动案例。
3. 显示两到三条曲线及图例，指向原阈值与新阈值的实验行。
4. 若需要剪辑，可在勾选完成后切回上方曲线，不保留寻找下拉项和滚动的全部过程。

**英文旁白**：

> These experiments were computed before recording. Raising the entry threshold from two to two-point-five percent reduced Sharpe from 1.48 to 0.95 in this period. The comparison makes parameter sensitivity visible, while each experiment retains its own configuration and execution records.

**字幕重点**：`Precomputed experiments`、`Entry threshold: 2.0% vs 2.5%`。

**录制提示**：这不是说明 2% 永远优于 2.5%，而是展示同一研究期间内的实际比较。无须把搜索中表现最高的结果重新设为主案例。

### 镜头 7：交付结果与结束（2:40–3:00）

**画面操作**：

1. 保持精选案例为当前活动实验，指向 English report、Research evidence、Equity PNG。
2. 切换至提前打开的精选英文报告标签页。
3. 在报告标题、净值图和指标处缓慢停留，结束录制。

**英文旁白**：

> Results can be exported as an English report, a chart or a research evidence package. With the environment and data prepared, the application works offline without a paid data subscription. The project combines financial reasoning with an interactive product that makes research decisions easier to inspect and communicate.

**字幕重点**：`Interactive · Explainable · Offline-ready`。

**录制提示**：报告导出针对当前活动实验，不是将已勾选的三条曲线合并成一个报告。提前打开报告可避免下载对话框打断镜头。

## 5. 哪些画面可以省略

- 不录安装依赖、启动终端和等待服务的过程；视频从已经打开的首页开始。
- 不录 45 个候选的完整搜索过程，也不逐个介绍五种策略。
- 不读完整技术栈、不翻源代码、不展示全部配置字段。
- 不需要现场运行回测。已有保存记录足够支持整个故事。
- 不把 Guided tour 与手动导航同时打开，避免遮挡页面。

如果要额外证明“可以运行”，可单独补录一次点击运行、任务完成、新实验出现的短镜头，剪掉中间等待并加 `Computation time shortened` 字幕。该补录不是三分钟主片的必要内容。

## 6. 成片检查

- 首页与旁白中的精选指标一致：1.48、19.3%，没有写成 Sharpe > 1.5。
- 滚动结果 1.30 与精选结果 1.48 有清楚区分。
- 修改滑块后的旧图没有被当作新回测结果。
- 参数对比明确标注为提前计算，+2.5% 版本显示约 0.95。
- 交易详情使用精选案例的 600106、2025-07-23，能看到三批实际成交。
- 关键日期、图例和字幕可读，鼠标没有遮挡数字。
- 保留回顾性研究说明；没有将研究模式描述成实盘撮合。
- 收尾展示的是英文报告，不是旧版实验目录里的其他报告。

有关当前记账限制、启动方式和完整页面说明，参见 [项目使用手册](../README.md)。简短现场演示稿见 [DEMO_EN.md](DEMO_EN.md)；本方案针对预计算结果的录屏，优先按本文件操作。
