---
name: dba-monitoring-alerts
description: "Interpret Prom/Zabbix/custom metrics and alert triage."
version: 2.1.0
author: wl
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dba, monitoring, prometheus, zabbix, victorialogs, alerts, visiondb]
    category: dba
    related_skills:
      - dba-troubleshooting
      - dba-performance-tuning
      - dba-engine-playbooks
---

# DBA Monitoring & Alerts Skill

解读 Prometheus / Zabbix / 自定义指标与告警，用 VictoriaLogs 做日志侧证。目标是把「告警在响」变成「含义、影响、是否误报、下一步」。

MCP 调用机制、VisionDB 定位链、参数命名见 SOUL.md；VisionDB 工具选型与枚举见 `dba-engine-playbooks/references/visiondb-mcp.md`。本 skill 补充：**告警类型 → 优先数据源/工具**，以及 Prom/VL 的具体取证约定。

## When to Use

- 用户粘贴了一条告警（短信/邮件/Zabbix/Prom），要求分析原因
- 某 IP/实例在某时段的指标走势、是否误报
- 巡检前先看监控基线

## Prerequisites

- Prometheus、Zabbix、VictoriaLogs MCP 可用
- 已知或可搜索到对象（IP、host、job、alertname）

## 告警类型 → 优先 MCP / tool（必读，防用错工具）

收到告警后**先对表选路径**，再 `tool_search` → `tool_describe` → `tool_call`。四个 MCP 的 `query` **不是同一个工具**——必须先 search 到带正确服务前缀的全名。

| 告警/用户表述 | 第 1 数据源 | 首选 tool（短名） | 第 2 步 | 勿用 |
|---------------|-------------|-------------------|---------|------|
| 主机 CPU/内存/磁盘/网卡、Zabbix 电话/短信 | Zabbix | `problem_active_get` / `host_status_get` → `item_history_summary_get`（指标怎么搜见 `dba-engine-playbooks/references/zabbix.md`） | Prom `range_query` 看同窗趋势 | 一上来只查 VL 当「主机证据」；负载误搜「磁盘使用率」当空间 |
| Prom 规则 firing、指标飙高、误报判断 | Prometheus | `list_alerts` → `label_values` → `range_query`（趋势）/`query`（瞬时） | VL `hits` 侧证 | `stats_query` / `stats_query_range`（那是 VL，不是 Prom） |
| 库挂了 / 连不上 / DeadMaster / 切换 | VisionDB | `search_instances` → status / `list_switchover_history` | **必查** Prom：告警/故障同窗 `range_query`（先确认 series 有无数据，再看 `up`/连接/复制等是否异常）→ Zabbix 主机 + VL errorlog | 只复述告警原文；跳过 Prom 只凭 VisionDB/日志下结论 |
| 慢查询 / 锁 / errorlog /「看日志」 | VictoriaLogs | `streams`/`field_values` 摸底 → `hits`（量）→ `query`（样本） | Prom 趋势对齐时间窗 | 用 `host` 当 IP 过滤；把 VL `query` 当 PromQL |
| 维护窗 / 静默怀疑 | Zabbix | `maintenance_get` | 再判是否误报 | — |

**同名短名消歧**（最常见用错原因）：

| 目的 | 正确 MCP | 短名 | 常见误用 |
|------|----------|------|----------|
| Prom 瞬时值 | Prometheus | `query` | 调到 VictoriaLogs 的 `query` |
| Prom 区间趋势 | Prometheus | `range_query` | 猜 `query_range`；或 VL `stats_query_range` |
| 日志行抽样 | VictoriaLogs | `query` | 用 Prom `query` 写 LogsQL |
| 日志量/错误突增 | VictoriaLogs | `hits` | 用 Prom `range_query` 查日志量 |
| 日志字段摸底 | VictoriaLogs | `streams` / `field_values` | 跳过摸底直接瞎写 `_stream` |

## Procedure

### 1. 识别告警与对象

告警文案只是「需要核实的输入」，不是证据。按上表选第 1 数据源后，本轮至少走一条真实取证链：

