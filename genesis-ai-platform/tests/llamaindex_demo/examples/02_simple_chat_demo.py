"""
示例 2: 简单对话引擎
演示如何使用 SimpleChatEngine 进行纯 LLM 对话（不使用 RAG）
"""
import sys
import os

# 添加父目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import Settings  # 初始化配置
from core.engines import SimpleChatEngine


def main():
    print("=" * 60)
    print("🤖 示例 2: 简单对话引擎 (Simple Chat)")
    print("=" * 60)
    print()
    
    # 创建引擎
    engine = SimpleChatEngine()
    
    # 示例 1: 同步对话
    print("\n💬 示例 1: 同步对话")
    print("-" * 60)
    message = "你好！请介绍一下你自己。"
    print(f"用户: {message}")
    print("\nAI: ", end="")
    response = engine.chat(message)
    print(response)
    
    # 示例 2: 流式对话
    print("\n\n🌊 示例 2: 流式对话")
    print("-" * 60)
    message = "写一首关于梅花的诗，要求押韵"
    print(f"用户: {message}")
    print("\nAI: ", end="")
    for token in engine.stream_chat(message):
        print(token, end="", flush=True)
    print()
    
    # 示例 3: 多轮对话
    print("\n\n🔄 示例 3: 多轮对话")
    print("-" * 60)
    messages = [
        "我最喜欢的颜色是蓝色",
        "我刚才说我最喜欢什么颜色？",
    ]
    
    for msg in messages:
        print(f"\n用户: {msg}")
        print("AI: ", end="")
        response = engine.chat(msg)
        print(response)
    
    print("\n" + "=" * 60)
    print("✅ 示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
