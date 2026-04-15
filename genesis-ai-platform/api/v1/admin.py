"""
管理员 API
系统管理、监控、维护等功能
"""
from fastapi import APIRouter, Depends, HTTPException, status
from models.user import User
from core.security import get_current_user
from core.response import ResponseBuilder
from core.database.session import get_redis_client
from tasks.cleanup_sessions import run_cleanup_tasks, cleanup_orphan_refresh_sessions, cleanup_expired_revoked_tokens

router = APIRouter()


@router.post("/cleanup/sessions")
async def cleanup_sessions(
    current_user: User = Depends(get_current_user)
):
    """
    清理孤儿 session
    
    权限：仅超级管理员
    
    功能：
    - 清理孤儿 refresh session（access session 已过期但 refresh session 仍存在）
    - 清理已过期的撤销 token 记录
    
    使用场景：
    - 手动触发清理
    - 测试清理逻辑
    - 紧急释放 Redis 内存
    """
    # 检查权限
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can perform this operation"
        )
    
    # 运行清理任务（FastAPI 中使用全局连接池）
    redis_client = get_redis_client()
    result = await run_cleanup_tasks(redis_client)
    
    return ResponseBuilder.build_success(
        data=result,
        message="Session 清理完成"
    )


@router.post("/cleanup/sessions/orphan")
async def cleanup_orphan_sessions_only(
    current_user: User = Depends(get_current_user)
):
    """
    只清理孤儿 refresh session
    
    权限：仅超级管理员
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can perform this operation"
        )
    
    redis_client = get_redis_client()
    result = await cleanup_orphan_refresh_sessions(redis_client)
    
    return ResponseBuilder.build_success(
        data=result,
        message="孤儿 session 清理完成"
    )


@router.post("/cleanup/sessions/revoked")
async def cleanup_revoked_tokens_only(
    current_user: User = Depends(get_current_user)
):
    """
    只清理已过期的撤销 token
    
    权限：仅超级管理员
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can perform this operation"
        )
    
    redis_client = get_redis_client()
    result = await cleanup_expired_revoked_tokens(redis_client)
    
    return ResponseBuilder.build_success(
        data=result,
        message="已过期的撤销 token 清理完成"
    )


@router.get("/stats/sessions")
async def get_session_stats(
    current_user: User = Depends(get_current_user)
):
    """
    获取 session 统计信息
    
    权限：仅超级管理员
    
    返回：
    - 总 session 数
    - Access session 数
    - Refresh session 数
    - 撤销 token 数
    - Redis 内存使用
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can perform this operation"
        )
    
    from core.security.token_store import SessionStore
    
    redis = get_redis_client()
    session_store = SessionStore(redis)
    
    # 统计各类 key 的数量
    access_count = 0
    refresh_count = 0
    revoked_count = 0
    
    # Access sessions
    cursor = 0
    while True:
        cursor, keys = await redis.scan(
            cursor=cursor,
            match=f"{session_store.ACCESS_SESSION_PREFIX}*",
            count=100
        )
        access_count += len(keys)
        if cursor == 0:
            break
    
    # Refresh sessions
    cursor = 0
    while True:
        cursor, keys = await redis.scan(
            cursor=cursor,
            match=f"{session_store.REFRESH_SESSION_PREFIX}*",
            count=100
        )
        refresh_count += len(keys)
        if cursor == 0:
            break
    
    # Revoked tokens
    cursor = 0
    while True:
        cursor, keys = await redis.scan(
            cursor=cursor,
            match="auth:refresh:revoked:*",
            count=100
        )
        revoked_count += len(keys)
        if cursor == 0:
            break
    
    # Redis 内存信息
    info = await redis.info("memory")
    used_memory = info.get("used_memory_human", "N/A")
    used_memory_peak = info.get("used_memory_peak_human", "N/A")
    
    return ResponseBuilder.build_success(
        data={
            "sessions": {
                "total": access_count + refresh_count,
                "access": access_count,
                "refresh": refresh_count,
                "revoked_tokens": revoked_count
            },
            "redis": {
                "used_memory": used_memory,
                "used_memory_peak": used_memory_peak
            }
        },
        message="获取 session 统计信息成功"
    )
