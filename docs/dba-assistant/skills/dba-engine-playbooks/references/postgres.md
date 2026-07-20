# PostgreSQL Playbook

## 识别

- 端口常 5432；指标常 `pg_*` / `postgres_*`

## 可用性

- 连接数 vs `max_connections`
- 复制槽膨胀、WAL 盘满
- 主从：`replay_lag` / `write_lag`（按实际指标）

## 性能

- 顺序扫描过多、索引失效、vacuum/autovacuum 堆积
- 锁：`blocking`、长事务导致 vacuum 无法清理
- `EXPLAIN (ANALYZE, BUFFERS)`（只读会话、控制代价）

## 变更风险

- 长 DDL、rewriting ALTER、创建索引 `CONCURRENTLY` 得失
- 统计信息与扩展（pg_stat_statements）是否可用

## 说明

辅助引擎：证据不足时明确假设，并优先用日志 + 主机资源定位。
