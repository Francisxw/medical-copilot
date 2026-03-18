"""
Agent 4: 质控检查Agent
检查病历完整性和质量
使用 OpenAI SDK tools 方式实现 Function Calling
"""

from typing import Dict, List
from loguru import logger

from src.config import get_settings
from src.models.function_schemas import SOAPNote, QAReport, QAIssue
from src.utils.llm_adapter import StructuredOutputAdapter

settings = get_settings()


class QAAgent:
    """
    质控检查Agent - 检查病历质量和完整性
    使用 OpenAI SDK 原生 tools 方式
    """

    def __init__(self):
        # 初始化结构化输出适配器
        self.adapter = StructuredOutputAdapter(
            response_model=QAReport,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            temperature=0.2,
        )

        self.system_prompt = self._build_system_prompt()
        self.rules = self._load_rules()

    def _build_system_prompt(self) -> str:
        """构建质控系统提示词"""
        return """你是一个病历质控专家。请检查以下SOAP病历的质量和完整性。

评分标准：
- 90-100分：优秀，无需修改
- 70-89分：良好，有小问题
- 60-69分：及格，有明显问题
- 60分以下：不及格，需要重写

请检查以下方面：
1. 完整性：所有必要信息是否都已包含
2. 一致性：病历内容是否与原始信息一致
3. 逻辑性：诊断是否与症状匹配，计划是否与诊断匹配
4. 准确性：是否有明显的医学错误

请给出客观评价。"""

    def _load_rules(self) -> List[Dict]:
        """加载规则型质控规则（保留作为补充）"""
        return [
            {
                "name": "检查主诉是否包含症状",
                "field": "subjective",
                "check": lambda emr, info: bool(
                    emr.subjective
                    and any(
                        symptom in emr.subjective
                        for symptom in info.get("symptoms", [])
                    )
                ),
                "error_message": "主诉中未包含患者提及的主要症状",
            },
            {
                "name": "检查病程是否记录",
                "field": "subjective",
                "check": lambda emr, info: (
                    not info.get("duration")
                    or (info.get("duration") and info.get("duration") in emr.subjective)
                ),
                "error_message": "现病史中缺少病程记录",
            },
            {
                "name": "检查评估非空",
                "field": "assessment",
                "check": lambda emr, info: bool(emr.assessment),
                "error_message": "评估（Assessment）部分为空",
            },
            {
                "name": "检查计划非空",
                "field": "plan",
                "check": lambda emr, info: bool(emr.plan),
                "error_message": "计划（Plan）部分为空",
            },
        ]

    async def check(self, emr: SOAPNote | Dict, medical_info: Dict) -> QAReport:
        """
        检查病历质量

        Args:
            emr: 待检查的SOAP病历（支持 Pydantic 模型或 dict）
            medical_info: 原始医疗信息

        Returns:
            QAReport: 质控报告（Pydantic模型）
        """
        try:
            logger.info("开始质控检查...")

            # 统一病历输入，避免 dict/object 混用导致属性访问失败
            normalized_emr = self._normalize_emr(emr)

            # 并行执行：规则检查和 LLM 检查
            import asyncio

            # 注意：medical_info 可能是 Pydantic 模型或字典
            if hasattr(medical_info, "model_dump"):
                medical_info_dict = medical_info.model_dump()
            else:
                medical_info_dict = medical_info

            rule_issues, llm_report = await asyncio.gather(
                asyncio.to_thread(self._check_rules, normalized_emr, medical_info_dict),
                self._check_with_llm(normalized_emr, medical_info_dict),
                return_exceptions=True,
            )

            # 处理异常
            if isinstance(rule_issues, Exception):
                logger.error(f"规则检查失败: {rule_issues}")
                rule_issues = []
            if isinstance(llm_report, Exception):
                logger.error(f"LLM检查失败: {llm_report}")
                llm_report = QAReport(is_complete=False, issues=[], score=0.0)

            # 合并问题
            all_issues = rule_issues + llm_report.issues

            # 计算分数
            score = self._calculate_score(normalized_emr, all_issues, medical_info_dict)

            # 判断完整性
            is_complete = not any(issue.severity == "error" for issue in all_issues)

            report = QAReport(is_complete=is_complete, issues=all_issues, score=score)

            logger.info(f"[OK] 质控完成，分数: {score:.1f}")
            return report

        except Exception as e:
            logger.error(f"[FAIL] 质控检查失败: {str(e)}")
            return QAReport(
                is_complete=False,
                issues=[
                    QAIssue(
                        type="error",
                        field="system",
                        message=f"质控检查出错: {str(e)}",
                        severity="error",
                    )
                ],
                score=0.0,
            )

    def _check_rules(self, emr: SOAPNote, medical_info: Dict) -> List[QAIssue]:
        """使用规则进行检查"""
        issues = []

        for rule in self.rules:
            try:
                if not rule["check"](emr, medical_info):
                    issues.append(
                        QAIssue(
                            type="missing",
                            field=rule["field"],
                            message=rule["error_message"],
                            severity="warning",
                        )
                    )
            except Exception as e:
                logger.warning(f"规则检查失败 ({rule['name']}): {str(e)}")

        return issues

    def _normalize_emr(self, emr: SOAPNote | Dict) -> SOAPNote:
        """统一病历输入为 SOAPNote 模型"""
        if isinstance(emr, SOAPNote):
            return emr
        return SOAPNote.model_validate(emr)

    async def _check_with_llm(self, emr: SOAPNote, medical_info: Dict) -> QAReport:
        """使用LLM进行检查"""
        try:
            import json

            medical_text = json.dumps(medical_info, ensure_ascii=False, default=str)

            # 构建消息列表
            messages = [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": f"""请检查以下SOAP病历：

病历内容：
Subjective: {emr.subjective}
Objective: {emr.objective}
Assessment: {emr.assessment}
Plan: {emr.plan}

原始医疗信息：
{medical_text}

请给出质控报告。""",
                },
            ]

            # 使用适配器获取结构化报告
            report = await self.adapter.ainvoke(messages)
            return report

        except Exception as e:
            logger.error(f"LLM质控失败: {str(e)}")
            return QAReport(is_complete=False, issues=[], score=0.0)

    def _calculate_score(
        self, emr: SOAPNote, issues: List[QAIssue], medical_info: Dict
    ) -> float:
        """计算质量分数"""
        base_score = 100.0

        # 根据问题严重程度扣分
        for issue in issues:
            if issue.severity == "error":
                base_score -= 15
            elif issue.severity == "warning":
                base_score -= 5
            elif issue.severity == "info":
                base_score -= 1

        # 检查SOAP各部分是否完整
        for section in ["subjective", "objective", "assessment", "plan"]:
            section_content = getattr(emr, section, "")
            if not section_content or len(section_content) < 10:
                base_score -= 5

        # 检查是否包含关键信息
        symptoms = medical_info.get("symptoms", [])
        if symptoms:
            symptom_mentioned = any(symptom in emr.subjective for symptom in symptoms)
            if not symptom_mentioned:
                base_score -= 10

        return max(0.0, min(100.0, base_score))


# 测试代码
if __name__ == "__main__":
    import asyncio

    async def test():
        agent = QAAgent()

        test_emr = SOAPNote(
            subjective="患者咳嗽1周",
            objective="建议查血常规",
            assessment="上呼吸道感染",
            plan="对症治疗",
        )

        medical_info = {"symptoms": ["咳嗽", "发热"], "duration": "1周"}

        report = await agent.check(test_emr, medical_info)
        print(f"\n质控结果:")
        print(f"是否完整: {report.is_complete}")
        print(f"分数: {report.score}")
        print(f"问题数: {len(report.issues)}")
        if report.issues:
            print("\n问题列表:")
            for issue in report.issues:
                print(f"  - [{issue.severity}] {issue.field}: {issue.message}")

    asyncio.run(test())
