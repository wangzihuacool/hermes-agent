# VisionDB MCP 使用约定

供 `dba-troubleshooting` / `dba-monitoring-alerts` / `dba-performance-tuning` / `dba-engine-playbooks` 定位 CMDB 与 MySQL/Redis 运行时使用。
调用经 VisionDB MCP：`tool_search` → `tool_describe` → `tool_call`（见 SOUL.md）。入参 **snake_case**，响应字段常为 **camelCase**。

> 依据：visiondb-mcp `0.1.0` 与 visiondb-service 联调（2026-07）。枚举以 `list_*` 字典与实查为准。

## 能做什么 / 不能做什么

| 能（只读） | 不能 |
|------------|------|
| 搜应用/集群/实例/Agent；查拓扑与元数据 | 改 CMDB、下线、改参、触发切换、投递修复 |
| 异常实例盘点、切换史、修复任务、集群运维日志 | 查 MySQL errorlog/slowlog（用 VictoriaLogs） |
| MySQL/Redis 运行时 status / configs（经 Agent） | Oracle 等引擎的专用 status（无对应 tool） |
| 集群实时健康汇总 | SQL EXPLAIN / 慢日志报告 / 工单 |

`compare_mysql_cluster_config` 需 MCP 侧 `enable_config_compare=true`，默认可能不可用。

连通性：先 `visiondb_health`；`service_reachable=false` 时先修网络/BASE_URL，勿反复调业务工具。

## 实体与 ID

```text
Application (applicationId)
  └─ DbCluster (dbClusterId)
       └─ DbInstance (dbId)  ← PRIMARY / STANDBY
            └─ Server / Agent (agentId)
```

| 实体 | 主键（入参） | 响应字段例 |
|------|--------------|------------|
| 应用 | — | `applicationId` |
| 集群 | `db_cluster_id` | `dbClusterId` |
| 实例 | `db_id` | `dbId` |
| Agent | `agent_id`（搜时） | `agentId` |

JSON 里 ID 常为**字符串**（如 `"60449"`）；按 `tool_describe` 类型传参。本轮已有 `dbId`/`dbClusterId` 勿重复 search。

## 统一响应

成功：`ok=true` + `data`；失败：`ok=false` + `error` / `http_status`。  
分页：`data` / `pageNum` / `pageSize` / `total` / `hasMore`（默认 `page_size`≈20，上限约 50）。  
大结果可能 `truncated=true`——缩小时间窗或加 `keys`/`prefix`/`max_items`。

**API 错误（未绑定 Agent、HTTP 400）是取数失败，不是故障根因。**

## 易错枚举（必读）

### 两套 `env_mode`

| 场景 | 合法值 | 工具 |
|------|--------|------|
| 集群 search/query | CMDB 原值：`PROD`/`UAT`/`DEV`/`TEST`/… | `list_env_modes` |
| 异常实例 / 按类型统计 | **仅** `ALL` / `PROD` / `TEST`（TEST=非生产汇总） | `list_abnormal_instances` 等 |

禁止向异常接口传 `UAT`（会 400）。

### 角色 / 类型 / 集群状态

| 项 | 正确 | 禁止 |
|----|------|------|
| `db_role` | `PRIMARY` / `STANDBY` | `master` / `slave` |
| `db_type_name` | `MYSQL` / `REDIS` / `ORACLE`（大写，先 `list_db_types`） | `MySQL`（可能 0 条） |
| `db_cluster_status` | `available` / `maintain` / `init` / `offline` / `switching` / `error` | `ACTIVE` |

### 实例状态与故障类型

| `db_instance_status` | 含义 |
|----------------------|------|
| `online` | 正常 |
| `error` | 故障（`list_abnormal_instances` **唯一**纳入） |
| `offline` | 人工离线（非异常列表） |
| `building` | 接入中 |
| `discard` | 已下线终态（默认排除） |

`dead_type`（解释为何 error）：`heartbeat_failed` / `replica_failed` / `buddies_failed` / `dead_master` / `normal`。  
`replica_status`：`sync` / `delay` / `error`。延迟可为 online+delay，不等于 error。

## 工具选型速查

