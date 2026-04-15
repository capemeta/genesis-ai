"""
Session 清理任务
定期清理孤儿 refresh session（access session 已过期但 refresh session 仍存在）
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, cast
from redis.asyncio import Redis
from core.security.token_store import SessionStore

logger = logging.getLogger(__name__)


async def cleanup_orphan_refresh_sessions(redis_client: Redis):
    """
    清理孤儿 refresh session
    
    孤儿 refresh session 的特征：
    - refresh session 存在
    - 但关联的 access session 不存在（已过期或被删除）
    - 且 refresh session 创建时间超过 access token 的有效期（30分钟）
    
    这种情况通常发生在：
    - 用户使用 sessionStorage（不勾选"记住我"）
    - 用户关闭标签页，前端 token 被清除
    - 但后端 session 仍在 Redis 中
    
    Args:
        redis_client: Redis 客户端（由调用方管理生命周期）
    """
    session_store = SessionStore(redis_client)
    
    cleaned_count = 0
    checked_count = 0
    
    try:
        # 获取所有 refresh session 的 key
        pattern = f"{session_store.REFRESH_SESSION_PREFIX}*"
        cursor = 0
        
        while True:
            # 使用 SCAN 遍历（不阻塞 Redis）
            cursor, keys = await redis_client.scan(
                cursor=cursor,
                match=pattern,
                count=100
            )
            
            for key in keys:
                checked_count += 1
                
                # 读取 refresh session
                session_data = await redis_client.get(key)
                if not session_data:
                    continue
                
                import json
                try:
                    session = json.loads(session_data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid session data: {key}")
                    continue
                
                # 检查关联的 access session 是否存在
                access_session_id = session.get("access_session_id")
                if not access_session_id:
                    continue
                
                access_key = f"{session_store.ACCESS_SESSION_PREFIX}{access_session_id}"
                access_exists = await redis_client.exists(access_key)
                
                # 如果 access session 不存在
                if not access_exists:
                    # 检查 refresh session 的创建时间
                    created_at_str = session.get("created_at")
                    if created_at_str:
                        try:
                            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                            now = datetime.now(timezone.utc)
                            age = (now - created_at).total_seconds()
                            
                            # 如果创建时间超过 access token 有效期（30分钟 + 5分钟缓冲）
                            if age > 35 * 60:
                                # 这是一个孤儿 session，删除它
                                session_id = key.replace(session_store.REFRESH_SESSION_PREFIX, "")
                                user_id = session.get("user_id")
                                
                                # 删除 refresh session
                                await redis_client.delete(key)
                                
                                # 从用户 session 列表中移除
                                if user_id:
                                    user_sessions_key = f"{session_store.USER_SESSIONS_PREFIX}{user_id}"
                                    await cast(Awaitable[Any], redis_client.srem(user_sessions_key, session_id))
                                
                                cleaned_count += 1
                                logger.info(
                                    f"Cleaned orphan refresh session: "
                                    f"session_id={session_id}, "
                                    f"user_id={user_id}, "
                                    f"age={age/60:.1f} minutes"
                                )
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Invalid created_at: {created_at_str}, error: {e}")
            
            # 如果 cursor 为 0，说明遍历完成
            if cursor == 0:
                break
        
        logger.info(
            f"Session cleanup completed: "
            f"checked={checked_count}, "
            f"cleaned={cleaned_count}"
        )
        
        return {
            "checked": checked_count,
            "cleaned": cleaned_count
        }
        
    except Exception as e:
        logger.error(f"Session cleanup failed: {e}", exc_info=True)
        raise


async def cleanup_expired_revoked_tokens(redis_client: Redis):
    """
    清理已过期的撤销 token 记录
    
    虽然这些记录有 TTL 会自动过期，但主动清理可以：
    - 减少 Redis 内存占用
    - 提高 SCAN 性能
    
    Args:
        redis_client: Redis 客户端（由调用方管理生命周期）
    """
    
    cleaned_count = 0
    checked_count = 0
    
    try:
        # 获取所有撤销 token 的 key
        pattern = "auth:refresh:revoked:*"
        cursor = 0
        
        while True:
            cursor, keys = await redis_client.scan(
                cursor=cursor,
                match=pattern,
                count=100
            )
            
            for key in keys:
                checked_count += 1
                
                # 检查 TTL
                ttl = await redis_client.ttl(key)
                
                # 如果 TTL 小于 0（已过期但未删除）或小于 1 小时
                if ttl < 0 or ttl < 3600:
                    await redis_client.delete(key)
                    cleaned_count += 1
            
            if cursor == 0:
                break
        
        logger.info(
            f"Revoked token cleanup completed: "
            f"checked={checked_count}, "
            f"cleaned={cleaned_count}"
        )
        
        return {
            "checked": checked_count,
            "cleaned": cleaned_count
        }
        
    except Exception as e:
        logger.error(f"Revoked token cleanup failed: {e}", exc_info=True)
        raise


async def run_cleanup_tasks(redis_client: Redis):
    """运行所有清理任务
    
    Args:
        redis_client: Redis 客户端（由调用方管理生命周期）
    """
    logger.info("Starting session cleanup tasks...")
    
    # 清理孤儿 refresh session
    result1 = await cleanup_orphan_refresh_sessions(redis_client)
    
    # 清理已过期的撤销 token
    result2 = await cleanup_expired_revoked_tokens(redis_client)
    
    logger.info("All cleanup tasks completed")
    
    return {
        "orphan_sessions": result1,
        "revoked_tokens": result2
    }


if __name__ == "__main__":
    # 测试运行
    async def _test_run():
        from core.database.session import create_task_redis_client, close_task_redis_client
        redis_client = create_task_redis_client()
        try:
            await run_cleanup_tasks(redis_client)
        finally:
            await close_task_redis_client(redis_client)
            
    asyncio.run(_test_run())
