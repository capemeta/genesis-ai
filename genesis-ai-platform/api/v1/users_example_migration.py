"""
用户管理 API - 使用 CRUD 工厂的示例

这个文件展示了如何将现有的 users.py 迁移到使用 CRUD 工厂
"""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from core.crud_factory import crud_factory
from core.security import get_current_active_user, require_permissions, Permission
from models.user import User
from schemas.user import UserRead, UserCreate, UserUpdate

# ==================== 方式 1：完全自动化（推荐） ====================
# 在 crud_registry.py 中注册：
# crud_factory.register(
#     model=User,
#     prefix="/users",
#     tags=["users"],
#     exclude_fields=["hashed_password"]  # 排除敏感字段
# )
# 
# 完成！自动拥有所有 CRUD 功能

# ==================== 方式 2：使用自定义 Schema ====================
# 如果需要自定义 Schema（如 users.py 中已有的 Schema）：
# crud_factory.register(
#     model=User,
#     prefix="/users",
#     tags=["users"],
#     create_schema=UserCreate,
#     update_schema=UserUpdate,
#     read_schema=UserRead
# )

# ==================== 方式 3：添加自定义路由 ====================
# 获取自动生成的 router，然后添加自定义路由
router = crud_factory.get_router("User")  # 获取已注册的 router

# 添加自定义路由：当前用户信息
@router.get("/me", response_model=UserRead)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
):
    """
    获取当前用户信息
    
    权限：任何登录用户
    """
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    user_service = Depends(lambda: crud_factory.get_service("User")),
):
    """
    更新当前用户信息
    
    权限：任何登录用户
    """
    updated_user = await user_service.update(
        resource_id=current_user.id,
        data=user_update,
        current_user=current_user
    )
    return updated_user


# ==================== 对比：原来的代码 vs 现在的代码 ====================

# 【原来】需要手动写所有路由：
# @router.get("/", response_model=dict)
# async def list_users(
#     page: int = Query(1, ge=1),
#     page_size: int = Query(20, ge=1, le=100),
#     search: str | None = Query(None),
#     status: str | None = Query(None),
#     organization_id: UUID | None = Query(None),
#     current_user: User = Depends(require_permissions(Permission.USER_READ)),
#     user_service: UserService = Depends(get_user_service),
# ):
#     users, total = await user_service.list_users(...)
#     return {
#         "data": [UserRead.model_validate(user) for user in users],
#         "total": total
#     }
# 
# @router.post("/", response_model=UserRead, status_code=201)
# async def create_user(...): ...
# 
# @router.get("/{user_id}", response_model=UserRead)
# async def get_user(...): ...
# 
# @router.put("/{user_id}", response_model=UserRead)
# async def update_user(...): ...
# 
# @router.delete("/{user_id}")
# async def delete_user(...): ...

# 【现在】只需 1 行注册代码：
# crud_factory.register(model=User, prefix="/users", tags=["users"])
# 
# 自动生成所有路由！
# 只需要添加特殊的路由（如 /me）

# ==================== 如果需要自定义 Service ====================
# 创建自定义 Service：
# 
# from core.base_service import BaseService
# 
# class UserService(BaseService[User, UserCreate, UserUpdate]):
#     async def list_resources(self, tenant_id, **kwargs):
#         """重写列表方法，添加搜索功能"""
#         search = kwargs.pop("search", None)
#         
#         # 调用父类方法
#         users, total = await super().list_resources(tenant_id, **kwargs)
#         
#         # 添加搜索过滤
#         if search:
#             users = [u for u in users if search.lower() in u.username.lower()]
#             total = len(users)
#         
#         return users, total
# 
# # 注册时使用自定义 Service
# crud_factory.register(
#     model=User,
#     prefix="/users",
#     tags=["users"],
#     service_class=UserService
# )

# ==================== 总结 ====================
# 
# 迁移步骤：
# 1. 在 crud_registry.py 中添加 1 行注册代码
# 2. 删除标准的 CRUD 路由代码（list、get、create、update、delete）
# 3. 保留特殊的自定义路由（如 /me）
# 4. 如果有复杂业务逻辑，创建自定义 Service
# 
# 代码减少：约 80%
# 维护成本：大幅降低
# 一致性：所有 API 自动符合规范
