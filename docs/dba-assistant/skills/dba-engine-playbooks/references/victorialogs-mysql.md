# VictoriaLogs · MySQL 日志排障约定

供 `dba-troubleshooting` / `dba-monitoring-alerts` / `dba-performance-tuning` 在查 MySQL 日志时使用。
调用经 VictoriaLogs MCP：`tool_search` → `tool_describe` → `tool_call`（见 SOUL.md）。短名目的见下表。

## MCP 工具速查

| 目的 | 短名 | 说明 |
|------|------|------|
| 列 stream / 摸底 | `streams` | 确认该 IP 有哪些日志源 |
| 字段分布 | `field_values` / `field_names` | 如 `log_level`、`log_type` |
| 量/趋势 | `hits` | 错误或慢日志是否突增 |
| 日志行抽样 | `query` | 取 5–30 条原文；**不是** Prometheus 的 `query` |
| 聚合统计 | `stats_query` / `stats_query_range` | 仅 LogsQL 统计；**不要**当 PromQL |

## 通用约定

1. **按实例 IP 过滤一律用 `source_ip:"<IP>"`**。`host` 是采集机主机名，禁止当 DB IP。
2. **顺序**：`streams` / `field_values` 摸底 → 按场景 `query` / `hits`（见下表）。
3. **体量**：`mysql_processlist` 必须 `source_ip` + 短 `_time`（如 `15m`）+ `limit`（建议 ≤30）。
4. **不限 ERROR**：慢查询、长会话、心跳 `repl_delay_time` 常在 INFO 或非 ERROR 字段。
5. 无 IP：先 `streams`/`field_values` 看 `source_ip` 分布，或请用户提供；禁止猜 IP。

通用前缀：

```text
source_ip:"<db_ip>" _time:1h
```

时间按用户指定调整；复制/间歇问题可用 `_time:6h` 或 `_time:1d`。

## 日志源与 stream

| 日志源 | 物理来源 | stream 片段 |
|--------|----------|-------------|
| MySQL 错误日志 | `log_error` | `_stream:{service="MySQL",log_type="mysql_errorlog"}` |
| MySQL 慢日志 | `slow_query_log` | `_stream:{service="MySQL",log_type="mysql_slowlog"}` |
| 进程列表快照 | `SHOW PROCESSLIST` | `_stream:{service="MySQL",log_type="mysql_processlist"}` |
| 系统日志 | `/var/log/messages` | `_stream:{service="system",log_type="system_log"}` |
| Agent 主日志 | `visiondb-agent.log` | `_stream:{service="visiondb-agent",log_type="visiondb_agent_log"}` |
| Agent 心跳 | `heartbeat.log` | `_stream:{service="visiondb-agent",log_type="heartbeat_log"}` |

环境若 stream 名不同：以 `streams`/`field_values` 实查为准，不要硬套。

## 按分类的推荐查询顺序

| 分类 | 第 1 步 | 第 2 步 | 第 3 步 | 第 4 步 |
|------|---------|---------|---------|---------|
| A 连接/可用性 | `heartbeat_log` `is_alive` | `mysql_errorlog` 连接类 | `visiondb_agent_log` 连接失败 | `system_log` 网络/端口 |
| B 性能/慢 | `mysql_slowlog` `query_time` | `mysql_processlist` 长 Query | `mysql_errorlog` | `hits` 慢日志趋势 |
| C 锁/事务 | `mysql_errorlog` deadlock/lock | `mysql_processlist` Locked/Waiting | `mysql_slowlog` `lock_time` | `visiondb_agent_log` |
| D 复制/HA | `heartbeat_log` `repl_*` | `mysql_errorlog` replication | `visiondb_agent_log` | 对端实例同查 |
| E 资源/IO | `system_log` cpu/io/oom | `mysql_errorlog` | `mysql_processlist` 活跃数 | `mysql_slowlog` 是否突发 |
| F 存储 | `mysql_errorlog` space | `system_log` disk/no space | — | — |
| G 崩溃 | `mysql_errorlog` crash/recovery | `system_log` oom/kill/mysqld | `heartbeat_log` 中断区间 | — |
| H Agent/误报 | `visiondb_agent_log` ERROR | `heartbeat_log` | `mysql_errorlog` 对照实例真相 | — |
| I 配置/权限 | `mysql_errorlog` access denied / read-only | `heartbeat_log` 角色 | `visiondb_agent_log` | — |

## Agent 排障要点

