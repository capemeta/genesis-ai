"""
示例 1: RAG 对话引擎
演示如何使用 ChatEngine 进行基于文档的问答
"""
import sys
import os

# 添加父目录到 Python 路径，以便导入 core 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import Settings  # 初始化配置
from core.engines import ChatEngine


def main():
    print("=" * 60)
    print("🤖 示例 1: RAG 对话引擎 (Chat Engine)")
    print("=" * 60)
    print()
    
    # 创建引擎
    engine = ChatEngine()
    
    # 示例 1: 检索相关文档
    print("\n📦 示例 1: 检索相关文档")
    print("-" * 60)
    query = "操作指引说了什么？"
    print(f"查询: {query}")
    nodes = engine.retrieve(query)
    print(f"\n检索到 {len(nodes)} 个相关文档片段:")
    for idx, node in enumerate(nodes, 1):
        score = node.score if hasattr(node, 'score') else 1.0
        text_preview = node.node.text[:100] + "..." if len(node.node.text) > 100 else node.node.text
        print(f"\n[{idx}] 相似度: {score:.3f}")
        print(f"内容预览: {text_preview}")
    
    # 示例 2: 同步对话
    print("\n\n💬 示例 2: 同步对话")
    print("-" * 60)
    question = "上下文说了什么？"
    print(f"问题: {question}")
    print("\n回答:")
    response = engine.chat(question)
    print(response)
    
    # 示例 3: 流式对话
    print("\n\n🌊 示例 3: 流式对话")
    print("-" * 60)
    question = "总结一下主要内容"
    print(f"问题: {question}")
    print("\n回答:")
    for token in engine.stream_chat(question):
        print(token, end="", flush=True)
    print()
    
    print("\n" + "=" * 60)
    print("✅ 示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
