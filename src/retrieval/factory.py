"""
检索策略工厂
根据配置创建对应的检索策略实例
"""

from loguru import logger
from typing import Dict, Type

from src.retrieval import RetrievalMode
from src.config import get_settings

settings = get_settings()


# 检索策略映射表
RETRIEVAL_STRATEGY_MAP: Dict[RetrievalMode, str] = {
    RetrievalMode.SIMPLE: "src.agents.retrieval_agent_simple.SimpleRetrievalAgent",
    RetrievalMode.VECTOR: "src.agents.retrieval_agent_vector.VectorRetrievalAgent",
    RetrievalMode.LLAMAGRAPH: "src.agents.retrieval_agent_llamagraph.LlamaGraphRAGAgent",
    RetrievalMode.LLAMAINDEX: "src.agents.retrieval_agent_llamaindex.LlamaIndexRetrievalAgent",
}


def create_retrieval_strategy(
    mode: str | RetrievalMode | None = None, **kwargs
) -> "BaseRetrievalStrategy":
    """
    创建检索策略实例

    Args:
        mode: 检索模式字符串或枚举，默认从配置读取
        **kwargs: 额外参数传递给检索策略构造函数

    Returns:
        检索策略实例

    Raises:
        ValueError: 当模式不支持时
    """
    # 解析模式
    if mode is None:
        mode = settings.retrieval_mode

    if isinstance(mode, str):
        mode = RetrievalMode.from_string(mode)

    # 获取策略类路径
    strategy_path = RETRIEVAL_STRATEGY_MAP.get(mode)
    if not strategy_path:
        logger.warning(f"未知检索模式: {mode}，自动回退到 simple")
        strategy_path = RETRIEVAL_STRATEGY_MAP[RetrievalMode.SIMPLE]
        mode = RetrievalMode.SIMPLE

    # 动态导入策略类
    try:
        module_path, class_name = strategy_path.rsplit(".", 1)
        import importlib

        module = importlib.import_module(module_path)
        strategy_class = getattr(module, class_name)

        logger.info(f"✅ 创建检索策略: {mode.value}")

        # 创建实例（传递额外参数）
        return strategy_class(**kwargs)

    except ImportError as e:
        logger.error(f"❌ 无法导入检索策略 {strategy_path}: {str(e)}")
        # 回退到 simple
        logger.warning("回退到 SimpleRetrievalAgent")
        from src.agents.retrieval_agent_simple import SimpleRetrievalAgent

        return SimpleRetrievalAgent(**kwargs)
    except Exception as e:
        logger.error(f"❌ 创建检索策略失败: {str(e)}")
        raise


def get_retrieval_mode() -> RetrievalMode:
    """获取当前检索模式"""
    return RetrievalMode.from_string(settings.retrieval_mode)


# 便捷函数：创建默认检索策略
def create_default_retrieval_strategy():
    """创建默认检索策略（从配置读取）"""
    return create_retrieval_strategy(settings.retrieval_mode)


# 导出
__all__ = [
    "RetrievalMode",
    "create_retrieval_strategy",
    "create_default_retrieval_strategy",
    "get_retrieval_mode",
]
