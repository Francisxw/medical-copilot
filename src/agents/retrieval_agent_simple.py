"""
简化版检索Agent - 使用关键词匹配替代向量检索
适用于没有Embedding API的场景（如DeepSeek）
"""
from typing import List, Dict, Any
from loguru import logger
import json
from pathlib import Path

from src.config import get_settings

settings = get_settings()


class SimpleRetrievalAgent:
    """
    简化版知识检索Agent
    使用关键词匹配而非向量检索
    """

    def __init__(self):
        self.guidelines = []
        self._load_guidelines()

    def _load_guidelines(self):
        """从文件加载临床指南"""
        guide_file = Path("data/guidelines/clinical_guidelines.json")

        if guide_file.exists():
            with open(guide_file, "r", encoding="utf-8") as f:
                self.guidelines = json.load(f)
            logger.info(f"已加载 {len(self.guidelines)} 条临床指南")
        else:
            logger.warning("指南文件不存在，请先运行: python scripts/prepare_data.py")

    def _calculate_relevance(self, symptoms: List[str], guideline: Dict) -> float:
        """计算症状与指南的相关度（基于关键词匹配）"""
        guideline_keywords = guideline.get("keywords", [])
        guideline_content = guideline.get("content", "")
        guideline_title = guideline.get("title", "")

        # 计算匹配分数
        score = 0.0

        # 关键词匹配（权重高）
        for symptom in symptoms:
            for keyword in guideline_keywords:
                if symptom in keyword or keyword in symptom:
                    score += 2.0

        # 标题匹配
        for symptom in symptoms:
            if symptom in guideline_title:
                score += 1.0

        # 内容匹配（权重低）
        for symptom in symptoms:
            if symptom in guideline_content:
                score += 0.5

        return score

    async def retrieve(
        self,
        query: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        检索相关临床指南（基于query文本）

        Args:
            query: 查询文本
            top_k: 返回前K个结果

        Returns:
            检索到的指南列表
        """
        # 简单分词（实际应用可用更复杂的NLP）
        keywords = query.split()

        return await self.retrieve_by_keywords(keywords, top_k)

    async def retrieve_by_symptoms(
        self,
        symptoms: List[str],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        基于症状列表检索指南

        Args:
            symptoms: 症状列表
            top_k: 返回前K个结果

        Returns:
            检索到的指南
        """
        return await self.retrieve_by_keywords(symptoms, top_k)

    async def retrieve_by_keywords(
        self,
        keywords: List[str],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        基于关键词检索指南

        Args:
            keywords: 关键词列表
            top_k: 返回前K个结果

        Returns:
            检索到的指南
        """
        if not self.guidelines:
            logger.warning("指南库为空")
            return []

        try:
            logger.info(f"检索相关指南: {', '.join(keywords)}")

            # 计算每个指南的相关度
            scored_guidelines = []
            for guideline in self.guidelines:
                score = self._calculate_relevance(keywords, guideline)
                if score > 0:  # 只返回有匹配的结果
                    scored_guidelines.append({
                        "content": guideline["content"],
                        "metadata": {
                            "id": guideline["id"],
                            "title": guideline["title"],
                            "category": guideline["metadata"]["category"]
                        },
                        "relevance_score": score
                    })

            # 按相关度排序
            scored_guidelines.sort(key=lambda x: x["relevance_score"], reverse=True)

            # 返回top_k结果
            results = scored_guidelines[:top_k]

            logger.info(f"检索到 {len(results)} 条相关指南")
            return results

        except Exception as e:
            logger.error(f"检索失败: {str(e)}")
            return []


# 测试代码
if __name__ == "__main__":
    import asyncio

    async def test():
        agent = SimpleRetrievalAgent()

        # 测试检索
        results = await agent.retrieve_by_symptoms(["咳嗽", "发热"])
        print(f"\n检索到 {len(results)} 条指南:")
        for i, guideline in enumerate(results, 1):
            print(f"\n指南 {i}:")
            print(f"标题: {guideline['metadata']['title']}")
            print(f"相关度: {guideline['relevance_score']:.1f}")
            print(f"内容: {guideline['content'][:100]}...")

    asyncio.run(test())
