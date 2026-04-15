"""
示例 3: 工具调用 Agent
演示如何使用 FunctionAgentEngine 创建能调用工具的 AI Agent
"""
import sys
import os
import asyncio

# 添加父目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import Settings  # 初始化配置
from core.engines import FunctionAgentEngine


# 定义工具函数
def multiply(a: float, b: float) -> float:
    """Multiply two numbers together."""
    print(f"  🔧 [工具调用] multiply({a}, {b})")
    return a * b


def add(a: float, b: float) -> float:
    """Add two numbers together."""
    print(f"  🔧 [工具调用] add({a}, {b})")
    return a + b


def get_weather(city: str) -> str:
    """Get the weather for a given city (mock function)."""
    print(f"  🔧 [工具调用] get_weather('{city}')")
    # 模拟天气数据
    weather_data = {
        "北京": "晴天，15°C",
        "上海": "多云，18°C",
        "广州": "小雨，22°C",
    }
    return weather_data.get(city, f"{city}的天气数据暂不可用")


async def main():
    print("=" * 60)
    print("🤖 示例 3: 工具调用 Agent (Function Agent)")
    print("=" * 60)
    print()
    
    # 创建引擎（注册工具）
    tools = [multiply, add, get_weather]
    engine = FunctionAgentEngine(
        tools=tools,
        system_prompt="You are a helpful assistant with access to mathematical operations and weather information."
    )
    
    # 示例 1: 数学计算
    print("\n🧮 示例 1: 数学计算")
    print("-" * 60)
    question = "What is 1234 multiplied by 4567?"
    print(f"用户: {question}")
    print("\nAI 处理中...")
    response = await engine.achat(question)
    print(f"\nAI: {response}")
    
    # 示例 2: 复杂计算
    print("\n\n🔢 示例 2: 复杂计算")
    print("-" * 60)
    question = "Calculate (123 + 456) * 789"
    print(f"用户: {question}")
    print("\nAI 处理中...")
    response = await engine.achat(question)
    print(f"\nAI: {response}")
    
    # 示例 3: 查询天气
    print("\n\n🌤️ 示例 3: 查询天气")
    print("-" * 60)
    question = "北京和上海今天的天气怎么样？"
    print(f"用户: {question}")
    print("\nAI 处理中...")
    response = await engine.achat(question)
    print(f"\nAI: {response}")
    
    print("\n" + "=" * 60)
    print("✅ 示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
