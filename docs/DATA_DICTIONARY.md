# 数据与实验契约

## 行情与证券

`symbol`为六位文本代码；`date`为YYYY-MM-DD。`raw_*`为原始开高低收，`adj_*`为同一来源和快照的调整开高低收。`volume`单位为股，`amount`单位为元。AKShare东方财富成交量原始为手，适配器乘100；BaoStock原始成交量为股。

`instruments`包含`symbol,name,exchange,board,list_date`，可选`delist_date`（最后交易日期）。普通主板证券须为`exchange=SSE,board=MAIN_A`，代码前缀不能代替证券类型验证。

`is_st,is_suspended,no_price_limit`为布尔列，未知留空，不能填false。`limit_up,limit_down`为当日有效原始限制价格。只有历史明确无价格限制时，才把`no_price_limit`设为true。

交易日历包含完整交易日，指标预热和执行推进共用同一日历。中间行情缺口直接拒绝；只有有来源的停牌允许沿用估值。下载快照的原始响应保留在本地downloads目录。

## 公司行动CSV

字段：`event_id,symbol,record_date,ex_date,pay_date,cash_per_share,share_multiplier,share_trade_date,source`。

- `record_date`登记日收盘记录股息及送转权益；`ex_date`除权日计入应收股息和新增股份。
- `pay_date`现金实际可用日；非交易日到账在下一交易日开盘前入账。
- `cash_per_share`每股实际建模现金金额。平台不猜测个人持股期限对应的差异化红利税；导入金额口径须在来源说明中注明。
- `share_multiplier`总股数乘数：无送转为1，10送10为2。新增股份在`share_trade_date`后可出售；之前仍有估值但不可售。
- 暂不自动估算配股、合股或不足1股权益；遇到这些事件阻止严格回测，要求提供经核实的实际分配记录或扩展事件处理。

真实股数运行还要求manifest提供逐证券的覆盖声明；空事件表也必须有“已经核查该期间无事件”的依据：

```json
{
  "corporate_action_coverage": {
    "600000": {
      "from": "2018-01-01",
      "to": "2025-02-28",
      "complete": true,
      "source": "核验所依据的公司公告或数据交付记录",
      "reviewed_at": "2026-09-13"
    }
  }
}
```

这是对提供数据的核验记录的结构要求，不是平台替数据供应商保证数据真实、完整。

## 退市与现金回收

有退市的研究区间使用真实股数模式。manifest的`exit_records`为记录列表，每项包含`symbol,recovery_date,net_cash_per_share,source,known_at`。回收价不能由最后收盘价默认替代；缺失时拒绝严格运行。

退市后的持仓继续存在，在现金回收日期前沿用最后可用估值（不代表仍能卖出）；记录的净回收款到账时，股份注销，现金增加并记录公司行动。该估值假设需要随报告解释，现金回收不是普通市场成交，也不计入交易换手。

## 结果

- `equity`：每日现金、应收股息、净值、累计显式费用及同路径费用返还曲线。
- `positions`：实际份额/股数、估值、市值、权重与可售数量。
- `decisions`：信号日、次日、全候选指标、得分、排名、资格与目标。
- `plans`：每只股票本轮预算、实际投入、批次、有效期、尝试次数及结束原因。
- `orders`与`fills`：通过订单编号、计划编号和信号日期关联，未成交必须保留理由。
- `corporate_events`、`closed_lots`：公司行动入账与真实股数FIFO已实现批次。
- `benchmarks`：同池买入持有、同池等权调仓及有覆盖时的上证综指价格参考。

净值最后一天不强制清仓；未平仓股票不进入已平仓胜率。同一路径成本前曲线只把费用留为不计息现金，不假设再投资，也不重复扣滑点。

快照通过内容哈希验证。实验保存完整参数、实际记账模式、数据hash、计算代码与费用表hash，以及CSV/JSON/HTML导出。
