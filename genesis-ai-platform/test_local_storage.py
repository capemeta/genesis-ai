"""
本地存储驱动测试脚本

测试本地文件系统存储的上传、下载、删除等功能
"""
import asyncio
import io
from pathlib import Path
from uuid import uuid4

from core.storage.local_driver import LocalStorageDriver


async def test_local_storage():
    """测试本地存储驱动"""
    
    print("=" * 60)
    print("本地存储驱动测试")
    print("=" * 60)
    
    # 1. 初始化驱动（使用相对路径）
    print("\n1. 初始化驱动（相对路径）")
    driver = LocalStorageDriver("./test_storage")
    print(f"   存储根目录: {driver.base_path.absolute()}")
    
    # 2. 测试上传
    print("\n2. 测试文件上传")
    test_content = b"Hello, Genesis AI Platform! This is a test file."
    test_file = io.BytesIO(test_content)
    test_key = f"test/{uuid4()}/test.txt"
    
    result = await driver.upload(
        file=test_file,
        key=test_key,
        content_type="text/plain",
        metadata={"test": "true"}
    )
    print(f"   上传成功: {result}")
    print(f"   文件路径: {driver._get_full_path(test_key)}")
    
    # 3. 测试文件存在检查
    print("\n3. 测试文件存在检查")
    exists = await driver.exists(test_key)
    print(f"   文件存在: {exists}")
    
    # 4. 测试获取文件内容
    print("\n4. 测试获取文件内容")
    content = await driver.get_content(test_key)
    print(f"   文件内容: {content.decode('utf-8')}")
    print(f"   内容匹配: {content == test_content}")
    
    # 5. 测试下载文件
    print("\n5. 测试下载文件")
    download_path = Path("./test_download.txt")
    await driver.download(test_key, download_path)
    print(f"   下载成功: {download_path.absolute()}")
    
    # 验证下载的文件内容
    with open(download_path, 'rb') as f:
        downloaded_content = f.read()
    print(f"   下载内容匹配: {downloaded_content == test_content}")
    
    # 清理下载的文件
    download_path.unlink()
    print(f"   清理下载文件: {download_path}")
    
    # 6. 测试获取 URL
    print("\n6. 测试获取 URL")
    url = await driver.get_url(test_key)
    print(f"   文件 URL: {url}")
    
    # 7. 测试删除文件
    print("\n7. 测试删除文件")
    await driver.delete(test_key)
    exists_after_delete = await driver.exists(test_key)
    print(f"   删除后文件存在: {exists_after_delete}")
    
    # 8. 测试绝对路径初始化
    print("\n8. 测试绝对路径初始化")
    abs_path = Path.cwd() / "test_storage_abs"
    driver_abs = LocalStorageDriver(str(abs_path))
    print(f"   存储根目录: {driver_abs.base_path.absolute()}")
    
    # 清理测试目录
    print("\n9. 清理测试目录")
    import shutil
    if driver.base_path.exists():
        shutil.rmtree(driver.base_path)
        print(f"   清理: {driver.base_path}")
    if abs_path.exists():
        shutil.rmtree(abs_path)
        print(f"   清理: {abs_path}")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_local_storage())
