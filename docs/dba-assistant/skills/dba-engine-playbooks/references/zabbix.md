# Zabbix · 主机资源监控约定

供 `dba-monitoring-alerts` / `dba-troubleshooting` / `dba-performance-tuning` 查**主机层** CPU/内存/磁盘时使用。
调用经 Zabbix MCP：`tool_search` → `tool_describe` → `tool_call`（见 SOUL.md）。
**item 名称与 key 以现网为准**；下表来自生产主机实查（如 `DISK-IO` / `文件系统` 中文命名）。空结果时先换表内「推荐 search」，禁止反复猜「磁盘使用率」空转。

## 概念澄清（必读）

| 用户说法 | 实际要看 | 正确 search / key 方向 | 勿当成 |
|----------|----------|------------------------|--------|
| 主机/库**负载**、IO 压力、卡顿 | IOPS、await、util、吞吐 | `DISK-IO` / `iostat` / `vfs.dev` | 磁盘**空间**占用 |
| 磁盘**空间**、快满、No space | 文件系统容量使用率 | `文件系统` / `vfs.fs.size` | DISK-IO 的 util |
| 「磁盘使用率」含糊时 | **先问清是空间还是 IO**；负载语境默认 IO | 同上两行 | 只搜「磁盘使用」→ 常返回 `[]` |

`item_get` 默认只返回 item 元数据（`itemid`/`name`/`key_`），**不等于已取到监控值**。必须再调 `item_history_summary_get`（或 `history_get` / `output` 含 `lastvalue`）。

## MCP 工具速查

| 目的 | 短名 | 说明 |
|------|------|------|
| 定位主机 | `host_get` | `search`/`filter` 用 IP、hostname、可见名称 → 拿到 `hostid` |
| 列 item | `item_get` | `hostids` + `search`（`name` 或 `key_`）；可 `limit` |
| 取数值/趋势 | `item_history_summary_get` | item 元数据 + 最近点 + min/max/avg；**取数首选** |
| 主机一览 | `host_status_get` | 身份 + 问题 + 最近若干 item 值；适合「这台怎么样」 |
| 当前问题 | `problem_active_get` | 正在响的告警（已滤禁用 trigger/host） |
| 原始历史 | `history_get` | 需要细粒度点时；须带 `itemids` + `history` 类型 |
| 连通性 | `health_check` | MCP ↔ Zabbix 是否通 |

## 发现→取数硬流程（违反即视为未按规程）

1. VisionDB `search_instances`（或用户给出）对齐 IP / `serverName`。
2. `host_get`：`search={"name":"<IP>"}` 或 hostname → 确认 `hostid`（如 `41919`）。
3. **按场景** `item_get(hostids=[...], search={...})`：只用下表推荐关键词；已返回非空列表则从中挑选，禁止立刻换词重搜。
4. 对选定 `itemid`（或 `host`+`key`）调 `item_history_summary_get`（`period` 如 `1h`/`6h`）。
5. **空结果（`[]`）连续 ≥2 次**：停止换假中文词；改用表内下一候选（`DISK-IO` / `iostat` / `文件系统` / `vfs.fs.size`），或报告「本机未找到该类 item」，交叉 Prom/VL。禁止同一意图空转超过 3 次。

**禁止**：

- 负载分析只搜「磁盘使用率 / 磁盘使用」却丢掉已返回的 `DISK-IO` 结果。
- 只 `item_get` 列出目录就下结论（无 `lastvalue` / history）。
- 把 `iostat[...,util]`（磁盘忙闲）说成「磁盘空间使用率」。

## 核心指标怎么查

定位主键一律：`hostids=["<hostid>"]`。下列 `search` 为**推荐起点**；`key_` 列为现网常见形态（多盘时 `sda/sdb/sdc/...` 各有一套）。

### 1. CPU 使用率

| 项 | 内容 |
|----|------|
| 看什么 | 整机 CPU 利用率、load、可选 iowait |
| `item_get` search | `{"name": "CPU"}` 或 `{"key_": "system.cpu.util"}` |
| 关键 key | `system.cpu.util`（总利用率）；`system.cpu.load[all,avg1\|avg5\|avg15]`；细分 `system.cpu.util[,idle\|iowait\|user\|system]` |
| 取数 | `item_history_summary_get(itemid=..., period="1h")` |
| 解读 | 高 `iowait` 常与磁盘 await/util 同升 → 交叉 IO 指标，勿只报 CPU% |

### 2. 内存使用率

| 项 | 内容 |
|----|------|
| 看什么 | 内存占用百分比；辅证 available / swap |
| `item_get` search | `{"name": "Memory"}` 或 `{"key_": "vm.memory"}` |
| 关键 key | `vm.memory.size.use.percent`（或 `vm.memory.size.use.percent-v1`）；`vm.memory.size[available]` / `[total]`；`system.swap.size[,pused]` |
| 取数 | 同上 `item_history_summary_get` |
| 解读 | 近 100% + swap 升高才接近内存压力；单看 cached 高不等于缺内存 |

### 3. 磁盘空间使用率（容量）

| 项 | 内容 |
|----|------|
| 看什么 | 各挂载点容量占用（`/`、`/data01`、`/boot` 等） |
| `item_get` search | **`{"name": "文件系统"}`** 或 `{"name": "容量使用"}` 或 `{"key_": "vfs.fs.size"}` |
| 关键 key | `vfs.fs.size[<mount>,pused]`；辅证 `...,pfree` / `...,used` / `...,total` |
| 典型 name | `文件系统 /: 容量使用百分比`、`文件系统 /data01: 容量使用百分比` |
| 取数 | 每个关注挂载点各取一条 `pused` 的 history |
| 勿用 | `{"name": "磁盘使用"}` → 现网常 `[]`；`DISK-IO` → 那是 IO 不是空间 |

