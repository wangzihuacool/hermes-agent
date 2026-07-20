# Prometheus · Redis 指标排障约定

供告警解读 / 故障排查 / 性能定界时查 Redis 监控使用。
调用经 Prometheus MCP（见 SOUL.md）。指标名来自现网 `v_metric_type="REDIS"`（集群场景可能还有 `REDISCLUSTER` / `RDSFORREDIS` / `ELASTICACHECLUSTER`——以 `label_values` 为准）。

## MCP 工具速查

| 目的 | 短名 |
|------|------|
| 发现 | `label_values` / `series` / `metric_metadata` |
| 瞬时 | `query`（Prometheus，不是 VL） |
| 趋势 | `range_query` |
| 告警 | `list_alerts` |

## 发现→查询硬流程（违反即视为未按规程排查）

1. `tool_describe(mcp__prometheus__query)` → 读 `server_instructions` 中的 MCP 规程。
2. 用 VisionDB 或告警确定 `<ip>:<port>`，selector 固定为 `{v_metric_source="...", v_metric_type="REDIS"}`（集群场景不确定时先 `label_values(v_metric_type)`）。
3. **发现**（至少一步）：`label_values` / `series` 确认指标与标签存在。
4. **再查询**：`query` / `range_query` 只用第 3 步已确认存在的指标名。
5. **空结果**：禁止换猜的 `redis_*` 名字；回到第 3 步或交叉 VisionDB `get_redis_status` + VL。

**禁止**：跳过发现直接套用下文模板；模板指标名为候选，不是默认存在。

## 通用约定

```text
{v_metric_source="<ip>:<port>", v_metric_type="REDIS"}
```

1. 定位用 `v_metric_source` + `v_metric_type`；禁止对 `instance` 做 IP 正则。
2. 端口：告警/VisionDB `dbPort1` → 默认 6379（兜底须声明）。
3. 集群节点可能 `v_metric_type="REDISCLUSTER"`：不确定时 `label_values(v_metric_type)` 或对同一 IP 用 `series`。
4. 当前负载优先 VisionDB `get_redis_status`；本文件补同窗趋势佐证。
5. **禁止**建议生产执行 `KEYS *`；大 key/热 key 用平台能力或用户授权命令。

## 按场景推荐指标顺序

| 场景 | 第 1 步 | 第 2 步 | 第 3 步 | 辅证 |
|------|---------|---------|---------|------|
| 挂了/连不上 | `redis_up` | `redis_connected_clients` | `rate(redis_rejected_connections_total)` | VisionDB status；主机/端口 |
| 内存满/OOM 风险 | `redis_memory_used_bytes` vs `redis_memory_max_bytes` | `rate(redis_evicted_keys_total)` | `redis_allocator_frag_ratio` | VL/系统 OOM；configs `maxmemory` |
| 慢/阻塞 | `redis_blocked_clients` | `rate(redis_commands_processed_total)` | `rate(redis_commands_duration_seconds_total)`（若有） | `SLOWLOG`（需授权） |
| 命中率差 | `rate(redis_keyspace_hits_total)` vs `misses` | `redis_db_keys` | eviction 是否升高 | 业务缓存策略 |
| 主从/复制 | `redis_master_link_up` | `redis_master_last_io_seconds_ago` | `redis_connected_slaves` / `redis_master_sync_in_progress` | 角色以 VisionDB 为准 |
| 集群槽异常 | `redis_cluster_state` | `redis_cluster_slots_ok` / `_fail` / `_pfail` | `redis_cluster_known_nodes` | 仅 cluster 模式 |

## 核心指标速查（现网常见）

| 用途 | 指标名 |
|------|--------|
| 存活 | `redis_up` |
| 客户端 | `redis_connected_clients`、`redis_blocked_clients`、`redis_rejected_connections_total` |
| 吞吐 | `redis_commands_processed_total`（`rate`）；失败/拒绝：`redis_commands_failed_calls_total`、`redis_commands_rejected_calls_total` |
| 内存 | `redis_memory_used_bytes`、`redis_memory_max_bytes`、`redis_memory_used_rss_bytes`、`redis_memory_used_peak_bytes` |
| 碎片 | `redis_allocator_frag_ratio`、`redis_allocator_frag_bytes` |
| 键/过期/驱逐 | `redis_db_keys`、`redis_db_keys_expiring`、`redis_expired_keys_total`、`redis_evicted_keys_total` |
| 命中 | `redis_keyspace_hits_total`、`redis_keyspace_misses_total` |
| 复制 | `redis_master_link_up`、`redis_master_last_io_seconds_ago`、`redis_connected_slaves`、`redis_master_repl_offset`、`redis_master_sync_in_progress` |
| 集群 | `redis_cluster_enabled`、`redis_cluster_state`、`redis_cluster_slots_*`、`redis_cluster_known_nodes` |
| AOF | `redis_aof_enabled`、`redis_aof_last_write_status`、`redis_aof_rewrite_in_progress` |
| Exporter | `redis_exporter_last_scrape_error` |

> 部分环境无 `redis_instantaneous_ops_per_sec`：用 `rate(redis_commands_processed_total[1m])` 代替瞬时 OPS。

## PromQL 模板（`S` = `v_metric_source="<ip>:<port>",v_metric_type="REDIS"`）

### 摸底 / 存活

```promql
redis_up{S}
redis_exporter_last_scrape_error{S}
```

### 连接与拒绝

```promql
redis_connected_clients{S}
redis_blocked_clients{S}
rate(redis_rejected_connections_total{S}[5m])
```

### 内存与驱逐

```promql
redis_memory_used_bytes{S}
redis_memory_max_bytes{S}
redis_memory_used_bytes{S} / clamp_min(redis_memory_max_bytes{S}, 1)
rate(redis_evicted_keys_total{S}[5m])
redis_allocator_frag_ratio{S}
```

### 吞吐与命中率

```promql
rate(redis_commands_processed_total{S}[5m])
rate(redis_keyspace_hits_total{S}[5m])
  / clamp_min(rate(redis_keyspace_hits_total{S}[5m]) + rate(redis_keyspace_misses_total{S}[5m]), 1e-9)
```

### 复制

```promql
redis_master_link_up{S}
redis_master_last_io_seconds_ago{S}
redis_connected_slaves{S}
redis_master_sync_in_progress{S}
```

### 集群（仅 cluster）

```promql
redis_cluster_state{S}
redis_cluster_slots_ok{S}
redis_cluster_slots_fail{S}
redis_cluster_slots_pfail{S}
```

## 解读要点

- `redis_up==0` / 无数据：先排除 exporter 断采，再判进程宕机。
- `used/maxmemory` 高 + `evicted` 升：容量/淘汰压力；对照 `maxmemory-policy`（VisionDB configs）。
- `blocked_clients` 升高：可能 BLPOP/慢命令/客户端阻塞，勿直接归因「QPS 高」。
- `master_link_up==0` 或 `last_io` 持续增大：复制中断/网络，交叉角色与切换史。

## 边界

- `v_metric_type` 在 REDIS / REDISCLUSTER / RDSFORREDIS 间切换时，空结果先换 type 再下「无监控」结论。
- 性能深挖仍依赖慢日志/授权命令；Prom 只给趋势与饱和信号。
