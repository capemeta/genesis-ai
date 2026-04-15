"""
文档上传 API

设计理念：
1. documents 表：纯载体对象管理，与知识库内容语义无关
2. 此 API 只负责文件上传，不涉及知识库关联

API 设计：
1. POST /documents/upload - 纯文件上传，只创建 documents 记录

存储路径规则：
- 未关联知识库: {tenant_id}/documents/temp/{year}/{month}/{uuid}.{ext}
- 已关联知识库: {tenant_id}/documents/{kb_id}/{year}/{month}/{uuid}.{ext}
"""
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.deps import get_current_user
from core.database import get_async_session
from core.storage import get_storage_driver
from core.storage.base import StorageDriver
from core.storage.path_utils import generate_storage_path
from core.config import settings
from models.document import Document
from models.knowledge_base_document import KnowledgeBaseDocument
from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Schemas ====================

class DocumentUploadResponse(BaseModel):
    """文件上传响应"""
    id: UUID
    name: str
    file_size: int
    file_type: str
    content_hash: str
    is_duplicate: bool  # 是否秒传（物理文件已存在）
    
    class Config:
        from_attributes = True


class DocumentDownloadRequest(BaseModel):
    """文件下载请求"""
    kb_document_id: UUID = Field(..., description="知识库文档关联 ID")
    
    class Config:
        from_attributes = True







# ==================== Helper Functions ====================

async def calculate_file_hash(file: UploadFile) -> str:
    """
    计算文件 SHA256 哈希值
    
    Args:
        file: 上传的文件对象
        
    Returns:
        str: SHA256 哈希值（十六进制）
    """
    sha256 = hashlib.sha256()
    
    # 重置文件指针到开始
    await file.seek(0)
    
    # 分块读取文件计算哈希
    while chunk := await file.read(8192):  # 8KB chunks
        sha256.update(chunk)
    
    # 重置文件指针到开始（供后续使用）
    await file.seek(0)
    
    return sha256.hexdigest()


def _build_upload_response(document: Document, is_duplicate: bool) -> DocumentUploadResponse:
    """统一构造上传响应，收敛可空字段。"""
    return DocumentUploadResponse(
        id=document.id,
        name=document.name,
        file_size=document.file_size,
        file_type=str(document.file_type or ""),
        content_hash=str(document.content_hash or ""),
        is_duplicate=is_duplicate,
    )


# ==================== API Routes ====================

