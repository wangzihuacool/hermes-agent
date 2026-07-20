---
name: dba-change-risk
description: "Assess database change risk before apply."
version: 1.2.0
author: wl
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dba, change, risk, ddl, migration, mysql, oracle, redis, visiondb]
    category: dba
    related_skills:
      - dba-inspection
      - dba-performance-tuning
      - dba-engine-playbooks
---

# DBA Change Risk Skill

在变更执行前做结构化风险评估。默认立场：生产变更高风险，除非证据证明低风险。
本 skill **只评估与建议**，不代替变更系统执行。

## When to Use

- DDL、索引变更、大表变更
- 参数调整、版本升级、切换/扩缩容
- Redis 配置/数据结构迁移
- 研发询问「这个 SQL/脚本能不能上」

## Prerequisites

- 变更对象、环境（prod/stg）、窗口、回滚方案（可追问）
- VisionDB：实例/集群元数据、主从角色、参数与集群配置对比
- 监控 MCP：当前负载基线
- MCP 经 `tool_search` → `tool_describe` → `tool_call` 调用（见 SOUL.md）；下文短名不是顶层工具名
- **没有**工单/变更单状态接口；工单信息需用户提供

## How to Run

按风险清单打分，输出：风险等级、阻塞项、建议窗口与验证。

## Quick Reference

| 风险域 | 高风险信号 |
|--------|------------|
| 锁与阻塞 | 大表 DDL 无在线策略、长事务并存 |
| 复制 | 从库延迟高、无延迟监控 |
| 性能 | 删索引、改类型导致计划劣化 |
| 容量 | 临时空间、binlog、磁盘余量不足 |
| 回滚 | 无反向脚本、不可逆数据变更 |
| 主机 | 变更窗内 util/CPU 已高位 |
| 配置漂移 | 集群内参数不一致（`compare_mysql_cluster_config`） |

### VisionDB 调用顺序（变更评估）

| 步骤 | Tool | 说明 |
|------|------|------|
| 1 | `search_clusters` / `search_instances`（`keyword`）/ `search_applications` | 锁定对象 |
| 2 | `get_cluster`（`db_cluster_id`）/ `get_instance` | 确认是否主库、拓扑、环境 |
| 3 | `get_cluster_realtime_status` | 当前主从/健康是否允许变更 |
| 4 | `get_mysql_configs` / `get_redis_configs` | 目标参数现值 |
| 5 | `compare_mysql_cluster_config` | MySQL 集群内配置差异 |
| 6 | `list_switchover_history` / `list_cluster_logs` | 近期是否刚切换 |
| 7 | Prometheus / Zabbix 基线 | 负载、磁盘、lag；遵守 SOUL 防空转 |

入参一律以 `tool_describe` 的 snake_case 为准，勿用响应 camelCase。

## Procedure

### 1. 澄清变更单

必须弄清：

1. 引擎与对象（库/表/key pattern/参数名）
2. 环境与是否主库执行（用 VisionDB 核对，不靠口述）
3. 预估表大小/QPS/是否业务高峰
4. 是否在线 DDL / 工具（pt-osc、gh-ost 等）
5. 回滚方案与验证 SQL
6. 关联工单/审批状态（用户提供；VisionDB 无工单查询）

### 2. VisionDB 对象与配置

1. 按调用顺序锁定集群/实例，确认**执行角色**（主/从）。
2. 读相关参数现状；MySQL 集群做配置对比，发现漂移先标风险。
3. 若近期有切换失败或异常修复未收敛，倾向提高风险等级或阻塞。

### 3. 基线快照（监控）

变更前用 Prometheus/Zabbix 记录：

- 主机：CPU、磁盘 util/await、空间
- 库：连接、QPS、lag、慢查询速率

基线用于变更后对比与「现在能不能上」。

### 4. 风险检查清单

**MySQL / OceanBase（类 MySQL）**

- [ ] 表大小与行数数量级已知
- [ ] DDL 是否锁表；有无 `ALGORITHM`/`LOCK` 或 OSC 方案
- [ ] 是否改主键/唯一键/列类型（重建风险）
- [ ] 索引增删对写放大与优化器影响
- [ ] binlog、磁盘、临时目录余量
- [ ] 长事务/大查询窗口冲突
- [ ] 从库应用延迟与只读流量
- [ ] 集群内关键参数一致（VisionDB 对比）

**Redis**

- [ ] 大 key / 热 key 变更方式（避免阻塞命令）
- [ ] 内存头寸与 eviction 策略（`get_redis_configs` / `get_redis_status`）
- [ ] 集群槽迁移或扩缩容影响
- [ ] 持久化（AOF/RDB）窗口

**Oracle**

- [ ] 对象锁与业务高峰
- [ ] 统计信息失效风险
- [ ] undo/temp 压力
- [ ] Data Guard 延迟与切换影响

**通用**

- [ ] 可回滚性
- [ ] 观测性：变更后看哪些指标/日志
- [ ] 沟通面：影响哪些应用（可用 `search_applications` 辅助）

### 5. 评级与建议

| 等级 | 含义 | 建议 |
|------|------|------|
| 低 | 可逆、在线、影响面小 | 可按窗口执行 |
| 中 | 有可控风险 | 限速/OSC/先从库 |
| 高 | 锁表/不可逆/高峰冲突 | 改方案或换窗口 |
| 阻塞 | 关键信息缺失或现网已红 | 禁止执行直到补齐 |

输出必须含：**阻塞项列表**（若有）、**建议执行步骤**、**回滚**、**监控守望项**。

## Pitfalls

- 只看 SQL 文本不看表现况负载。
- 把 stg 成功直接等同 prod 安全。
- 忽略「变更过程中」的复制与磁盘。
- 未查 VisionDB 却声称已知主从角色；或把「无工单接口」当成「已审批」。

## Verification

- 风险等级有清单条目支撑。
- 每个高风险项有缓解措施或明确「不可接受」。
- 给出变更后 15–30 分钟观察指标列表。
- 主库/从库角色有 VisionDB 证据（或已声明查不到）。
