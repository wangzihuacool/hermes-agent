# Prometheus · MySQL 指标排障约定

供 `dba-monitoring-alerts` / `dba-troubleshooting` / `dba-performance-tuning` 查 MySQL 监控时使用。
调用经 Prometheus MCP：`tool_search` → `tool_describe` → `tool_call`（见 SOUL.md）。
**指标名以现网为准**；下表来自 `v_metric_type="MYSQL"` 实查，空结果时先 `label_values`/`series` 再改写，禁止编造。

## MCP 工具速查

| 目的 | 短名 | 说明 |
|------|------|------|
| 确认指标/标签存在 | `label_values` / `label_names` / `series` | **先发现再查询** |
| 瞬时值 | `query` | 当前点；**不是** VictoriaLogs 的 `query` |
| 区间趋势 | `range_query` | 告警/故障同窗；**不是** `query_range`，也不是 VL `stats_query_range` |
| 告警状态 | `list_alerts` | 是否仍 firing |
| 指标说明 | `metric_metadata` | 不确定语义时 |

## 发现→查询硬流程（违反即视为未按规程排查）

1. `tool_describe(mcp__prometheus__query)` → 读 `server_instructions` 中的 MCP 规程。
2. 用 VisionDB 或告警确定 `<ip>:<port>`，selector 固定为 `{v_metric_source="...", v_metric_type="MYSQL"}`。
3. **发现**（至少一步，允许并行）：
   - `label_values`：确认 `v_metric_source` / 指标是否存在；
   - 或对已知候选指标名做 `series(matches=['mysql_up{...}'])`。
4. **再查询**：`range_query` / `query` 只使用第 3 步已确认存在的指标名。
5. **空结果**：不得换 `mysql_*` / `job:Mysql*` 等未验证名字；回到第 3 步，或改查 `mysql_exporter_last_scrape_error` / 交叉 VisionDB+VL。

**禁止**：跳过第 3 步直接套用下文模板 PromQL；模板里的指标名是「候选」，不是默认存在。

## 通用约定（标签定位）

```text
{v_metric_source="<ip>:<port>", v_metric_type="MYSQL"}
```

1. **定位主键**：`v_metric_source` + `v_metric_type` 等值匹配（见 SOUL.md）。禁止 `instance=~"<ip>.*"`。
2. **端口**：告警原文 → VisionDB `dbPort1` → 默认 3306（兜底须声明）。
3. **有无数据**：先对 `mysql_up` 或任一核心指标做同窗 `range_query`；无样本 = 断采/未纳管，**不等于**已证实宕机，须交叉 VisionDB + VL。
4. **Counter**：吞吐类用 `rate(...[5m])`；gauge（连接数、up、lag）直接看原值。
5. 当前负载优先 VisionDB `get_mysql_instance_status`；本文件补**趋势与同窗佐证**。

## 按场景推荐指标顺序

| 场景 | 第 1 步（有无数据/存活） | 第 2 步 | 第 3 步 | 辅证 |
|------|--------------------------|---------|---------|------|
| 挂了/连不上 | `mysql_up` | `threads_connected` / `connections` | `aborted_connects` / `connection_errors` | VL errorlog；VisionDB status |
| 连接打满 | `threads_connected` vs `max_connections` | `max_used_connections` | `threads_running` | VL「Too many connections」 |
| 慢/卡顿 | `threads_running` | `rate(questions\|queries)` / recording `job:MysqlQPS` | `rate(slow_queries)` / `job:MysqlSlowQueriesPerSecond*` | VL slowlog |
| 锁 | `innodb_row_lock_current_waits` | `rate(innodb_row_lock_waits)` | `innodb_row_lock_time_*` | VL deadlock/processlist |
| 复制延迟 | `mysql_slave_status_seconds_behind_master` | `slave_sql_running` / `slave_io_running` | MGR：`mysql_perf_schema_replication_group_*` | VL heartbeat `repl_*` |
| 缓冲池/IO | `innodb_buffer_pool_reads` vs `read_requests` | `innodb_data_pending_*` | `created_tmp_disk_tables` | Zabbix 磁盘 await |
| DeadMaster/切换 | `mysql_up` 旧主同窗是否掉 0 | 新主 `up`/连接是否起来 | 复制/lag 是否重建 | VisionDB 切换史 |