@router.post(
    "/download",
    summary="下载文件",
    description="通过后端代理下载文件，支持权限控制和审计（流式传输）"
)
async def download_document(
    request: DocumentDownloadRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    下载文件（后端代理方式，流式传输）
    
    Args:
        request: 下载请求（包含 kb_document_id）
        current_user: 当前用户
        session: 数据库会话
        
    Returns:
        文件流（StreamingResponse）
    """
    from fastapi.responses import StreamingResponse
    import urllib.parse
    
    kb_document_id = request.kb_document_id
    
    # 1. 查询文档（通过 kb_document_id）
    document = await _get_document_by_kb_document_id(session, kb_document_id, current_user.tenant_id)
    logger.info(f"下载文件 kb_document_id={kb_document_id}")
    if not document:
        logger.warning(f"文档不存在: kb_document_id={kb_document_id}, user={current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或已被删除"
        )
    
    # 2. 权限检查：只有所有者可以下载
    # TODO: 后续可以扩展为检查知识库权限
    if document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权下载此文件"
        )
    
    # 3. 从存储系统获取文件流
    try:
        # 根据 storage_driver 获取对应的驱动实例
        if document.storage_driver == "local":
            from core.storage.local_driver import get_local_driver
            # 使用文档记录中的 bucket_name（本地存储的基础路径）
            storage_driver: StorageDriver = get_local_driver(str(document.bucket_name or settings.LOCAL_STORAGE_PATH))
        elif document.storage_driver == "s3":
            from core.storage.s3_driver import get_s3_driver
            storage_driver = get_s3_driver()
        else:
            # 兜底：使用默认配置
            storage_driver = get_storage_driver()
        
        logger.info(f"开始流式下载文件: {document.name}, 用户: {current_user.id}, 大小: {document.file_size} bytes")
        
        # 4. 构建响应头（支持中文文件名）
        content_disposition = _build_content_disposition(document.name)
        
        # 5. 创建文件流迭代器（使用异步 I/O）
        async def file_iterator():
            """文件流迭代器 - 使用异步 I/O 避免阻塞"""
            total_sent = 0
            chunk_count = 0
            chunk_size = 65536  # 64KB
            
            try:
                # 获取文件完整路径
                if document.storage_driver == "local":
                    from pathlib import Path
                    import aiofiles  # type: ignore[import-untyped]  # 异步文件 I/O
                    
                    base_path = Path(document.bucket_name)
                    if not base_path.is_absolute():
                        # 相对路径：相对于项目根目录
                        from pathlib import Path as P
                        current = P(__file__).resolve()
                        for parent in [current] + list(current.parents):
                            if (parent / "main.py").exists():
                                base_path = parent / base_path
                                break
                    file_path = base_path / document.file_key
                    
                    # 使用异步文件 I/O
                    async with aiofiles.open(file_path, 'rb') as f:
                        while True:
                            chunk = await f.read(chunk_size)
                            if not chunk:
                                break
                            chunk_count += 1
                            total_sent += len(chunk)
                            if chunk_count % 100 == 0:
                                logger.debug(f"已发送 {chunk_count} 个数据块，共 {total_sent} 字节")
                            yield chunk
                else:
                    # S3 或其他存储：使用原有的 get_stream
                    async for chunk in storage_driver.get_stream(document.file_key, chunk_size=chunk_size):
                        chunk_count += 1
                        total_sent += len(chunk)
                        if chunk_count % 100 == 0:
                            logger.debug(f"已发送 {chunk_count} 个数据块，共 {total_sent} 字节")
                        yield chunk
                
                logger.info(f"文件下载完成: {document.name}, 共发送 {chunk_count} 个数据块，总计 {total_sent} 字节")
                
                # 验证发送的字节数是否与文件大小一致
                if total_sent != document.file_size:
                    logger.error(f"文件大小不匹配: 预期 {document.file_size} 字节，实际发送 {total_sent} 字节")
                    
            except Exception as e:
                logger.error(f"文件流传输失败: {document.name}, 错误: {e}", exc_info=True)
                raise
        
        # 6. 返回流式响应（不设置 Content-Length，让 FastAPI 自动处理）
        return StreamingResponse(
            file_iterator(),
            media_type=document.mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": content_disposition,
                # 🔥 移除 Content-Length，避免长度不匹配错误
                # StreamingResponse 会自动使用 Transfer-Encoding: chunked
                "Cache-Control": "no-cache",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
        
    except Exception as e:
        logger.error(f"下载文件失败: {document.name}, 错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载文件失败: {str(e)}"
        )


@router.get(
    "/inline/{kb_document_id}",
    summary="在线访问文件",
    description="用于图片等资源的内联访问（返回文件字节流）"
)
async def inline_document(
    request: Request,
    kb_document_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    在线访问文件（适用于 Markdown 图片渲染）。

    权限策略与下载接口一致：当前仅允许文档所有者访问。
    
    Args:
        kb_document_id: 知识库文档关联 ID（knowledge_base_documents 表的 ID）
    """
    from fastapi.responses import Response

    document = await _get_document_by_kb_document_id(session, kb_document_id, current_user.tenant_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或已被删除"
        )

    if document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此文件"
        )

    try:
        if document.storage_driver == "local":
            from core.storage.local_driver import get_local_driver
            storage_driver: StorageDriver = get_local_driver(str(document.bucket_name or settings.LOCAL_STORAGE_PATH))
        elif document.storage_driver == "s3":
            from core.storage.s3_driver import get_s3_driver
            storage_driver = get_s3_driver()
        else:
            storage_driver = get_storage_driver()

        file_content = await storage_driver.get_content(document.file_key)
        
        headers = {
            "Cache-Control": "private, max-age=3600",
        }
        
        # 添加 CORS 头
        origin = request.headers.get("origin")
        if origin:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
            headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            headers["Access-Control-Allow-Headers"] = "*"
        
        return Response(
            content=file_content,
            media_type=document.mime_type or "application/octet-stream",
            headers=headers
        )
    except Exception as e:
        logger.error(f"在线访问文件失败: {document.name}, 错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"访问文件失败: {str(e)}"
        )


