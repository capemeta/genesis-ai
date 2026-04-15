"""
知识库服务
"""
from typing import Optional, List, Tuple, Dict, Any
from uuid import UUID
import logging
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from core.base_service import BaseService
from models.knowledge_base import KnowledgeBase
from models.knowledge_base_document import KnowledgeBaseDocument
from models.user import User
from schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate

logger = logging.getLogger(__name__)


def _is_duplicate_name_error(exc: IntegrityError) -> bool:
    """判断是否为 (tenant_id, name) 唯一约束冲突"""
    msg = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
    return "tenant_id_name" in msg or "knowledge_bases_tenant_id_name" in msg


def _normalize_table_columns(columns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """提取定稿后需要锁定的字段结构信息。"""
    normalized: List[Dict[str, Any]] = []
    for column in columns or []:
        name = str((column or {}).get("name") or "").strip()
        if not name:
            continue
        normalized.append({
            "name": name,
            "nullable": bool((column or {}).get("nullable", True)),
        })
    return normalized


def _validate_table_columns_basic(columns: List[Dict[str, Any]]) -> None:
    """校验表格字段的基础合法性。"""
    seen_names: set[str] = set()
    for index, column in enumerate(columns or []):
        name = str((column or {}).get("name") or "").strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"第 {index + 1} 个字段名称不能为空",
            )
        if name in seen_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"字段名称不能重复：{name}",
            )
        seen_names.add(name)


def _is_table_schema_confirmed(retrieval_config: Dict[str, Any]) -> bool:
    """判断表格结构是否已定稿。"""
    table_cfg = dict((retrieval_config or {}).get("table") or {})
    return str(table_cfg.get("schema_status") or "").strip().lower() == "confirmed"


def _validate_confirmed_table_schema_update(
    existing_columns: List[Dict[str, Any]],
    next_columns: List[Dict[str, Any]],
) -> None:
    """校验已定稿结构允许的变更范围。"""
    if len(next_columns) < len(existing_columns):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="表格结构已定稿，不允许删除既有字段",
        )

    existing_names = [str((column or {}).get("name") or "").strip() for column in existing_columns]
    next_names = [str((column or {}).get("name") or "").strip() for column in next_columns]

    if len(set(next_names)) != len(next_names):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="字段名称不能重复",
        )

    for index, existing_column in enumerate(existing_columns):
        next_column = next_columns[index] if index < len(next_columns) else {}
        existing_name = str((existing_column or {}).get("name") or "").strip()
        next_name = str((next_column or {}).get("name") or "").strip()
        if existing_name != next_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="表格结构已定稿，不允许修改既有字段名称或顺序",
            )

        existing_nullable = bool((existing_column or {}).get("nullable", True))
        next_nullable = bool((next_column or {}).get("nullable", True))
        if existing_nullable and not next_nullable:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="表格结构已定稿后，不允许把可空字段改成必填字段",
            )

    appended_columns = next_columns[len(existing_columns):]
    for column in appended_columns:
        column_name = str((column or {}).get("name") or "").strip()
        if not column_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="新增字段名称不能为空",
            )
        if not bool((column or {}).get("nullable", True)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="表格结构已定稿后，新增字段必须允许为空",
            )


