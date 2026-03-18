"""检索模式对比脚本（simple vs llamagraph）。"""

import asyncio
import sys

sys.path.append(".")

from src.agents.retrieval_agent_simple import SimpleRetrievalAgent
from src.agents.retrieval_agent_llamagraph import LlamaGraphRAGAgent


async def main():
    symptoms = ["咳嗽", "发热"]

    simple_agent = SimpleRetrievalAgent()
    simple_results = await simple_agent.retrieve_by_symptoms(symptoms, top_k=3)

    graph_agent = LlamaGraphRAGAgent()
    graph_results = await graph_agent.retrieve_by_symptoms(symptoms, top_k=3)

    print("=" * 60)
    print("关键词检索结果")
    print("=" * 60)
    for idx, item in enumerate(simple_results, 1):
        print(
            f"{idx}. {item.get('metadata', {}).get('title', 'N/A')} | {item.get('relevance_score', 0):.3f}"
        )

    print("\n" + "=" * 60)
    print("LlamaGraphRAG 检索结果")
    print("=" * 60)
    for idx, item in enumerate(graph_results, 1):
        print(
            f"{idx}. {item.get('metadata', {}).get('title', 'N/A')} | {item.get('relevance_score', 0):.3f}"
        )


if __name__ == "__main__":
    asyncio.run(main())
