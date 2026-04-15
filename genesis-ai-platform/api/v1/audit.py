"""
审计日志 API
提供统一审计日志的查询接口（包括权限审计、业务审计等）
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
from datetime import datetime

from core.database import get_async_session
from core.security.auth import get_current_user
from core.response import ResponseBuilder
from services.permission_service import PermissionService
from models.user import User
from schemas.common import PaginatedResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.post("/permission-logs/list")
async def list_permission_audit_logs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    operator_id: Optional[UUID] = Query(None, description="操作人ID"),
    target_type: Optional[str] = Query(None, description="目标类型"),
    target_id: Optional[UUID] = Query(None, description="目标对象ID"),
    action: Optional[str] = Query(None, description="操作类型"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    查询审计日志（统一的 audit_logs 表）
    
    支持查询：
    - 权限审计日志（assign_role, revoke_role, assign_permission, revoke_permission）
    - 业务审计日志（create_kb, delete_doc, share_kb 等）
    
    需要权限：audit:read 或 admin
    """
    service = PermissionService(session)
    
    logs, total = await service.get_audit_logs(
        tenant_id=current_user.tenant_id,
        operator_id=operator_id,
        target_type=target_type,
        target_id=target_id,
        action=action,
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        page=page,
        page_size=page_size
    )
    
    # 转换为字典格式
    log_list = []
    for log in logs:
        log_dict = {
            "id": str(log.id),
            "action": log.action,
            "operator_id": str(log.user_id),  # user_id 对应 operator_id
            "target_type": log.target_type,
            "target_id": str(log.target_id) if log.target_id else None,
            "created_at": log.created_at.isoformat(),
            "ip_address": log.ip_address,
        }
        
        # 从 detail 中提取额外信息
        if log.detail:
            log_dict["operator_name"] = log.detail.get("operator_name")
            log_dict["target_name"] = log.detail.get("target_name")
            log_dict["success"] = log.detail.get("success", True)
            log_dict["error_message"] = log.detail.get("error_message")
            log_dict["user_agent"] = log.detail.get("user_agent")
            log_dict["details"] = log.detail  # 完整的 detail 数据
        else:
            log_dict["operator_name"] = None
            log_dict["target_name"] = None
            log_dict["success"] = True
            log_dict["error_message"] = None
            log_dict["user_agent"] = None
            log_dict["details"] = None
        
        log_list.append(log_dict)
    
    return ResponseBuilder.build_success(
        data={
            "data": log_list,
            "total": total
        },
        message="查询成功"
    )


@router.get("/permission-logs/{log_id}")
async def get_permission_audit_log(
    log_id: int,  # 🔥 改为 int 类型（BIGSERIAL）
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    获取审计日志详情
    
    需要权限：audit:read 或 admin
    """
    from sqlalchemy import select
    from models.audit_log import AuditLog
    
    stmt = select(AuditLog).where(
        AuditLog.id == log_id,
        AuditLog.tenant_id == current_user.tenant_id
    )
    
    result = await session.execute(stmt)
    log = result.scalar_one_or_none()
    
    if not log:
        return ResponseBuilder.build_error(
            message="审计日志不存在",
            http_status=404
        )
    
    log_dict = {
        "id": str(log.id),
        "action": log.action,
        "operator_id": str(log.user_id),  # user_id 对应 operator_id
        "target_type": log.target_type,
        "target_id": str(log.target_id) if log.target_id else None,
        "created_at": log.created_at.isoformat(),
        "ip_address": log.ip_address,
    }
    
    # 从 detail 中提取额外信息
    if log.detail:
        log_dict["operator_name"] = log.detail.get("operator_name")
        log_dict["target_name"] = log.detail.get("target_name")
        log_dict["success"] = log.detail.get("success", True)
        log_dict["error_message"] = log.detail.get("error_message")
        log_dict["user_agent"] = log.detail.get("user_agent")
        log_dict["details"] = log.detail  # 完整的 detail 数据
    else:
        log_dict["operator_name"] = None
        log_dict["target_name"] = None
        log_dict["success"] = True
        log_dict["error_message"] = None
        log_dict["user_agent"] = None
        log_dict["details"] = None
    
    return ResponseBuilder.build_success(
        data=log_dict,
        message="查询成功"
    )
