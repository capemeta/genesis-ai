# PostgreSQL 数据库设计与最佳实践分析 (V5 Master 版)

本文档是基于项目需求与 `doc/数据库设计.md` 逐行对照、并整合 RAG 混合检索最佳实践后的最终版本。

## 1. 核心约定与优化点 (V5 Master)

*   **分级审计对齐 (策略 #1)**：
    *   **业务主表**：全审计（Owner, CreatedBy, UpdatedBy, Timestamps）。
    *   **海量数据表**（Segments/Embeddings）：极简审计（仅 CreatedAt），极致性能。
    *   **中间表/日志表**：极简审计（仅 CreatedAt/User），无更新触发器。
*   **主键策略对齐 (策略 #5)**：
    *   核心实体：UUID (v4/v7)。
    *   海量流水：BIGINT (BIGSERIAL)。
*   **多租户安全约束**：
    *   知识库名称约束：`UNIQUE(tenant_id, name)`，确保租户内唯一。
*   **高性能索引**：
    *   **LTREE GiST**：针对组织和文件夹的树形检索。
    *   **HNSW**：针对向量相似度检索。
    *   **Partial Index**：针对 `documents.status` 加速解析任务扫描。
    *   **JSONB Path Ops**：针对元数据过滤加速。

---

## 2. 完整 SQL 初始化脚本

### 2.1 数据库创建脚本

**说明：**
- 使用 PostgreSQL 默认的 `postgres` 超级用户进行管理
- 创建应用专用用户 `genesis_app`（权限受限）
- 手动创建数据库以精确控制编码参数
