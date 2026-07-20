# Oracle Playbook

## 识别

- 端口常 1521；日志与 exporter 因环境差异大，先发现指标前缀
- 关注实例 / PDB / Data Guard 角色（不确定就问）

## Prometheus（Oracle）

现网多为 `oracledb_*`；标签、场景顺序与 PromQL 模板见：

`references/prometheus-oracle.md`

要点：`v_metric_type` 可能是 `ORACLE` 或 `ORACLERAC`；无 VisionDB 运行时 status，Prom + Zabbix + 用户 AWR/ASH 为主证据。

## 可用性

- 实例能否接受连接、监听问题、归档盘满
- Data Guard：apply lag、传输中断
- 告警与 alert log 关键字：ORA-、deadlock、out of memory

## 性能

- 等待事件思路：CPU / IO / concurrency / commit / cluster（RAC）
- 高消耗 SQL：需 AWR/ASH 或平台报告（无权限则请用户提供）
- 临时表空间与 undo 压力

## 变更风险

- DDL 锁、统计信息失效、不可逆数据变更
- 参数是否 SPFILE、是否需重启
- 物理/逻辑复制延迟对切换窗口的影响

## VisionDB（Oracle）

若实例已纳管：可用 `search_instances` / `get_cluster` / `get_instance` 等做元数据定位（详见 `references/visiondb-mcp.md`）。
**无** Oracle 专用运行时 status/config / AWR 接口。

## 说明

无 Oracle 客户端时：以主机指标 + 告警 + 用户提供的 AWR/ASH/SQL 文本分析为主，并在缺口中写明。
