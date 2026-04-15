"""
异步任务服务
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime

from core.base_service import BaseService
from models.task import Task
from models.user import User
from schemas.task import TaskCreate, TaskUpdate


class TaskService(BaseService[Task, TaskCreate, TaskUpdate]):
    """
    异步任务管理服务
    """
    
    async def start_task(
        self, 
        task_id: UUID, 
        current_user: User, 
        session: Optional[AsyncSession] = None
    ) -> Optional[Task]:
        """
        标记任务开始执行，记录开始时间
        """
        use_session = session or self.db
        stmt = update(Task).where(
            Task.id == task_id,
            Task.tenant_id == current_user.tenant_id
        ).values(
            status="running",
            started_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        await use_session.execute(stmt)
        await use_session.commit()
        return await self.get(task_id, current_user, use_session)

    async def complete_task(
        self, 
        task_id: UUID, 
        result: Dict[str, Any], 
        current_user: User,
        session: Optional[AsyncSession] = None
    ) -> Optional[Task]:
        """
        标记任务完成，记录结果和结束时间
        """
        use_session = session or self.db
        stmt = update(Task).where(
            Task.id == task_id,
            Task.tenant_id == current_user.tenant_id
        ).values(
            status="success",
            progress=100,
            result=result,
            ended_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        await use_session.execute(stmt)
        await use_session.commit()
        return await self.get(task_id, current_user, use_session)

    async def fail_task(
        self, 
        task_id: UUID, 
        error_msg: str, 
        current_user: User,
        session: Optional[AsyncSession] = None
    ) -> Optional[Task]:
        """
        标记任务失败，记录错误信息
        """
        use_session = session or self.db
        stmt = update(Task).where(
            Task.id == task_id,
            Task.tenant_id == current_user.tenant_id
        ).values(
            status="failed",
            error_message=error_msg,
            ended_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        await use_session.execute(stmt)
        await use_session.commit()
        return await self.get(task_id, current_user, use_session)
