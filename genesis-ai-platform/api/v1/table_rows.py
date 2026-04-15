"""
表格知识库行数据接口
"""
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.deps import get_current_user
from core.database import get_async_session
from models.user import User
from schemas.kb_table_row import (
    TableRowCreateRequest,
    TableRowDatasetDetailRequest,
    TableRowDeleteRequest,
    TableRowListRequest,
    TableRowRebuildRequest,
    TableRowUpdateRequest,
)
from services.table_dataset_service import TableDatasetService

router = APIRouter(prefix="/knowledge-bases/table-rows", tags=["knowledge-bases-table"])

# 模板与后端同目录发布：genesis-ai-platform/templates/（与 qa_items.QA_TEMPLATE_PATH 一致）
TABLE_IMPORT_SAMPLE_PATH = Path(__file__).resolve().parents[2] / "templates" / "table_import_sample.csv"


def _serialize_table_row(row) -> dict:
    """统一表格行响应结构。"""
    return {
        "id": str(row.id),
        "kb_doc_id": str(row.kb_doc_id),
        "row_uid": row.row_uid,
        "sheet_name": row.sheet_name,
        "row_index": row.row_index,
        "source_row_number": row.source_row_number,
        "source_type": row.source_type,
        "row_version": row.row_version,
        "is_deleted": row.is_deleted,
        "row_data": row.row_data,
        "source_meta": row.source_meta,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.post("/detail", summary="获取表格数据集详情")
async def get_table_dataset_detail(
    request: TableRowDatasetDetailRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """获取表格数据集详情与统计信息。"""
    service = TableDatasetService(session)
    result = await service.get_dataset_detail(
        kb_doc_id=request.kb_doc_id,
        current_user=current_user,
    )
    return {"success": True, "data": result}


@router.post("/list", summary="列出表格行")
async def list_table_rows(
    request: TableRowListRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """按数据集列出表格行。"""
    service = TableDatasetService(session)
    rows = await service.list_rows(
        page=request.page,
        page_size=request.page_size,
        kb_doc_id=request.kb_doc_id,
        current_user=current_user,
        include_deleted=request.include_deleted,
        search=request.search,
        column_filters=request.column_filters,
    )
    paged_rows, total = rows
    dataset = await service.get_dataset_detail(
        kb_doc_id=request.kb_doc_id,
        current_user=current_user,
    )
    return {
        "success": True,
        "data": {
            "dataset": dataset,
            "rows": [_serialize_table_row(row) for row in paged_rows],
            "total": total,
            "page": request.page,
            "page_size": request.page_size,
        },
    }


@router.post("/update", summary="更新单条表格行")
async def update_table_row(
    request: TableRowUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """更新单条表格行，并将数据集置为待重解析。"""
    service = TableDatasetService(session)
    result = await service.update_row(
        row_id=request.row_id,
        row_data=request.item.row_data,
        current_user=current_user,
    )
    return {"success": True, "message": "表格行更新成功，请重新触发解析", "data": result}


@router.post("/create", summary="新增单条表格行")
async def create_table_row(
    request: TableRowCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """新增单条表格行，并将数据集置为待重解析。"""
    service = TableDatasetService(session)
    result = await service.create_row(
        kb_doc_id=request.kb_doc_id,
        row_data=request.item.row_data,
        current_user=current_user,
        sheet_name=request.item.sheet_name,
    )
    return {"success": True, "message": "表格行新增成功，请重新触发解析", "data": result}


@router.post("/delete", summary="删除单条表格行")
async def delete_table_row(
    request: TableRowDeleteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """软删除单条表格行，并将数据集置为待重解析。"""
    service = TableDatasetService(session)
    result = await service.delete_row(
        row_id=request.row_id,
        current_user=current_user,
    )
    return {"success": True, "message": "表格行删除成功，请重新触发解析", "data": result}


@router.post("/rebuild", summary="基于行表重新生成表格 chunks")
async def rebuild_table_dataset(
    request: TableRowRebuildRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """基于 kb_table_rows 重新生成表格知识库 chunks。"""
    service = TableDatasetService(session)
    result = await service.rebuild_dataset(
        kb_doc_id=request.kb_doc_id,
        current_user=current_user,
    )
    return {"success": True, "message": "表格数据集重新解析成功", "data": result}


@router.get("/download-template", summary="下载表格导入 CSV 样例")
async def download_table_import_template(
    current_user: User = Depends(get_current_user),
):
    """下载结构化表格知识库用 CSV 样例：第 1 行为表头，第 2 行起为数据（列名可替换为业务字段）。"""
    if not TABLE_IMPORT_SAMPLE_PATH.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="表格导入样例不存在")

    return FileResponse(
        path=str(TABLE_IMPORT_SAMPLE_PATH),
        media_type="text/csv; charset=utf-8",
        filename="table_import_sample.csv",
    )
