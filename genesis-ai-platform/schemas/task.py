"""
异步任务 Schema 定义
"""
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class TaskBase(BaseModel):
    """任务基础字段"""
    task_type: str = Field(..., description="任务类型")
    status: str = Field("pending", description="任务状态")
    target_id: Optional[UUID] = Field(None, description="关联目标ID")
    target_type: Optional[str] = Field(None, description="目标类型")
    progress: int = Field(0, ge=0, le=100, description="进度")
    payload: Optional[Dict[str, Any]] = Field(None, description="输入参数")


class TaskCreate(TaskBase):
    """创建任务"""
    id: UUID = Field(..., description="任务ID (外部生成)")
    tenant_id: UUID
    owner_id: UUID


class TaskUpdate(BaseModel):
    """更新任务状态及进度"""
    status: Optional[str] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class TaskRead(TaskBase):
    """获取任务详情"""
    id: UUID
    tenant_id: UUID
    owner_id: UUID
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # 审计字段
    created_by_id: Optional[UUID] = None
    created_by_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TaskListRequest(BaseModel):
    """任务列表查询"""
    status: Optional[str] = None
    task_type: Optional[str] = None
    target_id: Optional[UUID] = None
    page: int = 1
    page_size: int = 20
