"""
Function Agent Engine - 工具调用引擎
支持调用自定义工具的 Agent
"""
from typing import Optional, List, Callable
from llama_index.core.agent.workflow import FunctionAgent
from ..config import Settings
from .base import BaseEngine


class FunctionAgentEngine(BaseEngine):
    """工具调用 Agent 引擎"""
    
    def __init__(
        self, 
        tools: List[Callable],
        system_prompt: Optional[str] = None,
        data_dir: Optional[str] = None
    ):
        """
        初始化 Agent 引擎
        
        Args:
            tools: 工具函数列表
            system_prompt: 系统提示词
            data_dir: 数据目录（此引擎不使用，但保持接口一致）
        """
        super().__init__(data_dir)
        self.tools = tools
        self.system_prompt = system_prompt or "You are a helpful assistant with access to tools."
        self.agent = FunctionAgent(
            tools=self.tools,
            llm=Settings.llm,
            system_prompt=self.system_prompt,
        )
        print(f"🚀 Function Agent 引擎初始化完成，已加载 {len(tools)} 个工具")
    
    def chat(self, message: str) -> str:
        """同步对话（注意：FunctionAgent 主要支持异步）"""
        import asyncio
        return asyncio.run(self.achat(message))
    
    async def achat(self, message: str) -> str:
        """异步对话"""
        response = await self.agent.run(message)
        return str(response)
    
    def add_tool(self, tool: Callable):
        """添加工具"""
        self.tools.append(tool)
        # 重新创建 agent
        self.agent = FunctionAgent(
            tools=self.tools,
            llm=Settings.llm,
            system_prompt=self.system_prompt,
        )
