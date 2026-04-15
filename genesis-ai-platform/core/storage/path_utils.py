"""
SeaweedFS 路径管理工具

提供统一的文件路径生成规则，支持多层路径结构

设计原则：
1. 租户隔离：所有路径以 tenant_id 开头
2. 资源分类：按业务类型分目录（documents/avatars/exports/temp）
3. 时间分区：使用 year/month 分区，避免单目录文件过多
4. 唯一标识：使用 UUID 避免文件名冲突
5. 可追溯性：路径包含足够信息用于审计和清理

路径深度限制：
- 最大深度：6 层（tenant/type/sub/year/month/file）
- 推荐深度：4-5 层
- 避免超过 7 层（影响性能）

S3/SeaweedFS 最佳实践：
- 使用前缀（prefix）而非真实目录结构
- 避免热点分区（使用 UUID 而非递增 ID）
- 合理使用分区键（tenant_id, year/month）
- 支持批量操作（通过 prefix 过滤）
"""
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4
from typing import Optional

ParsedStoragePath = dict[str, str | bool | None]


def generate_storage_path(
    tenant_id: UUID,
    filename: str,
    resource_type: str = "documents",
    kb_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    document_id: Optional[UUID] = None,
    kb_doc_id: Optional[UUID] = None,
    use_date_partition: bool = True
) -> str:
    """
    生成 SeaweedFS 存储路径（支持多层路径结构）
    
    路径规则（遵循 S3 最佳实践）：
    ┌─────────────────────────────────────────────────────────────────┐
    │ genesis-ai-files/                    # Bucket                   │
    │   └── {tenant_id}/                   # 租户隔离（第1层）         │
    │       ├── documents/                 # 文档类型（第2层）         │
    │       │   └── {year}/{month}/       # 时间分区（第3-4层）      │
    │       │       └── {document_id}{ext} # 文件（第5层）           │
    │       ├── avatars/                  # 头像（第2层）             │
    │       │   └── {user_id}{ext}       # 文件（第3层，直接覆盖）   │
    │       ├── exports/                  # 导出文件（第2层）         │
    │       │   └── {year}/{month}/      # 时间分区（第3-4层）       │
    │       │       └── {uuid}{ext}      # 文件（第5层）            │
    │       ├── chunks/                   # 文档分块（第2层）         │
    │       │   └── doc-{document_id}/   # 文档分组（第3层）         │
    │       │       └── {uuid}.json      # 分块文件（第4层）         │
    │       └── temp/                     # 临时文件（第2层）         │
    │           └── {year}/{month}/      # 时间分区（第3-4层）       │
    │               └── {uuid}{ext}      # 文件（第5层）            │
    └─────────────────────────────────────────────────────────────────┘
    
    设计原则：
    - 物理去重：同一个文件（相同 content_hash）只存储一份
    - 按 document_id 存储：多个知识库可以引用同一个 document
    - 不按 kb_id 存储：避免同一文件被复制多份
    
    路径深度：
    - documents: 5 层 ✓ (tenant/documents/year/month/document_id.ext)
    - avatars: 3 层 ✓ (简单直接，自动覆盖)
    - exports: 5 层 ✓
    - chunks: 4 层 ✓
    - temp: 5 层 ✓
    
    Args:
        tenant_id: 租户ID
        filename: 原始文件名
        resource_type: 资源类型
            - documents: 知识库文档（按 document_id 存储）
            - avatars: 用户头像
            - exports: 导出文件
            - chunks: 文档分块
            - temp: 临时文件
        kb_id: 知识库ID（已废弃，不再使用）
        user_id: 用户ID（仅用于 avatars 类型）
        document_id: 文档ID（用于 documents 和 chunks 类型）
        use_date_partition: 是否使用日期分区（默认 True）
        
    Returns:
        str: 存储路径
        
    Examples:
        >>> # 文档上传（使用 document_id）
        >>> generate_storage_path(tenant_id, "report.pdf", "documents", document_id=doc_id)
        "tenant-uuid/documents/2024/01/document-uuid.pdf"
        
        >>> # 临时文件（未创建 document 记录）
        >>> generate_storage_path(tenant_id, "temp.pdf", "temp")
        "tenant-uuid/temp/2024/01/uuid.pdf"
        
        >>> # 用户头像（直接覆盖）
        >>> generate_storage_path(tenant_id, "avatar.jpg", "avatars", user_id=user_uuid)
        "tenant-uuid/avatars/user-uuid.jpg"
        
        >>> # 导出文件
        >>> generate_storage_path(tenant_id, "export.zip", "exports")
        "tenant-uuid/exports/2024/01/export-uuid.zip"
        
        >>> # 文档分块
        >>> generate_storage_path(tenant_id, "chunk.json", "chunks", document_id=doc_uuid)
        "tenant-uuid/chunks/doc-doc-uuid/chunk-uuid.json"
    """
    # 提取文件扩展名
    ext = Path(filename).suffix.lower()
    
    # 生成唯一文件名
    unique_id = uuid4()
    
    # 时间分区（如果启用）
    date_partition = ""
    if use_date_partition:
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        date_partition = f"{year}/{month}/"
    
    # 根据资源类型生成路径
    if resource_type == "documents":
        if document_id:
            # 使用 document_id 作为文件名（物理去重）
            # 格式: tenant/documents/year/month/document_id.ext
            return f"{tenant_id}/documents/{date_partition}{document_id}{ext}"
        else:
            # 临时文件：使用 UUID
            # 格式: tenant/documents/temp/year/month/uuid.ext
            return f"{tenant_id}/documents/temp/{date_partition}{unique_id}{ext}"
    
    elif resource_type == "avatars":
        # 头像：直接使用 user_id 命名，覆盖旧头像
        # 格式: tenant/avatars/{user_id}.ext
        if user_id:
            return f"{tenant_id}/avatars/{user_id}{ext}"
        else:
            return f"{tenant_id}/avatars/{unique_id}{ext}"
    
    elif resource_type == "exports":
        # 导出文件：按时间分组
        # 格式: tenant/exports/year/month/uuid.ext
        return f"{tenant_id}/exports/{date_partition}{unique_id}{ext}"
    
    elif resource_type == "chunks":
        # 文档分块：按文档ID分组（不使用日期分区，避免过深）
        # 格式: tenant/chunks/doc-{document_id}/uuid.json
        if document_id:
            return f"{tenant_id}/chunks/doc-{document_id}/{unique_id}.json"
        else:
            return f"{tenant_id}/chunks/{unique_id}.json"
    
    elif resource_type == "temp":
        # 临时文件：使用日期分区便于清理
        # 格式: tenant/temp/year/month/uuid.ext
        return f"{tenant_id}/temp/{date_partition}{unique_id}{ext}"
    
    elif resource_type == "parsed":
        # 解析结果（如 Markdown 预览）：使用 kb_doc_id 命名，实现重解析时自动覆盖
        # 格式: tenant/parsed/kb_doc_{kb_doc_id}.md
        if kb_doc_id:
            return f"{tenant_id}/parsed/kb_doc_{kb_doc_id}{ext}"
        elif document_id:
            return f"{tenant_id}/parsed/doc_{document_id}{ext}"
        else:
            return f"{tenant_id}/parsed/{unique_id}{ext}"
    
    else:
        # 默认：放在对应类型目录下
        return f"{tenant_id}/{resource_type}/{date_partition}{unique_id}{ext}"


