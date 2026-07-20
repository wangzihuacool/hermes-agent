# Prometheus · Oracle 指标排障约定

供告警解读 / 故障排查时查 Oracle 监控使用。
调用经 Prometheus MCP（见 SOUL.md）。现网前缀多为 `oracledb_*`；`v_metric_type` 常见 `ORACLE` / `ORACLERAC`（以 `label_values` 为准）。
VisionDB **无** Oracle 专用运行时 status——Prom + Zabbix + 用户提供的 AWR/ASH/alert log 是主证据链。

## MCP 工具速查

| 目的 | 短名 |
|------|------|
| 发现 | `label_values` / `series` / `metric_metadata` |
| 瞬时 | `query`（Prometheus，不是 VL） |
| 趋势 | `range_query` |
| 告警 | `list_alerts` |

## 发现→查询硬流程（违反即视为未按规程排查）

1. `tool_describe(mcp__prometheus__query)` → 读 `server_instructions` 中的 MCP 规程。
2. 用 VisionDB 或告警确定 `<ip>:<port>`，selector 固定为 `{v_metric_source="...", v_metric_type="ORACLE"}`（RAC 不确定时先 `label_values(v_metric_type)` 试 `ORACLERAC`）。
3. **发现**（至少一步）：`label_values` / `series` 确认 `oracledb_*` 等指标存在。
4. **再查询**：`query` / `range_query` 只用第 3 步已确认存在的指标名。
5. **空结果**：禁止换猜的 `oracledb_*` / `oracle_*` 名字；回到第 3 步或交叉 Zabbix + 用户侧 alert/AWR。

**禁止**：跳过发现直接套用下文模板；模板指标名为候选，不是默认存在。

## 通用约定

```text
{v_metric_source="<ip>:<port>", v_metric_type="ORACLE"}
# RAC 场景可能是：
{v_metric_source="<ip>:<port>", v_metric_type="ORACLERAC"}
```

1. 定位主键仍是 `v_metric_source` + `v_metric_type`；禁止 `instance` IP 正则。
2. 端口：告警/VisionDB → 默认 1521（兜底须声明）。
3. 空结果时先试 `ORACLERAC`，再 `label_values` 看该 IP 实际 type。
4. **有无数据**：同窗 `oracledb_up`；无样本 = 断采/未纳管，交叉 Zabbix 主机与用户侧监听状态。
5. 会话/等待细节有限：深挖 SQL 需用户提供 AWR/ASH 或授权查询。

## 按场景推荐指标顺序

| 场景 | 第 1 步 | 第 2 步 | 第 3 步 | 辅证 |
|------|---------|---------|---------|------|
| 挂了/连不上 | `oracledb_up` | `oracledb_exporter_last_scrape_error` | `oracledb_user_failed_logon_times` | Zabbix；监听/alert log |
| 负载高/慢 | `oracledb_sysmetric_average_active_sessions` | `oracledb_sysmetric_database_time_per_sec` | `oracledb_waitclassmetric_value` / `oracledb_sesion_wait_value` | AWR/ASH；录制 `job:Oracle*` |
| 会话/资源打满 | `oracledb_resource_current_utilization` vs `oracledb_resource_limit_value` | `oracledb_long_query_session_cnt` | `oracledb_killed_session_cnt` | 用户查 v$session |
| 表空间/ASM 满 | `oracledb_tablespace_used_of_max` / `used_gb` | `oracledb_asm_diskgroup_used_percent` | `oracledb_db_files_cnt` vs `_param` | 告警原文盘符 |
| Data Guard | `oracledb_dataguard_stats_stat_value_in_seconds` | `oracledb_managed_standby_error_cnt` | `oracledb_dataguard_logswitch_times24h` | 角色确认 |
| 备份/作业 | `oracledb_rman_backup_job_status` | `oracledb_jobs_status` / `jobs_running_*` | — | 备份窗口变更 |
| 结构健康 | `oracledb_corrupt_block_count` | `oracledb_unusable_index_cnt` | `oracledb_2pc_pending_cnt` | 运维窗口处理 |

