"""
定期清理任务

功能：
1. 清理已删除超过 N 天的文档（物理删除）
2. 清理过期的临时文件
3. 清理孤立的物理文件
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.storage import get_storage_driver
from models.document import Document
from models.knowledge_base_document import KnowledgeBaseDocument

logger = logging.getLogger(__name__)


async def cleanup_deleted_documents(session_maker, days: int = 30) -> dict:
    """
    清理已删除超过 N 天的文档（物理删除）
    
    流程：
    1. 查询已删除超过 N 天的文档
    2. 删除关联数据（knowledge_base_documents 等）
    3. 删除物理文件
    4. 删除文档记录
    
    Args:
        session_maker: 数据库 session 工厂（由调用方管理引擎生命周期）
        days: 删除超过多少天的文档（默认 30 天）
        
    Returns:
        清理结果统计
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    logger.info(f"开始清理已删除超过 {days} 天的文档（截止日期: {cutoff_date}）")
    
    cleaned_count = 0
    failed_count = 0
    failed_documents = []
    
    async with session_maker() as session:
        try:
            # 1. 查询需要清理的文档
            stmt = select(Document).where(
                Document.is_deleted == True,
                Document.deleted_at < cutoff_date
            )
            result = await session.execute(stmt)
            documents = result.scalars().all()
            
            logger.info(f"找到 {len(documents)} 个需要清理的文档")
            
            # 2. 逐个清理
            for doc in documents:
                try:
                    await _cleanup_single_document(session, doc)
                    cleaned_count += 1
                    logger.info(f"清理文档成功: {doc.name} (ID: {doc.id})")
                except Exception as e:
                    failed_count += 1
                    failed_documents.append({
                        "id": str(doc.id),
                        "name": doc.name,
                        "error": str(e)
                    })
                    logger.error(f"清理文档失败: {doc.name} (ID: {doc.id}), 错误: {e}")
            
            await session.commit()
            
        except Exception as e:
            logger.error(f"清理任务失败: {e}")
            await session.rollback()
            raise
    
    result = {
        "success": True,
        "cleaned_count": cleaned_count,
        "failed_count": failed_count,
        "failed_documents": failed_documents,
        "cutoff_date": cutoff_date.isoformat()
    }
    
    logger.info(f"清理任务完成: 成功 {cleaned_count} 个，失败 {failed_count} 个")
    
    return result


async def _cleanup_single_document(session: AsyncSession, document: Document):
    """
    清理单个文档
    
    Args:
        session: 数据库会话
        document: 文档对象
    """
    # 1. 删除知识库文档关联
    await session.execute(
        delete(KnowledgeBaseDocument).where(
            KnowledgeBaseDocument.document_id == document.id
        )
    )
    
    # 2. 删除物理文件
    try:
        storage_driver = get_storage_driver()
        await storage_driver.delete(document.file_key)
        logger.debug(f"删除物理文件: {document.file_key}")
    except Exception as e:
        logger.warning(f"删除物理文件失败（继续删除数据库记录）: {e}")
    
    # 3. 删除文档记录
    await session.delete(document)


async def cleanup_temp_files(session_maker, days: int = 7) -> dict:
    """
    清理临时文件
    
    临时文件：上传后未关联到知识库的文档
    存储路径：{tenant_id}/documents/temp/
    
    Args:
        session_maker: 数据库 session 工厂（由调用方管理引擎生命周期）
        days: 清理超过多少天的临时文件（默认 7 天）
        
    Returns:
        清理结果统计
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    logger.info(f"开始清理超过 {days} 天的临时文件（截止日期: {cutoff_date}）")
    
    cleaned_count = 0
    failed_count = 0
    
    async with session_maker() as session:
        try:
            # 查询临时文件（file_key 包含 /temp/）
            stmt = select(Document).where(
                Document.file_key.like('%/temp/%'),
                Document.created_at < cutoff_date
            )
            result = await session.execute(stmt)
            documents = result.scalars().all()
            
            logger.info(f"找到 {len(documents)} 个临时文件")
            
            # 逐个删除
            for doc in documents:
                try:
                    # 检查是否已关联到知识库
                    kb_doc_stmt = select(KnowledgeBaseDocument).where(
                        KnowledgeBaseDocument.document_id == doc.id
                    )
                    kb_doc_result = await session.execute(kb_doc_stmt)
                    kb_doc = kb_doc_result.scalar_one_or_none()
                    
                    if kb_doc:
                        # 已关联，跳过
                        logger.debug(f"跳过已关联的临时文件: {doc.name}")
                        continue
                    
                    # 删除物理文件和数据库记录
                    await _cleanup_single_document(session, doc)
                    cleaned_count += 1
                    logger.info(f"清理临时文件: {doc.name}")
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"清理临时文件失败: {doc.name}, 错误: {e}")
            
            await session.commit()
            
        except Exception as e:
            logger.error(f"清理临时文件任务失败: {e}")
            await session.rollback()
            raise
    
    result = {
        "success": True,
        "cleaned_count": cleaned_count,
        "failed_count": failed_count,
        "cutoff_date": cutoff_date.isoformat()
    }
    
    logger.info(f"清理临时文件完成: 成功 {cleaned_count} 个，失败 {failed_count} 个")
    
    return result


# 导出函数供 celery_tasks.py 调用
async def run_cleanup_deleted_documents(session_maker, days: int = 30):
    """运行文档清理任务"""
    return await cleanup_deleted_documents(session_maker, days)


async def run_cleanup_temp_files(session_maker, days: int = 7):
    """运行临时文件清理任务"""
    return await cleanup_temp_files(session_maker, days)