def parse_storage_path(file_key: str) -> ParsedStoragePath:
    """
    解析存储路径，提取元信息
    
    Args:
        file_key: 存储路径
        
    Returns:
        dict: 包含 tenant_id, resource_type, document_id 等信息
        
    Examples:
        >>> parse_storage_path("tenant-uuid/documents/2024/01/document-uuid.pdf")
        {
            "tenant_id": "tenant-uuid",
            "resource_type": "documents",
            "document_id": "document-uuid",
            "year": "2024",
            "month": "01"
        }
        
        >>> parse_storage_path("tenant-uuid/avatars/user-uuid.jpg")
        {
            "tenant_id": "tenant-uuid",
            "resource_type": "avatars",
            "user_id": "user-uuid",
            "filename": "user-uuid.jpg"
        }
    """
    parts = file_key.split("/")
    
    if len(parts) < 2:
        return {"tenant_id": None, "resource_type": None}
    
    # 这里显式标注联合类型，避免 mypy 将后续 bool 字段误推断成 str。
    result: ParsedStoragePath = {
        "tenant_id": parts[0],
        "resource_type": parts[1] if len(parts) > 1 else None,
    }
    
    # 根据资源类型解析
    if result["resource_type"] == "documents":
        if len(parts) >= 5:
            # 格式: tenant/documents/year/month/document_id.ext
            result["year"] = parts[2]
            result["month"] = parts[3]
            filename_with_ext = parts[4]
            # 提取 document_id（去掉扩展名）
            result["document_id"] = Path(filename_with_ext).stem
            result["filename"] = filename_with_ext
        elif len(parts) >= 6 and parts[2] == "temp":
            # 旧格式（临时文件）: tenant/documents/temp/year/month/uuid.ext
            result["year"] = parts[3]
            result["month"] = parts[4]
            result["filename"] = parts[5]
            result["is_temp"] = True
    
    elif result["resource_type"] == "avatars":
        if len(parts) >= 3:
            # 格式: tenant/avatars/{user_id}.ext
            result["filename"] = parts[2]
            # 提取 user_id（去掉扩展名）
            filename_without_ext = Path(parts[2]).stem
            result["user_id"] = filename_without_ext
    
    elif result["resource_type"] == "exports":
        if len(parts) >= 5:
            # 格式: tenant/exports/year/month/file
            result["year"] = parts[2]
            result["month"] = parts[3]
            result["filename"] = parts[4]
    
    elif result["resource_type"] == "chunks":
        if len(parts) >= 4 and parts[2].startswith("doc-"):
            # 格式: tenant/chunks/doc-{document_id}/file
            result["document_id"] = parts[2][4:]  # 移除 "doc-" 前缀
            result["filename"] = parts[3]
    
    elif result["resource_type"] == "temp":
        if len(parts) >= 5:
            # 格式: tenant/temp/year/month/file
            result["year"] = parts[2]
            result["month"] = parts[3]
            result["filename"] = parts[4]
            result["is_temp"] = True
    
    return result


