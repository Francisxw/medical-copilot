"""
单元测试 - Agent测试
"""
import pytest
import asyncio
from src.agents.dialogue_agent import DialogueAgent
from src.agents.generation_agent import GenerationAgent
from src.agents.qa_agent import QAAgent


@pytest.mark.asyncio
class TestDialogueAgent:
    """测试对话解析Agent"""

    async def test_extract_basic_info(self):
        """测试基本医疗信息提取"""
        agent = DialogueAgent()

        conversation = [
            {"role": "doctor", "content": "今天有什么不舒服？"},
            {"role": "patient", "content": "我咳嗽已经一周了，还有发热"}
        ]

        result = await agent.extract(conversation)

        assert "symptoms" in result
        assert len(result["symptoms"]) > 0
        assert "咳嗽" in result["symptoms"] or "发热" in result["symptoms"]


@pytest.mark.asyncio
class TestGenerationAgent:
    """测试病历生成Agent"""

    async def test_generate_basic_emr(self):
        """测试基本病历生成"""
        agent = GenerationAgent()

        patient_info = {"age": 35, "gender": "男"}
        medical_info = {
            "symptoms": ["咳嗽", "发热"],
            "duration": "1周",
            "severity": "中等"
        }

        result = await agent.generate(patient_info, medical_info, [])

        assert "subjective" in result
        assert "objective" in result
        assert "assessment" in result
        assert "plan" in result


@pytest.mark.asyncio
class TestQAAgent:
    """测试质控Agent"""

    async def test_qa_check(self):
        """测试质控检查"""
        agent = QAAgent()

        emr = {
            "subjective": "患者咳嗽1周",
            "objective": "建议查血常规",
            "assessment": "上感",
            "plan": "对症治疗"
        }

        medical_info = {"symptoms": ["咳嗽"]}

        result = await agent.check(emr, medical_info)

        assert "is_complete" in result
        assert "issues" in result
        assert "score" in result
        assert 0 <= result["score"] <= 100
