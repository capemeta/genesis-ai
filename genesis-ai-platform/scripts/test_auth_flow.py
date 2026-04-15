"""
测试认证流程
测试登录、获取用户信息等功能
"""
import asyncio
import httpx
from typing import Optional


BASE_URL = "http://localhost:8200"


class AuthTester:
    """认证测试器"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.token: Optional[str] = None
    
    async def test_health(self):
        """测试健康检查"""
        print("\n" + "=" * 60)
        print("1. 测试健康检查")
        print("=" * 60)
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/health")
                print(f"✅ 状态码: {response.status_code}")
                print(f"✅ 响应: {response.json()}")
                return True
            except Exception as e:
                print(f"❌ 错误: {e}")
                return False
    
    async def test_login(self, username: str = "admin", password: str = "admin123"):
        """测试登录"""
        print("\n" + "=" * 60)
        print("2. 测试用户登录")
        print("=" * 60)
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/auth/login",
                    json={"username": username, "password": password}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.token = data.get("access_token")
                    print(f"✅ 登录成功")
                    print(f"✅ Token: {self.token[:50]}...")
                    return True
                else:
                    print(f"❌ 登录失败: {response.status_code}")
                    print(f"   响应: {response.text}")
                    return False
            except Exception as e:
                print(f"❌ 错误: {e}")
                return False
    
    async def test_get_current_user(self):
        """测试获取当前用户信息"""
        print("\n" + "=" * 60)
        print("3. 测试获取当前用户信息")
        print("=" * 60)
        
        if not self.token:
            print("❌ 未登录，请先执行登录测试")
            return False
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {self.token}"}
                )
                
                if response.status_code == 200:
                    user = response.json()
                    print(f"✅ 获取用户信息成功")
                    print(f"   用户ID: {user.get('id')}")
                    print(f"   用户名: {user.get('username')}")
                    print(f"   昵称: {user.get('nickname')}")
                    print(f"   邮箱: {user.get('email')}")
                    print(f"   租户ID: {user.get('tenant_id')}")
                    print(f"   状态: {user.get('status')}")
                    return True
                else:
                    print(f"❌ 获取失败: {response.status_code}")
                    print(f"   响应: {response.text}")
                    return False
            except Exception as e:
                print(f"❌ 错误: {e}")
                return False
    
    async def test_update_current_user(self):
        """测试更新当前用户信息"""
        print("\n" + "=" * 60)
        print("4. 测试更新当前用户信息")
        print("=" * 60)
        
        if not self.token:
            print("❌ 未登录，请先执行登录测试")
            return False
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(
                    f"{self.base_url}/api/v1/users/me",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={"nickname": "Super Admin"}
                )
                
                if response.status_code == 200:
                    user = response.json()
                    print(f"✅ 更新用户信息成功")
                    print(f"   新昵称: {user.get('nickname')}")
                    return True
                else:
                    print(f"❌ 更新失败: {response.status_code}")
                    print(f"   响应: {response.text}")
                    return False
            except Exception as e:
                print(f"❌ 错误: {e}")
                return False
    
    async def test_invalid_token(self):
        """测试无效 Token"""
        print("\n" + "=" * 60)
        print("5. 测试无效 Token")
        print("=" * 60)
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/users/me",
                    headers={"Authorization": "Bearer invalid_token_here"}
                )
                
                if response.status_code == 401:
                    print(f"✅ 正确拒绝无效 Token")
                    return True
                else:
                    print(f"❌ 未正确处理无效 Token: {response.status_code}")
                    return False
            except Exception as e:
                print(f"❌ 错误: {e}")
                return False
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "=" * 60)
        print("认证流程测试")
        print("=" * 60)
        print(f"测试服务器: {self.base_url}")
        
        results = []
        
        # 1. 健康检查
        results.append(await self.test_health())
        
        # 2. 登录
        results.append(await self.test_login())
        
        # 3. 获取当前用户
        results.append(await self.test_get_current_user())
        
        # 4. 更新用户信息
        results.append(await self.test_update_current_user())
        
        # 5. 测试无效 Token
        results.append(await self.test_invalid_token())
        
        # 总结
        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)
        passed = sum(results)
        total = len(results)
        print(f"通过: {passed}/{total}")
        
        if passed == total:
            print("✅ 所有测试通过！")
        else:
            print(f"❌ {total - passed} 个测试失败")
        
        return passed == total


async def main():
    """主函数"""
    tester = AuthTester()
    success = await tester.run_all_tests()
    
    if not success:
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
