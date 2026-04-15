"""
术语与同义词服务

说明：
- API 层保持轻量，本文件承载核心业务逻辑。
- 包含术语管理、同义词主从管理、查询改写预览。
"""
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, or_, select

from core.base_service import BaseService
from models.kb_glossary import KBGlossary
from models.kb_synonym import KBSynonym
from models.kb_synonym_variant import KBSynonymVariant
from models.user import User
from schemas.dictionary import (
    KBGlossaryCreate,
    KBGlossaryUpdate,
    KBSynonymCreate,
    KBSynonymUpdate,
    KBSynonymVariantCreate,
    KBSynonymVariantUpdate,
    SynonymRewriteMatch,
    SynonymRewritePreviewResponse,
    SynonymVariantBatchItem,
    SynonymVariantBatchUpsertResponse,
)


def _normalize_text(value: str) -> str:
    """统一文本比较口径，避免空白造成重复规则。"""
    return " ".join((value or "").strip().split())


def _scope_conflict_expr(target_kb_id: Optional[UUID], model_kb_id_col):
    """
    生成作用域冲突表达式。

    规则：
    - 当前为知识库级：只与同 kb_id 冲突；
    - 当前为租户级：只与 kb_id IS NULL 冲突。
    """
    if target_kb_id is None:
        return model_kb_id_col.is_(None)
    return model_kb_id_col == target_kb_id


class KBGlossaryService(BaseService[KBGlossary, KBGlossaryCreate, KBGlossaryUpdate]):
    """专业术语服务（定义增强，不参与改写）"""

    async def _check_duplicate_term(
        self,
        term: str,
        tenant_id: UUID,
        kb_id: Optional[UUID],
        exclude_id: Optional[UUID] = None,
    ) -> None:
        """校验同作用域术语是否重复。"""
        normalized_term = _normalize_text(term)
        stmt = select(KBGlossary).where(
            KBGlossary.tenant_id == tenant_id,
            _scope_conflict_expr(kb_id, KBGlossary.kb_id),
            func.lower(func.trim(KBGlossary.term)) == normalized_term.lower(),
        )
        if exclude_id:
            stmt = stmt.where(KBGlossary.id != exclude_id)
        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="同一作用域下术语已存在",
            )

    async def create(
        self,
        data: KBGlossaryCreate | Dict[str, Any],
        current_user: Optional[User] = None,
    ) -> KBGlossary:
        """创建术语并做作用域重复校验。"""
        payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else dict(data)
        term = _normalize_text(str(payload.get("term") or ""))
        definition = str(payload.get("definition") or "").strip()
        if not term:
            raise HTTPException(status_code=400, detail="术语名称不能为空")
        if not definition:
            raise HTTPException(status_code=400, detail="术语定义不能为空")

        payload["term"] = term
        payload["definition"] = definition

        if not current_user:
            raise HTTPException(status_code=401, detail="当前用户不存在")
        await self._check_duplicate_term(
            term=term,
            tenant_id=current_user.tenant_id,
            kb_id=payload.get("kb_id"),
        )
        return await super().create(payload, current_user)

    async def update(
        self,
        resource_id: UUID,
        data: KBGlossaryUpdate | Dict[str, Any],
        current_user: Optional[User] = None,
    ) -> KBGlossary:
        """更新术语并做作用域重复校验。"""
        if not current_user:
            raise HTTPException(status_code=401, detail="当前用户不存在")

        payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else dict(data)
        current = await self.get_by_id(resource_id, tenant_id=current_user.tenant_id, user_id=current_user.id)

        next_kb_id = payload.get("kb_id", current.kb_id)
        next_term = _normalize_text(str(payload.get("term", current.term) or ""))
        next_definition = str(payload.get("definition", current.definition) or "").strip()
        if not next_term:
            raise HTTPException(status_code=400, detail="术语名称不能为空")
        if not next_definition:
            raise HTTPException(status_code=400, detail="术语定义不能为空")

        payload["term"] = next_term
        payload["definition"] = next_definition
        await self._check_duplicate_term(
            term=next_term,
            tenant_id=current_user.tenant_id,
            kb_id=next_kb_id,
            exclude_id=resource_id,
        )
        return await super().update(resource_id, payload, current_user)


