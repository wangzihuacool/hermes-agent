# Redis Playbook

## 识别

- 端口常 6379；指标常 `redis_*`
- 模式：单机 / 哨兵 / 集群
- VisionDB：`get_instance` / `list_db_types` 确认类型与角色

## Prometheus（Redis）

同窗趋势与关键指标约定、PromQL 模板见：

`references/prometheus-redis.md`

要点：`v_metric_source`+`v_metric_type="REDIS"`（集群可能是 `REDISCLUSTER` 等）；`redis_up` / 内存 / 复制 / 集群槽；先发现再查询。

## 可用性

- `rejected_connections`、OOM、进程消失
- 集群：槽迁移中、节点 fail、脑裂相关日志
- 持久化失败导致重启策略异常
- VisionDB：`get_cluster_realtime_status`；实例用 `get_redis_status`

## 性能

- `instantaneous_ops_per_sec`、命中率、`evicted_keys`、`blocked_clients`
- 延迟：慢日志（`SLOWLOG`，只读）、大 key、热 key
- **禁止**在生产用 `KEYS *`；慎用可能阻塞的命令
- VisionDB：`get_redis_status`（可用 keys/prefix 收窄返回）补强运行时

## 内存与容量

- `used_memory` vs `maxmemory`、eviction 策略是否符合预期
- 碎片率异常需结合版本与负载解释
- VisionDB：`get_redis_configs` 查 `maxmemory`、timeout 等

## 变更风险

- 配置变更是否需重启
- 数据结构迁移避免大 value 一次写入
- 扩容迁移窗口与客户端拓扑刷新
- 变更前用 VisionDB 核对角色与当前配置现值

## 只读诊断（需授权）

```text
INFO
INFO memory
INFO clients
SLOWLOG GET 16
```

集群信息类命令按权限最小化执行。无客户端时优先 `get_redis_status` / `get_redis_configs`。

## VisionDB（Redis）

工具通览：`references/visiondb-mcp.md`。

| 用途 | Tool | 入参注意 |
|------|------|----------|
| 定位 | `search_instances` / `search_clusters` | `keyword`，不是 `ip` |
| 拓扑/详情 | `get_cluster` / `get_instance` | `db_cluster_id` 等以 describe 为准 |
| 健康 | `get_cluster_realtime_status` | — |
| **当前负载** | **`get_redis_status`** | 优先 Prom；不足时用本 tool；可用 keys/prefix 收窄 |
| 配置 | `get_redis_configs` | — |

调用与防空转见 SOUL.md。