@router.get(
    "/public/{document_id}",
    summary="公开访问文件",
    description="免登录公开访问文件（用于 Markdown 图片外链渲染）"
)
async def public_document(
    request: Request,
    document_id: UUID,
    session: AsyncSession = Depends(get_async_session)
):
    """
    公开访问文件（不需要登录）。

    说明：
    - 当前按 document_id 直接访问；
    - 仅校验文档存在且未被软删除。
    """
    from fastapi.responses import Response

    stmt = select(Document).where(
        Document.id == document_id,
        Document.is_deleted == False
    )
    result = await session.execute(stmt)
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或已被删除"
        )

    try:
        if document.storage_driver == "local":
            from core.storage.local_driver import get_local_driver
            storage_driver: StorageDriver = get_local_driver(str(document.bucket_name or settings.LOCAL_STORAGE_PATH))
        elif document.storage_driver == "s3":
            from core.storage.s3_driver import get_s3_driver
            storage_driver = get_s3_driver()
        else:
            storage_driver = get_storage_driver()

        file_content = await storage_driver.get_content(document.file_key)
        
        headers = {
            "Cache-Control": "public, max-age=31536000",
        }
        
        # 显式添加 CORS 头，解决预览组件 fetch 下载时的跨域问题
        origin = request.headers.get("origin")
        if origin:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
            headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            headers["Access-Control-Allow-Headers"] = "*"
        else:
            headers["Access-Control-Allow-Origin"] = "*"

        return Response(
            content=file_content,
            media_type=document.mime_type or "application/octet-stream",
            headers=headers
        )
    except Exception as e:
        logger.error(f"公开访问文件失败: {document.name}, 错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"访问文件失败: {str(e)}"
        )


async def _get_document_by_kb_document_id(
    session: AsyncSession,
    kb_document_id: UUID,
    tenant_id: UUID
) -> Document | None:
    """
    根据知识库文档关联 ID 查询物理文档
    
    Args:
        session: 数据库会话
        kb_document_id: 知识库文档关联 ID（knowledge_base_documents 表的 ID）
        tenant_id: 租户 ID
        
    Returns:
        Document 对象或 None
    """
    # 1. 查询知识库文档关联记录
    kb_stmt = select(KnowledgeBaseDocument).where(
        KnowledgeBaseDocument.id == kb_document_id,
        KnowledgeBaseDocument.tenant_id == tenant_id
    )
    result = await session.execute(kb_stmt)
    kb_doc = result.scalar_one_or_none()
    
    if not kb_doc:
        logger.debug(f"未找到 kb_document_id={kb_document_id}")
        return None
    
    # 2. 查询实际的物理文档
    logger.debug(f"找到 kb_document，实际 document_id={kb_doc.document_id}")
    doc_stmt = select(Document).where(
        Document.id == kb_doc.document_id,
        Document.tenant_id == tenant_id
    )
    result = await session.execute(doc_stmt)
    return cast(Document | None, result.scalar_one_or_none())


async def _get_document_by_id(
    session: AsyncSession,
    document_id: UUID,
    tenant_id: UUID
) -> Document | None:
    """
    根据物理文档 ID 查询文档
    
    Args:
        session: 数据库会话
        document_id: 物理文档 ID（documents 表的 ID）
        tenant_id: 租户 ID
        
    Returns:
        Document 对象或 None
    """
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == tenant_id
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _build_content_disposition(filename: str) -> str:
    """
    构建 Content-Disposition 响应头（支持中文文件名）
    
    使用 RFC 6266 / RFC 2231 标准：
    - filename: ASCII 安全的后备文件名（旧浏览器）
    - filename*: UTF-8 编码的完整文件名（现代浏览器）
    
    Args:
        filename: 原始文件名
        
    Returns:
        Content-Disposition 头值
    """
    import urllib.parse
    
    # URL 编码文件名（用于 filename*）
    encoded_filename = urllib.parse.quote(filename, safe='')
    
    # ASCII 后备文件名（用于 filename）
    try:
        ascii_filename = filename.encode('ascii').decode('ascii')
    except UnicodeEncodeError:
        # 如果包含非 ASCII 字符，使用 download + 扩展名
        name_parts = filename.rsplit('.', 1)
        ascii_filename = f"download.{name_parts[1]}" if len(name_parts) == 2 else "download"
    
    return f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'