1. 心跳关键字段：`is_alive`、`repl_sync_status`、`repl_delay_time`、`repl_error_info`、`buddy_info`、`response_success`。
2. `repl_error_info` 含「连接池未就绪」→ 查 `visiondb_agent_log` 连接/池相关 ERROR，并对照 `mysql_errorlog` 区分 Agent 问题 vs 实例问题。
3. 约 60s 周期性 ERROR：可能是采集兼容性噪声，须用 `mysql_errorlog` 交叉验证。
4. Agent 不可达 ≠ MySQL 宕机：交叉 `mysql_errorlog` + `system_log` 后再下结论。

## LogsQL 模板（把 `<db_ip>` 换成实例 IP）

### 摸底

```text
streams: source_ip:"<db_ip>" _time:1h
source_ip:"<db_ip>" _time:1h | limit 1
```

### A. 连接与可用性

```text
source_ip:"<db_ip>" _stream:{service="visiondb-agent",log_type="heartbeat_log"} _time:1h | limit 10
source_ip:"<db_ip>" _stream:{service="visiondb-agent",log_type="heartbeat_log"} is_alive:0 _time:6h | limit 20
source_ip:"<db_ip>" _stream:{service="MySQL",log_type="mysql_errorlog"} "Too many connections" _time:6h | limit 20
source_ip:"<db_ip>" _stream:{service="MySQL",log_type="mysql_errorlog"} "Can't connect" _time:6h | limit 20
source_ip:"<db_ip>" _stream:{service="MySQL",log_type="mysql_errorlog"} "Aborted connection" _time:6h | limit 20
source_ip:"<db_ip>" _stream:{service="visiondb-agent",log_type="visiondb_agent_log"} level:ERROR _time:1h | limit 15
source_ip:"<db_ip>" _stream:{service="system",log_type="system_log"} "Connection refused" _time:6h | limit 20
```

### B. 性能与慢查询

```text
source_ip:"<db_ip>" _stream:{service="MySQL",log_type="mysql_slowlog"} query_time:>2 _time:1h | limit 30
hits: query=source_ip:"<db_ip>" _stream:{service="MySQL",log_type="mysql_slowlog"} _time:6h, step=15m
source_ip:"<db_ip>" _stream:{service="MySQL",log_type="mysql_processlist"} processlist_command:Query processlist_time:>60 _time:15m | limit 20
```

### C. 锁与事务

```text
source_ip:"<db_ip>" _stream:{service="MySQL",log_type="mysql_errorlog"} Deadlock _time:6h | limit 20
source_ip:"<db_ip>" _stream:{service="MySQL",log_type="mysql_errorlog"} "Lock wait timeout" _time:6h | limit 20
source_ip:"<db_ip>" _stream:{service="MySQL",log_type="mysql_processlist"} "Waiting for" _time:15m | limit 20
source_ip:"<db_ip>" _stream:{service="MySQL",log_type="mysql_slowlog"} lock_time:>1 _time:6h | limit 20
```

### D. 复制与高可用

```text
source_ip:"<db_ip>" _stream:{service="visiondb-agent",log_type="heartbeat_log"} repl_delay_time:>0 _time:1d | limit 20
source_ip:"<db_ip>" _stream:{service="visiondb-agent",log_type="heartbeat_log"} repl_error_info _time:1d | limit 20
source_ip:"<db_ip>" _stream:{service="MySQL",log_type="mysql_errorlog"} "Replication" _time:1d | limit 20
source_ip:"<db_ip>" _stream:{service="MySQL",log_type="mysql_errorlog"} "Group Replication" _time:1d | limit 20
```

### E / F / G. 资源 · 磁盘 · 崩溃

```text
source_ip:"<db_ip>" _stream:{service="system",log_type="system_log"} "Out of memory" _time:1d | limit 20
source_ip:"<db_ip>" _stream:{service="system",log_type="system_log"} "No space left" _time:1d | limit 20
source_ip:"<db_ip>" _stream:{service="system",log_type="system_log"} "oom-killer" _time:1d | limit 20
source_ip:"<db_ip>" _stream:{service="MySQL",log_type="mysql_errorlog"} "not shut down normally" _time:1d | limit 20
source_ip:"<db_ip>" _stream:{service="MySQL",log_type="mysql_errorlog"} "ready for connections" _time:1d | limit 20
```

### H. Agent

```text
source_ip:"<db_ip>" _stream:{service="visiondb-agent",log_type="visiondb_agent_log"} level:ERROR _time:1h | limit 20
source_ip:"<db_ip>" _stream:{service="visiondb-agent",log_type="heartbeat_log"} response_success:false _time:1d | limit 10
```

## 边界

- `mysql_processlist` 为周期性快照，避免单点误判；可短窗多次 `query`。
- 跨源比对注意宿主机 NTP 时差。
- MCP 不可用：说明原因，禁止伪造查询结果。
- Oracle / Redis 日志路径不同，勿套本文件的 MySQL `log_type`。
