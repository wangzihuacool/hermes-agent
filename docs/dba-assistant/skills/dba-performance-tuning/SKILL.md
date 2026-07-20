---
name: dba-performance-tuning
description: "Tune SQL, indexes, locks, params, and hosts."
version: 1.3.0
author: wl
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dba, performance-tuning, sql, index, lock, mysql, redis, oracle, visiondb]
    category: dba
    related_skills:
      - dba-troubleshooting
      - dba-engine-playbooks
      - dba-monitoring-alerts
---

# DBA Performance Tuning Skill

性能问题从「症状 → 资源 → SQL/锁/参数/架构」收敛。
监控 + 日志为主；VisionDB 用于定位实例、运行时 status 与参数核对。
**无** SQL EXPLAIN / format / sandbox / 慢日志报告接口——计划分析需用户粘贴 EXPLAIN 或授权只读会话。

## When to Use

- 慢查询、RT 升高、QPS 掉、锁等待、缓存命不中
- 评估索引、SQL 改写、参数、读写分离与分片方向
- 主机 IO/CPU 高且怀疑库负载驱动

## Prerequisites

- Prometheus + VictoriaLogs（慢日志/错误日志）优先
- Zabbix 用于主机侧饱和度
- VisionDB：实例定位、`get_*_status`、`get_*_configs`（经 `tool_search` → `tool_describe` → `tool_call`；细节见 `visiondb-mcp.md`）

## How to Run

1. VisionDB 锁定实例（`search_instances` 用 `keyword`）；**先** `get_*_status` / configs 定界。
2. 趋势再用 Prom（`tool_search` 短名 `range_query`；用 `v_metric_source`+`v_metric_type` 定位，见 SOUL.md）或 Zabbix；搜不到则跳过并写缺口。
3. 从慢日志找候选（VictoriaLogs，勿当 Prom）。
4. 按引擎 checklist 分析（`dba-engine-playbooks`）。
5. 给出可验证的优化建议与风险。

## Quick Reference

| 层级 | 信号 | 常见方向 |
|------|------|----------|
| 运行时 | **VisionDB status（优先）** | 定界是否库内饱和 |
| 主机 | Zabbix util/await/CPU | 扩容、IO、吵闹邻居 |
| 趋势 | Prom `range_query`（可选） | 对比基线 |
| SQL | VL slowlog | 改写、索引 |
| 锁 | 等待、死锁日志 | 缩短事务 |
| 参数 | VisionDB configs | 有依据调参 |
| 架构 | 单写热点、大表 | 读写分离、分片 |

### VisionDB 调用顺序（性能定界）

| 步骤 | 能力 | 说明 |
|------|------|------|
| 1 | `search_instances`（`keyword`）等 | 锁定；已有 dbId 则跳过 |
| 2 | `get_mysql_instance_status` / `get_redis_status` | **当前负载第一步** |
| 3 | `get_mysql_configs` / `get_redis_configs` | 缓冲池/连接/超时等 |
| 4 | `get_cluster`（`db_cluster_id`）仅需拓扑时 | 勿重复已回答过的归属问题 |
| 5 | Zabbix / Prom / VL | 主机、趋势、慢日志；遵守 SOUL 防空转 |

**不要**声称已通过 VisionDB 做 EXPLAIN；需要计划时请用户回贴或走只读客户端。

## Procedure

### Step 1 — 定界

- 时间窗、实例、业务入口
- 对比基线：昨天同时段 / 上周
- VisionDB：status/config 定界库内状态
- Prom：QPS、RT、连接、锁、缓冲池/命中率（按实际指标）
- Zabbix：CPU、iowait、磁盘、swap

### Step 2 — 找 SQL / 命令热点

VictoriaLogs（MySQL 约定与 LogsQL 模板见 `dba-engine-playbooks/references/victorialogs-mysql.md`）：

1. 过滤用 **`source_ip:"<IP>"`**（勿用 `host`）；先 `streams` / `field_values` 确认 `mysql_slowlog` / `mysql_processlist`。
2. `hits` 看慢查询是否突增（VL 的 `hits`，不是 Prom `range_query`）。
3. VL `query` 抽样：指纹、表名、`query_time` / `lock_time`、锁等待关键字；`processlist` 必须短窗 + `limit`。

### Step 3 — 分析维度

对每条热点 SQL/命令评估：

1. **访问路径**：能否用索引？选择性？覆盖索引？（需 EXPLAIN 证据）
2. **数据量**：时间窗、分页、是否全表
3. **写入模型**：是否放大写、是否热点键
4. **锁**：持锁时长、事务边界、间隙锁风险（MySQL）
5. **执行频率**：单次慢 vs 高频放大

### Step 4 — 建议分级

| 级别 | 例子 | 要求 |
|------|------|------|
| 立即 | kill 长事务（需确认）、限流、切从库读 | 可回滚、说明影响 |
| 短期 | 加索引、改 SQL、补统计信息 | 给出验证 EXPLAIN/对比 |
| 中期 | 参数、拆分、缓存、架构 | 评估风险与窗口；参数建议对照 VisionDB 现值 |

**禁止**：无 EXPLAIN/证据的「先加个索引」；生产直接改参数不说明重启/动态性。

### Step 5 — 验证

- 优化前后：耗时、扫描行、util/await、业务 RT
- 用同一时间窗对比 Prom/`hits`；必要时复查 VisionDB status

## Pitfalls

- 优化表象 SQL，忽略错误的业务调用频率。
- 在主库做昂贵分析影响生产。
- Redis 大 KEY / 热 KEY 与 MySQL 慢 SQL 混用同一套话术。
- 把 OceanBase/PG 的执行计划术语套到 MySQL（加载 engine playbooks）。
- 把 VisionDB status 当 SQL 计划依据。
- 用 `host` 过滤 VL 实例 IP，或把 Prom `query` 当成 LogsQL 入口。

## Verification

- 至少一条证据链：监控或慢日志 → 候选 SQL/命令 → 建议 → 验证方法。
- 每条 DDL/参数变更建议附风险与回滚点；参数建议引用当前配置来源。