class KBSynonymService(BaseService[KBSynonym, KBSynonymCreate, KBSynonymUpdate]):
    """同义词主表服务（标准词管理）"""

    async def _check_duplicate_professional_term(
        self,
        professional_term: str,
        tenant_id: UUID,
        kb_id: Optional[UUID],
        exclude_id: Optional[UUID] = None,
    ) -> None:
        """校验同作用域标准词是否重复。"""
        normalized_term = _normalize_text(professional_term)
        stmt = select(KBSynonym).where(
            KBSynonym.tenant_id == tenant_id,
            _scope_conflict_expr(kb_id, KBSynonym.kb_id),
            func.lower(func.trim(KBSynonym.professional_term)) == normalized_term.lower(),
        )
        if exclude_id:
            stmt = stmt.where(KBSynonym.id != exclude_id)
        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="同一作用域下标准词已存在",
            )

    async def create(
        self,
        data: KBSynonymCreate | Dict[str, Any],
        current_user: Optional[User] = None,
    ) -> KBSynonym:
        """创建标准词并做作用域重复校验。"""
        payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else dict(data)
        professional_term = _normalize_text(str(payload.get("professional_term") or ""))
        if not professional_term:
            raise HTTPException(status_code=400, detail="标准词不能为空")
        payload["professional_term"] = professional_term

        if not current_user:
            raise HTTPException(status_code=401, detail="当前用户不存在")
        await self._check_duplicate_professional_term(
            professional_term=professional_term,
            tenant_id=current_user.tenant_id,
            kb_id=payload.get("kb_id"),
        )
        return await super().create(payload, current_user)

    async def update(
        self,
        resource_id: UUID,
        data: KBSynonymUpdate | Dict[str, Any],
        current_user: Optional[User] = None,
    ) -> KBSynonym:
        """更新标准词并做作用域重复校验。"""
        if not current_user:
            raise HTTPException(status_code=401, detail="当前用户不存在")

        payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else dict(data)
        current = await self.get_by_id(resource_id, tenant_id=current_user.tenant_id, user_id=current_user.id)

        next_kb_id = payload.get("kb_id", current.kb_id)
        next_term = _normalize_text(str(payload.get("professional_term", current.professional_term) or ""))
        if not next_term:
            raise HTTPException(status_code=400, detail="标准词不能为空")

        payload["professional_term"] = next_term
        await self._check_duplicate_professional_term(
            professional_term=next_term,
            tenant_id=current_user.tenant_id,
            kb_id=next_kb_id,
            exclude_id=resource_id,
        )
        return await super().update(resource_id, payload, current_user)

    async def rewrite_query_preview(
        self,
        tenant_id: UUID,
        query: str,
        kb_id: Optional[UUID] = None,
    ) -> SynonymRewritePreviewResponse:
        """
        同义词改写预览。

        规则：
        - 优先知识库级，再回退租户级。
        - 同层按 priority ASC、updated_at DESC。
        - 最长口语优先匹配，避免短词抢占。
        """
        raw_query = str(query or "").strip()
        if not raw_query:
            raise HTTPException(status_code=400, detail="query 不能为空")

        stmt = (
            select(KBSynonymVariant, KBSynonym)
            .join(KBSynonym, KBSynonym.id == KBSynonymVariant.synonym_id)
            .where(
                KBSynonym.tenant_id == tenant_id,
                KBSynonym.is_active.is_(True),
                KBSynonymVariant.is_active.is_(True),
                or_(
                    KBSynonym.kb_id == kb_id,
                    KBSynonym.kb_id.is_(None),
                ) if kb_id else KBSynonym.kb_id.is_(None),
            )
            .order_by(
                case((KBSynonym.kb_id == kb_id, 0), else_=1) if kb_id else case((KBSynonym.kb_id.is_(None), 0), else_=1),
                KBSynonym.priority.asc(),
                KBSynonym.updated_at.desc(),
                KBSynonymVariant.updated_at.desc(),
            )
        )
        rows = (await self.db.execute(stmt)).all()

        # 按优先级构建口语->标准词映射，后续同口语忽略
        mapping: Dict[str, Dict[str, Any]] = {}
        for variant, synonym in rows:
            key = _normalize_text(variant.user_term)
            if not key or key in mapping:
                continue
            mapping[key] = {
                "professional_term": synonym.professional_term,
                "synonym_id": synonym.id,
                "variant_id": variant.id,
                "scope": "kb" if synonym.kb_id is not None else "tenant",
            }

        if not mapping:
            return SynonymRewritePreviewResponse(
                raw_query=raw_query,
                rewritten_query=raw_query,
                matches=[],
            )

        # 最长词优先，避免短词覆盖长词
        sorted_terms = sorted(mapping.keys(), key=len, reverse=True)
        pattern = re.compile("|".join(re.escape(term) for term in sorted_terms))
        matched_rules: Dict[str, SynonymRewriteMatch] = {}

        def _replace(match: re.Match[str]) -> str:
            user_term = match.group(0)
            rule = mapping.get(user_term)
            if not rule:
                return user_term
            if user_term not in matched_rules:
                matched_rules[user_term] = SynonymRewriteMatch(
                    user_term=user_term,
                    professional_term=rule["professional_term"],
                    synonym_id=rule["synonym_id"],
                    variant_id=rule["variant_id"],
                    scope=rule["scope"],
                )
            return str(rule["professional_term"])

        rewritten_query = pattern.sub(_replace, raw_query)
        return SynonymRewritePreviewResponse(
            raw_query=raw_query,
            rewritten_query=rewritten_query,
            matches=list(matched_rules.values()),
        )


