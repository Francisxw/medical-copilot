"""
Tests for RevisionAgent — revising SOAP notes based on QA issues.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.agents.revision_agent import RevisionAgent
from src.models.function_schemas import (
    MedicalInfoExtraction,
    MedicationInfo,
    QAIssue,
    QAIssueSeverity,
    QAIssueType,
    QAReport,
    SOAPNote,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_adapter():
    """Patch StructuredOutputAdapter so no real LLM calls are made."""
    with patch("src.agents.revision_agent.StructuredOutputAdapter") as cls:
        instance = MagicMock()
        instance.ainvoke = AsyncMock()
        cls.return_value = instance
        yield instance


@pytest.fixture
def agent(mock_adapter):
    """RevisionAgent with a mocked adapter."""
    return RevisionAgent()


def _original_emr() -> SOAPNote:
    return SOAPNote(
        subjective="患者不适",
        objective="查体无殊",
        assessment="待查",
        plan="观察",
    )


def _revised_emr() -> SOAPNote:
    return SOAPNote(
        subjective="35岁男性，咳嗽1周伴发热T 38.5℃",
        objective="咽部充血，双肺呼吸音粗。建议查血常规、胸片",
        assessment="急性上呼吸道感染可能性大",
        plan="1. 对症治疗\n2. 注意休息\n3. 随诊",
    )


def _qa_report_with_issues() -> QAReport:
    return QAReport(
        is_complete=False,
        issues=[
            QAIssue(
                type=QAIssueType.MISSING,
                field="subjective",
                message="主诉中未包含患者提及的主要症状",
                severity=QAIssueSeverity.WARNING,
            ),
            QAIssue(
                type=QAIssueType.MISSING,
                field="assessment",
                message="评估（Assessment）部分为空",
                severity=QAIssueSeverity.ERROR,
            ),
        ],
        score=65.0,
    )


def _medical_info() -> MedicalInfoExtraction:
    return MedicalInfoExtraction(
        symptoms=["咳嗽", "发热"],
        duration="1周",
        severity="中等",
    )


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_returns_revised_emr(agent, mock_adapter):
    """revise() returns the revised SOAPNote from the adapter."""
    revised = _revised_emr()
    mock_adapter.ainvoke.return_value = revised

    result = await agent.revise(
        original_emr=_original_emr(),
        qa_report=_qa_report_with_issues(),
        medical_info=_medical_info(),
    )

    assert result.subjective == revised.subjective
    assert result.assessment == revised.assessment
    mock_adapter.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_revise_passes_issues_to_prompt(agent, mock_adapter):
    """Issues are formatted into the user message."""
    mock_adapter.ainvoke.return_value = _revised_emr()

    await agent.revise(
        original_emr=_original_emr(),
        qa_report=_qa_report_with_issues(),
        medical_info=_medical_info(),
    )

    call_messages = mock_adapter.ainvoke.call_args[0][0]
    user_content = call_messages[1]["content"]
    assert "主诉中未包含患者提及的主要症状" in user_content
    assert "评估（Assessment）部分为空" in user_content


@pytest.mark.asyncio
async def test_revise_passes_medical_info_to_prompt(agent, mock_adapter):
    """Medical info is formatted into the user message."""
    mock_adapter.ainvoke.return_value = _revised_emr()

    await agent.revise(
        original_emr=_original_emr(),
        qa_report=_qa_report_with_issues(),
        medical_info=_medical_info(),
    )

    call_messages = mock_adapter.ainvoke.call_args[0][0]
    user_content = call_messages[1]["content"]
    assert "咳嗽" in user_content
    assert "发热" in user_content


@pytest.mark.asyncio
async def test_revise_accepts_dict_emr(agent, mock_adapter):
    """revise() normalises dict original_emr to SOAPNote."""
    mock_adapter.ainvoke.return_value = _revised_emr()

    emr_dict = {"subjective": "不适", "objective": "查", "assessment": "", "plan": "观察"}
    result = await agent.revise(
        original_emr=emr_dict,
        qa_report=_qa_report_with_issues(),
        medical_info=_medical_info(),
    )
    assert isinstance(result, SOAPNote)


@pytest.mark.asyncio
async def test_revise_accepts_dict_medical_info(agent, mock_adapter):
    """revise() normalises dict medical_info."""
    mock_adapter.ainvoke.return_value = _revised_emr()

    result = await agent.revise(
        original_emr=_original_emr(),
        qa_report=_qa_report_with_issues(),
        medical_info={"symptoms": ["咳嗽"], "duration": "1周"},
    )
    assert isinstance(result, SOAPNote)


@pytest.mark.asyncio
async def test_revise_with_no_issues(agent, mock_adapter):
    """revise() works even when QA report has no issues."""
    mock_adapter.ainvoke.return_value = _revised_emr()
    empty_report = QAReport(is_complete=True, issues=[], score=95.0)

    result = await agent.revise(
        original_emr=_original_emr(),
        qa_report=empty_report,
        medical_info=_medical_info(),
    )
    assert isinstance(result, SOAPNote)


# ---------------------------------------------------------------------------
# Failure-path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_propagates_adapter_error(agent, mock_adapter):
    """revise() lets adapter exceptions propagate (no wrapping)."""
    mock_adapter.ainvoke.side_effect = RuntimeError("LLM unavailable")

    with pytest.raises(RuntimeError, match="LLM unavailable"):
        await agent.revise(
            original_emr=_original_emr(),
            qa_report=_qa_report_with_issues(),
            medical_info=_medical_info(),
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def test_format_issues_empty(agent):
    text = agent._format_issues([])
    assert "无质控问题" in text


def test_format_issues_with_items(agent):
    issues = [
        QAIssue(
            type=QAIssueType.MISSING,
            field="subjective",
            message="缺少症状",
            severity=QAIssueSeverity.WARNING,
        ),
        QAIssue(
            type=QAIssueType.CONFLICT,
            field="plan",
            message="剂量冲突",
            severity=QAIssueSeverity.ERROR,
        ),
    ]
    text = agent._format_issues(issues)
    assert "缺少症状" in text
    assert "剂量冲突" in text
    assert "1." in text
    assert "2." in text


def test_format_medical_info(agent):
    info = MedicalInfoExtraction(
        symptoms=["咳嗽"],
        medications=[MedicationInfo(name="布洛芬", dosage="400mg prn")],
    )
    text = agent._format_medical_info(info)
    assert "咳嗽" in text
    assert "布洛芬" in text
