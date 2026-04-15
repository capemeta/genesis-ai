"""
通用 Schema 定义

包含分页、过滤、排序等通用基类
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, TypeVar, Generic
from enum import Enum
from uuid import UUID


class FilterOperator(str, Enum):
    """过滤操作符"""
    EQ = "eq"              # 等于
    NE = "ne"              # 不等于
    GT = "gt"              # 大于
    GTE = "gte"            # 大于等于
    LT = "lt"              # 小于
    LTE = "lte"            # 小于等于
    LIKE = "like"          # 模糊匹配
    IN = "in"              # 在列表中
    NOT_IN = "not_in"      # 不在列表中
    IS_NULL = "is_null"    # 为空
    IS_NOT_NULL = "is_not_null"  # 不为空


class AdvancedFilter(BaseModel):
    """高级过滤条件"""
    field: str = Field(..., description="字段名")
    op: FilterOperator = Field(..., description="操作符")
    value: Optional[Any] = Field(None, description="过滤值")


class SortOrder(str, Enum):
    """排序方向"""
    ASC = "asc"
    DESC = "desc"


class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=200, description="每页数量")


class SortParams(BaseModel):
    """排序参数"""
    sort_by: Optional[str] = Field("created_at", description="排序字段")
    sort_order: SortOrder = Field(SortOrder.DESC, description="排序方向")


class FilterParams(BaseModel):
    """过滤参数（三种模式）"""
    search: Optional[str] = Field(None, description="简单搜索（模糊匹配）")
    filters: Optional[Dict[str, Any]] = Field(None, description="精确过滤（字典格式）")
    advanced_filters: Optional[List[AdvancedFilter]] = Field(None, description="高级过滤（支持操作符）")


class SelectionParams(BaseModel):
    """Refine 标准的分页 and 排序参数"""
    model_config = ConfigDict(populate_by_name=True)
    
    start: Optional[int] = Field(None, alias="_start", description="起始位置（Refine 标准）")
    end: Optional[int] = Field(None, alias="_end", description="结束位置（Refine 标准）")
    sort: Optional[str] = Field(None, alias="_sort", description="排序字段（Refine 标准）")
    order: Optional[str] = Field(None, alias="_order", description="排序方向：ASC/DESC（Refine 标准）")
    q: Optional[str] = Field(None, description="搜索关键词（Refine 标准）")


class ListRequest(PaginationParams, SortParams, FilterParams, SelectionParams):
    """
    列表请求基类（通用）
    
    包含分页、过滤、排序的完整参数，同时兼容内部标准和 Refine 标准
    """
    
    def get_page(self) -> int:
        """获取标准页码"""
        if self.start is not None and self.end is not None:
            size = self.get_page_size()
            return (self.start // size) + 1 if size > 0 else 1
        return self.page
    
    def get_page_size(self) -> int:
        """获取每页数量"""
        if self.start is not None and self.end is not None:
            return self.end - self.start
        return self.page_size
    
    def get_order_by(self) -> Optional[str]:
        """获取标准排序字符串"""
        # 优先使用 Refine 标准
        if self.sort and self.order:
            return f"{self.sort} {self.order.lower()}"
        # 其次使用内部标准
        if self.sort_by:
            return f"{self.sort_by} {self.sort_order.value if hasattr(self.sort_order, 'value') else self.sort_order}"
        return None
    
    def get_search(self) -> Optional[str]:
        """获取搜索关键词"""
        return self.search or self.q


class ItemIdRequest(BaseModel):
    """通用的 ID 请求（用于 get/delete/update）"""
    id: UUID = Field(..., description="资源 ID")


# 泛型类型变量
T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """
    分页响应基类（通用）
    
    使用示例：
    
    @router.post("/list", response_model=PaginatedResponse[TenantResponse])
    async def list_tenants(...):
        return {
            "data": [TenantResponse.model_validate(t) for t in tenants],
            "total": total
        }
    """
    data: List[T]
    total: int


class ResourceResponse(BaseModel, Generic[T]):
    """
    单个资源响应基类（通用）
    
    使用示例：
    
    @router.post("/get", response_model=ResourceResponse[TenantResponse])
    async def get_tenant(...):
        return {"data": TenantResponse.model_validate(tenant)}
    """
    data: T


class SuccessResponse(BaseModel):
    """操作成功响应"""
    message: str = Field(..., description="成功消息")


class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str = Field(..., description="错误详情")
