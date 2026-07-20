---
name: dba-troubleshooting
description: "Troubleshoot DB availability and performance issues."
version: 2.1.0
author: wl
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dba, troubleshooting, availability, performance, mysql, redis, oracle, visiondb]
    category: dba
    related_skills:
      - dba-monitoring-alerts
      - dba-performance-tuning
      - dba-engine-playbooks
---

# DBA Troubleshooting Skill

按分层做数据库故障定位：主机 → 库运行时 → 切换/运维痕迹 → 日志。先取证、交叉验证，再给止血与根因建议。只定位分析，不做写操作。

MCP 调用机制、VisionDB 定位链、参数命名见 SOUL.md；VisionDB 工具细节见 `dba-engine-playbooks/references/visiondb-mcp.md`。本 skill 补充：**场景分类 → 查询顺序**，以及各层首选 tool。

## When to Use

- 库不可用、连接失败、主从中断、切换/DeadMaster
- 延迟飙升、超时、连接打满、大量报错
- 「今天 X 点到 Y 点某 IP/实例有问题」类排查

## Prerequisites

- VisionDB + Prometheus / Zabbix / VictoriaLogs MCP 已配置
- 用户尽量提供：IP 或实例名、时间窗、引擎类型、症状；缺失就问 1–2 个关键问题，不要空转

## 场景分类（必须先做，再动手查）

将用户描述映射到主类；一句话可归多类时选**最贴近痛点**的为主，其余作辅查。仅「数据库有问题」无细节 → 先 VisionDB status + VL `heartbeat_log`/`mysql_errorlog` 最近 1h，再二次分类。

| 主类 | 典型表述 | 第 1 层 | 第 2 层 | 第 3 层 |
|------|----------|---------|---------|---------|
| A 连接/可用性 | 连不上、超时、Too many connections、挂了 | VisionDB status / `search_instances` | VL `heartbeat_log` + `mysql_errorlog` | Zabbix 主机连通/端口 |
| B 性能/慢 | 慢、卡顿、RT 高、QPS 掉 | VL `mysql_slowlog`（`hits`→`query`） | Prom `range_query` | VL `mysql_processlist` |
| C 锁/事务 | Lock wait、死锁、长事务 | VL `mysql_errorlog` deadlock/lock | VL `mysql_processlist` Waiting/Locked | VL `mysql_slowlog` `lock_time` |
| D 复制/HA | 延迟、复制中断、DeadMaster、切换 | VisionDB `list_switchover_history` / status | VL `heartbeat_log` `repl_*` + errorlog | Prom lag 趋势 |
| E 资源/主机 | CPU 高、IO、await、OOM | Zabbix `problem_active_get` / history | Prom 同窗趋势 | VL `system_log` |
| F 存储/空间 | 磁盘满、No space、binlog 占满 | Zabbix 磁盘 | VL `system_log` + `mysql_errorlog` | — |
| G 崩溃/恢复 | 重启、crash、OOM kill mysqld | VL `mysql_errorlog` + `system_log` | VL `heartbeat_log` 中断区间 | VisionDB 切换史 |
| H Agent/误报 | 平台红但业务正常、采集失败 | VL `visiondb_agent_log` + `heartbeat_log` | 对照 `mysql_errorlog` | Zabbix/Prom 是否真异常 |

MySQL 日志 stream、字段与可复制 LogsQL：`dba-engine-playbooks/references/victorialogs-mysql.md`。

## MCP 层首选 tool（防跨 MCP 用错）

| 层 | MCP | 首选短名 | 禁止/易错 |
|----|-----|----------|-----------|
| 元数据/负载/切换 | VisionDB | `search_instances` → `get_mysql_instance_status` / `get_redis_status`；切换用 `list_switchover_history` | 编造 `get_sqlserver_instance_status` |
| 主机当前问题 | Zabbix | `host_get` → `problem_active_get` / `host_status_get` → `item_history_summary_get` | 用 VL 代替主机 util/await 结论 |
| 指标趋势 | Prometheus | `label_values` → `range_query`；瞬时用 `query` | VL `stats_query_range`；`instance=~"ip.*"` 模糊匹配 |
| 日志 | VictoriaLogs | `streams`/`field_values` → `hits` → `query` | 用 `host` 过滤 IP；Prom `query` 写 LogsQL |