@router.post(
    "/upload",
    response_model=dict,
    summary="上传文件（纯物理上传）",
    description="上传文件到存储系统，创建 documents 记录，支持秒传。与知识库无关。"
)
async def upload_document(
    file: UploadFile = File(..., description="上传的文件"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    纯文件上传 API
    
    流程：
    1. 验证文件类型和大小
    2. 计算文件 Hash
    3. 检查物理文件是否存在（秒传）
    4. 上传到 SeaweedFS（如果需要）
    5. 创建 Document 记录
    
    注意：此 API 不涉及知识库，只负责物理文件管理
    """
    
    # 1. 验证文件名
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名不能为空"
        )
    
    # 2. 验证文件类型
    allowed_extensions = {
        '.pdf', '.doc', '.docx', '.txt', '.md',
        '.xlsx', '.xls', '.ppt', '.pptx', '.csv'
    }
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file_ext}。支持的格式：{', '.join(allowed_extensions)}"
        )
    
    # 3. 验证文件大小（100MB）
    file.file.seek(0, 2)  # 移动到文件末尾
    file_size = file.file.tell()
    file.file.seek(0)  # 重置到开始
    
    max_size = 100 * 1024 * 1024  # 100MB
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件大小超过限制（最大 {max_size // 1024 // 1024}MB）"
        )
    
    # 4. 计算文件 Hash
    content_hash = await calculate_file_hash(file)
    logger.info(f"文件 Hash: {content_hash}, 大小: {file_size} bytes, 用户: {current_user.id}")
    
    # 5. 检查物理文件是否存在（秒传）
    existing_doc_stmt = select(Document).where(
        Document.tenant_id == current_user.tenant_id,
        Document.content_hash == content_hash,
        Document.is_deleted.is_(False),
    )
    existing_doc_stmt = existing_doc_stmt.order_by(
        desc(Document.created_at),
        desc(Document.id),
    ).limit(1)
    existing_doc_result = await session.execute(existing_doc_stmt)
    existing_doc = existing_doc_result.scalars().first()
    
    if existing_doc:
        # 秒传：物理文件已存在，直接返回
        logger.info(f"秒传: {file.filename}, 复用已有文档 {existing_doc.id}")
        
        return {
            "success": True,
            "message": "文件秒传成功（物理文件已存在）",
            "data": _build_upload_response(existing_doc, is_duplicate=True)
        }
    
    # 6. 正常上传：上传到 SeaweedFS + 创建 Document 记录
    logger.info(f"开始上传文件: {file.filename}")
    
    # 先创建 Document 记录（获取 document_id）
    # bucket_name 字段用途：
    # - S3 存储：存储 bucket 名称（如 "genesis-ai-files"）
    # - 本地存储：存储基础路径（如 "./storage-data"）
    bucket_name = (
        settings.SEAWEEDFS_BUCKET if settings.STORAGE_DRIVER == "s3"
        else settings.LOCAL_STORAGE_PATH
    )
    
    new_document = Document(
        tenant_id=current_user.tenant_id,
        owner_id=current_user.id,
        name=file.filename,
        file_type=file_ext.upper().lstrip('.'),
        storage_driver=settings.STORAGE_DRIVER,  # 存储驱动类型
        bucket_name=bucket_name,  # S3: bucket名称，本地: 基础路径
        file_key="",  # 临时占位，稍后更新（相对于 bucket_name 的路径）
        file_size=file_size,
        mime_type=file.content_type,
        carrier_type="file",
        asset_kind="physical",
        source_type="upload",
        content_hash=content_hash,
        metadata_info={},
        created_by_id=current_user.id,
        created_by_name=current_user.nickname
    )
    session.add(new_document)
    await session.flush()  # 获取 document_id
    
    # 生成存储路径（使用 document_id）
    file_key = generate_storage_path(
        tenant_id=current_user.tenant_id,
        filename=file.filename,
        resource_type="documents",
        document_id=new_document.id  # 使用 document_id 作为文件名
    )
    
    # 上传到存储系统
    try:
        storage_driver = get_storage_driver()
        
        # 准备元数据
        metadata = {
            "tenant_id": str(current_user.tenant_id),
            "uploaded_by": str(current_user.id),
            "document_id": str(new_document.id)
        }
        
        # S3 存储需要 URL 编码文件名
        if settings.STORAGE_DRIVER == "s3":
            import urllib.parse
            encoded_filename = urllib.parse.quote(file.filename)
            metadata["original_filename"] = encoded_filename
        else:
            # 本地存储直接使用原始文件名
            metadata["original_filename"] = file.filename
        
        await storage_driver.upload(
            file=file.file,
            key=file_key,
            content_type=file.content_type,
            metadata=metadata
        )
        logger.info(f"文件上传成功: {file_key}")
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        # 删除已创建的 Document 记录
        await session.delete(new_document)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件上传失败: {str(e)}"
        )
    
    # 更新 Document 记录的 file_key
    new_document.file_key = file_key
    await session.commit()
    await session.refresh(new_document)
    
    logger.info(f"创建 Document 记录: {new_document.id}")
    
    # 8. 返回响应
    return {
        "success": True,
        "message": "文件上传成功",
        "data": _build_upload_response(new_document, is_duplicate=False)
    }





# ==================== 软删除相关 API ====================

class SoftDeleteRequest(BaseModel):
    """软删除请求"""
    document_id: UUID = Field(..., description="文档ID")
    
    class Config:
        from_attributes = True


class RestoreRequest(BaseModel):
    """恢复文档请求"""
    document_id: UUID = Field(..., description="文档ID")
    
    class Config:
        from_attributes = True


class PermanentDeleteRequest(BaseModel):
    """物理删除请求"""
    document_id: UUID = Field(..., description="文档ID")
    
    class Config:
        from_attributes = True


@router.post(
    "/soft-delete",
    summary="软删除文档",
    description="将文档移至回收站，可以恢复"
)
async def soft_delete_document(
    request: SoftDeleteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    软删除文档（推荐方式）
    
    - 标记为已删除，但数据仍保留
    - 可以通过回收站恢复
    - 不删除物理文件
    
    Args:
        request: 删除请求
        current_user: 当前用户
        session: 数据库会话
        
    Returns:
        成功消息
    """
    from sqlalchemy import update
    
    document_id = request.document_id
    
    # 1. 查询文档
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id,
        Document.is_deleted == False  # 只能删除未删除的文档
    )
    result = await session.execute(stmt)
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或已被删除"
        )
    
    # 2. 权限检查：只有所有者可以删除
    # TODO: 后续可以扩展为检查资源权限
    if document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此文档"
        )
    
    # 3. 软删除
    update_stmt = (
        update(Document)
        .where(Document.id == document_id)
        .values(
            is_deleted=True,
            deleted_at=datetime.utcnow(),
            deleted_by_id=current_user.id,
            deleted_by_name=current_user.nickname,
            updated_at=datetime.utcnow(),
            updated_by_id=current_user.id
        )
    )
    await session.execute(update_stmt)
    await session.commit()
    
    logger.info(f"软删除文档: {document.name} (ID: {document_id}), 用户: {current_user.id}")
    
    return {
        "success": True,
        "message": "文档已移至回收站",
        "data": {
            "document_id": document_id,
            "document_name": document.name
        }
    }