def get_document_chunks_prefix(tenant_id: UUID, document_id: UUID) -> str:
    """
    获取文档分块的路径前缀
    
    用途：
    - 列出文档的所有分块
    - 删除文档时清理分块
    
    Args:
        tenant_id: 租户ID
        document_id: 文档ID
        
    Returns:
        str: 路径前缀
        
    Examples:
        >>> get_document_chunks_prefix(tenant_id, document_id)
        "tenant-uuid/chunks/doc-doc-uuid/"
    """
    return f"{tenant_id}/chunks/doc-{document_id}/"


def get_user_avatar_path(tenant_id: UUID, user_id: UUID, ext: str = ".jpg") -> str:
    """
    获取用户头像的完整路径
    
    Args:
        tenant_id: 租户ID
        user_id: 用户ID
        ext: 文件扩展名（默认 .jpg）
        
    Returns:
        str: 头像路径
        
    Examples:
        >>> get_user_avatar_path(tenant_id, user_id)
        "tenant-uuid/avatars/user-uuid.jpg"
        
        >>> get_user_avatar_path(tenant_id, user_id, ".png")
        "tenant-uuid/avatars/user-uuid.png"
    """
    if not ext.startswith("."):
        ext = f".{ext}"
    return f"{tenant_id}/avatars/{user_id}{ext}"


def is_temp_file(file_key: str) -> bool:
    """
    判断是否为临时文件
    
    Args:
        file_key: 存储路径
        
    Returns:
        bool: 是否为临时文件
        
    Examples:
        >>> is_temp_file("tenant-uuid/documents/temp/2024/01/file.pdf")
        True
        
        >>> is_temp_file("tenant-uuid/temp/2024/01/file.tmp")
        True
        
        >>> is_temp_file("tenant-uuid/documents/kb-uuid/2024/01/file.pdf")
        False
    """
    parts = file_key.split("/")
    if len(parts) < 3:
        return False
    
    # 检查是否在 temp 目录
    return parts[1] == "temp" or (parts[1] == "documents" and parts[2] == "temp")


def should_cleanup_file(file_key: str, days_old: int = 7) -> bool:
    """
    判断文件是否应该被清理（基于路径中的日期）
    
    注意：这只是基于路径的粗略判断，实际清理应该结合 S3 对象的 LastModified 时间
    
    Args:
        file_key: 存储路径
        days_old: 保留天数（默认 7 天）
        
    Returns:
        bool: 是否应该清理
        
    Examples:
        >>> # 假设今天是 2024-02-01
        >>> should_cleanup_file("tenant-uuid/temp/2024/01/file.tmp", days_old=7)
        True  # 1月的文件，超过7天
        
        >>> should_cleanup_file("tenant-uuid/temp/2024/02/file.tmp", days_old=7)
        False  # 2月的文件，不到7天
    """
    if not is_temp_file(file_key):
        return False
    
    parsed = parse_storage_path(file_key)
    if not parsed.get("year") or not parsed.get("month"):
        return False
    
    try:
        from datetime import datetime, timedelta

        year_value = parsed.get("year")
        month_value = parsed.get("month")
        if not isinstance(year_value, str) or not isinstance(month_value, str):
            return False

        file_date = datetime(int(year_value), int(month_value), 1)
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        return file_date < cutoff_date
    except (ValueError, KeyError):
        return False

