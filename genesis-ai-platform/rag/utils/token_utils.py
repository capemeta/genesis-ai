import re
import logging
import os
from typing import Optional, Any, Dict
from .model_utils import model_config_manager

logger = logging.getLogger(__name__)

def count_mixed_units(s: str) -> int:
    """
    混合单位数统计 (方案 A):
    1. 连续的英文字母/数字/下划线 -> 1个单位
    2. 每个中文字符/中文标点 -> 1个单位
    3. 每个其他非空白字符 -> 1个单位
    4. 针对长单词进行惩罚性平衡
    """
    if not s:
        return 0
    # 模式说明：CJK字符 | 单词/数字 | 其他非空白
    pattern = r'[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef]|\w+|[^\s]'
    matches = re.findall(pattern, s)
    
    total_count = 0
    for m in matches:
        if '\u4e00' <= m[0] <= '\u9fff' or '\u3400' <= m[0] <= '\u4dbf' or 0x3000 <= ord(m[0]) <= 0x303F:
            total_count += 1
        elif len(m) > 8:
            # 补偿长单词：每 4 个字符额外记一次单位
            total_count += (len(m) + 3) // 4
        else:
            total_count += 1
    return total_count

def is_chunk_safe(text: str, model_name: Optional[str] = None) -> bool:
    """
    通用、高性能的安全检查
    
    Args:
        text: 待检查文本
        model_name: 嵌入模型名称，若不传则使用默认 BGE 限制
    """
    # 1. 获取模型配置限制
    model_name = model_name or "BAAI/bge-large-zh-v1.5"
    config = model_config_manager.get_model_config(model_name)
    safe_size = config.get("safe_tokens", 400) if config else 400

    # 2. 从环境变量读取选择的方案 (A 或 B)，支持 .env
    # 注意：这里不直接导入 core.config.settings 以免触发繁重的数据库初始化
    schema = os.environ.get("RAG_CHUNK_SAFE_CHECK_SCHEMA", "B").upper()
    
    count = 0
    if schema == "A":
        # 方案 A：极致性能 (正则混合单位)
        count = count_mixed_units(text)
    else:
        # 方案 B：工业级标准 (Tiktoken)
        try:
            import tiktoken
            # 虽然 BGE 与 OpenAI 词表不同，但 tiktoken 通常更严，作为度量衡非常安全
            enc = tiktoken.get_encoding("cl100k_base")
            count = len(enc.encode(text))
        except (ImportError, Exception) as e:
            # 降级方案
            logger.debug(f"[is_chunk_safe] Tiktoken unavailable or failed, fallback to Scheme A: {e}")
            count = count_mixed_units(text)
            
    return count <= safe_size


def count_tokens(text: str) -> int:
    """
    使用 Tiktoken 计算 Token 数 (cl100k_base)
    专门用于存储和回传前端的 Token 统计
    """
    if not text:
        return 0
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except (ImportError, Exception) as e:
        logger.debug(f"[count_tokens] Fallback to count_mixed_units: {e}")
        return count_mixed_units(text)
