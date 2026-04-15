"""
请求工具函数
处理 HTTP 请求相关的通用逻辑
"""
from fastapi import Request


def get_client_ip(request: Request) -> str:
    """
    获取客户端真实 IP 地址
    
    支持代理和负载均衡场景，按优先级检查：
    1. X-Forwarded-For 头（代理/负载均衡器添加）
    2. X-Real-IP 头（Nginx 等添加）
    3. request.client.host（直连）
    
    Args:
        request: FastAPI Request 对象
        
    Returns:
        客户端 IP 地址
    """
    # 1. 检查 X-Forwarded-For（可能包含多个 IP，取第一个）
    forwarded_for = request.headers.get("X-Forwarded-For", "").strip()
    if forwarded_for:
        # X-Forwarded-For 格式: client, proxy1, proxy2
        return forwarded_for.split(",")[0].strip()
    
    # 2. 检查 X-Real-IP
    real_ip = request.headers.get("X-Real-IP", "").strip()
    if real_ip:
        return real_ip
    
    # 3. 使用直连 IP
    if request.client:
        return request.client.host
    
    # 4. 兜底
    return "unknown"