class KnowledgeBaseService(BaseService[KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseUpdate]):
    """
    知识库服务类
    
    继承自 BaseService，自动获得基础 CRUD 功能：
    - list_resources (带租户隔离和权限控制)
    - get_by_id
    - create (自动填充审计字段)
    - update
    - delete
    """
    
    def __init__(self, db, model=KnowledgeBase):
        super().__init__(model=model, db=db, resource_name="knowledge_base")

    async def create(
        self,
        data: KnowledgeBaseCreate,
        current_user: Optional[User] = None
    ) -> KnowledgeBase:
        """创建知识库，同名冲突时返回友好提示"""
        try:
            return await super().create(data, current_user)
        except IntegrityError as e:
            await self.db.rollback()
            if _is_duplicate_name_error(e):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="该租户下已存在同名知识库，请使用其他名称",
                ) from e
            raise

    async def update(
        self,
        resource_id: UUID,
        data: KnowledgeBaseUpdate,
        current_user: Optional[User] = None
    ) -> KnowledgeBase:
        """更新知识库，改名与其他知识库同名时返回友好提示"""
        try:
            if data.retrieval_config is not None:
                tenant_id = current_user.tenant_id if current_user else None
                user_id = current_user.id if current_user else None
                existing = await self.get_by_id(
                    resource_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
                if existing and existing.type == "table":
                    existing_retrieval = dict(existing.retrieval_config or {})
                    next_retrieval = dict(data.retrieval_config or {})
                    existing_table = dict(existing_retrieval.get("table") or {})
                    next_table = dict(next_retrieval.get("table") or {})
                    next_columns_raw = list(dict(next_table.get("schema") or {}).get("columns") or [])
                    _validate_table_columns_basic(next_columns_raw)
                    attached_doc_count = int(
                        (
                            await self.db.scalar(
                                select(func.count()).select_from(KnowledgeBaseDocument).where(
                                    KnowledgeBaseDocument.kb_id == resource_id,
                                    KnowledgeBaseDocument.tenant_id == tenant_id,
                                )
                            )
                        )
                        or 0
                    )
                    logger.info(
                        "[TABLE_SCHEMA_SAVE] 更新表格结构 kb=%s existing_status=%s next_status=%s attached_doc_count=%s existing_columns=%s next_columns=%s",
                        resource_id,
                        existing_table.get("schema_status"),
                        next_table.get("schema_status"),
                        attached_doc_count,
                        [str((item or {}).get("name") or "") for item in list(dict(existing_table.get("schema") or {}).get("columns") or [])],
                        [str((item or {}).get("name") or "") for item in next_columns_raw],
                    )
                    if _is_table_schema_confirmed(existing_retrieval) and attached_doc_count > 0:
                        existing_columns = _normalize_table_columns(
                            list(dict(existing_table.get("schema") or {}).get("columns") or [])
                        )
                        next_columns = _normalize_table_columns(
                            next_columns_raw
                        )
    
                        _validate_confirmed_table_schema_update(existing_columns, next_columns)
    
                        if dict(next_table.get("field_map") or {}):
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="表格结构已定稿，不允许再配置 Excel 字段映射",
                            )
    
                        if next_table.get("table_header_row") not in (None, ""):
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="表格知识库固定要求第 1 行为表头，不允许单独修改表头行",
                            )
    
                        if next_table.get("table_data_start_row") not in (None, ""):
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="表格知识库固定要求第 2 行起为数据，不允许单独修改数据起始行",
                            )
    
                        if str(next_table.get("schema_status") or "confirmed").strip().lower() != "confirmed":
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="表格结构已定稿后不能回退为草稿状态",
                            )
    
            # 获取未设置的字段（用于判断哪些字段需要被清空）
            unset_fields = data.model_fields_set
                
            # 调用父类更新逻辑
            updated_kb = await super().update(resource_id, data, current_user)
                
            # 处理模型字段的清空：当前端显式传递 None 时，应该清空数据库中的旧值
            # 但由于 base_service 使用 exclude_unset=True，None 值不会被更新
            # 所以这里需要手动处理
            if current_user and hasattr(current_user, "tenant_id"):
                tenant_id = current_user.tenant_id
            else:
                tenant_id = None
                
            # 模型相关字段列表
            model_fields = {
                "embedding_model": "embedding_model_id",
                "index_model": "index_model_id",
                "vision_model": "vision_model_id",
            }
                
            need_update = False
            for model_field, model_id_field in model_fields.items():
                # 如果前端显式传递了该字段（无论是具体值还是 None），则需要检查
                if model_field in unset_fields or model_id_field in unset_fields:
                    # 获取前端传递的值（如果传递了 None，应该清空）
                    model_value = getattr(data, model_field, None)
                    model_id_value = getattr(data, model_id_field, None)
                        
                    if model_value is None or model_id_value is None:
                        # 前端显式要求清空，设置字段为 None
                        current_model_value = getattr(updated_kb, model_field, None)
                        current_model_id_value = getattr(updated_kb, model_id_field, None)
                            
                        if (model_value is None and current_model_value is not None) or \
                           (model_id_value is None and current_model_id_value is not None):
                            setattr(updated_kb, model_field, None)
                            setattr(updated_kb, model_id_field, None)
                            need_update = True
                            logger.info(
                                "[MODEL_CLEAR] 知识库 %s 的 %s 相关字段已清空（前端选择使用租户默认模型）",
                                resource_id,
                                model_field,
                            )
                
            if need_update:
                await self.db.commit()
                await self.db.refresh(updated_kb)
                
            return updated_kb
        except IntegrityError as e:
            await self.db.rollback()
            if _is_duplicate_name_error(e):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="该租户下已存在同名知识库，请先使用其他名称",
                ) from e
            raise

    async def get_stats(self, tenant_id: UUID) -> Dict[str, Any]:
        """
        获取租户下知识库的统计信息 (示例自定义方法)
        """
        stmt = select(func.count(KnowledgeBase.id)).where(
            KnowledgeBase.tenant_id == tenant_id
        )
        count = await self.db.scalar(stmt) or 0
        return {"total_count": count}
