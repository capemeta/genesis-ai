#!/usr/bin/env python3
"""
SeaweedFS S3 API 测试脚本

使用方法:
    python test-s3.py

需要安装 boto3:
    pip install boto3
"""

import boto3
from botocore.exceptions import ClientError
import os
import tempfile

# S3 配置
S3_ENDPOINT = "http://192.168.110.110:8304"
S3_ACCESS_KEY = "GAI_AK_4VQOIH5HJZ1U"
S3_SECRET_KEY = "l90dyiB62TaQKH2uT8UIIfMPhtKmuepw1vF3xP5m"
S3_REGION = "us-east-1"

# 测试 bucket 名称
TEST_BUCKET = "test-bucket"


def create_s3_client():
    """创建 S3 客户端"""
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION
    )


def test_create_bucket(s3_client):
    """测试创建 bucket"""
    print(f"\n1. 创建 bucket: {TEST_BUCKET}")
    try:
        s3_client.create_bucket(Bucket=TEST_BUCKET)
        print(f"   ✓ Bucket '{TEST_BUCKET}' 创建成功")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
            print(f"   ✓ Bucket '{TEST_BUCKET}' 已存在")
            return True
        else:
            print(f"   ✗ 创建失败: {e}")
            return False


def test_list_buckets(s3_client):
    """测试列出所有 buckets"""
    print("\n2. 列出所有 buckets")
    try:
        response = s3_client.list_buckets()
        buckets = response.get('Buckets', [])
        if buckets:
            for bucket in buckets:
                print(f"   - {bucket['Name']}")
        else:
            print("   (无 bucket)")
        return True
    except ClientError as e:
        print(f"   ✗ 列出失败: {e}")
        return False


def test_upload_file(s3_client):
    """测试上传文件"""
    print("\n3. 上传文件")
    
    # 创建临时测试文件
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Hello, SeaweedFS!\n")
        f.write("This is a test file.\n")
        temp_file = f.name
    
    try:
        key = "test-file.txt"
        s3_client.upload_file(temp_file, TEST_BUCKET, key)
        print(f"   ✓ 文件上传成功: {key}")
        return True
    except ClientError as e:
        print(f"   ✗ 上传失败: {e}")
        return False
    finally:
        os.unlink(temp_file)


def test_list_objects(s3_client):
    """测试列出对象"""
    print(f"\n4. 列出 bucket '{TEST_BUCKET}' 中的对象")
    try:
        response = s3_client.list_objects_v2(Bucket=TEST_BUCKET)
        objects = response.get('Contents', [])
        if objects:
            for obj in objects:
                size_kb = obj['Size'] / 1024
                print(f"   - {obj['Key']} ({size_kb:.2f} KB)")
        else:
            print("   (无对象)")
        return True
    except ClientError as e:
        print(f"   ✗ 列出失败: {e}")
        return False


def test_download_file(s3_client):
    """测试下载文件"""
    print("\n5. 下载文件")
    
    # 创建临时下载路径
    download_file = tempfile.mktemp(suffix='.txt')
    
    try:
        key = "test-file.txt"
        s3_client.download_file(TEST_BUCKET, key, download_file)
        
        # 读取并显示内容
        with open(download_file, 'r') as f:
            content = f.read()
        
        print(f"   ✓ 文件下载成功: {key}")
        print(f"   内容:\n{content}")
        return True
    except ClientError as e:
        print(f"   ✗ 下载失败: {e}")
        return False
    finally:
        if os.path.exists(download_file):
            os.unlink(download_file)


def test_generate_presigned_url(s3_client):
    """测试生成预签名 URL"""
    print("\n6. 生成预签名 URL")
    try:
        key = "test-file.txt"
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': TEST_BUCKET, 'Key': key},
            ExpiresIn=3600  # 1 小时
        )
        print(f"   ✓ 预签名 URL 生成成功")
        print(f"   URL: {url}")
        return True
    except ClientError as e:
        print(f"   ✗ 生成失败: {e}")
        return False


def test_delete_object(s3_client):
    """测试删除对象"""
    print("\n7. 删除对象")
    try:
        key = "test-file.txt"
        s3_client.delete_object(Bucket=TEST_BUCKET, Key=key)
        print(f"   ✓ 对象删除成功: {key}")
        return True
    except ClientError as e:
        print(f"   ✗ 删除失败: {e}")
        return False


def test_delete_bucket(s3_client):
    """测试删除 bucket"""
    print(f"\n8. 删除 bucket: {TEST_BUCKET}")
    try:
        s3_client.delete_bucket(Bucket=TEST_BUCKET)
        print(f"   ✓ Bucket '{TEST_BUCKET}' 删除成功")
        return True
    except ClientError as e:
        print(f"   ✗ 删除失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("SeaweedFS S3 API 测试")
    print("=" * 60)
    print(f"\nEndpoint: {S3_ENDPOINT}")
    print(f"Access Key: {S3_ACCESS_KEY}")
    
    # 创建 S3 客户端
    try:
        s3_client = create_s3_client()
        print("\n✓ S3 客户端创建成功")
    except Exception as e:
        print(f"\n✗ S3 客户端创建失败: {e}")
        return
    
    # 运行测试
    tests = [
        test_create_bucket,
        test_list_buckets,
        test_upload_file,
        test_list_objects,
        test_download_file,
        test_generate_presigned_url,
        test_delete_object,
        # test_delete_bucket,  # 可选：取消注释以删除测试 bucket
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func(s3_client)
            results.append(result)
        except Exception as e:
            print(f"   ✗ 测试异常: {e}")
            results.append(False)
    
    # 显示测试结果
    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"\n通过: {passed}/{total}")
    
    if passed == total:
        print("\n✓ 所有测试通过！")
    else:
        print(f"\n✗ {total - passed} 个测试失败")


if __name__ == "__main__":
    main()
