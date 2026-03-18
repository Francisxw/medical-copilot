"""
Agent 3: 病历生成Agent
生成结构化SOAP格式病历
使用 OpenAI SDK tools 方式实现 Function Calling
"""

from typing import Dict, List
from loguru import logger

from src.config import get_settings
from src.models.function_schemas import SOAPNote, MedicalInfoExtraction
from src.utils.llm_adapter import StructuredOutputAdapter

settings = get_settings()


class GenerationAgent:
    """
    病历生成Agent - 生成SOAP格式病历
    使用 OpenAI SDK 原生 tools 方式
    """

    def __init__(self):
        # 初始化结构化输出适配器
        self.adapter = StructuredOutputAdapter(
            response_model=SOAPNote,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            temperature=settings.temperature,
        )

        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专业的病历书写助手。请根据提供的医疗信息和临床指南，生成一份标准的SOAP格式病历。

请生成SOAP格式病历，包含以下四个部分：

1. Subjective（主诉/现病史）：
   - 主诉：患者的主要症状及持续时间
   - 现病史：症状的详细描述、起病情况、伴随症状等

2. Objective（客观检查）：
   - 根据症状建议的体格检查
   - 建议的实验室/影像学检查

3. Assessment（评估）：
   - 初步诊断或鉴别诊断
   - 病情严重程度评估

4. Plan（计划）：
   - 进一步检查计划
   - 治疗方案建议
   - 健康教育

请确保内容专业、准确、完整。"""

    async def generate(
        self,
        patient_info: Dict,
        medical_info: MedicalInfoExtraction | Dict,
        guidelines: List[Dict],
    ) -> SOAPNote:
        """
        生成SOAP病历

        Args:
            patient_info: 患者基本信息
            medical_info: 提取的医疗信息（支持 Pydantic 模型或 dict）
            guidelines: 检索到的临床指南

        Returns:
            SOAPNote: 生成的SOAP病历（Pydantic模型）
        """
        try:
            logger.info("开始生成SOAP病历...")

            # 统一医疗信息输入类型，避免 dict/object 混用导致崩溃
            normalized_medical_info = self._normalize_medical_info(medical_info)

            # 格式化输入
            patient_text = self._format_patient_info(patient_info)
            medical_text = self._format_medical_info(normalized_medical_info)
            guidelines_text = self._format_guidelines(guidelines)

            # 构建消息列表
            messages = [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": f"""请根据以下信息生成SOAP病历：

患者信息：
{patient_text}

提取的医疗信息：
{medical_text}

相关临床指南：
{guidelines_text}

请生成SOAP格式病历。""",
                },
            ]

            # 使用适配器获取结构化输出
            soap_note = await self.adapter.ainvoke(messages)

            logger.info("[OK] 成功生成SOAP病历")
            return soap_note
        except Exception as e:
            logger.error(f"[FAIL] SOAP病历生成失败: {str(e)}")
            raise

    def _format_patient_info(self, patient_info: Dict) -> str:
        """格式化患者信息"""
        return (
            f"年龄: {patient_info.get('age', '未知')}\n"
            f"性别: {patient_info.get('gender', '未知')}"
        )

    def _normalize_medical_info(
        self, medical_info: MedicalInfoExtraction | Dict
    ) -> MedicalInfoExtraction:
        """统一医疗信息输入为 MedicalInfoExtraction 模型"""
        if isinstance(medical_info, MedicalInfoExtraction):
            return medical_info
        return MedicalInfoExtraction.model_validate(medical_info)

    def _format_medical_info(self, medical_info: MedicalInfoExtraction) -> str:
        """格式化医疗信息"""
        lines = [
            f"症状: {', '.join(medical_info.symptoms) or '无'}",
            f"病程: {medical_info.duration or '未提及'}",
            f"严重程度: {medical_info.severity or '未提及'}",
            f"用药: {', '.join([m.name for m in medical_info.medications]) or '无'}",
            f"过敏史: {', '.join(medical_info.allergies) or '无'}",
            f"既往史: {', '.join(medical_info.past_history) or '无'}",
            f"家族史: {', '.join(medical_info.family_history) or '无'}",
        ]
        return "\n".join(lines)

    def _format_guidelines(self, guidelines: List[Dict]) -> str:
        """格式化临床指南"""
        if not guidelines:
            return "暂无相关指南"

        formatted = []
        for i, guideline in enumerate(guidelines, 1):
            formatted.append(
                f"{i}. {guideline['content'][:200]}... "
                f"(相关度: {guideline.get('relevance_score', 0):.2f})"
            )
        return "\n".join(formatted)


# 测试代码
if __name__ == "__main__":
    import asyncio

    async def test():
        agent = GenerationAgent()

        patient_info = {"age": 35, "gender": "男"}
        medical_info = MedicalInfoExtraction(
            symptoms=["咳嗽", "发热"], duration="1周", severity="中等"
        )
        guidelines = []

        result = await agent.generate(patient_info, medical_info, guidelines)
        print("\n=== SOAP病历 ===")
        print(f"Subjective: {result.subjective}")
        print(f"Objective: {result.objective}")
        print(f"Assessment: {result.assessment}")
        print(f"Plan: {result.plan}")

    asyncio.run(test())
