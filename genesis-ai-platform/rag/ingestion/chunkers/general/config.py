"""
通用分块器配置
"""


class GeneralChunkerConfig:
    """通用分块器配置常量"""
    
    DEFAULT_CHUNK_SIZE = 512
    DEFAULT_CHUNK_OVERLAP = 50
    DEFAULT_COMPLEXITY_THRESHOLD = 4000
    
    # 优化后的中文标点正则
    # 包含了中英文逗号、分号、句号、感叹号、问号、换行
    # 只要总长度不超过 chunk_size，它会尽量保持句子完整
    # 注意：避免在 Markdown 图片语法 ![alt](url) 中间分割
    DEFAULT_SECONDARY_CHUNKING_REGEX = r"[^,，;；.。！？!?;；\n]+[,，;；.。！？!?;；\n]?"
    
    # Markdown 图片语法保护模式
    # 匹配 ![...](...)，确保不会在 ! 和 [ 之间分割
    MARKDOWN_IMAGE_PATTERN = r"!\[.*?\]\(.*?\)"