## 核心指标速查（现网常见）

| 用途 | 指标名 |
|------|--------|
| 存活 | `oracledb_up` |
| 实例信息 | `oracledb_instance_info`、`oracledb_version_info`、`oracledb_database_dbid`、`oracledb_rac_enabled` |
| 活动/DB time | `oracledb_sysmetric_average_active_sessions`、`oracledb_sysmetric_database_time_per_sec`、`oracledb_sysmetric_io_requests_per_second` |
| 活动计数 | `oracledb_activity_execute_count`、`..._user_commits`、`..._user_rollbacks`、`..._parse_count_total`、`..._db_block_changes` |
| 等待 | `oracledb_waitclassmetric_value`、`oracledb_sesion_wait_value` |
| 资源限制 | `oracledb_resource_current_utilization`、`oracledb_resource_limit_value` |
| 会话异常 | `oracledb_long_query_session_cnt`、`oracledb_killed_session_cnt`、`oracledb_user_failed_logon_times` |
| 空间 | `oracledb_tablespace_used_gb`、`oracledb_tablespace_used_of_max`、`oracledb_asm_diskgroup_*` |
| Data Guard | `oracledb_dataguard_stats_stat_value_in_seconds`、`oracledb_managed_standby_error_cnt`、`oracledb_dataguard_logswitch_times24h` |
| 作业/备份 | `oracledb_jobs_status`、`oracledb_jobs_running_running_seconds`、`oracledb_rman_backup_job_status`、`oracledb_scheduler_running_seconds` |
| 健康 | `oracledb_corrupt_block_count`、`oracledb_unusable_index_cnt`、`oracledb_2pc_pending_cnt` |
| Exporter | `oracledb_exporter_last_scrape_error`、`oracledb_exporter_scrape_errors_total` |
| 录制规则（若有） | `job:OracleActSessAvg5m`、`job:OracleDBtime*`、`job:OracleNumCpus` |

部分指标带额外 label（表空间名、等待类、resource name）：`series` 看清后再聚合，避免扫高基数。

## PromQL 模板

`S` 先用 `v_metric_type="ORACLE"`；空则换 `ORACLERAC`。

### 摸底 / 存活

```promql
oracledb_up{S}
oracledb_exporter_last_scrape_error{S}
oracledb_instance_info{S}
```

### 负载与等待

```promql
oracledb_sysmetric_average_active_sessions{S}
oracledb_sysmetric_database_time_per_sec{S}
oracledb_sysmetric_io_requests_per_second{S}
oracledb_waitclassmetric_value{S}
```

### 资源与长会话

```promql
oracledb_resource_current_utilization{S}
oracledb_resource_limit_value{S}
oracledb_long_query_session_cnt{S}
oracledb_killed_session_cnt{S}
rate(oracledb_user_failed_logon_times{S}[5m])
```

### 空间

```promql
oracledb_tablespace_used_of_max{S}
oracledb_tablespace_used_gb{S}
oracledb_asm_diskgroup_used_percent{S}
oracledb_db_files_cnt{S}
oracledb_db_files_param{S}
```

### Data Guard

```promql
oracledb_dataguard_stats_stat_value_in_seconds{S}
oracledb_managed_standby_error_cnt{S}
oracledb_dataguard_logswitch_times24h{S}
```

## 解读要点

- `oracledb_up==0`：先看 exporter scrape error 与主机存活，再判实例 down。
- AAS / DB time 升高：只说明负载或等待增加，**根因**落到 wait class + AWR/ASH。
- `tablespace_used_of_max` / ASM percent 逼近 100%：可用性风险，优先于「优化 SQL」叙事。
- Data Guard `stat_value_in_seconds` 持续增大或 `managed_standby_error_cnt>0`：复制/备库异常，对齐角色与切换窗口。

## 边界

- 无 VisionDB Oracle status：不要声称「已从平台拉取会话列表」。
- `waitclassmetric` / `resource_*` 可能多 series：先 `series` 再选关键 label。
- 深度 SQL 调优超出 Prom 能力，输出中明确待用户补充 AWR/ASH。
