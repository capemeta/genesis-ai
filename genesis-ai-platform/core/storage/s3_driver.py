"""
S3 存储驱动（支持 AWS S3 / SeaweedFS S3）
"""
import logging
from typing import BinaryIO, Optional
from pathlib import Path
import aioboto3
from botocore.exceptions import ClientError

from core.storage.base import StorageDriver
from core.config import settings

logger = logging.getLogger(__name__)


class S3StorageDriver(StorageDriver):
    """S3 存储驱动"""
    
    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1"
    ):
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self.region = region
        
        # 创建 aioboto3 session
        self.session = aioboto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
    
    async def _get_client(self):
        """获取 S3 客户端"""
        return self.session.client(
            's3',
            endpoint_url=self.endpoint_url,
            region_name=self.region
        )
    
    async def upload(
        self,
        file: BinaryIO,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """上传文件到 S3"""
        try:
            async with await self._get_client() as s3:
                extra_args: dict[str, object] = {}
                if content_type:
                    extra_args['ContentType'] = content_type
                if metadata:
                    extra_args['Metadata'] = metadata
                
                await s3.upload_fileobj(
                    file,
                    self.bucket,
                    key,
                    ExtraArgs=extra_args if extra_args else None
                )
                
                logger.info(f"文件上传成功: {key}")
                return key
                
        except ClientError as e:
            logger.error(f"文件上传失败: {key}, 错误: {e}")
            raise
    
    async def download(self, key: str, destination: Path) -> None:
        """从 S3 下载文件"""
        try:
            async with await self._get_client() as s3:
                destination.parent.mkdir(parents=True, exist_ok=True)
                
                with open(destination, 'wb') as f:
                    await s3.download_fileobj(self.bucket, key, f)
                
                logger.info(f"文件下载成功: {key} -> {destination}")
                
        except ClientError as e:
            logger.error(f"文件下载失败: {key}, 错误: {e}")
            raise
    
    async def delete(self, key: str) -> None:
        """从 S3 删除文件"""
        try:
            async with await self._get_client() as s3:
                await s3.delete_object(Bucket=self.bucket, Key=key)
                logger.info(f"文件删除成功: {key}")
                
        except ClientError as e:
            logger.error(f"文件删除失败: {key}, 错误: {e}")
            raise
    
    async def exists(self, key: str) -> bool:
        """检查文件是否存在"""
        try:
            async with await self._get_client() as s3:
                await s3.head_object(Bucket=self.bucket, Key=key)
                return True
                
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"检查文件存在失败: {key}, 错误: {e}")
            raise
    
    async def get_url(
        self, 
        key: str, 
        expires_in: int = 3600,
        filename: Optional[str] = None
    ) -> str:
        """
        获取预签名 URL
        
        Args:
            key: 文件存储路径
            expires_in: URL 有效期（秒）
            filename: 下载时的文件名（可选）
            
        Returns:
            预签名 URL
        """
        try:
            async with await self._get_client() as s3:
                params = {'Bucket': self.bucket, 'Key': key}
                
                # 如果指定了文件名，添加 Content-Disposition 响应头
                if filename:
                    # 使用 RFC 6266 格式，支持中文文件名
                    # 使用 filename* 参数支持 UTF-8 编码
                    import urllib.parse
                    encoded_filename = urllib.parse.quote(filename)
                    params['ResponseContentDisposition'] = (
                        f"attachment; filename=\"{filename}\"; "
                        f"filename*=UTF-8''{encoded_filename}"
                    )
                
                url = await s3.generate_presigned_url(
                    'get_object',
                    Params=params,
                    ExpiresIn=expires_in
                )
                return url
                
        except ClientError as e:
            logger.error(f"生成预签名 URL 失败: {key}, 错误: {e}")
            raise

    async def get_content(self, key: str) -> bytes:
        """从 S3 获取文件内容（一次性读取，适用于小文件）"""
        try:
            async with await self._get_client() as s3:
                response = await s3.get_object(Bucket=self.bucket, Key=key)
                async with response['Body'] as stream:
                    return await stream.read()
        except ClientError as e:
            logger.error(f"获取文件内容失败: {key}, 错误: {e}")
            raise
    
    async def get_stream(self, key: str, chunk_size: int = 8192):
        """
        从 S3 获取文件流（分块读取，适用于大文件）
        
        Args:
            key: 存储键名/路径
            chunk_size: 每次读取的块大小（字节）
            
        Yields:
            bytes: 文件内容块
        """
        try:
            async with await self._get_client() as s3:
                response = await s3.get_object(Bucket=self.bucket, Key=key)
                async with response['Body'] as stream:
                    while True:
                        try:
                            chunk = await stream.read(chunk_size)
                        except TypeError:
                            chunk = await stream.content.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
        except ClientError as e:
            logger.error(f"获取文件流失败: {key}, 错误: {e}")
            raise


# 全局 S3 驱动实例
_s3_driver: Optional[S3StorageDriver] = None


def get_s3_driver() -> S3StorageDriver:
    """获取 S3 驱动实例（单例）"""
    global _s3_driver
    
    if _s3_driver is None:
        if not settings.SEAWEEDFS_ENDPOINT or not settings.SEAWEEDFS_ACCESS_KEY or not settings.SEAWEEDFS_SECRET_KEY:
            raise ValueError("S3 存储驱动初始化失败：缺少 SEAWEEDFS_ENDPOINT / SEAWEEDFS_ACCESS_KEY / SEAWEEDFS_SECRET_KEY")
        _s3_driver = S3StorageDriver(
            endpoint_url=settings.SEAWEEDFS_ENDPOINT,
            access_key=settings.SEAWEEDFS_ACCESS_KEY,
            secret_key=settings.SEAWEEDFS_SECRET_KEY,
            bucket=settings.SEAWEEDFS_BUCKET,
            region=settings.SEAWEEDFS_REGION
        )
    
    return _s3_driver