### 4. IOPS

| 项 | 内容 |
|----|------|
| 看什么 | 每秒读写 IO 次数 |
| `item_get` search | **`{"name": "DISK-IO"}`** 或 `{"key_": "iostat"}` |
| 关键 key | `iostat[<dev>,r/s]`、`iostat[<dev>,w/s]`；或 `*.vfs.dev.read.rate[<dev>]` / `*.vfs.dev.write.rate[<dev>]` |
| 典型 name | `DISK-IO: /dev/sda 磁盘每秒成功读取的扇区数(读IOPS)`（以实网 name 为准） |
| 取数 | 按数据盘（常为 `/data*` 所在 `sdX`）优先；系统盘可略 |
| 解读 | 绝对值需对照基线；突增 + await 升高更有意义 |

### 5. IO wait time（响应/等待时间）

| 项 | 内容 |
|----|------|
| 看什么 | 平均每次 IO 等待/服务时延（ms 量级，以 units 为准） |
| `item_get` search | `{"name": "DISK-IO"}` + 结果里挑 await；或 `{"key_": "await"}` |
| 关键 key | `iostat[<dev>,await]`、`iostat[<dev>,r_await]`、`iostat[<dev>,w_await]`、`iostat[<dev>,svctm]`；或 `vfs.dev.read.await[<dev>]` / `vfs.dev.write.await[<dev>]` |
| 取数 | `item_history_summary_get`，看均值与峰值 |
| 解读 | **await 升高**比单纯 util 高更能说明排队/慢设备；与 CPU `iowait`、库侧慢查询交叉 |

### 6. IO util（磁盘繁忙度）

| 项 | 内容 |
|----|------|
| 看什么 | 采样期内设备处理 IO 的时间占比（忙闲），**不是**空间占用率 |
| `item_get` search | `{"name": "DISK-IO"}`；或 `{"key_": "iostat"}` / `vfs.dev.util` |
| 关键 key | `iostat[<dev>,util]`；或 `*.vfs.dev.util[<dev>]` |
| 典型 name | `DISK-IO: /dev/sda 磁盘在单位时间内处理所有IO请求所占的CPU比例`；`DISK-IO sda: Disk utilization` |
| 解读 | util 长期很高但 await 仍低 → 可能「健康繁忙」；util 高且 await 升 → 饱和/瓶颈 |

### 7. IO 吞吐

| 项 | 内容 |
|----|------|
| 看什么 | 每秒读写数据量（带宽） |
| `item_get` search | `{"name": "DISK-IO"}` |
| 关键 key | `iostat[<dev>,rkB/s]`、`iostat[<dev>,wkB/s]` |
| 典型 name | `...磁盘每秒读取的数据大小` / `...写入的数据大小` |
| 解读 | 与 IOPS 对照：大块顺序 IO 可低 IOPS 高吞吐；小随机 IO 相反 |

## 按场景推荐顺序

| 场景 | 第 1 步 | 第 2 步 | 第 3 步 | 辅证 |
|------|---------|---------|---------|------|
| 当前主机负载 | CPU `system.cpu.util` + load | 内存 `vm.memory.size.use.percent` | **DISK-IO**：await → util → r/s·w/s → rkB/s·wkB/s | VisionDB status；Prom 同窗 |
| 库慢/卡顿疑 IO | await + util | IOPS + 吞吐 | CPU iowait | VL slowlog；InnoDB pending |
| 磁盘将满 / No space | `文件系统` · `vfs.fs.size[...,pused]` | 各挂载点 used/total | — | VL `system_log` / errorlog |
| Zabbix 电话告警 | `problem_active_get` / `host_status_get` | 对告警相关 item 拉 history | 上表对症指标 | 维护窗 `maintenance_get` |

## 调用示例（参数形态）

```text
# 1) 定位
host_get(search={"name": "172.16.64.53"})  → hostid

# 2) 负载：列 IO item（不要搜「磁盘使用率」）
item_get(hostids=["<hostid>"], search={"name": "DISK-IO"}, limit=100)

# 3) 取 await / util / IOPS / 吞吐 的数值
item_history_summary_get(itemid="<await的itemid>", period="1h")
item_history_summary_get(host="<hostname>", key="iostat[sda,util]", period="1h")

# 4) 仅当需要空间时
item_get(hostids=["<hostid>"], search={"name": "文件系统"})
item_history_summary_get(itemid="<pused的itemid>", period="1h")
```

也可用扩展工具一次拿主机快照：`host_status_get(host="dgvxl10089")` 或 `host_status_get(host_id="<hostid>")`，再对缺失维度补 `item_history_summary_get`。

## 解读要点

- **负载结论**至少覆盖：CPU%、内存%、以及磁盘 **await + util + IOPS/吞吐**（有数据盘则点名设备）。
- 多块盘时写明看的是哪块（`sda` vs 数据盘）；只报一块且未说明易误导。
- Zabbix 采样周期与 Prom 不同，同名概念不要直接数值横比；趋势同向即可交叉印证。
- item `status=1` 为禁用，勿当有效监控。

## 与其它 reference 的分工

| 文件 | 职责 |
|------|------|
| 本文件 `zabbix.md` | 主机 CPU/内存/磁盘空间与 **DISK-IO** |
| `prometheus-mysql.md` 等 | 实例级 QPS/连接/复制等趋势 |
| `victorialogs-mysql.md` | 慢日志 / errorlog 侧证 |
| `visiondb-mcp.md` | 拓扑、角色、MySQL/Redis 瞬时 status |
