"""
认证功能测试脚本
用于快速测试用户注册、登录等功能
"""
import asyncio
import httpx


BASE_URL = "http://localhost:8200"


async def test_health():
    """测试健康检查"""
    print("\n=== 测试健康检查 ===")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/health")
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")


async def test_register():
    """测试用户注册"""
    print("\n=== 测试用户注册 ===")
    
    # 首先需要创建一个租户
    # 这里假设租户 ID 已存在，实际使用时需要先创建租户
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    
    user_data = {
        "email": "test@example.com",
        "password": "SecurePassword123!",
        "tenant_id": tenant_id,
        "username": "testuser",
        "nickname": "Test User",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/auth/register",
            json=user_data,
        )
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        return response.json()


async def test_login():
    """测试用户登录"""
    print("\n=== 测试用户登录 ===")
    
    login_data = {
        "username": "test@example.com",
        "password": "SecurePassword123!",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/auth/jwt/login",
            data=login_data,  # 注意：使用 data 而不是 json
        )
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        
        if response.status_code == 200:
            token = response.json().get("access_token")
            return token
        return None


async def test_get_current_user(token: str):
    """测试获取当前用户信息"""
    print("\n=== 测试获取当前用户信息 ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/users/me",
            headers=headers,
        )
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")


async def main():
    """主函数"""
    print("🚀 开始测试认证功能...")
    
    try:
        # 1. 健康检查
        await test_health()
        
        # 2. 注册用户
        # await test_register()
        
        # 3. 登录
        token = await test_login()
        
        # 4. 获取当前用户信息
        if token:
            await test_get_current_user(token)
        
        print("\n✅ 测试完成！")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
