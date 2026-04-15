"""
健康检查 API
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from .deps import get_db
from core.response import ResponseBuilder

router = APIRouter()


@router.get("")
async def health_check():
    """基础健康检查"""
    return ResponseBuilder.build_success(
        data={
            "status": "healthy",
            "service": "Genesis AI Platform",
            "version": "0.1.0"
        },
        message="服务运行正常"
    )


@router.get("/db")
async def health_check_db(db: AsyncSession = Depends(get_db)):
    """数据库健康检查"""
    try:
        # 执行简单查询测试数据库连接
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        return ResponseBuilder.build_success(
            data={
                "status": "healthy",
                "database": "connected"
            },
            message="数据库连接正常"
        )
    except Exception as e:
        return ResponseBuilder.build_success(
            data={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e)
            },
            message="数据库连接异常",
            http_status=503
        )
