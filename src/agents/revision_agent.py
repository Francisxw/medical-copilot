"""
Agent 5: 病历修改Agent
根据质控报告中的问题修改SOAP病历
使用 OpenAI SDK tools 方式实现 Function Calling
"""

from typing import Any, Dict, List
from loguru import logger

from src.config import get_settings
from src.models.function_schemas import MedicalInfoExtraction, QAIssue, QAReport, SOAPNote
from src.utils.llm_adapter import StructuredOutputAdapter

settings = get_settings()


class RevisionAgent:
    """
    病历修改Agent - 根据质控问题修改SOAP病历
    使用 OpenAI SDK 原生 tools 方式
    """

    def __init__(self):
        # 初始化结构化输出适配器
        self.adapter = StructuredOutputAdapter(
            response_model=SOAPNote,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            temperature=0.3,
        )

        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专业的病历修改助手。请根据质控报告中指出的问题，对现有SOAP病历进行修改。

修改原则：
1. 仅修改质控报告中指出的问题，不要改动没有问题的部分
2. 保持病历的专业性和准确性
3. 如果问题是信息缺失，根据已有信息合理补充
4. 如果问题是内容冲突，修正为与原始信息一致的描述
5. 保持SOAP格式的完整性

请输出修改后的完整SOAP病历。"""

    async def revise(
        self,
        original_emr: SOAPNote | Dict[str, Any],
        qa_report: QAReport,
        medical_info: MedicalInfoExtraction | Dict[str, Any],
    ) -> SOAPNote:
        """
        根据质控问题修改病历

        Args:
            original_emr: 当前SOAP病历
            qa_report: 质控报告
            medical_info: 原始医疗信息

        Returns:
            SOAPNote: 修改后的SOAP病历（Pydantic模型）
        """
        try:
            logger.info("开始修改病历...")

            # 统一输入类型
            normalized_emr = self._normalize_emr(original_emr)
            normalized_medical_info = self._normalize_medical_info(medical_info)
            issues_text = self._format_issues(qa_report.issues)
            medical_info_text = self._format_medical_info(normalized_medical_info)

            # 构建消息列表
            messages = [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": f"""请根据以下质控问题修改病历：

当前病历：
Subjective: {normalized_emr.subjective}
Objective: {normalized_emr.objective}
Assessment: {normalized_emr.assessment}
Plan: {normalized_emr.plan}

原始医疗信息：
{medical_info_text}

质控问题：
{issues_text}

请输出修改后的完整SOAP病历。""",
                },
            ]

            # 使用适配器获取结构化输出
            revised_emr = await self.adapter.ainvoke(messages)

            logger.info(f"[OK] 成功修改病历，处理 {len(qa_report.issues)} 个问题")
            return revised_emr
        except Exception as e:
            logger.error(f"[FAIL] 病历修改失败: {str(e)}", exc_info=True)
            raise

    def _normalize_emr(self, emr: SOAPNote | Dict[str, Any]) -> SOAPNote:
        """统一病历输入为 SOAPNote 模型"""
        if isinstance(emr, SOAPNote):
            return emr
        return SOAPNote.model_validate(emr)

    def _normalize_medical_info(
        self,
        medical_info: MedicalInfoExtraction | Dict[str, Any],
    ) -> MedicalInfoExtraction:
        """统一医疗信息输入为 MedicalInfoExtraction 模型。"""
        if isinstance(medical_info, MedicalInfoExtraction):
            return medical_info
        return MedicalInfoExtraction.model_validate(medical_info)

    def _format_medical_info(self, medical_info: MedicalInfoExtraction) -> str:
        """格式化原始医疗信息。"""
        return "\n".join(
            [
                f"症状: {', '.join(medical_info.symptoms) or '无'}",
                f"病程: {medical_info.duration or '未提及'}",
                f"严重程度: {medical_info.severity or '未提及'}",
                f"用药: {', '.join(m.name for m in medical_info.medications) or '无'}",
                f"过敏史: {', '.join(medical_info.allergies) or '无'}",
                f"既往史: {', '.join(medical_info.past_history) or '无'}",
                f"家族史: {', '.join(medical_info.family_history) or '无'}",
            ]
        )

    def _format_issues(self, issues: List[QAIssue]) -> str:
        """格式化质控问题列表"""
        if not issues:
            return "无质控问题"

        formatted = []
        for i, issue in enumerate(issues, 1):
            formatted.append(f"{i}. [{issue.severity}] {issue.field}: {issue.message}")

        return "\n".join(formatted) if formatted else "无质控问题"
