"""
统一响应处理
自动将响应转换为 Refine 兼容格式
"""
from typing import Any, List, TypeVar, Generic, Callable
from functools import wraps
from pydantic import BaseModel
from fastapi import Response
from fastapi.responses import JSONResponse

T = TypeVar("T")


class RefineListResponse(BaseModel, Generic[T]):
    """Refine 列表响应格式"""
    data: List[T]
    total: int


class RefineSingleResponse(BaseModel, Generic[T]):
    """Refine 单个资源响应格式"""
    data: T


def refine_list_response(data: List[Any], total: int) -> dict:
    """
    构造 Refine 列表响应
    
    Args:
        data: 数据列表
        total: 总记录数
        
    Returns:
        {"data": [...], "total": 100}
    """
    return {"data": data, "total": total}


def refine_single_response(data: Any) -> dict:
    """
    构造 Refine 单个资源响应
    
    Args:
        data: 单个资源对象
        
    Returns:
        {"data": {...}}
    """
    return {"data": data}


def refine_delete_response(resource_id: Any) -> dict:
    """
    构造 Refine 删除响应
    
    Args:
        resource_id: 被删除资源的 ID
        
    Returns:
        {"data": {"id": "..."}}
    """
    return {"data": {"id": str(resource_id)}}


def auto_refine_response(func: Callable) -> Callable:
    """
    装饰器：自动将返回值转换为 Refine 格式
    
    使用方式：
    
    @router.get("/")
    @auto_refine_response
    async def list_users(...) -> tuple[List[User], int]:
        users, total = await service.list_users(...)
        return users, total  # 自动转换为 {"data": [...], "total": 100}
    
    @router.get("/{id}")
    @auto_refine_response
    async def get_user(...) -> User:
        user = await service.get_user(...)
        return user  # 自动转换为 {"data": {...}}
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        
        # 如果返回的是元组 (data, total)，说明是列表响应
        if isinstance(result, tuple) and len(result) == 2:
            data, total = result
            return refine_list_response(data, total)
        
        # 如果返回的是列表，但没有 total，抛出错误提示
        if isinstance(result, list):
            raise ValueError(
                "列表响应必须返回 (data, total) 元组。"
                "例如：return users, total"
            )
        
        # 如果返回的是字典且已经包含 data 字段，直接返回
        if isinstance(result, dict) and "data" in result:
            return result
        
        # 其他情况，包装为单个资源响应
        return refine_single_response(result)
    
    return wrapper


class RefineResponseMiddleware:
    """
    响应中间件：自动处理 Refine 响应格式
    
    可以在 FastAPI 应用中全局启用，自动转换所有响应
    """
    
    @staticmethod
    def process_response(response_data: Any) -> dict:
        """处理响应数据"""
        # 如果已经是标准格式，直接返回
        if isinstance(response_data, dict):
            if "data" in response_data or "message" in response_data or "detail" in response_data:
                return response_data
        
        # 如果是元组 (data, total)
        if isinstance(response_data, tuple) and len(response_data) == 2:
            data, total = response_data
            return refine_list_response(data, total)
        
        # 如果是单个对象
        return refine_single_response(response_data)


# ============================================================================
# 统一异常响应格式（新增）
# ============================================================================

from typing import Optional


class StandardResponse(BaseModel):
    """
    统一响应格式
    
    用于全局异常处理器返回标准化的错误响应
    
    格式：
    {
        "code": 422,
        "message": "参数校验失败",
        "data": null,
        "details": [...]  # 可选
    }
    """
    code: int
    message: str
    data: Any = None
    details: Optional[List[Any]] = None

    @classmethod
    def success(
        cls,
        data: Any = None,
        message: str = "操作成功",
        code: int = 200
    ) -> "StandardResponse":
        """
        构建成功响应
        
        Args:
            data: 业务数据
            message: 成功消息
            code: 业务状态码（默认 200）
            
        Returns:
            StandardResponse 实例
        """
        return cls(
            code=code,
            message=message,
            data=data
        )

    @classmethod
    def error(
        cls,
        message: str,
        code: int = 500,
        details: Optional[List[Any]] = None
    ) -> "StandardResponse":
        """
        构建错误响应
        
        Args:
            message: 错误消息
            code: 业务状态码（默认 500）
            details: 详细错误信息（可选）
            
        Returns:
            StandardResponse 实例
        """
        return cls(
            code=code,
            message=message,
            data=None,
            details=details
        )

    def to_json_response(self, status_code: int = 200) -> JSONResponse:
        """
        转换为 FastAPI JSONResponse
        
        Args:
            status_code: HTTP 状态码
            
        Returns:
            JSONResponse 对象
        """
        return JSONResponse(
            content=self.model_dump(exclude_none=True),
            status_code=status_code
        )


class ResponseBuilder:
    """
    响应构建器
    
    负责将异常转换为统一响应格式
    """
    
    # 状态码映射表（HTTP 状态码 -> (业务状态码, 默认消息)）
    CODE_MAPPING = {
        200: (200, "操作成功"),
        201: (201, "创建成功"),
        400: (400, "请求参数错误"),
        401: (401, "未授权访问"),
        403: (403, "权限不足"),
        404: (404, "资源不存在"),
        409: (409, "资源冲突"),
        422: (422, "参数校验失败"),
        429: (429, "请求过于频繁"),
        500: (500, "服务器内部错误"),
    }

    @classmethod
    def build_success(
        cls,
        data: Any = None,
        message: str = "操作成功",
        http_status: int = 200
    ) -> dict:
        """
        构建成功响应
        
        Args:
            data: 业务数据
            message: 成功消息
            http_status: HTTP 状态码
            
        Returns:
            标准响应字典
        """
        # 从映射表获取业务状态码
        code, default_message = cls.CODE_MAPPING.get(http_status, (200, "操作成功"))
        
        # 构建标准响应
        response = StandardResponse.success(
            data=data,
            message=message,
            code=code
        )
        
        # 返回字典（FastAPI 会自动转换为 JSON）
        return response.model_dump(exclude_none=True)

    @classmethod
    def build_error(
        cls,
        message: str,
        http_status: int = 500,
        details: Optional[List[Any]] = None
    ) -> JSONResponse:
        """
        构建错误响应
        
        Args:
            message: 错误消息
            http_status: HTTP 状态码
            details: 详细错误信息（可选）
            
        Returns:
            JSONResponse 对象
        """
        # 从映射表获取业务状态码和默认消息
        code, default_message = cls.CODE_MAPPING.get(http_status, (500, "服务器内部错误"))
        
        # 构建标准响应
        response = StandardResponse.error(
            message=message,
            code=code,
            details=details
        )
        
        # 转换为 JSONResponse
        return response.to_json_response(http_status)