| 用户意图 | 优先 tool | 不要用 |
|----------|-----------|--------|
| 模糊搜（名/IP/域名） | `search_clusters` / `search_instances`（`keyword`） | `get_cluster`（需已有 ID） |
| 精确条件列集群 | `query_clusters` | 硬猜 keyword |
| 主备拓扑 | `get_cluster` | 把 realtime 当拓扑详情 |
| 集群级复制/心跳健康 | `get_cluster_realtime_status` | `get_instance` |
| Threads_running / 连接 | `get_mysql_instance_status`（`keys`/`prefix`） | `get_instance`（那是元数据） |
| max_connections 等参数 | `get_mysql_configs` / `get_redis_configs` | status 工具 |
| 当前故障库 | `list_abnormal_instances` | `query_instances` 当异常盘点 |
| 切换成败 | `list_switchover_history` | `list_cluster_logs` 代替切换结论 |
| 切换逐步审计 | `get_orchestrator_switch_steps`（`recovery_uid`←`switchOverToolUid`） | 仅看历史列表不下结论 |
| 从库修复史 | `list_recovery_tasks` / `get_recovery_task` | 与 switchover 混淆 |
| VisionDB 运维操作痕迹 | `list_cluster_logs` | MySQL errorlog（那是 VL） |
| 业务名 → 应用 | `search_applications` | — |
| Agent 是否在线 | `search_agents` | — |
| Service 是否通 | `visiondb_health` | 盲调业务工具 |

**无此接口（勿编造）**：`get_sqlserver_instance_status`、`get_oracle_instance_status` 等。

## 工具分类清单

| 分类 | 短名 |
|------|------|
| 健康 | `visiondb_health` |
| 字典 | `list_env_modes` / `list_db_types` / `list_areas` / `search_applications` / `search_agents` |
| 集群 | `search_clusters` / `query_clusters` / `get_cluster` / `list_cluster_domains` |
| 实例 | `search_instances` / `query_instances` / `get_instance` / `list_abnormal_instances` / `instance_stats_by_type` |
| 运行时 | `get_cluster_realtime_status` / `get_mysql_instance_status` / `get_redis_status` |
| 配置 | `get_mysql_configs` / `get_redis_configs` / `compare_mysql_cluster_config` |
| 历史 | `list_switchover_history` / `get_orchestrator_switch_steps` / `list_recovery_tasks` / `get_recovery_task` / `list_cluster_logs` |

## 典型调用链

### 1. 业务名 → 拓扑健康

```text
search_applications(application_name=...)
  → query_clusters / search_clusters → db_cluster_id
  → get_cluster → masters/slaves、masterDbId
  → get_cluster_realtime_status
  →（MySQL/Redis）get_*_status(db_id=..., keys=[...])
```

### 2. 只有 IP

```text
search_instances(keyword="<ip>")
  → get_instance / 取 dbClusterId
  → get_cluster（需要拓扑时）
```

### 3. DeadMaster / 切换核实

```text
list_switchover_history(start_time, end_time)  # 成对；默认约近 7 天
  → switchOverToolUid
  → get_orchestrator_switch_steps(recovery_uid=...)
  → list_recovery_tasks / list_cluster_logs（同窗交叉）
```

### 4. 盘点故障实例

```text
list_abnormal_instances(env_mode="PROD", include_stats=true, page_size=20)
  → 目标 dbId：get_instance + get_mysql_instance_status（若 MYSQL）
```

### 5. 查连接数（控体量）

```text
get_mysql_instance_status(
  db_id=...,
  keys=["Threads_running", "Threads_connected", "Connections", "Uptime"],
  max_items=10
)
```

## 与其它 MCP 的分工

| 问题 | 优先 |
|------|------|
| 拓扑、CMDB 状态、切换/修复、MySQL/Redis 当前 status | **VisionDB** |
| 同窗趋势、`up`、历史曲线 | **Prometheus**（见 `prometheus-*.md`） |
| 主机 util/await、Zabbix 告警 | **Zabbix** |
| errorlog / slowlog / processlist / agent 日志 | **VictoriaLogs**（见 `victorialogs-mysql.md`） |

推荐组合：VisionDB 定位 `dbId`/IP/角色 → Prom 同窗佐证 → VL 日志侧证。

当前负载：SOUL 约定 **先 Prom 趋势**；Prom 无数据或需 SHOW STATUS 细节时再 `get_mysql_instance_status` / `get_redis_status`。

## 常见误区

| 误区 | 正确做法 |
|------|----------|
| `search_instances(ip=...)` | 参数名是 **`keyword`** |
| 入参用 `dbClusterId` | 入参用 **`db_cluster_id`** |
| `get_instance` 当运行时 | 用 `get_*_status` |
| `list_cluster_logs` 当 errorlog | 用 VictoriaLogs |
| 异常接口 `env_mode=UAT` | 用 `TEST` 或 `ALL` |
| `db_type_name=MySQL` | 用 `MYSQL` |
| 已有 ID 仍反复 search | 直接 `get_cluster` / `get_instance` |
| `discard`/`offline` 当异常列表口径 | 异常列表仅 `error` |
| Agent 未绑定报错当「库挂了」 | 写明取数失败，改 Prom/Zabbix/VL |

## 超时与截断

- status/config 经 Agent，超时可能较长（约 60s）；先确认 Agent online（`search_agents` / 实例上的 `agentId`）。
- 切换史过大 → 缩时间窗；status 过大 → `keys`/`prefix`/`max_items`。
- `hasMore=true` 时翻 `page_num`，勿假设一页即全集。
