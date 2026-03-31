"""
Tests for DialogueAgent — medical information extraction from conversations.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.agents.dialogue_agent import DialogueAgent
from src.exceptions import DialogueError
from src.models.function_schemas import MedicalInfoExtraction, MedicationInfo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_adapter():
    """Patch StructuredOutputAdapter so no real LLM calls are made."""
    with patch("src.agents.dialogue_agent.StructuredOutputAdapter") as cls:
        instance = MagicMock()
        instance.ainvoke = AsyncMock()
        cls.return_value = instance
        yield instance


@pytest.fixture
def agent(mock_adapter):
    """DialogueAgent with a mocked adapter."""
    return DialogueAgent()


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_returns_medical_info(agent, mock_adapter):
    """extract() returns the MedicalInfoExtraction produced by the adapter."""
    expected = MedicalInfoExtraction(
        symptoms=["咳嗽", "发热"],
        duration="1周",
        severity="中等",
    )
    mock_adapter.ainvoke.return_value = expected

    conversation = [
        {"role": "doctor", "content": "你好，今天有什么不舒服？"},
        {"role": "patient", "content": "我咳嗽已经一周了，还有点发热"},
    ]
    result = await agent.extract(conversation)

    assert result.symptoms == ["咳嗽", "发热"]
    assert result.duration == "1周"
    assert result.severity == "中等"
    mock_adapter.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_extract_formats_conversation_text(agent, mock_adapter):
    """The conversation is formatted into the user message."""
    mock_adapter.ainvoke.return_value = MedicalInfoExtraction()

    conversation = [
        {"role": "doctor", "content": "哪里不舒服？"},
        {"role": "patient", "content": "头疼两天了"},
    ]
    await agent.extract(conversation)

    call_messages = mock_adapter.ainvoke.call_args[0][0]
    user_content = call_messages[1]["content"]
    assert "医生: 哪里不舒服？" in user_content
    assert "患者: 头疼两天了" in user_content


@pytest.mark.asyncio
async def test_extract_with_medications(agent, mock_adapter):
    """extract() handles medication info correctly."""
    expected = MedicalInfoExtraction(
        symptoms=["咳嗽"],
        medications=[MedicationInfo(name="阿莫西林", dosage="0.5g tid")],
        allergies=["青霉素"],
    )
    mock_adapter.ainvoke.return_value = expected

    conversation = [
        {"role": "patient", "content": "我在吃阿莫西林，对青霉素过敏"},
    ]
    result = await agent.extract(conversation)

    assert len(result.medications) == 1
    assert result.medications[0].name == "阿莫西林"
    assert result.allergies == ["青霉素"]


@pytest.mark.asyncio
async def test_extract_empty_conversation(agent, mock_adapter):
    """extract() works with an empty conversation list."""
    mock_adapter.ainvoke.return_value = MedicalInfoExtraction()

    result = await agent.extract([])
    assert result.symptoms == []
    assert result.duration is None


# ---------------------------------------------------------------------------
# Failure-path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_raises_dialogue_error_on_adapter_failure(agent, mock_adapter):
    """Adapter failures are wrapped in DialogueError."""
    mock_adapter.ainvoke.side_effect = RuntimeError("API timeout")

    with pytest.raises(DialogueError, match="Failed to extract medical info"):
        await agent.extract([{"role": "patient", "content": "test"}])


@pytest.mark.asyncio
async def test_extract_preserves_original_exception_chain(agent, mock_adapter):
    """The original exception is chained for debugging."""
    original = RuntimeError("connection refused")
    mock_adapter.ainvoke.side_effect = original

    with pytest.raises(DialogueError) as exc_info:
        await agent.extract([{"role": "patient", "content": "test"}])

    assert exc_info.value.__cause__ is original


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def test_format_conversation_maps_roles(agent):
    """_format_conversation maps doctor/patient to Chinese labels."""
    conv = [
        {"role": "doctor", "content": "你好"},
        {"role": "patient", "content": "头疼"},
    ]
    text = agent._format_conversation(conv)
    assert "医生: 你好" in text
    assert "患者: 头疼" in text


def test_format_conversation_unknown_role(agent):
    """Unknown roles default to 患者."""
    conv = [{"role": "nurse", "content": "量个体温"}]
    text = agent._format_conversation(conv)
    assert "患者: 量个体温" in text
