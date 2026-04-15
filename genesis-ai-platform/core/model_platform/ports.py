"""
模型平台能力端口定义。
"""
from typing import Any, Protocol


class ChatModelPort(Protocol):
    """文本对话能力端口。"""

    async def chat(self, request: Any) -> Any:
        """执行普通对话请求。"""

    async def stream_chat(self, request: Any) -> Any:
        """执行流式对话请求。"""


class EmbeddingModelPort(Protocol):
    """向量化能力端口。"""

    async def embed(self, request: Any) -> Any:
        """执行向量化请求。"""


class RerankModelPort(Protocol):
    """重排序能力端口。"""

    async def rerank(self, request: Any) -> Any:
        """执行重排序请求。"""


class VisionModelPort(Protocol):
    """视觉理解能力端口。"""

    async def analyze(self, request: Any) -> Any:
        """执行视觉理解请求。"""


class AsrModelPort(Protocol):
    """语音识别能力端口。"""

    async def transcribe(self, request: Any) -> Any:
        """执行语音转文字请求。"""


class TtsModelPort(Protocol):
    """语音播报能力端口。"""

    async def synthesize(self, request: Any) -> Any:
        """执行文本转语音请求。"""


class OcrModelPort(Protocol):
    """OCR 识别能力端口。"""

    async def recognize(self, request: Any) -> Any:
        """执行图片或页面 OCR 识别请求。"""


class DocumentParseModelPort(Protocol):
    """文档解析能力端口。"""

    async def parse(self, request: Any) -> Any:
        """执行版面分析、结构抽取、文档理解等请求。"""
