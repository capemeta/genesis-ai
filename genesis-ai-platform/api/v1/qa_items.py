"""
QA 数据集与内容项接口
"""
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.deps import get_current_user
from api.v1.documents import _build_content_disposition
from core.database import get_async_session
from models.user import User
from schemas.kb_qa_row import (
    QAKBFacetRequest,
    QADatasetRebuildRequest,
    QADatasetDetailRequest,
    QAItemBatchUpdateRequest,
    QAItemBatchDeleteRequest,
    QAItemBatchToggleEnabledRequest,
    QAItemBatchCreateRequest,
    QAItemCreateRequest,
    QAItemDeleteRequest,
    QAItemListRequest,
    QAItemReorderRequest,
    QAItemToggleEnabledRequest,
    QAItemUpdateRequest,
    QAVirtualDatasetCreateRequest,
)
from services.qa_dataset_service import QADatasetService
from utils.qa_markdown import build_qa_markdown_text

router = APIRouter(prefix="/knowledge-bases/qa-items", tags=["knowledge-bases-qa"])
# 模板与后端同目录发布：genesis-ai-platform/templates/
QA_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "templates" / "qa_import_template.csv"


def _serialize_qa_item(item) -> dict:
    """统一 QA 行响应结构，兼容前端当前使用的字段形状。"""
    summary = str(item.answer or "").strip()
    if len(summary) > 120:
        summary = f"{summary[:117]}..."
    return {
        "id": str(item.id),
        "kb_doc_id": str(item.kb_doc_id),
        "position": item.position,
        "title": item.question,
        "content_text": build_qa_markdown_text(
            question=str(item.question or "").strip(),
            answer=str(item.answer or "").strip(),
            similar_questions=item.similar_questions or [],
            category=str(item.category or "").strip(),
            tags=item.tags or [],
        ),
        "content_structured": {
            "question": item.question,
            "answer": item.answer,
            "similar_questions": list(item.similar_questions or []),
            "tags": list(item.tags or []),
            "category": item.category,
        },
        "summary": summary,
        "metadata": {
            "source_row": item.source_row,
            "source_sheet_name": item.source_sheet_name,
            "has_manual_edits": item.has_manual_edits,
        },
        "is_enabled": item.is_enabled,
        "edit_mode": "editable",
        "source_mode": item.source_mode,
        "version_no": item.version_no,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


@router.post("/detail", summary="获取 QA 数据集详情")
async def get_dataset_detail(
    request: QADatasetDetailRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """获取 QA 数据集详情与统计信息。"""
    service = QADatasetService(session)
    result = await service.get_dataset_detail(
        kb_doc_id=request.kb_doc_id,
        current_user=current_user,
    )
    return {"success": True, "data": result}


@router.post("/kb-facets", summary="获取 QA 知识库可选分类与标签")
async def get_kb_facets(
    request: QAKBFacetRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """返回当前 QA 知识库中可用于显式范围设置的分类与标签。"""
    service = QADatasetService(session)
    result = await service.get_kb_facets(
        kb_id=request.kb_id,
        current_user=current_user,
    )
    return {"success": True, "data": result}


@router.post("/export-csv", summary="导出 QA 数据集为 CSV")
async def export_dataset_csv(
    request: QADatasetDetailRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """导出当前 QA 数据集为 CSV（基于最新 QA 行数据）。"""
    service = QADatasetService(session)
    csv_bytes, filename = await service.export_dataset_csv(
        kb_doc_id=request.kb_doc_id,
        current_user=current_user,
    )

    # HTTP 头必须为 latin-1；中文需走 filename*（与 documents 下载一致）
    content_disposition = _build_content_disposition(filename)
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": content_disposition,
            "Access-Control-Expose-Headers": "Content-Disposition",
            "Cache-Control": "no-cache",
        },
    )


@router.post("/rebuild", summary="基于 QA 行重建问答集 chunks")
async def rebuild_dataset(
    request: QADatasetRebuildRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """基于 kb_qa_rows 重新生成当前 QA 数据集的 chunks。"""
    service = QADatasetService(session)
    result = await service.rebuild_dataset(
        kb_doc_id=request.kb_doc_id,
        current_user=current_user,
    )
    return {"success": True, "message": "问答集重建成功", "data": result}


@router.post("/create-virtual-dataset", summary="创建 QA 虚拟文件问答集")
async def create_virtual_dataset(
    request: QAVirtualDatasetCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """创建可手工维护的 QA 虚拟文件数据集。"""
    service = QADatasetService(session)
    result = await service.create_virtual_dataset(
        kb_id=request.kb_id,
        dataset_name=request.dataset_name,
        folder_id=request.folder_id,
        items=[item.model_dump() for item in request.items],
        current_user=current_user,
    )
    return {"success": True, "message": "问答集创建成功", "data": result}


@router.get("/download-template", summary="下载 QA 导入模板")
async def download_import_template(
    current_user: User = Depends(get_current_user),
):
    """下载 QA 固定模板 CSV 文件。"""
    if not QA_TEMPLATE_PATH.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA 导入模板不存在")

    return FileResponse(
        path=str(QA_TEMPLATE_PATH),
        media_type="text/csv; charset=utf-8",
        filename="qa_import_template.csv",
    )


@router.post("/preview-import", summary="预检 QA 导入文件模板")
async def preview_import_file(
    file: UploadFile = File(..., description="待预检的 QA 导入文件，仅支持 csv/xlsx"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """在正式导入前预检 QA 文件模板并返回解析预览。"""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件名不能为空")

    file_buffer = await file.read()
    service = QADatasetService(session)
    result = await service.preview_import_file(
        filename=file.filename,
        file_buffer=file_buffer,
    )
    return {"success": True, "message": "预检成功", "data": result}


@router.post("/import-file", summary="导入 QA 文件为问答集")
async def import_dataset_file(
    kb_id: UUID = Form(..., description="目标 QA 知识库 ID"),
    folder_id: UUID | None = Form(None, description="目标文件夹 ID"),
    file: UploadFile = File(..., description="待导入的 QA 文件，仅支持 csv/xlsx"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """导入 QA 文件并创建只读问答集。"""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件名不能为空")

    file_buffer = await file.read()
    service = QADatasetService(session)
    result = await service.import_dataset_file(
        kb_id=kb_id,
        folder_id=folder_id,
        filename=file.filename,
        file_buffer=file_buffer,
        content_type=file.content_type,
        current_user=current_user,
    )
    return {"success": True, "message": "问答集导入成功", "data": result}


@router.post("/list", summary="列出 QA 内容项")
async def list_qa_items(
    request: QAItemListRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """按数据集列出问答内容。"""
    service = QADatasetService(session)
    items = await service.list_items(
        kb_doc_id=request.kb_doc_id,
        current_user=current_user,
        include_disabled=request.include_disabled,
    )
    dataset = await service.get_dataset_detail(
        kb_doc_id=request.kb_doc_id,
        current_user=current_user,
    )
    return {
        "success": True,
        "data": {
            "dataset": dataset,
            "items": [_serialize_qa_item(item) for item in items],
            "total": len(items),
        },
    }


@router.post("/create", summary="创建单条 QA 内容项")
async def create_qa_item(
    request: QAItemCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """在指定 QA 数据集中创建单条问答。"""
    service = QADatasetService(session)
    result = await service.create_item(
        kb_doc_id=request.kb_doc_id,
        item=request.item.model_dump(),
        current_user=current_user,
    )
    return {"success": True, "message": "问答创建成功", "data": result}


@router.post("/batch-create", summary="批量创建 QA 内容项")
async def batch_create_qa_items(
    request: QAItemBatchCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """在指定 QA 数据集中批量创建问答。"""
    service = QADatasetService(session)
    result = await service.batch_create_items(
        kb_doc_id=request.kb_doc_id,
        items=[item.model_dump() for item in request.items],
        current_user=current_user,
    )
    return {"success": True, "message": "问答批量创建成功", "data": result}


@router.post("/update", summary="更新单条 QA 内容项")
async def update_qa_item(
    request: QAItemUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """更新单条问答内容。"""
    service = QADatasetService(session)
    result = await service.update_item(
        item_id=request.item_id,
        item=request.item.model_dump(),
        current_user=current_user,
    )
    return {"success": True, "message": "问答更新成功", "data": result}


@router.post("/batch-update", summary="批量更新 QA 内容项")
async def batch_update_qa_items(
    request: QAItemBatchUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """批量更新 QA 内容项。"""
    service = QADatasetService(session)
    result = await service.batch_update_items(
        item_updates=[
            {
                "item_id": item.item_id,
                "item": item.item.model_dump(),
            }
            for item in request.items
        ],
        current_user=current_user,
    )
    return {"success": True, "message": "问答批量更新成功", "data": result}


@router.post("/delete", summary="删除单条 QA 内容项")
async def delete_qa_item(
    request: QAItemDeleteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """删除单条问答内容。"""
    service = QADatasetService(session)
    result = await service.delete_item(
        item_id=request.item_id,
        current_user=current_user,
    )
    return {"success": True, "message": "问答删除成功", "data": result}


@router.post("/batch-delete", summary="批量删除 QA 内容项")
async def batch_delete_qa_items(
    request: QAItemBatchDeleteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """批量删除 QA 内容项。"""
    service = QADatasetService(session)
    result = await service.batch_delete_items(
        item_ids=request.item_ids,
        current_user=current_user,
    )
    return {"success": True, "message": "问答批量删除成功", "data": result}


@router.post("/toggle-enabled", summary="启用或禁用单条 QA 内容项")
async def toggle_qa_item_enabled(
    request: QAItemToggleEnabledRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """启用或禁用单条问答。"""
    service = QADatasetService(session)
    result = await service.toggle_item_enabled(
        item_id=request.item_id,
        enabled=request.enabled,
        current_user=current_user,
    )
    return {
        "success": True,
        "message": f"问答已{'启用' if request.enabled else '禁用'}",
        "data": result,
    }


@router.post("/batch-toggle-enabled", summary="批量启用或禁用 QA 内容项")
async def batch_toggle_qa_items_enabled(
    request: QAItemBatchToggleEnabledRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """批量启用或禁用 QA 内容项。"""
    service = QADatasetService(session)
    result = await service.batch_toggle_items_enabled(
        item_ids=request.item_ids,
        enabled=request.enabled,
        current_user=current_user,
    )
    return {
        "success": True,
        "message": f"问答已批量{'启用' if request.enabled else '禁用'}",
        "data": result,
    }


@router.post("/reorder", summary="调整 QA 内容项顺序")
async def reorder_qa_items(
    request: QAItemReorderRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """调整 QA 内容项顺序。"""
    service = QADatasetService(session)
    result = await service.reorder_items(
        kb_doc_id=request.kb_doc_id,
        item_orders=[
            {
                "item_id": item.item_id,
                "position": item.position,
            }
            for item in request.items
        ],
        current_user=current_user,
    )
    return {"success": True, "message": "问答顺序调整成功", "data": result}
