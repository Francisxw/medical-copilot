"""LlamaGraphRAG 检索冒烟测试。"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.append(".")

from src.agents.retrieval_agent_llamagraph import LlamaGraphRAGAgent


async def main():
    agent = LlamaGraphRAGAgent()

    guide_path = Path("data/guidelines/clinical_guidelines.json")
    if not guide_path.exists():
        print("未找到指南文件，请先运行: python scripts/prepare_data.py")
        return

    with open(guide_path, "r", encoding="utf-8") as f:
        guidelines = json.load(f)

    await agent.load_guidelines(guidelines)
    results = await agent.retrieve_by_symptoms(["咳嗽", "发热", "咽痛"], top_k=3)

    print("=" * 60)
    print("LlamaGraphRAG 检索测试")
    print("=" * 60)
    print(f"结果数量: {len(results)}")

    for i, item in enumerate(results, 1):
        print("-" * 60)
        print(f"结果 {i}")
        print(f"相关度: {item.get('relevance_score', 0):.3f}")
        print(f"来源: {item.get('source', 'unknown')}")
        print(f"标题: {item.get('metadata', {}).get('title', 'N/A')}")
        content = item.get("content", "")
        print(f"内容: {content[:180]}...")


if __name__ == "__main__":
    asyncio.run(main())