@router.post(
    "/restore",
    summary="恢复已删除的文档",
    description="从回收站恢复文档"
)
async def restore_document(
    request: RestoreRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    恢复已删除的文档
    
    Args:
        request: 恢复请求
        current_user: 当前用户
        session: 数据库会话
        
    Returns:
        成功消息
    """
    from sqlalchemy import update
    
    document_id = request.document_id
    
    # 1. 查询文档（只查询已删除的）
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id,
        Document.is_deleted == True  # 只能恢复已删除的文档
    )
    result = await session.execute(stmt)
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或未被删除"
        )
    
    # 2. 权限检查：只有所有者可以恢复
    if document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权恢复此文档"
        )
    
    # 3. 恢复文档
    update_stmt = (
        update(Document)
        .where(Document.id == document_id)
        .values(
            is_deleted=False,
            deleted_at=None,
            deleted_by_id=None,
            deleted_by_name=None,
            updated_at=datetime.utcnow(),
            updated_by_id=current_user.id
        )
    )
    await session.execute(update_stmt)
    await session.commit()
    
    logger.info(f"恢复文档: {document.name} (ID: {document_id}), 用户: {current_user.id}")
    
    return {
        "success": True,
        "message": "文档已恢复",
        "data": {
            "document_id": document_id,
            "document_name": document.name
        }
    }


@router.post(
    "/permanent-delete",
    summary="物理删除文档（谨慎使用）",
    description="彻底删除文档，无法恢复，需要管理员权限"
)
async def permanent_delete_document(
    request: PermanentDeleteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    物理删除文档（谨慎使用）
    
    - 彻底删除，无法恢复
    - 需要管理员权限
    - 同时删除物理文件和所有关联数据
    
    Args:
        request: 删除请求
        current_user: 当前用户
        session: 数据库会话
        
    Returns:
        成功消息
    """
    from sqlalchemy import delete
    
    document_id = request.document_id
    
    # 1. 权限检查：需要管理员权限
    # TODO: 实现完整的权限检查系统
    # if "admin" not in current_user.permissions:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="需要管理员权限"
    #     )
    
    # 2. 查询文档
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id
    )
    result = await session.execute(stmt)
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )
    
    # 3. 权限检查：只有所有者或管理员可以物理删除
    if document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此文档"
        )
    
    # 4. 删除关联数据
    # TODO: 根据实际业务需求，删除相关的 segments、embeddings 等
    # 这里暂时只删除 knowledge_base_documents 关联
    try:
        # 删除知识库文档关联
        await session.execute(
            delete(KnowledgeBaseDocument).where(
                KnowledgeBaseDocument.document_id == document_id
            )
        )
        
        # 5. 删除物理文件
        try:
            # 根据 storage_driver 获取对应的驱动实例
            if document.storage_driver == "local":
                from core.storage.local_driver import get_local_driver
                storage_driver: StorageDriver = get_local_driver(str(document.bucket_name or settings.LOCAL_STORAGE_PATH))
            elif document.storage_driver == "s3":
                from core.storage.s3_driver import get_s3_driver
                storage_driver = get_s3_driver()
            else:
                storage_driver = get_storage_driver()
            
            await storage_driver.delete(document.file_key)
            logger.info(f"删除物理文件: {document.file_key}")
        except Exception as e:
            logger.warning(f"删除物理文件失败（继续删除数据库记录）: {e}")
        
        # 6. 删除文档记录
        await session.delete(document)
        await session.commit()
        
        logger.info(f"物理删除文档: {document.name} (ID: {document_id}), 用户: {current_user.id}")
        
        return {
            "success": True,
            "message": "文档已彻底删除",
            "data": {
                "document_id": document_id,
                "document_name": document.name
            }
        }
        
    except Exception as e:
        await session.rollback()
        logger.error(f"物理删除文档失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除文档失败: {str(e)}"
        )


