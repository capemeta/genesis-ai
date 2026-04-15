"""
FastAPI 应用入口
"""
from pathlib import Path
from dotenv import load_dotenv

# 最先加载 .env，与 Celery Worker 共用同一套配置（环境变量或 .env 任选其一）
load_dotenv(Path(__file__).resolve().parent / ".env")

import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.responses import HTMLResponse, Response
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError
from core.config import settings, ConfigValidator
from core.database import lifespan
from core.logging_config import init_logging
from api.v1 import api_router
from middleware.auth_middleware import AuthMiddleware
from middleware.validation_middleware import validation_exception_handler
# 导入新的全局异常处理器
from core.exceptions import (
    starlette_http_exception_handler,  # 新增：处理 Starlette HTTP 异常（405 等）
    http_exception_handler,
    enhanced_validation_exception_handler,
    database_exception_handler,
    redis_exception_handler,
    general_exception_handler
)
from starlette.exceptions import HTTPException as StarletteHTTPException  # 新增导入


# 配置统一日志
init_logging("app")
# SQLAlchemy 只输出 WARN 及以上，避免打印每条 SQL
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# 启动前验证配置
ConfigValidator.validate_all()


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="企业级 RAG 知识库系统",
    lifespan=lifespan,
    root_path=settings.ROOT_PATH,  # 设置应用根路径上下文
    docs_url=None,  # 禁用默认文档，使用自定义的
    redoc_url=None,  # 禁用默认 ReDoc
    openapi_url="/openapi.json",  # OpenAPI schema 路径（相对于 root_path）
)


# 挂载静态文件目录（用于头像等上传文件）
# 注意：必须在中间件和路由之前挂载
from pathlib import Path
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# 自定义 Swagger UI 文档（使用国内 CDN - bootcdn）
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """自定义 Swagger UI，使用国内 bootcdn"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - API 文档",
        swagger_js_url="https://cdn.bootcdn.net/ajax/libs/swagger-ui/5.10.5/swagger-ui-bundle.min.js",
        swagger_css_url="https://cdn.bootcdn.net/ajax/libs/swagger-ui/5.10.5/swagger-ui.min.css",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
    )


# 自定义 ReDoc 文档（使用国内 CDN）
@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    """自定义 ReDoc，使用国内 CDN"""
    from fastapi.openapi.docs import get_redoc_html
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - API 文档",
        redoc_js_url="https://cdn.bootcdn.net/ajax/libs/redoc/2.1.3/bundles/redoc.standalone.min.js",
    )


# 配置 CORS（必须在认证中间件之前）
# 解析 CORS_ORIGINS（支持字符串或列表）
cors_origins = settings.CORS_ORIGINS
if isinstance(cors_origins, str):
    import json
    try:
        cors_origins = json.loads(cors_origins)
    except json.JSONDecodeError:
        # 如果不是 JSON，按逗号分割
        cors_origins = [origin.strip() for origin in cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


# 添加安全响应头中间件
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """添加安全响应头"""
    response: Response = await call_next(request)
    
    # 1. X-Content-Type-Options: 防止 MIME 类型嗅探
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # 2. X-Frame-Options: 防止点击劫持
    response.headers["X-Frame-Options"] = "DENY"
    
    # 3. X-XSS-Protection: XSS 保护（虽然现代浏览器已内置，但仍建议添加）
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # 4. Referrer-Policy: 控制 Referrer 信息泄露
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # 5. Permissions-Policy: 限制浏览器功能访问
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    # 6. Content-Security-Policy: 内容安全策略（根据实际需求调整）
    # 注意：这是一个基础配置，可能需要根据前端实际使用的资源进行调整
    csp_directives = [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.bootcdn.net",
        "style-src 'self' 'unsafe-inline' https://cdn.bootcdn.net",
        "img-src 'self' data: https: http:",
        "font-src 'self' data: https://cdn.bootcdn.net",
        "connect-src 'self' http://localhost:* https:",
        "frame-ancestors 'none'",
    ]
    response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
    
    # 7. Strict-Transport-Security (HSTS): 强制 HTTPS（仅在生产环境且使用 HTTPS 时启用）
    # 注意：只有在确保使用 HTTPS 时才启用，否则会导致无法访问
    # if not settings.DEBUG and request.url.scheme == "https":
    #     response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response


# 配置全局认证中间件
# 注意：中间件的执行顺序是后注册先执行
# 所以认证中间件会在 CORS 之后执行
app.add_middleware(AuthMiddleware)


# 注册全局异常处理器（按优先级顺序）
# 0. Starlette HTTP 异常处理器（处理 405、404 等框架级错误）
app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)

# 1. FastAPI HTTP 异常处理器（包括自定义的 BaseAPIException）
app.add_exception_handler(HTTPException, http_exception_handler)

# 2. 验证异常处理器（替换原有的 validation_exception_handler）
# 保持现有的登录失败记录逻辑，同时统一响应格式
app.add_exception_handler(RequestValidationError, enhanced_validation_exception_handler)

# 3. 数据库异常处理器
app.add_exception_handler(SQLAlchemyError, database_exception_handler)

# 4. Redis 异常处理器
app.add_exception_handler(RedisError, redis_exception_handler)

# 5. 通用异常处理器（兜底）
app.add_exception_handler(Exception, general_exception_handler)


# 注册 API 路由
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# 根路径
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Welcome to Genesis AI Platform",
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=True,
        log_level="info",
        timeout_keep_alive=300,  # 🔥 增加 keep-alive 超时到 300 秒（5 分钟），支持大文件下载
        timeout_graceful_shutdown=30,  # 优雅关闭超时
    )
