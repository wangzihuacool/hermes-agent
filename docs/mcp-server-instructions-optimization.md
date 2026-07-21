# MCP Agent 优化经验：注入 Server Instructions

> 来源：2026-07-20 SQL Server「平均活跃会话数」告警排障对比（Cursor Agent vs 自建 AI Agent）  
> 结论优先级：**注入 MCP Server Instructions 是自建 Agent 的高性价比优化项**

---

## 1. 问题现象

同一套 MCP（VisionDB + Prometheus），同一告警：

| 侧 | 结果 |
|---|---|
| Cursor Agent | 定位到 `mssql_exec_sessions` / `mssql_server_cpu`，还原昨天 16:52–17:20 并发风暴 |
| 自建 Agent | 盲猜 `sqlserver_*` 指标名 → 全部空结果 → 误报「监控数据缺失」 |

**MCP 与数据都没问题，差在 Agent 怎么用 MCP。**

---

## 2. 根因

Prometheus MCP Server 在协议层提供了 **server-level `instructions`**（Cursor 侧可见为 `serverDescription` / `serverUseInstructions`），其中明确要求：

> **Discover Before You Query**  
> - Never assume a metric or label name exists  
> - 先用 `label_values` / `series` 发现真实指标名与标签  
> - 查询返回空时，先验证 metric 是否存在，再改查询

| 侧 | 是否注入该规程 | 行为 |
|---|---|---|
| Cursor | 注入进 Agent 上下文 | 先发现 `mssql_*`，再 `range_query` |
| 自建 Agent | 通常只挂了 tool schema / `tool_describe` | 猜 `sqlserver_*`，空结果死循环 |

自建侧常见缺口：

1. 只 `list_tools`，丢弃 MCP `initialize.instructions`
2. 用 tool 延迟发现（`tool_search`）时，每次只带短描述，**服务器级长指引从未全量进入 prompt**
3. 空结果没有强制策略，继续换假名字直到打满 tool 迭代上限

---

## 3. 这是什么、在哪里

| 概念 | 说明 |
|---|---|
| 层级 | **Per-server 一份**，不是每个 tool 各一份 |
| 协议来源 | MCP Server `initialize` 返回的 `instructions` |
| 仓库内 | 一般**不在** `.cursor/skills`；写在 MCP 服务端 |
| 与 tool description 区别 | tool 描述参数怎么填；instructions 描述**怎么排查/何时先发现再查询** |

Prometheus 这份实测体积（2026-07）：

| 项 | 约值 |
|---|---|
| 字符 | ~17,160（约 16.8 KB） |
| Token（粗估） | **约 3k–5k** |

其它 MCP 通常短很多（数十～数百 tokens）。Prometheus 偏「话痨」，但单独一段一般远不到上下文上限。

---

## 4. Cursor 怎么喂上下文（可观察行为）

```text
已启用 MCP 列表
  ├─ Server instructions（常驻 / 进元信息；Prometheus 可全文）
  ├─ 工具目录：name + 短描述（长描述可 truncated）
  └─ 真正调用前：按需 GetMcpTools 拉完整 inputSchema
         └─ CallMcpTool 执行
```

要点：

- **会注入各 MCP 的 server-level instructions**
- **不会**默认把所有工具的完整 JSON schema 永久塞进 system prompt
- 工具 schema **懒加载**；目录检索可截断长描述
- 查询类工具可用 `truncation_limit` 控制回包体积

更危险的往往是：全量 tool schema 常驻 + 巨型 `range_query`/`history_get` 回包，而不是单独一段 instructions。

---

## 5. 推荐做法（自建 Agent）

### 5.1 必须做：注入 Server Instructions

握手后读取并注入：

```text
MCP initialize → instructions
        ↓
拼进 system / 常驻策略段（与 tool schema 分开）
```

没有这段，模型只有「工具叫什么」，没有「先发现再查询」。

### 5.2 建议做：分层上下文

| 层级 | 内容 | 策略 |
|---|---|---|
| L0 常驻 | Discover / 空结果处理 / 禁止瞎猜 metric 等硬规则摘要（可压缩到 ~20 行） | 每轮都在 |
| L1 按需 | 完整 server instructions | 首次用到该 MCP 或任务相关时加载 |
| L2 按需 | 单个 tool 的完整 inputSchema | `describe` / 即将调用时加载 |
| L3 截断 | 工具返回值 | 强制 limit / truncation |

### 5.3 硬规则（即使 instructions 被截断也要留下）

1. **禁止猜测 metric / label 名**；空结果必须先 `label_values` / `series`
2. 本环境 SQL Server 优先模式：`{__name__=~"mssql_.*"}`（会话：`mssql_exec_sessions`，CPU：`mssql_server_cpu`）
3. 「昨天告警」用 `range_query` + 明确时间窗，不要只做当前 instant `query`
4. VisionDB 对 SQL Server 的 `dbInfo=null` / `isSuccess=false` **不等于**监控缺失；历史曲线走 Prometheus
5. 同一查询连续空结果 ≥ 2 次 → **禁止继续换假名字**，强制切发现流程
6. 预留 tool 迭代次数给「发现 + 查曲线 + 对比」，不要在盲猜上烧光配额

### 5.4 自证清单

- [ ] `initialize` 响应里是否有非空 `instructions`？
- [ ] 这段文字是否进入发给 LLM 的 messages？
- [ ] 是否被截断到只剩工具名列表？
- [ ] 空结果时日志是否出现 `label_values` / `series`，而不是下一轮假 metric？

---

## 6. 案例对照（一句话）

| | Cursor | 自建（未注入） |
|---|---|---|
| 策略 | 先问「库里有什么指标」 | 先问「`sqlserver_xxx` 多少」 |
| 空结果 | 验证 metric 是否存在 | 断定监控缺失 |
| 修复点 | — | **注入 instructions + 空结果强制发现** |

---

## 7. 经验总结

1. **MCP 相同 ≠ 行为相同**；差在客户端有没有把 server instructions 喂给模型。  
2. **注入 server instructions** 是低成本、高收益优化，直接决定会不会「Discover Before You Query」。  
3. Instructions 与 tool schema 职责不同：前者是操作规程，后者是调用合同；两者都要，但注入策略应分层。  
4. 防超限：常驻摘要 + 按需全文 + schema 懒加载 + 回包截断；不要「全量 schema 永久进 system」。  
5. 业务侧可再补短 skill（如本环境 `mssql_*` 指标字典），与 MCP instructions **互补**，不能替代。

---

## 8. 相关材料

- 告警案例：`10.80.16.111:1433`，2026-07-19 约 16:52–17:20，`mssql_exec_sessions{status="running"}` 峰值约 400，CPU 约 98%  
- Prometheus MCP 关键规程名：**Discover Before You Query**  
- Cursor 侧 MCP 工具发现：`GetMcpTools` → `CallMcpTool`（按需拉 schema）