@router.get(
    "/recycle-bin",
    summary="查看回收站",
    description="查看已删除的文档列表"
)
async def list_deleted_documents(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    查看回收站（已删除的文档）
    
    Args:
        page: 页码
        page_size: 每页数量
        current_user: 当前用户
        session: 数据库会话
        
    Returns:
        已删除的文档列表
    """
    from sqlalchemy import func
    
    # 1. 查询已删除的文档
    stmt = (
        select(Document)
        .where(
            Document.tenant_id == current_user.tenant_id,
            Document.owner_id == current_user.id,  # 只显示自己的文档
            Document.is_deleted == True
        )
        .order_by(Document.deleted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    
    result = await session.execute(stmt)
    documents = result.scalars().all()
    
    # 2. 计算总数
    count_stmt = select(func.count()).select_from(Document).where(
        Document.tenant_id == current_user.tenant_id,
        Document.owner_id == current_user.id,
        Document.is_deleted == True
    )
    total = await session.scalar(count_stmt)
    
    # 3. 构建响应
    return {
        "success": True,
        "data": [
            {
                "id": doc.id,
                "name": doc.name,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "deleted_at": doc.deleted_at.isoformat() if doc.deleted_at else None,
                "deleted_by_name": doc.deleted_by_name,
                "created_at": doc.created_at.isoformat() if doc.created_at else None
            }
            for doc in documents
        ],
        "total": total,
        "page": page,
        "page_size": page_size
    }