1. `search_instances(keyword=IP)`（或告警里的集群名）对齐 VisionDB 实体，拿到 `dbId` / `dbPort1`。
2. 按上表调用对应 MCP；可能在维护窗口时用 `maintenance_get` 核对。
3. **可用性/切换类告警**（挂了、连不上、DeadMaster）：VisionDB 之后**必须**用 Prometheus 同窗佐证——`label_values`/`series` 确认该 `v_metric_source` 在故障时段**有无样本**；再 `range_query` 看 `up`、连接数、复制 lag 等是否中断或异常。引擎具体指标与 PromQL 见 `dba-engine-playbooks/references/prometheus-mysql.md`（及 redis/oracle 对应文件）。解读：无数据/断采 ≠ 已证实宕机（可能是 exporter/采集挂了），须对照 VisionDB status + VL；有数据且指标持续正常则倾向误报或局部问题，勿单凭告警名定性。

引擎无 VisionDB 运行时 status（SQL Server/Oracle 等）时，以 Zabbix + VictoriaLogs 为主，缺口写明拉不到 DMV，不要编。

### 2. 定位实例标签，再拉指标（Prometheus 路径）

现网 Prometheus 标签是拼接好的复合字符串，例如：

```text
mysql_up{instance="10.70.32.31:3306-东莞_MYSQL_LINUX_PROD_PRIMARY_SMT镭雕机系统",
         v_metric_source="10.70.32.31:3306", v_metric_type="MYSQL",
         v_metric_role="PRIMARY", cluster="东莞_SMT镭雕机系统",
         v_application="SMT镭雕机系统", v_area="东莞", v_env="PROD",
         node_name="10.70.32.31:3306", service_name="10.70.32.31:3306-东莞_..."}
```

按 SOUL.md「Prometheus 标签定位」：用 `v_metric_source`+`v_metric_type` 联合等值匹配（`{v_metric_source="10.70.32.31:3306", v_metric_type="MYSQL"}`），不要用 `instance` 做正则/子串匹配。

端口确定顺序：告警原文 → VisionDB `dbPort1` → 引擎默认端口兜底（兜底须声明是猜的）。

`label_values` / `metric_metadata` 确认指标与标签真实存在，再 `range_query` 用故障窗或告警 `for` 窗口拉值。同时看绝对值、变化率、是否突破历史基线。

### 3. 解读框架

对每个关键指标回答：什么变了、偏到什么程度（均值/峰值 vs 日常）、影响谁（单盘/单实例/整机/整集群）、是否足够解释症状。

经验阈值（需按环境校准，勿教条）：磁盘 `util` 长期 >80% 但 `await` 低可能是健康繁忙；`await` 升高更接近排队/慢设备；连接数逼近 `max_connections` 是可用性风险；复制 lag 持续升高是一致性风险。

### 4. 日志侧证（VictoriaLogs 路径）

用户要日志侧证、或指标不足以解释症状时，本轮必须实际调用 **VictoriaLogs** MCP（不是 Prometheus）：

**通用约定**（MySQL 细节与可复制 LogsQL 见 `dba-engine-playbooks/references/victorialogs-mysql.md`）：

- **按 IP 过滤用 `source_ip:"<IP>"`**；`host` 是采集机主机名，**禁止**当 DB IP 用。
- 顺序：`streams` / `field_values` 摸底 → `hits` 看是否突增 → `query` 取 5–20 条样本（`limit` 控制体量）。
- MySQL 常见 `_stream`：`mysql_errorlog` / `mysql_slowlog` / `mysql_processlist` / `system_log` / `heartbeat_log` / `visiondb_agent_log`。
- `mysql_processlist` 必须带 `source_ip` + 短 `_time` + `limit`（建议 ≤30）。

### 5. 输出

告警是否有效/可能误报原因（含是否在维护窗）；关联指标数字与时间点；有处置动作再写建议，纯解读且无异常时只保留结论+证据。

## Pitfalls

- 未验证 label 就写 PromQL，空结果当「无问题」。
- 把 Zabbix 与 Prom 同名概念混为一谈（采样周期不同）。
- 只报峰值不报持续时间。
- 忽略静默/维护窗口。
- 把用户粘贴的告警全文当成「已完成查询」，直接在此基础上编证据。
- **跨 MCP 同名工具**：Prom `query` ≠ VL `query`；VL `stats_query_range` ≠ Prom `range_query`。
- **用 `host` 过滤实例 IP** → 查空或查到采集机，误判「无日志」。

## Verification

- 结论引用的指标查询与时间窗都来自 tool 返回，非臆造。
- 主机与库指标已尝试对齐同一 IP/主机（及 VisionDB 实体，若可用）。
- 需要日志侧证时已实际调用 VictoriaLogs，或写明已尝试的调用与失败原因。
- 本轮选用的 MCP/短名与「告警类型 → 优先 MCP」表一致，或已说明为何偏离。
