import json
import os
from typing import Dict, Any, Optional

class ModelConfigManager:
    """嵌入模型配置管理器，用于管理不同模型的 Token 限制和分块建议"""
    
    _instance = None
    _configs: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelConfigManager, cls).__new__(cls)
            cls._instance._load_configs()
        return cls._instance

    def _load_configs(self):
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "model_configs.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._configs = {m["id"]: m for m in data.get("embedding_models", [])}
        except Exception as e:
            # 这里的 fallback 逻辑
            self._configs = {}
            print(f"[ModelConfigManager] 无法加载配置: {e}")

    def get_model_config(self, model_id: str) -> Optional[Dict[str, Any]]:
        """获取指定模型的配置信息，增加智能兜底"""
        if not model_id:
            return None
        
        # 提取模型名称：如果包含 /，取最后一个 / 后面的部分，否则取全部
        extracted_model_name = model_id.split('/')[-1].lower() if '/' in model_id else model_id.lower()
        
        # 1. 完整匹配配置表
        for mid, config in self._configs.items():
            if extracted_model_name == mid.lower():
                return config
        
        # 2. 智能兜底：根据命名关键词推断
        # 针对长文本模型的特征词
        long_context_keywords = ["8k", "long", "32k", "128k", "jina-v2", "jina-v3", "m3", "qwen"]
        if any(kw in extracted_model_name for kw in long_context_keywords):
            return {
                "id": "generic-long-context",
                "max_tokens": 8192,
                "safe_tokens": 2048,
                "recommend_chars": 1200,
                "type": "fallback-long"
            }
            
        # 默认为最保守的 512 架构（BERT系）
        return {
            "id": "generic-standard",
            "max_tokens": 512,
            "safe_tokens": 400,
            "recommend_chars": 400,
            "type": "fallback-standard"
        }

    def get_safe_token_limit(self, model_id: str, default: int = 400) -> int:
        """获取指定模型的安全 Token 限制"""
        config = self.get_model_config(model_id)
        return config.get("safe_tokens", default) if config else default

    def get_recommend_chars(self, model_id: str, default: int = 400) -> int:
        """获取指定模型的推荐分块字符数"""
        config = self.get_model_config(model_id)
        return config.get("recommend_chars", default) if config else default

model_config_manager = ModelConfigManager()
