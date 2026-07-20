# OceanBase Playbook

## 识别

- 常兼容 MySQL 协议；实例名/租户信息重要
- 指标可能混有 `ob_*` 与 node exporter；IP 上可能有多个端口（SQL / RPC）

## 与 MySQL 的差异（必读）

- **租户 / 资源单元**：CPU、内存、IOPS 配额打满表现为「库慢」但主机未必打满
- 副本与 locality、合并（major/minor）窗口对 RT 的影响
- 执行计划与 hint 体系不完全等同社区 MySQL

## 可用性

- observer 进程、选举/切主日志
- 租户只读、磁盘水位、clog 磁盘
- 对照主机 IO（如 `io_util`）与 `ob_*` 资源指标

## 性能

- 先分清：租户配额 vs 主机饱和 vs SQL
- 慢日志/请求队列（以现网日志字段为准）
- SQL 优化可借鉴 MySQL 思路，但验证需在 OB 上 EXPLAIN

## 变更与巡检

- 参数是否租户级/集群级
- 合并窗口避开高峰
- 容量：数据盘 + clog/日志盘分离场景

## VisionDB（OceanBase）

若实例已纳管：可用 `search_instances` / `get_cluster` / `get_instance` / `list_cluster_logs` 等做元数据与运维痕迹定位。
**无** OB 专用运行时 status/config tool；不要套用 `get_mysql_instance_status`。
租户配额、合并窗口、执行计划仍依赖监控指标 + 用户提供的 OB EXPLAIN/平台报告。
