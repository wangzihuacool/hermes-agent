---
name: dba-engine-playbooks
description: "Engine-specific checklists for MySQL and peers."
version: 1.5.0
author: wl
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dba, mysql, redis, oracle, oceanbase, postgres, elasticsearch, sqlserver, visiondb]
    category: dba
    related_skills:
      - dba-troubleshooting
      - dba-performance-tuning
---

# DBA Engine Playbooks Skill

按数据库引擎加载差异化检查清单。先识别引擎，再打开对应 reference。
指标名以环境 Prometheus/Zabbix 实际为准；清单是提问框架不是固定 PromQL。
VisionDB 对 MySQL/Redis 有运行时与配置能力；其他引擎多为元数据级（若已纳管）。
跨引擎的 VisionDB MCP 工具/枚举/调用链见 `references/visiondb-mcp.md`。

## When to Use

- 已知引擎的排障或优化
- 多引擎环境需要切换检查口径
- 写巡检/变更评估时需要引擎要点

## Prerequisites

- 已确定引擎类型（或可由端口/日志/指标/VisionDB `list_db_types` 推断并声明置信度）
- 监控与日志 MCP 可用；VisionDB 用于元数据与 MySQL/Redis 运行时

## How to Run

1. 判定引擎（用户声明 > VisionDB 库类型 > 端口/日志/指标）。
2. `read_file` 读取本 skill 下 `references/<engine>.md`；需要 VisionDB 工具细节时读 `references/visiondb-mcp.md`。
3. 按清单取证；缺只读 SQL / EXPLAIN 能力时改为「请用户执行并回贴」。

## Quick Reference

| 引擎 | Reference | VisionDB 运行时 |
|------|-----------|-----------------|
| （跨引擎） | `references/visiondb-mcp.md` | 定位/拓扑/切换/异常；仅 MySQL/Redis 有 status/configs |
| MySQL | `references/mysql.md`；日志 `victorialogs-mysql.md`；指标 `prometheus-mysql.md` | status / configs / 集群配置对比 |
| Redis | `references/redis.md`；指标 `prometheus-redis.md` | status / configs |
| Oracle | `references/oracle.md`；指标 `prometheus-oracle.md` | 元数据（若纳管）；无专用 status tool |
| OceanBase | `references/oceanbase.md` | 元数据（若纳管）；无专用 status tool |
| PostgreSQL | `references/postgres.md` | 视纳管情况 |
| Elasticsearch | `references/elasticsearch.md` | 视纳管情况 |
| SQL Server | `references/sqlserver.md` | 视纳管情况 |

## Procedure

1. **识别**：用户声明 > VisionDB `get_instance`/`list_db_types` > 端口/进程日志 > exporter 指标前缀。
2. **加载**：只读对应 reference，避免一次塞入全部引擎。
3. **执行**：结合 `dba-troubleshooting` / `dba-performance-tuning` 流程；MySQL/Redis 优先补 VisionDB status/config。
4. **标注**：哪些检查因缺客户端/EXPLAIN/引擎专用接口未能完成。

## Pitfalls

- 用 MySQL 话术硬套 Oracle/ES。
- OceanBase 当「纯 MySQL」忽略租户/资源单元差异。
- Redis 使用可能阻塞的命令做「诊断」。
- 对 Oracle/OB 假装已有与 MySQL 同级的 VisionDB status。

## Verification

- 输出中声明引擎与所使用的 checklist 文件名。
- 引擎特有风险（如 Redis 阻塞命令、Oracle 等待事件）被显式提到或标为未检查。