四个 MCP 都可能有名为 `query` 的工具——**必须**经 `tool_search` 拿到带服务前缀的全名后再 `tool_call`。

## Procedure

### Phase 0 — 锁定范围与对象

复述目标（IP/集群/端口）、时间窗、引擎、症状，完成**场景分类**。按 SOUL.md「VisionDB 通用定位链」与 `visiondb-mcp.md` 解析 `dbId`/`dbClusterId`。已有 dbId 且引擎为 MySQL/Redis：Prom 不足时立刻 `get_mysql_instance_status` / `get_redis_status` 看当前负载。

### Phase 1 — 主机层（Zabbix）— 主类 E/F 优先；A/G 必交叉

`host_get` 定位主机 → `problem_active_get` / `host_status_get` → 需要历史时 `item_history_summary_get`。重点：磁盘 util/await、CPU iowait、内存、网卡丢包。

### Phase 2 — 趋势指标（Prometheus）— 主类 B/D/E

已有 VisionDB status 时本层只补趋势，不重复问「现在忙不忙」。用 `v_metric_source`+`v_metric_type` 定位 series（见 SOUL.md），`label_values` 先确认指标存在，再 `range_query`；`list_alerts` 看是否 firing。引擎指标清单与 PromQL：`prometheus-mysql.md` / `prometheus-redis.md` / `prometheus-oracle.md`。搜不到 Prom 工具就用 VisionDB status + Zabbix 作答，缺口写明。

### Phase 3 — 日志（VictoriaLogs）— 主类 A/B/C/D/G/H；用户点名日志时插队

用户点名「日志/VictoriaLogs/errorlog」时，可跳过等待前两层，直接按 IP + 故障时间窗查。

**约定**：

1. 过滤：`source_ip:"<IP>"`（**不是** `host`）。
2. 摸底：`streams` / `field_values` 确认该 IP 有哪些 `log_type`。
3. 按场景分类表选第 1/2/3 日志源；MySQL 顺序与模板见 `victorialogs-mysql.md`。
4. `hits` 看突增 → `query` 取代表性样本，控制 `limit`。

### Phase 3.5 — DeadMaster / 切换事件（主类 D）

告警或用户给出 `DeadMaster`、旧主 IP、事件 ID、集群名时：先 `list_switchover_history` / `get_orchestrator_switch_steps`（带上事件 ID），再查旧主 IP 的 `mysql_errorlog` + visiondb-service/orchestrator 相关日志，对齐切换时间窗后再下结论。

### Phase 4 — 综合

对照时间线判断：主机问题 / 库内问题 / 切换事件，还是叠加；最可能的根因层级（资源/SQL/锁/复制/参数/变更）；需要止血时只列需用户确认的操作；给验证步骤。

深挖 SQL/锁时加载 `dba-performance-tuning`；引擎专项清单加载 `dba-engine-playbooks`。

## Pitfalls

- 主机 IO 高就直接归因「SQL 差」，不交叉验证库内状态。
- Prom `instance` 端口不等于业务端口（可能是 exporter）。
- 日志流名因环境而异，先 `streams`/`field_values` 再写 LogsQL。
- 把告警名当根因；告警只是症状入口。
- 无切换步骤/日志证据就对 DeadMaster 下结论。
- **Prom `query` 与 VL `query` 混用**；用 `host` 当实例 IP 过滤。
- Agent 心跳失败 ≠ MySQL 宕机：必须交叉 `mysql_errorlog` / `system_log`。

## Verification

- 证据含明确时间窗与数据源，且都能回溯到本轮工具返回。
- 主机结论与 Prom/日志/切换时间线一致，或已解释矛盾。
- 建议区分「已确认」与「待验证假设」。
- 已完成场景分类，且查询顺序与主类推荐路径一致（或写明偏离原因）。
