# SQL Server Playbook

## 识别

- 端口常 1433；指标前缀因 exporter 而异，先 `label_values`
- Always On 角色常在告警/实例名中带 `STANDBY` / `PRIMARY`；用 VisionDB `search_instances` 对齐，勿臆造拓扑

## 可用性

- 实例服务状态、数据库 suspect/recovering
- Always On：同步延迟、角色异常
- 错误日志：I/O、内存、登录失败风暴（VictoriaLogs，必须实际 `query`/`hits`）

## 性能

- 等待统计思路：PAGEIOLATCH、LCK_、CXPACKET/CXCONSUMER、WRITELOG 等
- 高消耗查询 / 活跃会话需 DMV/Query Store（**VisionDB 无 `get_sqlserver_instance_status`**；无权限则请用户提供 `sys.dm_exec_sessions` / 计划）
- 「平均活跃会话数」类 Zabbix 告警：先 Zabbix 拉历史与主机资源，再 VL 看 errorlog/连接相关；禁止编造会话列表与 CPU%

## 变更风险

- 在线 DDL 能力有限场景；大表索引重建窗口
- 兼容级别、统计信息更新
- 日志盘空间与完整恢复模式膨胀

## 说明

辅助引擎：优先 **Zabbix + VictoriaLogs +（可选）Prometheus**；深度会话/等待/计划分析依赖授权或用户粘贴。
禁止伪造 DMV 结果或假工具名。
