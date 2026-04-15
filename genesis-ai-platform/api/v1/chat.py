"""
聊天模块 API
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_session
from core.response import ResponseBuilder
from core.security.auth import get_current_user
from models.user import User
from schemas.chat import (
    ChatCapabilityBindingCreate,
    ChatCapabilityBindingUpdate,
    ChatKnowledgeBasePickerRequest,
    ChatMessageSendRequest,
    ChatSessionCreate,
    ChatSessionUpdate,
    ChatSpaceCreate,
    ChatSpaceUpdate,
)
from services.chat import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_service(db: AsyncSession = Depends(get_async_session)) -> ChatService:
    """获取聊天服务实例。"""
    return ChatService(db)


@router.get("/bootstrap")
async def get_chat_bootstrap(
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """获取聊天页面初始化选项。"""
    data = await service.get_bootstrap_options(current_user=current_user)
    return ResponseBuilder.build_success(
        data=data.model_dump(mode="json"),
        message="获取聊天初始化数据成功",
    )


@router.post("/knowledge-base-picker/list")
async def list_chat_knowledge_base_picker(
    body: ChatKnowledgeBasePickerRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """聊天挂载知识库选择器专用列表（支持 exclude_ids），与知识库列表页接口隔离。"""
    items, total = await service.list_knowledge_base_picker_options(
        current_user=current_user,
        page=body.page,
        page_size=body.page_size,
        search=body.search,
        exclude_ids=body.exclude_ids,
    )
    return ResponseBuilder.build_success(
        data={
            "data": [item.model_dump(mode="json") for item in items],
            "total": total,
        },
        message="获取可选知识库列表成功",
    )


@router.get("/spaces")
async def list_chat_spaces(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: str | None = Query(None, description="搜索关键词"),
    status_filter: str = Query("active", alias="status", description="空间状态"),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """分页获取聊天空间列表。"""
    items, total = await service.list_spaces(
        current_user=current_user,
        search=search,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return ResponseBuilder.build_success(
        data={"data": [item.model_dump(mode="json") for item in items], "total": total},
        message="获取聊天空间列表成功",
    )


@router.post("/spaces", status_code=status.HTTP_201_CREATED)
async def create_chat_space(
    data: ChatSpaceCreate,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """创建聊天空间。"""
    item = await service.create_space(data=data, current_user=current_user)
    return ResponseBuilder.build_success(
        data=item.model_dump(mode="json"),
        message="创建聊天空间成功",
        http_status=status.HTTP_201_CREATED,
    )


@router.get("/spaces/{space_id}")
async def get_chat_space(
    space_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """获取聊天空间详情。"""
    item = await service.get_space(space_id=space_id, current_user=current_user)
    return ResponseBuilder.build_success(
        data=item.model_dump(mode="json"),
        message="获取聊天空间详情成功",
    )


@router.put("/spaces/{space_id}")
async def update_chat_space(
    space_id: UUID,
    data: ChatSpaceUpdate,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """更新聊天空间。"""
    item = await service.update_space(space_id=space_id, data=data, current_user=current_user)
    return ResponseBuilder.build_success(
        data=item.model_dump(mode="json"),
        message="更新聊天空间成功",
    )


@router.delete("/spaces/{space_id}")
async def delete_chat_space(
    space_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """删除聊天空间。"""
    await service.delete_space(space_id=space_id, current_user=current_user)
    return ResponseBuilder.build_success(
        data={"id": str(space_id)},
        message="删除聊天空间成功",
    )


@router.post("/sessions/{session_id}/capabilities", status_code=status.HTTP_201_CREATED)
async def create_chat_session_capability(
    session_id: UUID,
    data: ChatCapabilityBindingCreate,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """新增聊天会话能力挂载。"""
    item = await service.create_session_capability(
        session_id=session_id,
        data=data,
        current_user=current_user,
    )
    return ResponseBuilder.build_success(
        data=item,
        message="添加能力挂载成功",
        http_status=status.HTTP_201_CREATED,
    )


@router.put("/sessions/{session_id}/capabilities/{binding_id}")
async def update_chat_session_capability(
    session_id: UUID,
    binding_id: UUID,
    data: ChatCapabilityBindingUpdate,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """更新聊天会话能力挂载。"""
    item = await service.update_session_capability(
        session_id=session_id,
        binding_id=binding_id,
        data=data,
        current_user=current_user,
    )
    return ResponseBuilder.build_success(
        data=item,
        message="更新能力挂载成功",
    )


@router.delete("/sessions/{session_id}/capabilities/{binding_id}")
async def delete_chat_session_capability(
    session_id: UUID,
    binding_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """删除聊天会话能力挂载。"""
    await service.delete_session_capability(
        session_id=session_id,
        binding_id=binding_id,
        current_user=current_user,
    )
    return ResponseBuilder.build_success(
        data={"id": str(binding_id)},
        message="删除能力挂载成功",
    )


@router.get("/spaces/{space_id}/sessions")
async def list_chat_sessions(
    space_id: UUID,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status_filter: str = Query("active", alias="status", description="会话状态"),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """分页获取聊天空间下的会话列表。"""
    items, total = await service.list_sessions(
        space_id=space_id,
        current_user=current_user,
        page=page,
        page_size=page_size,
        status=status_filter,
    )
    return ResponseBuilder.build_success(
        data={"data": [item.model_dump(mode="json") for item in items], "total": total},
        message="获取会话列表成功",
    )


@router.post("/spaces/{space_id}/sessions", status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    space_id: UUID,
    data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """在聊天空间下创建会话。"""
    item = await service.create_session(space_id=space_id, data=data, current_user=current_user)
    return ResponseBuilder.build_success(
        data=item.model_dump(mode="json"),
        message="创建会话成功",
        http_status=status.HTTP_201_CREATED,
    )


@router.get("/sessions/{session_id}")
async def get_chat_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """获取会话详情。"""
    item = await service.get_session(session_id=session_id, current_user=current_user)
    return ResponseBuilder.build_success(
        data=item.model_dump(mode="json"),
        message="获取会话详情成功",
    )


@router.put("/sessions/{session_id}")
async def update_chat_session(
    session_id: UUID,
    data: ChatSessionUpdate,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """更新会话。"""
    item = await service.update_session(session_id=session_id, data=data, current_user=current_user)
    return ResponseBuilder.build_success(
        data=item.model_dump(mode="json"),
        message="更新会话成功",
    )


@router.get("/sessions/{session_id}/messages")
async def list_chat_messages(
    session_id: UUID,
    include_backend_only: bool = Query(False, description="是否包含后台不可见消息"),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """获取会话消息列表。"""
    items = await service.list_messages(
        session_id=session_id,
        current_user=current_user,
        include_backend_only=include_backend_only,
    )
    return ResponseBuilder.build_success(
        data=[item.model_dump(mode="json", by_alias=True) for item in items],
        message="获取消息列表成功",
    )


@router.delete("/sessions/{session_id}/messages")
async def clear_chat_messages(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """清空当前会话的全部聊天记录（会话本身保留）。"""
    await service.clear_session_messages(session_id=session_id, current_user=current_user)
    return ResponseBuilder.build_success(
        data={"session_id": str(session_id)},
        message="聊天记录已清空",
    )


@router.post("/sessions/{session_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_chat_message(
    session_id: UUID,
    data: ChatMessageSendRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """发送聊天消息。"""
    result = await service.send_message(session_id=session_id, data=data, current_user=current_user)
    return ResponseBuilder.build_success(
        data=result.model_dump(mode="json", by_alias=True),
        message="发送消息成功",
        http_status=status.HTTP_201_CREATED,
    )


@router.post("/sessions/{session_id}/messages/stream")
async def stream_chat_message(
    session_id: UUID,
    data: ChatMessageSendRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """以 SSE 方式发送聊天消息。"""
    generator = service.stream_message(
        session_id=session_id,
        data=data,
        current_user=current_user,
    )
    return StreamingResponse(generator, media_type="text/event-stream")