class KBSynonymVariantService(BaseService[KBSynonymVariant, KBSynonymVariantCreate, KBSynonymVariantUpdate]):
    """同义词口语子表服务（口语词管理）"""

    async def list_resources(
        self,
        tenant_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        advanced_filters: Optional[List[Dict[str, Any]]] = None,
        order_by: str = "created_at desc",
        user_id: Optional[UUID] = None,
        include_public: bool = True,
    ) -> Tuple[List[KBSynonymVariant], int]:
        """
        口语子表列表查询（按标准词租户隔离）。

        由于子表无 tenant_id 字段，这里必须通过 join 主表做租户过滤。
        """
        if tenant_id is None:
            return [], 0

        conditions = [KBSynonym.tenant_id == tenant_id]

        if search:
            conditions.append(KBSynonymVariant.user_term.ilike(f"%{search}%"))

        filters = filters or {}
        if "synonym_id" in filters and filters["synonym_id"]:
            conditions.append(KBSynonymVariant.synonym_id == filters["synonym_id"])
        if "is_active" in filters and filters["is_active"] is not None:
            conditions.append(KBSynonymVariant.is_active == bool(filters["is_active"]))

        count_stmt = (
            select(func.count())
            .select_from(KBSynonymVariant)
            .join(KBSynonym, KBSynonym.id == KBSynonymVariant.synonym_id)
            .where(and_(*conditions))
        )
        total = int((await self.db.scalar(count_stmt)) or 0)

        offset = (page - 1) * page_size
        stmt = (
            select(KBSynonymVariant)
            .join(KBSynonym, KBSynonym.id == KBSynonymVariant.synonym_id)
            .where(and_(*conditions))
            .offset(offset)
            .limit(page_size)
        )

        if order_by:
            parts = str(order_by).split()
            if len(parts) == 2 and hasattr(KBSynonymVariant, parts[0]):
                col = getattr(KBSynonymVariant, parts[0])
                stmt = stmt.order_by(col.desc() if parts[1].lower() == "desc" else col.asc())
            else:
                stmt = stmt.order_by(KBSynonymVariant.created_at.desc())
        else:
            stmt = stmt.order_by(KBSynonymVariant.created_at.desc())

        resources = (await self.db.execute(stmt)).scalars().all()
        return list(resources), total

    async def get_by_id(
        self,
        resource_id: UUID,
        tenant_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        check_permission: bool = True,
    ) -> KBSynonymVariant:
        """
        口语子表详情查询（按标准词租户隔离）。
        """
        stmt = (
            select(KBSynonymVariant)
            .join(KBSynonym, KBSynonym.id == KBSynonymVariant.synonym_id)
            .where(KBSynonymVariant.id == resource_id)
        )
        if tenant_id is not None:
            stmt = stmt.where(KBSynonym.tenant_id == tenant_id)

        resource = (await self.db.execute(stmt)).scalar_one_or_none()
        if not resource:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.resource_name.capitalize()} not found",
            )
        return resource

    async def _get_synonym_with_tenant_guard(
        self,
        synonym_id: UUID,
        tenant_id: UUID,
    ) -> KBSynonym:
        """按租户校验并获取标准词主记录。"""
        synonym = (
            await self.db.execute(
                select(KBSynonym).where(
                    KBSynonym.id == synonym_id,
                    KBSynonym.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not synonym:
            raise HTTPException(status_code=404, detail="关联的标准词不存在")
        return synonym

    async def _check_user_term_conflict(
        self,
        user_term: str,
        synonym: KBSynonym,
        exclude_variant_id: Optional[UUID] = None,
    ) -> None:
        """
        校验同作用域口语冲突。

        说明：
        - 同一作用域下，同一个口语建议只映射到一个标准词。
        - 这里做服务层治理，避免 API 逻辑过重。
        """
        normalized_user_term = _normalize_text(user_term)
        base_conditions = [
            KBSynonym.tenant_id == synonym.tenant_id,
            _scope_conflict_expr(synonym.kb_id, KBSynonym.kb_id),
            func.lower(func.trim(KBSynonymVariant.user_term)) == normalized_user_term.lower(),
        ]
        if exclude_variant_id:
            base_conditions.append(KBSynonymVariant.id != exclude_variant_id)

        conflict_stmt = (
            select(KBSynonymVariant.id, KBSynonym.id.label("synonym_id"), KBSynonym.professional_term)
            .join(KBSynonym, KBSynonym.id == KBSynonymVariant.synonym_id)
            .where(and_(*base_conditions))
            .limit(1)
        )
        conflict = (await self.db.execute(conflict_stmt)).first()
        if conflict and conflict.synonym_id != synonym.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"口语词“{normalized_user_term}”在当前作用域已映射到其他标准词：{conflict.professional_term}",
            )

    async def create(
        self,
        data: KBSynonymVariantCreate | Dict[str, Any],
        current_user: Optional[User] = None,
    ) -> KBSynonymVariant:
        """创建口语词并校验租户归属与冲突。"""
        if not current_user:
            raise HTTPException(status_code=401, detail="当前用户不存在")
        payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else dict(data)
        user_term = _normalize_text(str(payload.get("user_term") or ""))
        if not user_term:
            raise HTTPException(status_code=400, detail="用户口语词不能为空")

        synonym_id = payload.get("synonym_id")
        if not synonym_id:
            raise HTTPException(status_code=400, detail="synonym_id 不能为空")
        synonym = await self._get_synonym_with_tenant_guard(synonym_id=synonym_id, tenant_id=current_user.tenant_id)

        payload["user_term"] = user_term
        await self._check_user_term_conflict(user_term=user_term, synonym=synonym)
        return await super().create(payload, current_user)

    async def update(
        self,
        resource_id: UUID,
        data: KBSynonymVariantUpdate | Dict[str, Any],
        current_user: Optional[User] = None,
    ) -> KBSynonymVariant:
        """更新口语词并校验租户归属与冲突。"""
        if not current_user:
            raise HTTPException(status_code=401, detail="当前用户不存在")

        payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else dict(data)
        current = await self.get_by_id(resource_id, tenant_id=None, user_id=None, check_permission=False)
        current_synonym = await self._get_synonym_with_tenant_guard(
            synonym_id=current.synonym_id,
            tenant_id=current_user.tenant_id,
        )

        next_synonym_id = payload.get("synonym_id", current.synonym_id)
        next_synonym = await self._get_synonym_with_tenant_guard(
            synonym_id=next_synonym_id,
            tenant_id=current_user.tenant_id,
        )
        next_user_term = _normalize_text(str(payload.get("user_term", current.user_term) or ""))
        if not next_user_term:
            raise HTTPException(status_code=400, detail="用户口语词不能为空")

        # 说明性访问，确保当前记录归属租户
        _ = current_synonym

        payload["user_term"] = next_user_term
        payload["synonym_id"] = next_synonym_id
        await self._check_user_term_conflict(
            user_term=next_user_term,
            synonym=next_synonym,
            exclude_variant_id=resource_id,
        )
        return await super().update(resource_id, payload, current_user)

    async def delete(
        self,
        resource_id: UUID,
        current_user: Optional[User] = None,
        soft_delete: bool = True,
    ) -> None:
        """删除口语词前校验租户归属。"""
        if not current_user:
            raise HTTPException(status_code=401, detail="当前用户不存在")

        variant = await self.get_by_id(resource_id, tenant_id=None, user_id=None, check_permission=False)
        await self._get_synonym_with_tenant_guard(variant.synonym_id, current_user.tenant_id)
        await super().delete(resource_id=resource_id, current_user=current_user, soft_delete=soft_delete)

    async def batch_upsert_variants(
        self,
        *,
        synonym_id: UUID,
        variants: List[SynonymVariantBatchItem],
        replace: bool,
        current_user: User,
    ) -> SynonymVariantBatchUpsertResponse:
        """
        批量维护口语词（核心逻辑在 service 层）。

        规则：
        - 同请求内口语词去空白后不允许重复。
        - 同作用域下口语词不允许映射到其他标准词。
        - replace=True 时，以本次列表为准删除其余口语词。
        """
        synonym = await self._get_synonym_with_tenant_guard(
            synonym_id=synonym_id,
            tenant_id=current_user.tenant_id,
        )

        normalized_items: List[Dict[str, Any]] = []
        seen_terms: set[str] = set()
        for item in variants:
            normalized_user_term = _normalize_text(item.user_term)
            if not normalized_user_term:
                raise HTTPException(status_code=400, detail="用户口语词不能为空")
            if normalized_user_term.lower() in seen_terms:
                raise HTTPException(status_code=400, detail=f"批量请求中存在重复口语词：{normalized_user_term}")
            seen_terms.add(normalized_user_term.lower())
            normalized_items.append(
                {
                    "user_term": normalized_user_term,
                    "is_active": bool(item.is_active),
                    "description": item.description,
                }
            )

        # 预先检测跨标准词冲突，避免部分写入
        if normalized_items:
            lowered_terms = [str(item["user_term"]).lower() for item in normalized_items]
            conflict_stmt = (
                select(
                    KBSynonymVariant.user_term,
                    KBSynonym.professional_term,
                    KBSynonym.id.label("synonym_id"),
                )
                .join(KBSynonym, KBSynonym.id == KBSynonymVariant.synonym_id)
                .where(
                    KBSynonym.tenant_id == synonym.tenant_id,
                    _scope_conflict_expr(synonym.kb_id, KBSynonym.kb_id),
                    func.lower(func.trim(KBSynonymVariant.user_term)).in_(lowered_terms),
                    KBSynonym.id != synonym.id,
                )
                .limit(1)
            )
            conflict = (await self.db.execute(conflict_stmt)).first()
            if conflict:
                raise HTTPException(
                    status_code=409,
                    detail=f"口语词“{conflict.user_term}”在当前作用域已映射到其他标准词：{conflict.professional_term}",
                )

        existing_rows = (
            await self.db.execute(
                select(KBSynonymVariant).where(KBSynonymVariant.synonym_id == synonym.id)
            )
        ).scalars().all()
        existing_map = {_normalize_text(row.user_term).lower(): row for row in existing_rows}

        inserted_count = 0
        updated_count = 0
        deleted_count = 0

        # 批量新增/更新
        for variant_payload in normalized_items:
            key = str(variant_payload["user_term"]).lower()
            row = existing_map.get(key)
            if row is None:
                new_row = KBSynonymVariant(
                    synonym_id=synonym.id,
                    user_term=variant_payload["user_term"],
                    is_active=variant_payload["is_active"],
                    description=variant_payload["description"],
                    created_by_id=current_user.id,
                    created_by_name=current_user.nickname or current_user.username or "System",
                    updated_by_id=current_user.id,
                    updated_by_name=current_user.nickname or current_user.username or "System",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                self.db.add(new_row)
                inserted_count += 1
            else:
                changed = False
                if row.is_active != variant_payload["is_active"]:
                    row.is_active = variant_payload["is_active"]
                    changed = True
                if (row.description or None) != (variant_payload["description"] or None):
                    row.description = variant_payload["description"]
                    changed = True
                # 归一化后可能有大小写/空格差异，统一回写
                if row.user_term != variant_payload["user_term"]:
                    row.user_term = variant_payload["user_term"]
                    changed = True
                if changed:
                    row.updated_by_id = current_user.id
                    row.updated_by_name = current_user.nickname or current_user.username or "System"
                    row.updated_at = datetime.now(timezone.utc)
                    updated_count += 1

        # 替换模式：删除未在本次列表中的口语词
        if replace:
            keep_keys = {str(variant_payload["user_term"]).lower() for variant_payload in normalized_items}
            for key, row in existing_map.items():
                if key not in keep_keys:
                    await self.db.delete(row)
                    deleted_count += 1

        await self.db.commit()

        total_count_stmt = select(func.count()).select_from(KBSynonymVariant).where(
            KBSynonymVariant.synonym_id == synonym.id
        )
        total_count = int((await self.db.scalar(total_count_stmt)) or 0)

        return SynonymVariantBatchUpsertResponse(
            synonym_id=synonym.id,
            inserted_count=inserted_count,
            updated_count=updated_count,
            deleted_count=deleted_count,
            total_count=total_count,
        )
