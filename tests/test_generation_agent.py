"""
Tests for GenerationAgent — SOAP note generation.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.agents.generation_agent import GenerationAgent
from src.exceptions import GenerationError
from src.models.function_schemas import MedicalInfoExtraction, MedicationInfo, SOAPNote


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_adapter():
    """Patch StructuredOutputAdapter so no real LLM calls are made."""
    with patch("src.agents.generation_agent.StructuredOutputAdapter") as cls:
        instance = MagicMock()
        instance.ainvoke = AsyncMock()
        cls.return_value = instance
        yield instance


@pytest.fixture
def agent(mock_adapter):
    """GenerationAgent with a mocked adapter."""
    return GenerationAgent()


def _sample_medical_info() -> MedicalInfoExtraction:
    return MedicalInfoExtraction(
        symptoms=["咳嗽", "发热"],
        duration="1周",
        severity="中等",
        medications=[MedicationInfo(name="阿莫西林", dosage="0.5g tid")],
        allergies=["青霉素"],
        past_history=["高血压"],
        family_history=["糖尿病"],
    )


def _sample_soap() -> SOAPNote:
    return SOAPNote(
        subjective="35岁男性，咳嗽1周伴发热T 38.5℃",
        objective="建议查血常规、胸片",
        assessment="急性上呼吸道感染",
        plan="对症治疗，注意休息",
    )


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_returns_soap_note(agent, mock_adapter):
    """generate() returns the SOAPNote produced by the adapter."""
    expected = _sample_soap()
    mock_adapter.ainvoke.return_value = expected

    result = await agent.generate(
        patient_info={"age": 35, "gender": "男"},
        medical_info=_sample_medical_info(),
        guidelines=[],
    )

    assert result.subjective == expected.subjective
    assert result.assessment == expected.assessment
    mock_adapter.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_generate_accepts_dict_medical_info(agent, mock_adapter):
    """generate() normalises dict medical_info to MedicalInfoExtraction."""
    mock_adapter.ainvoke.return_value = _sample_soap()

    medical_dict = {"symptoms": ["咳嗽"], "duration": "3天"}
    result = await agent.generate(
        patient_info={"age": 30, "gender": "女"},
        medical_info=medical_dict,
        guidelines=[],
    )
    assert isinstance(result, SOAPNote)


@pytest.mark.asyncio
async def test_generate_with_guidelines(agent, mock_adapter):
    """Guidelines are formatted into the prompt."""
    mock_adapter.ainvoke.return_value = _sample_soap()

    guidelines = [
        {"content": "上呼吸道感染诊疗指南摘要", "relevance_score": 0.92},
    ]
    await agent.generate(
        patient_info={"age": 40, "gender": "男"},
        medical_info=_sample_medical_info(),
        guidelines=guidelines,
    )

    call_messages = mock_adapter.ainvoke.call_args[0][0]
    user_content = call_messages[1]["content"]
    assert "上呼吸道感染诊疗指南摘要" in user_content


@pytest.mark.asyncio
async def test_generate_empty_guidelines(agent, mock_adapter):
    """Empty guidelines list is handled gracefully."""
    mock_adapter.ainvoke.return_value = _sample_soap()

    result = await agent.generate(
        patient_info={"age": 25, "gender": "女"},
        medical_info=_sample_medical_info(),
        guidelines=[],
    )
    assert isinstance(result, SOAPNote)


# ---------------------------------------------------------------------------
# Failure-path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_raises_generation_error_on_failure(agent, mock_adapter):
    """Adapter failures are wrapped in GenerationError."""
    mock_adapter.ainvoke.side_effect = RuntimeError("LLM unavailable")

    with pytest.raises(GenerationError, match="Failed to generate SOAP note"):
        await agent.generate(
            patient_info={"age": 35, "gender": "男"},
            medical_info=_sample_medical_info(),
            guidelines=[],
        )


@pytest.mark.asyncio
async def test_generate_chains_original_exception(agent, mock_adapter):
    """Original exception is preserved in the chain."""
    original = RuntimeError("timeout")
    mock_adapter.ainvoke.side_effect = original

    with pytest.raises(GenerationError) as exc_info:
        await agent.generate(
            patient_info={"age": 35, "gender": "男"},
            medical_info=_sample_medical_info(),
            guidelines=[],
        )
    assert exc_info.value.__cause__ is original


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def test_format_patient_info(agent):
    text = agent._format_patient_info({"age": 50, "gender": "女"})
    assert "50" in text
    assert "女" in text


def test_format_patient_info_missing_keys(agent):
    text = agent._format_patient_info({})
    assert "未知" in text


def test_format_medical_info(agent):
    info = _sample_medical_info()
    text = agent._format_medical_info(info)
    assert "咳嗽" in text
    assert "阿莫西林" in text
    assert "青霉素" in text


def test_format_guidelines_empty(agent):
    text = agent._format_guidelines([])
    assert "暂无" in text


def test_format_guidelines_with_items(agent):
    items = [{"content": "指南内容A" * 300, "relevance_score": 0.85}]
    text = agent._format_guidelines(items)
    assert "指南内容A" in text
    assert "0.85" in text
