"""
视觉大模型解析器

使用视觉大模型解析复杂布局文档
"""

from typing import Tuple, Dict, Any, List
from ..base import BaseParser


class VisionParser(BaseParser):
    """
    视觉大模型解析器
    
    特点：
    - 理解图表、图片内容
    - 处理复杂布局
    - 提取视觉信息
    
    适用场景：
    - 图表密集文档
    - 复杂布局
    - 扫描件（配合 OCR）
    
    ⚠️ 重要设计原则：
    1. 虽然调用 API 是 I/O 密集，但解析任务整体是 CPU 密集（图像处理）
    2. 使用同步方法 + 阻塞 HTTP 调用（requests）
    3. 部署时使用 prefork Worker，多个 Worker 并行处理
    4. 如果 API 调用占比很大，考虑拆分为独立的 enhance 任务
    """
    
    SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".bmp"}
    
    def supports(self, file_extension: str) -> bool:
        """检查是否支持该文件类型"""
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS
    
    def parse(self, file_buffer: bytes, file_extension: str) -> Tuple[str, Dict[str, Any]]:
        """
        使用视觉大模型解析文档（同步方法）
        
        注意：使用同步 HTTP 调用（requests），不使用 async
        """
        print(f"[VisionParser] 开始解析文档，类型: {file_extension}")
        
        # 1. 转换为图片
        images = self._convert_to_images(file_buffer, file_extension)
        
        # 2. 调用视觉模型（同步，阻塞）
        texts = self._parse_images(images)
        
        # 3. 合并结果
        full_text = "\n\n".join(texts)
        
        metadata = {
            "parse_method": "vision_model",
            "page_count": len(images),
            "text_length": len(full_text)
        }
        
        print(f"[VisionParser] 解析完成，页数: {len(images)}")
        
        return full_text, metadata
    
    def _convert_to_images(self, file_buffer: bytes, file_extension: str) -> List[bytes]:
        """
        将文档转换为图片（同步方法）
        
        TODO: 实现文档转图片逻辑
        """
        print("[VisionParser] 转换文档为图片")
        
        # TODO: 实现转换逻辑
        # - PDF: pdf2image
        # - 图片: 直接使用
        
        return [file_buffer]  # 占位
    
    def _parse_images(self, images: List[bytes]) -> List[str]:
        """
        调用视觉模型解析图片（同步方法）
        
        TODO: 实现视觉模型调用（使用 requests，不使用 async）
        
        注意：
        - 使用同步 HTTP 库（requests）
        - 不使用 async/await
        - 多个 Worker 并行处理不同文档
        """
        print(f"[VisionParser] 调用视觉模型解析 {len(images)} 张图片")
        
        # TODO: 实现视觉模型调用
        # import requests
        # for image in images:
        #     response = requests.post(
        #         "https://api.openai.com/v1/chat/completions",
        #         json={...},
        #         headers={...}
        #     )
        #     texts.append(response.json()["choices"][0]["message"]["content"])
        
        return ["视觉模型解析结果（待实现）"] * len(images)