## 核心指标速查（现网常见）

| 用途 | 指标名 |
|------|--------|
| 存活 | `mysql_up` |
| 连接 | `mysql_global_status_threads_connected`、`mysql_global_variables_max_connections`、`mysql_global_status_max_used_connections`、`mysql_global_status_connections` |
| 活跃线程 | `mysql_global_status_threads_running`、`mysql_global_status_threads_rejected` |
| QPS | `mysql_global_status_questions` / `mysql_global_status_queries`（用 `rate`）；录制规则 `job:MysqlQPS*` |
| 慢查询 | `mysql_global_status_slow_queries`；`job:MysqlSlowQueriesPerSecond*` |
| 行锁 | `mysql_global_status_innodb_row_lock_current_waits`、`..._waits`、`..._time` / `_avg` / `_max` |
| 复制 lag | `mysql_slave_status_seconds_behind_master` |
| 复制线程 | `mysql_slave_status_slave_io_running`、`mysql_slave_status_slave_sql_running`（值为 1/0 语义以实查为准） |
| 缓冲池 | `mysql_global_status_innodb_buffer_pool_reads`、`..._read_requests`、`..._pages` 等 |
| Exporter | `mysql_exporter_last_scrape_error`（=1 时先怀疑采集，再判实例） |

## PromQL 模板（替换 `<ip>:<port>`）

以下 selector 记为 `S`：`v_metric_source="<ip>:<port>",v_metric_type="MYSQL"`。

### 摸底 / 有无数据

```promql
mysql_up{S}
# MCP: label_values / series 确认该 source 存在后再 range_query
```

### 可用性与连接

```promql
mysql_up{S}
mysql_global_status_threads_connected{S}
mysql_global_variables_max_connections{S}
mysql_global_status_max_used_connections{S}
mysql_global_status_threads_running{S}
rate(mysql_global_status_aborted_connects{S}[5m])
```

### 吞吐与慢查询

```promql
rate(mysql_global_status_questions{S}[5m])
rate(mysql_global_status_queries{S}[5m])
rate(mysql_global_status_slow_queries{S}[5m])
# 若环境有录制规则，可优先：
# job:MysqlQPS{S} 或带 job 标签的等价 series（以 label_values 为准）
```

### 锁

```promql
mysql_global_status_innodb_row_lock_current_waits{S}
rate(mysql_global_status_innodb_row_lock_waits{S}[5m])
mysql_global_status_innodb_row_lock_time_avg{S}
```

### 复制

```promql
mysql_slave_status_seconds_behind_master{S}
mysql_slave_status_slave_io_running{S}
mysql_slave_status_slave_sql_running{S}
mysql_slave_status_last_errno{S}
```

## 解读要点

- `mysql_up==0` 或同窗无点：先看 `mysql_exporter_last_scrape_error` / 采集机，再下「实例宕机」结论。
- `threads_connected` 逼近 `max_connections`：可用性风险；结合 aborted/拒绝类指标。
- `threads_running` 持续高 + QPS 不升：偏锁/等待/饱和，转 VL processlist/slowlog。
- `seconds_behind_master` 持续升高：一致性风险；线程为 0 时先查复制中断而非单纯延迟。

## 边界

- Prom `query` ≠ VL `query`；趋势用 `range_query`。
- 录制规则名（`job:MysqlQPS` 等）因环境而异，用前 `label_values`。
- 无客户端 EXPLAIN：性能结论到候选 SQL 后请用户回贴或走只读会话。
