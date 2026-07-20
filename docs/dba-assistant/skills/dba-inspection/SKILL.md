---
name: dba-inspection
description: "Run structured DB health and capacity checks."
version: 1.2.0
author: wl
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dba, inspection, healthcheck, capacity, mysql, redis, oracle, visiondb]
    category: dba
    related_skills:
      - dba-monitoring-alerts
      - dba-change-risk
      - dba-engine-playbooks
---

# DBA Inspection Skill

结构化巡检：健康、容量、复制/高可用信号、错误与慢查询趋势。
输出可归档的巡检结论，而不是聊天感想。

## When to Use

- 日常/周常巡检
- 重大活动前体检
- 接手陌生实例的快速画像
- 巡检发现异常后转 `dba-troubleshooting`

## Prerequisites

- VisionDB + Prometheus + Zabbix + VictoriaLogs
- 巡检范围：应用/环境/集群列表、主机列表或网段（可分批）
- MCP 经 `tool_search` → `tool_describe` → `tool_call`（见 SOUL.md）；入参 snake_case；防 search 空转

## How to Run

按范围收集 → VisionDB 批量异常与规模 → 监控/日志填表 → 标红项 → 处置优先级。

## Quick Reference

| 检查项 | 数据源 | 红灯示例（需环境校准） |
|--------|--------|------------------------|
| 异常实例盘点 | VisionDB `list_abnormal_instances` | status=error 且未在维护解释内 |
| 规模分布 | `instance_stats_by_type` | 某类型异常占比突增（对照历史） |
| 集群/实例清单 | `query_clusters` / `query_instances` / `search_*` | 范围对象对不上 CMDB 预期 |
| 主从/健康 | `get_cluster_realtime_status` | 角色异常、健康汇总失败 |
| Agent | `search_agents` | 关键 Agent 离线/未绑定 |
| 主机存活 | Zabbix | agent down / unreachable |
| CPU/内存/磁盘 | Zabbix + Prom | 持续高位或磁盘将满 |
| 磁盘 IO | Prom `io_util`/`io_await` | util 长期很高且 await 升高 |
| 库可用性 | Prom alerts / 日志 | 连续错误、连接拒绝 |
| 复制/HA | VisionDB + Prom + 日志 | lag 持续升高、切换失败 |
| 慢查询 | VL `hits` + slowlog | 同比显著上涨 |
| 错误日志 | VL errorlog | crash、OOM、corruption 关键字 |

### VisionDB 调用顺序（巡检）

| 步骤 | Tool | 说明 |
|------|------|------|
| 0 | `visiondb_health` | 可选预检 |
| 1 | `list_env_modes` / `list_db_types` / `list_areas` | 需要精确过滤时 |
| 2 | `list_abnormal_instances` | 当前故障实例（可要统计） |
| 3 | `instance_stats_by_type` | 按库类型规模（可按环境） |
| 4 | `search_applications` → `query_clusters` / `query_instances` | 按应用/环境分批清单 |
| 5 | `search_agents` | Agent 在线与绑定 |
| 6 | 红/黄对象：`get_cluster` / `get_cluster_realtime_status` / `get_*_status` | 下钻健康与运行时 |
| 7 | 再进 Zabbix → Prometheus → VictoriaLogs | 主机、容量趋势、错误/慢日志 |

一次扫过多对象会爆上下文：VisionDB 先出异常清单与分批摘要，再对红灯深挖。

## Procedure

### 1. 定范围与窗口

- 对象清单（应用/集群/IP；优先 VisionDB 拉清单）
- 窗口：通常近 24h 或近 7d（容量用更长）
- 环境：prod 优先（`list_env_modes` / `envMode`）

### 2. VisionDB 批量画像

1. `list_abnormal_instances` 列出当前异常，记入红灯候选。
2. `instance_stats_by_type` 了解规模分布。
3. 按范围 `query_clusters` / `query_instances`（或 search）分批。
4. `search_agents` 记录离线/异常 Agent。
5. 对红灯候选：`get_cluster_realtime_status`，MySQL/Redis 补 `get_*_status`。

### 3. 主机层批量画像（Zabbix）

1. `host_get` / `hostgroup_overview_get`（若适用）获取组概览。
2. `problem_active_get` 列出当前问题；`maintenance_get` 排除维护窗（若适用）。
3. 对重点主机 `host_status_get`。
4. 记录：严重问题数、磁盘、内存、是否维护中。

### 4. 指标层（Prometheus）

对每个重点实例/IP：

1. 确认 series 存在（`label_values`/`series`）。
2. 拉取可用性、连接、QPS、lag、缓存命中等关键指标的 avg/max。
3. `list_alerts` 是否与巡检对象相关。

### 5. 日志层（VictoriaLogs）

1. 错误日志 `hits` 按小时间隔。
2. 慢日志 `hits` 对比昨日。
3. 抽样严重错误（corruption、out of memory、fatal、failover）。

### 6. 巡检报告模板

```text
# 巡检报告
范围：...
窗口：...
生成时间：...

## 总览
- 主机：N；红/黄/绿：...
- 实例：N；红/黄/绿：...（含 VisionDB 异常实例数）
- Agent：在线/异常：...

## 红灯（立即处理）
| 对象 | 问题 | 证据 | 建议 |

## 黄灯（计划处理）
| 对象 | 问题 | 证据 | 建议 |

## 容量与趋势
...

## 下周期关注
...
```

红灯转入 `dba-troubleshooting`；涉及变更的黄灯结合 `dba-change-risk`。

## Pitfalls

- 巡检变成只贴告警列表，没有优先级。
- 阈值照搬书本，不看该集群历史基线。
- 一次扫过多主机导致上下文爆炸：应分批并写中间摘要。
- 忽略 VisionDB 异常实例，只扫 Zabbix 主机问题。

## Verification

- 报告含总览计数与至少一条可复核证据查询。
- 每个红灯有明确下一步 owner 动作（即使 owner 是「请 DBA 确认」）。
