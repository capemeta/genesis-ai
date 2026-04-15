"""
文件夹标签 API 路由
"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_session
from core.security.auth import get_current_user
from models.user import User
from models.folder import Folder
from schemas.tag import FolderTagsRequest, FolderTagsResponse, TagRead
from services.folder_tag_service import FolderTagService

router = APIRouter(prefix="/folder-tags", tags=["folder-tags"])


@router.post("/get", response_model=FolderTagsResponse)
async def get_folder_tags(
    request: dict,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    获取文件夹的标签
    
    请求体：
    - folder_id: 文件夹ID
    """
    folder_id = UUID(request["folder_id"])
    
    # 检查文件夹是否存在且属于当前租户
    folder = await session.get(Folder, folder_id)
    if not folder or folder.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件夹不存在"
        )
    
    # 获取标签
    tags = await FolderTagService.get_folder_tags(
        session=session,
        folder_id=folder_id,
        tenant_id=current_user.tenant_id
    )
    
    return {
        "folder_id": folder_id,
        "tags": tags
    }


@router.post("/set", response_model=FolderTagsResponse)
async def set_folder_tags(
    request: FolderTagsRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    设置文件夹的标签（替换现有标签）
    
    请求体：
    - folder_id: 文件夹ID
    - tag_ids: 标签ID列表
    """
    # 检查文件夹是否存在且属于当前租户
    folder = await session.get(Folder, request.folder_id)
    if not folder or folder.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件夹不存在"
        )
    
    # 设置标签
    tags = await FolderTagService.set_folder_tags(
        session=session,
        folder_id=request.folder_id,
        tag_ids=request.tag_ids,
        tenant_id=current_user.tenant_id,
        kb_id=folder.kb_id
    )
    
    return {
        "folder_id": request.folder_id,
        "tags": tags
    }


@router.post("/add")
async def add_folder_tag(
    request: dict,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    为文件夹添加单个标签
    
    请求体：
    - folder_id: 文件夹ID
    - tag_id: 标签ID
    """
    folder_id = UUID(request["folder_id"])
    tag_id = UUID(request["tag_id"])
    
    # 检查文件夹是否存在且属于当前租户
    folder = await session.get(Folder, folder_id)
    if not folder or folder.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件夹不存在"
        )
    
    # 添加标签
    tag = await FolderTagService.add_folder_tag(
        session=session,
        folder_id=folder_id,
        tag_id=tag_id,
        tenant_id=current_user.tenant_id,
        kb_id=folder.kb_id
    )
    
    return {"data": tag}


@router.post("/remove")
async def remove_folder_tag(
    request: dict,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    移除文件夹的标签
    
    请求体：
    - folder_id: 文件夹ID
    - tag_id: 标签ID
    """
    folder_id = UUID(request["folder_id"])
    tag_id = UUID(request["tag_id"])
    
    # 检查文件夹是否存在且属于当前租户
    folder = await session.get(Folder, folder_id)
    if not folder or folder.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件夹不存在"
        )
    
    # 移除标签
    await FolderTagService.remove_folder_tag(
        session=session,
        folder_id=folder_id,
        tag_id=tag_id,
        tenant_id=current_user.tenant_id
    )
    
    return {"message": "标签已移除"}
