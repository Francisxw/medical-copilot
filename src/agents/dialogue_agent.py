"""
Agent 1: 对话解析Agent
从医患对话中提取结构化医疗信息
使用 OpenAI SDK tools 方式实现 Function Calling
"""

from typing import Dict, List
from loguru import logger

from src.config import get_settings
from src.models.function_schemas import MedicalInfoExtraction
from src.utils.llm_adapter import StructuredOutputAdapter

settings = get_settings()


class DialogueAgent:
    """
    对话解析Agent - 负责从对话中提取医疗信息
    使用 OpenAI SDK 原生 tools 方式
    """

    def __init__(self):
        # 初始化结构化输出适配器
        self.adapter = StructuredOutputAdapter(
            response_model=MedicalInfoExtraction,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            temperature=0.3,
        )

        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专业的医疗信息提取助手。请从医患对话中提取关键医疗信息。

请提取以下信息：
- 症状（symptoms）：患者提到的所有症状
- 病程（duration）：症状持续的时间
- 严重程度（severity）：症状的严重程度
- 用药记录（medications）：当前用药，包括药名和剂量
- 过敏史（allergies）：药物或其他过敏史
- 既往病史（past_history）：既往疾病史
- 家族史（family_history）：家族疾病史

如果对话中未提及某些信息，请返回空列表或null。"""

    async def extract(
        self, conversation: List[Dict[str, str]]
    ) -> MedicalInfoExtraction:
        """
        从对话中提取医疗信息

        Args:
            conversation: 对话历史列表

        Returns:
            MedicalInfoExtraction: 提取的医疗信息（Pydantic模型）
        """
        try:
            # 格式化对话为可读文本
            conversation_text = self._format_conversation(conversation)

            logger.info("开始提取医疗信息...")

            # 构建消息列表
            messages = [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": f"请从以下对话中提取医疗信息：\n\n{conversation_text}",
                },
            ]

            # 使用适配器获取结构化输出
            result = await self.adapter.ainvoke(messages)

            logger.info(f"[OK] 成功提取医疗信息: {len(result.symptoms)}个症状")
            return result
        except Exception as e:
            logger.error(f"[FAIL] 医疗信息提取失败: {str(e)}")
            raise

    def _format_conversation(self, conversation: List[Dict[str, str]]) -> str:
        """格式化对话为文本"""
        formatted = []
        for turn in conversation:
            role = "医生" if turn.get("role") == "doctor" else "患者"
            formatted.append(f"{role}: {turn.get('content', '')}")
        return "\n".join(formatted)


# 测试代码
if __name__ == "__main__":
    import asyncio

    async def test():
        agent = DialogueAgent()
        test_conversation = [
            {"role": "doctor", "content": "你好，今天有什么不舒服？"},
            {
                "role": "patient",
                "content": "我咳嗽已经一周了，还有点发热，体温38度左右。有点头疼，没有食欲。",
            },
        ]
        result = await agent.extract(test_conversation)
        print("\n提取结果：")
        print(f"症状: {result.symptoms}")
        print(f"病程: {result.duration}")
        print(f"严重程度: {result.severity}")
        print(f"用药记录: {result.medications}")
        print(f"过敏史: {result.allergies}")
        print(f"既往病史: {result.past_history}")
        print(f"家族史: {result.family_history}")

    asyncio.run(test())
