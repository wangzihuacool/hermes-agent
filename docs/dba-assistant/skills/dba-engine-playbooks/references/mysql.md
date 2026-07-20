# MySQL Playbook

## 识别

- 端口常 3306；日志 `log_type` 常见 `mysql_errorlog` / `mysql_slowlog` / `mysql_processlist`（以环境为准）
- Prom 指标常见 `mysql_*` / `mysqld_exporter`
- VisionDB：`list_db_types` / `get_instance` 确认库类型

## VictoriaLogs（MySQL）

排障/告警侧证时的 **过滤约定、stream 映射、按场景查询顺序、可复制 LogsQL** 见同目录：

`references/victorialogs-mysql.md`

要点：`source_ip` 过滤实例 IP（勿用 `host`）；`streams`/`field_values` → `hits` → `query`；VL `query` ≠ Prom `query`。

## Prometheus（MySQL）

同窗趋势、存活与连接/复制/锁等指标约定与 PromQL 模板：

`references/prometheus-mysql.md`

要点：`v_metric_source`+`v_metric_type="MYSQL"`；先 `label_values`/`series` 再 `range_query`；`mysql_up` 无数据先排除断采。

## 可用性

- 连通性、只读探测失败、连接打满（Threads_connected vs max_connections）
- 错误日志：crash、InnoDB、磁盘满、权限、认证风暴
- HA：Orchestrator/自研切换日志；只读实例误写
- VisionDB：`get_cluster_realtime_status`；切换用 `list_switchover_history` → `get_orchestrator_switch_steps`；修复用 `list_recovery_tasks`

## 性能

- 慢日志突增（VL `hits`）→ 抽样指纹
- 锁：死锁日志、行锁等待、metadata lock
- 临时表/文件排序、全表扫描线索
- 缓冲池命中、redo/刷新相关指标（按实际导出）
- VisionDB：`get_mysql_instance_status`（Threads_running 等）；**无 EXPLAIN 接口**，计划需用户回贴

## 复制

- Seconds_Behind_Source/Slave、IO/SQL 线程状态
- 延迟升高时区分：大事务、从库资源、网络
- VisionDB 实时状态 + Prom lag 交叉验证

## 参数与变更

- 动态 vs 需重启；`innodb_buffer_pool_size`、超时类、并行复制
- DDL：在线策略、OSC、磁盘与 binlog 余量
- VisionDB：`get_mysql_configs`（可 `param_name`）；集群差异 `compare_mysql_cluster_config`

## 只读诊断 SQL（需授权，控制结果集）

```sql
SHOW GLOBAL STATUS LIKE 'Threads_%';
SHOW PROCESSLIST;  -- 或 performance_schema 摘要
-- EXPLAIN / EXPLAIN ANALYZE（版本允许时）针对单条 SQL
```

## VisionDB（MySQL）

工具入参、枚举与调用链通览：`references/visiondb-mcp.md`。

| 用途 | Tool | 入参注意 |
|------|------|----------|
| 定位 | `search_instances` / `search_clusters` / `list_cluster_domains` | `search_instances` 用 **`keyword`**，不是 `ip` |
| 拓扑 | `get_cluster` / `query_instances` / `get_instance` | `get_cluster` 用 **`db_cluster_id`**，不是 `dbClusterId` |
| 健康 | `get_cluster_realtime_status` | — |
| **当前负载** | **`get_mysql_instance_status`** | 优先 Prom；Prom 不足时用本 tool；控体量用 `keys`/`prefix` |
| 配置 | `get_mysql_configs` / `compare_mysql_cluster_config` | compare 可能未启用 |
| 切换/修复 | `list_switchover_history` / `get_orchestrator_switch_steps` / `list_recovery_tasks` / `get_recovery_task` | — |
| 运维日志 | `list_cluster_logs` | 不是 MySQL errorlog |

仍不可用：SQL explain/format/sandbox、慢日志报告平台接口。
调用经 `tool_search` → `tool_describe` → `tool_call`；防空转见 SOUL.md。
