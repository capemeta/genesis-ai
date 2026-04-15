"""
文件夹自定义路由

在 CRUD 工厂生成的标准路由基础上，添加自定义路由
"""
from fastapi import Depends, Body
from uuid import UUID
from pydantic import BaseModel

from core.security.auth import get_current_user
from core.database import get_async_session
from services.folder_service import FolderService
from schemas.folder import FolderRead
from models.user import User
from api.crud_registry import crud_factory

# 从 CRUD 工厂获取已生成的 router
router = crud_factory.get_router("Folder")


class FolderTreeRequest(BaseModel):
    """获取文件夹树请求"""
    kb_id: UUID


@router.post("/tree", response_model=dict)
async def get_folder_tree(
    request: FolderTreeRequest = Body(...),
    current_user: User = Depends(get_current_user),
    session = Depends(get_async_session)
):
    """
    获取知识库的完整文件夹树（不分页）
    
    用于前端展示文件夹树，返回所有文件夹
    
    请求体：
    ```json
    {
        "kb_id": "uuid"
    }
    ```
    
    响应：
    ```json
    {
        "data": [
            {
                "id": "uuid",
                "name": "文件夹名称",
                "parent_id": "uuid",
                "path": "kb_xxx.folder1.folder2",
                "level": 2,
                ...
            }
        ]
    }
    ```
    """
    from models.folder import Folder
    
    service = FolderService(model=Folder, db=session, resource_name="folder")
    folders = await service.get_tree(
        kb_id=request.kb_id,
        current_user=current_user
    )
    
    return {
        "data": [FolderRead.model_validate(folder) for folder in folders]
    }


class FolderPathRequest(BaseModel):
    """获取文件夹路径请求"""
    folder_id: UUID


@router.post("/path", response_model=dict)
async def get_folder_path(
    request: FolderPathRequest = Body(...),
    current_user: User = Depends(get_current_user),
    session = Depends(get_async_session)
):
    """
    获取文件夹的完整路径（面包屑导航）
    
    优化版本：利用 ltree 的祖先查询功能，
    通过单次查询获取所有祖先文件夹，避免递归查询。
    
    请求体：
    ```json
    {
        "folder_id": "uuid"
    }
    ```
    
    响应：
    ```json
    {
        "data": [
            {
                "id": "uuid",
                "name": "父文件夹",
                "full_name_path": "/父文件夹",
                ...
            },
            {
                "id": "uuid",
                "name": "当前文件夹",
                "full_name_path": "/父文件夹/当前文件夹",
                ...
            }
        ]
    }
    ```
    """
    from models.folder import Folder
    from sqlalchemy import select, text
    
    # 获取当前文件夹
    stmt = select(Folder).where(
        Folder.id == request.folder_id,
        Folder.tenant_id == current_user.tenant_id
    )
    result = await session.execute(stmt)
    current_folder = result.scalar_one_or_none()
    
    if not current_folder:
        return {"data": []}
    
    # 使用 ltree 的祖先查询功能，一次性获取所有父级文件夹（包括当前文件夹）
    # 
    # ltree 路径示例：kb_xxx.f_aaa.f_bbb.f_ccc
    # 我们需要找到所有满足以下条件的文件夹：
    # 1. 它们的 path 是 current_folder.path 的前缀（祖先）
    # 2. 或者就是 current_folder 本身
    #
    # 使用 @> 操作符：path @> '{current_folder.path}'
    # 表示 path 是 current_folder.path 的祖先（path 包含在 current_folder.path 中）
    # 
    # 或者使用 <@ 操作符：'{current_folder.path}' <@ path
    # 表示 current_folder.path 是 path 的后代
    stmt = select(Folder).where(
        Folder.tenant_id == current_user.tenant_id,
        Folder.kb_id == current_folder.kb_id,
        text(f"path @> '{current_folder.path}'::ltree")
    ).order_by(Folder.level)
    
    result = await session.execute(stmt)
    ancestors = result.scalars().all()
    
    # 返回从根到当前文件夹的完整路径
    return {
        "data": [FolderRead.model_validate(folder) for folder in ancestors]
    }
