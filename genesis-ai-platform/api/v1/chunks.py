"""Chunk 扩展路由。"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crud_registry import crud_factory
from core.database import get_async_session
from core.response import ResponseBuilder
from core.security import get_current_active_user
from models.chunk import Chunk
from models.user import User
from schemas.chunk import ChunkNodeIdRequest, ChunkRead
from services.chunk_service import ChunkService

router = crud_factory.get_router("Chunk")


def get_chunk_service(db: AsyncSession = Depends(get_async_session)) -> ChunkService:
    """获取切片服务实例。"""
    return ChunkService(model=Chunk, db=db)


@router.post("/get-by-node-id", response_model=dict)
async def get_chunk_by_node_id(
    request: ChunkNodeIdRequest,
    current_user: User = Depends(get_current_active_user),
    service: ChunkService = Depends(get_chunk_service),
):
    """按 node_id 获取单个切片。"""
    resource = await service.get_by_node_id(
        node_id=request.node_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )
    return ResponseBuilder.build_success(
        data=ChunkRead.model_validate(resource).model_dump(by_alias=True),
        message="获取详情成功",
    )
