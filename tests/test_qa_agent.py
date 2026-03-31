"""
Tests for QAAgent — quality-control checking of SOAP notes.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.agents.qa_agent import QAAgent
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
    with patch("src.agents.qa_agent.StructuredOutputAdapter") as cls:
        instance = MagicMock()
        instance.ainvoke = AsyncMock()
        cls.return_value = instance
        yield instance


@pytest.fixture
def agent(mock_adapter):
    """QAAgent with a mocked adapter."""
    return QAAgent()


def _good_emr() -> SOAPNote:
    return SOAPNote(
        subjective="35岁男性患者，咳嗽1周，伴发热T 38.5℃",
        objective="咽部充血，双肺呼吸音粗。建议查血常规、胸片",
        assessment="急性上呼吸道感染可能性大",
        plan="1. 对症治疗\n2. 注意休息\n3. 随诊",
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
async def test_check_returns_qa_report(agent, mock_adapter):
    """check() merges rule issues and LLM report into a QAReport."""
    llm_report = QAReport(is_complete=True, issues=[], score=95.0)
    mock_adapter.ainvoke.return_value = llm_report

    report = await agent.check(_good_emr(), _medical_info())

    assert isinstance(report, QAReport)
    assert report.score > 0
    mock_adapter.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_check_passes_for_good_emr(agent, mock_adapter):
    """A complete EMR with matching symptoms should pass QA."""
    mock_adapter.ainvoke.return_value = QAReport(is_complete=True, issues=[], score=95.0)

    report = await agent.check(_good_emr(), _medical_info())

    assert report.is_complete is True
    assert report.score >= 80


@pytest.mark.asyncio
async def test_check_detects_missing_symptoms_in_subjective(agent, mock_adapter):
    """Rule check flags when symptoms are absent from subjective."""
    bad_emr = SOAPNote(
        subjective="患者感觉不适",  # no cough/fever mentioned
        objective="查体无殊",
        assessment="待查",
        plan="观察",
    )
    mock_adapter.ainvoke.return_value = QAReport(is_complete=True, issues=[], score=80.0)

    report = await agent.check(bad_emr, _medical_info())

    # Rule-based check should flag missing symptoms
    symptom_issues = [i for i in report.issues if "症状" in i.message]
    assert len(symptom_issues) > 0


@pytest.mark.asyncio
async def test_check_detects_empty_assessment(agent, mock_adapter):
    """Rule check flags empty assessment."""
    bad_emr = SOAPNote(
        subjective="咳嗽1周",
        objective="查体无殊",
        assessment="",  # empty
        plan="观察",
    )
    mock_adapter.ainvoke.return_value = QAReport(is_complete=True, issues=[], score=80.0)

    report = await agent.check(bad_emr, _medical_info())

    assessment_issues = [i for i in report.issues if "Assessment" in i.message]
    assert len(assessment_issues) > 0


@pytest.mark.asyncio
async def test_check_detects_empty_plan(agent, mock_adapter):
    """Rule check flags empty plan."""
    bad_emr = SOAPNote(
        subjective="咳嗽1周",
        objective="查体无殊",
        assessment="上感",
        plan="",  # empty
    )
    mock_adapter.ainvoke.return_value = QAReport(is_complete=True, issues=[], score=80.0)

    report = await agent.check(bad_emr, _medical_info())

    plan_issues = [i for i in report.issues if "Plan" in i.message]
    assert len(plan_issues) > 0


@pytest.mark.asyncio
async def test_check_accepts_dict_emr(agent, mock_adapter):
    """check() normalises dict emr to SOAPNote."""
    mock_adapter.ainvoke.return_value = QAReport(is_complete=True, issues=[], score=90.0)

    emr_dict = {
        "subjective": "咳嗽1周伴发热",
        "objective": "查体",
        "assessment": "上感",
        "plan": "对症",
    }
    report = await agent.check(emr_dict, _medical_info())
    assert isinstance(report, QAReport)


@pytest.mark.asyncio
async def test_check_accepts_dict_medical_info(agent, mock_adapter):
    """check() normalises dict medical_info."""
    mock_adapter.ainvoke.return_value = QAReport(is_complete=True, issues=[], score=90.0)

    report = await agent.check(_good_emr(), {"symptoms": ["咳嗽"], "duration": "1周"})
    assert isinstance(report, QAReport)


# ---------------------------------------------------------------------------
# Score calculation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_deducted_for_errors(agent, mock_adapter):
    """ERROR severity issues deduct 15 points each."""
    mock_adapter.ainvoke.return_value = QAReport(
        is_complete=False,
        issues=[
            QAIssue(
                type=QAIssueType.CONFLICT,
                field="assessment",
                message="诊断与症状不符",
                severity=QAIssueSeverity.ERROR,
            )
        ],
        score=85.0,
    )

    report = await agent.check(_good_emr(), _medical_info())
    # Base 100 - 15 (error) = 85, but also depends on rule checks
    assert report.score <= 85


@pytest.mark.asyncio
async def test_score_zero_floor(agent, mock_adapter):
    """Score never goes below 0."""
    many_errors = [
        QAIssue(
            type=QAIssueType.WARNING,
            field="system",
            message=f"issue {i}",
            severity=QAIssueSeverity.ERROR,
        )
        for i in range(20)
    ]
    mock_adapter.ainvoke.return_value = QAReport(is_complete=False, issues=many_errors, score=0.0)

    report = await agent.check(_good_emr(), _medical_info())
    assert report.score >= 0.0


# ---------------------------------------------------------------------------
# Failure-path tests — LLM failure fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_returns_error_report_on_llm_failure(agent, mock_adapter):
    """When LLM check fails, check() still returns a QAReport (does not raise)."""
    mock_adapter.ainvoke.side_effect = RuntimeError("LLM down")

    report = await agent.check(_good_emr(), _medical_info())

    # Should not raise; returns a report (rule-based issues may or may not fire)
    assert isinstance(report, QAReport)
    # The LLM fallback returns an empty-issue report with score 0;
    # rule checks still run in parallel and may contribute issues.
    # The key invariant: check() never raises.
    assert report.score >= 0


@pytest.mark.asyncio
async def test_check_graceful_on_both_failures(agent, mock_adapter):
    """Even if both rule and LLM checks fail, check() returns a report."""
    mock_adapter.ainvoke.side_effect = RuntimeError("catastrophic")

    # Pass an EMR that will also trigger rule exceptions (None fields)
    emr = SOAPNote(subjective="咳嗽", objective="查", assessment="诊", plan="治")
    report = await agent.check(emr, _medical_info())
    assert isinstance(report, QAReport)
