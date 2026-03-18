"""
检索策略接口定义
定义统一的检索接口，所有检索实现需遵循此接口
"""

from typing import List, Dict, Any, Protocol
from abc import ABC, abstractmethod


class RetrievalStrategy(Protocol):
    """检索策略协议 - 定义统一的检索接口"""

    async def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        检索相关临床指南（基于query文本）

        Args:
            query: 查询文本
            top_k: 返回前K个结果

        Returns:
            检索到的指南列表
        """
        ...

    async def retrieve_by_symptoms(
        self, symptoms: List[str], top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        基于症状列表检索指南

        Args:
            symptoms: 症状列表
            top_k: 返回前K个结果

        Returns:
            检索到的指南
        """
        ...


class BaseRetrievalStrategy(ABC):
    """检索策略基类 - 提供通用实现"""

    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """检索相关临床指南"""
        pass

    @abstractmethod
    async def retrieve_by_symptoms(
        self, symptoms: List[str], top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """基于症状列表检索指南"""
        pass


# 检索模式枚举
from enum import Enum


class RetrievalMode(str, Enum):
    """检索模式枚举"""

    SIMPLE = "simple"
    VECTOR = "vector"
    LLAMAGRAPH = "llamagraph"
    LLAMAINDEX = "llamaindex"

    @classmethod
    def from_string(cls, mode: str) -> "RetrievalMode":
        """从字符串转换为枚举"""
        mode_lower = mode.lower()
        for m in cls:
            if m.value == mode_lower:
                return m
        # 默认回退到 simple
        logger.warning(f"未知检索模式: {mode}，自动回退到 simple")
        return cls.SIMPLE


from loguru import logger
