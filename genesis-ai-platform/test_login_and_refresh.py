"""
测试登录和刷新流程
"""
import requests
import time

BASE_URL = "http://localhost:8200/genesis-ai"

def test_login_and_refresh():
    """测试登录和刷新"""
    print("=" * 60)
    print("测试登录和刷新流程")
    print("=" * 60)
    
    # 1. 登录
    print("\n1. 登录...")
    login_response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={
            "username": "admin",
            "password": "Admin@123456",
            "remember": True
        }
    )
    
    print(f"   状态码: {login_response.status_code}")
    if login_response.status_code == 200:
        data = login_response.json()
        print(f"   ✅ 登录成功")
        print(f"   Access Token: {data['access_token'][:20]}...")
        print(f"   Refresh Token: {data['refresh_token'][:20]}...")
        print(f"   Expires In: {data['expires_in']}秒")
        
        # 检查 Cookie
        cookies = login_response.cookies
        print(f"\n   Cookies:")
        for cookie in cookies:
            print(f"     - {cookie.name}: {cookie.value[:20]}... (path={cookie.path}, max_age={cookie.expires})")
        
        access_token = data['access_token']
        refresh_token = data['refresh_token']
    else:
        print(f"   ❌ 登录失败: {login_response.text}")
        return
    
    # 2. 使用 access token 访问受保护资源
    print("\n2. 使用 Access Token 访问受保护资源...")
    me_response = requests.get(
        f"{BASE_URL}/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    print(f"   状态码: {me_response.status_code}")
    if me_response.status_code == 200:
        user = me_response.json()
        print(f"   ✅ 访问成功: {user.get('username')}")
    else:
        print(f"   ❌ 访问失败: {me_response.text}")
    
    # 3. 使用 refresh token 刷新
    print("\n3. 使用 Refresh Token 刷新...")
    refresh_response = requests.post(
        f"{BASE_URL}/api/v1/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    print(f"   状态码: {refresh_response.status_code}")
    if refresh_response.status_code == 200:
        data = refresh_response.json()
        print(f"   ✅ 刷新成功")
        print(f"   New Access Token: {data['access_token'][:20]}...")
        print(f"   New Refresh Token: {data['refresh_token'][:20]}...")
        
        new_access_token = data['access_token']
    else:
        print(f"   ❌ 刷新失败: {refresh_response.text}")
        return
    
    # 4. 使用新的 access token 访问
    print("\n4. 使用新的 Access Token 访问...")
    me_response2 = requests.get(
        f"{BASE_URL}/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_access_token}"}
    )
    print(f"   状态码: {me_response2.status_code}")
    if me_response2.status_code == 200:
        user = me_response2.json()
        print(f"   ✅ 访问成功: {user.get('username')}")
    else:
        print(f"   ❌ 访问失败: {me_response2.text}")
    
    # 5. 测试 Cookie 模式
    print("\n5. 测试 Cookie 模式...")
    session = requests.Session()
    
    # 登录（获取 Cookie）
    login_response2 = session.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={
            "username": "admin",
            "password": "Admin@123456",
            "remember": True
        }
    )
    print(f"   登录状态码: {login_response2.status_code}")
    
    if login_response2.status_code == 200:
        print(f"   ✅ Cookie 模式登录成功")
        
        # 使用 Cookie 访问
        me_response3 = session.get(f"{BASE_URL}/api/v1/users/me")
        print(f"   访问状态码: {me_response3.status_code}")
        if me_response3.status_code == 200:
            print(f"   ✅ Cookie 模式访问成功")
        else:
            print(f"   ❌ Cookie 模式访问失败")
        
        # 使用 Cookie 刷新
        refresh_response2 = session.post(f"{BASE_URL}/api/v1/auth/refresh", json={})
        print(f"   刷新状态码: {refresh_response2.status_code}")
        if refresh_response2.status_code == 200:
            print(f"   ✅ Cookie 模式刷新成功")
        else:
            print(f"   ❌ Cookie 模式刷新失败: {refresh_response2.text}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_login_and_refresh()
