# Elasticsearch Playbook

## 识别

- 端口常 9200；指标常 `elasticsearch_*`

## 可用性

- 集群 health：red/yellow、未分配分片
- 节点离开、磁盘水位导致只读
- 脑裂/选主相关日志

## 性能

- 查询延迟、拒绝、线程池 queue
- GC / heap、segment 合并压力
- 慢查询日志（若采集到 VL）

## 变更风险

- mapping 变更、reindex、shrink/split
- 副本数调整与磁盘
- 大删除与 force merge 窗口

## 说明

无 ES API 权限时：以节点主机资源 + 集群类指标 + 日志为主，缺口写明。
