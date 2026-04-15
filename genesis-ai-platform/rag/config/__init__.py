"""
RAG 配置解析模块。

统一收敛：
- 原始配置的层级合并
- effective_*_config 计算
- 任务链配置快照构建
"""

from .effective import build_effective_config, resolve_effective_pipeline_config

__all__ = [
    "build_effective_config",
    "resolve_effective_pipeline_config",
]
