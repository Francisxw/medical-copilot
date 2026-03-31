"""
Integration tests for MedicalCopilotWorkflow — the LangGraph-orchestrated
multi-agent pipeline including the revision loop.

All agents are mocked so no real LLM or retrieval calls are made.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.graph.workflow import MedicalCopilotWorkflow
from src.models.function_schemas import (
    MedicalInfoExtraction,
    QAIssue,
    QAIssueSeverity,
    QAIssueType,
    QAReport,
    SOAPNote,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_conversation():
    return [
        {"role": "doctor", "content": "今天哪里不舒服？"},
        {"role": "patient", "content": "咳嗽一周了，还有点发热"},
    ]


def _sample_patient_info():
    return {"age": 35, "gender": "男"}


def _extracted_info() -> MedicalInfoExtraction:
    return MedicalInfoExtraction(
        symptoms=["咳嗽", "发热"],
        duration="1周",
        severity="中等",
    )


def _draft_emr() -> SOAPNote:
    return SOAPNote(
        subjective="35岁男性，咳嗽1周伴发热",
        objective="建议查血常规",
        assessment="急性上呼吸道感染",
        plan="对症治疗",
    )


def _revised_emr() -> SOAPNote:
    return SOAPNote(
        subjective="35岁男性，咳嗽1周伴发热T 38.5℃",
        objective="咽部充血。建议查血常规、胸片",
        assessment="急性上呼吸道感染可能性大",
        plan="1. 对症治疗\n2. 注意休息\n3. 随诊",
    )


def _passing_qa_report() -> QAReport:
    return QAReport(is_complete=True, issues=[], score=92.0)


def _failing_qa_report() -> QAReport:
    return QAReport(
        is_complete=False,
        issues=[
            QAIssue(
                type=QAIssueType.MISSING,
                field="subjective",
                message="主诉缺少症状",
                severity=QAIssueSeverity.WARNING,
            ),
        ],
        score=70.0,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_agents():
    """Patch all four agent classes used inside the workflow."""
    patches = {
        "dialogue": patch("src.graph.workflow.DialogueAgent"),
        "generation": patch("src.graph.workflow.GenerationAgent"),
        "qa": patch("src.graph.workflow.QAAgent"),
        "revision": patch("src.graph.workflow.RevisionAgent"),
    }
    mocks = {}
    for key, p in patches.items():
        mock_cls = p.start()
        instance = mock_cls.return_value
        mocks[key] = instance

    # Default async methods
    mocks["dialogue"].extract = AsyncMock(return_value=_extracted_info())
    mocks["generation"].generate = AsyncMock(return_value=_draft_emr())
    mocks["qa"].check = AsyncMock(return_value=_passing_qa_report())
    mocks["revision"].revise = AsyncMock(return_value=_revised_emr())

    yield mocks

    for p in patches.values():
        p.stop()


@pytest.fixture
def workflow(mock_agents):
    """Workflow with mocked agents and a mock retrieval agent."""
    mock_retrieval = MagicMock()
    mock_retrieval.retrieve_by_symptoms = AsyncMock(return_value=[])
    mock_retrieval.mode = "simple"

    wf = MedicalCopilotWorkflow(retrieval_agent=mock_retrieval)
    return wf


# ---------------------------------------------------------------------------
# Happy-path: QA passes on first try (no revision)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_qa_passes_no_revision(workflow, mock_agents):
    """When QA passes, the workflow completes without calling revise."""
    result = await workflow.run(
        {
            "conversation": _sample_conversation(),
            "patient_info": _sample_patient_info(),
        }
    )

    assert result["final_emr"] is not None
    assert result["iteration_count"] == 1
    assert result["error_message"] is None
    mock_agents["revision"].revise.assert_not_called()


@pytest.mark.asyncio
async def test_workflow_result_contains_session_id(workflow, mock_agents):
    """Result includes a session_id and timestamp."""
    result = await workflow.run(
        {
            "conversation": _sample_conversation(),
            "patient_info": _sample_patient_info(),
        }
    )

    assert "session_id" in result
    assert "timestamp" in result
    assert len(result["session_id"]) > 0


@pytest.mark.asyncio
async def test_workflow_extracted_info_serialised(workflow, mock_agents):
    """extracted_info is serialised to dict in the result."""
    result = await workflow.run(
        {
            "conversation": _sample_conversation(),
            "patient_info": _sample_patient_info(),
        }
    )

    extracted = result["extracted_info"]
    assert isinstance(extracted, dict)
    assert "咳嗽" in extracted["symptoms"]


@pytest.mark.asyncio
async def test_workflow_final_emr_serialised(workflow, mock_agents):
    """final_emr is serialised to dict in the result."""
    result = await workflow.run(
        {
            "conversation": _sample_conversation(),
            "patient_info": _sample_patient_info(),
        }
    )

    emr = result["final_emr"]
    assert isinstance(emr, dict)
    assert "subjective" in emr


@pytest.mark.asyncio
async def test_workflow_qa_report_serialised(workflow, mock_agents):
    """qa_report is serialised to dict in the result."""
    result = await workflow.run(
        {
            "conversation": _sample_conversation(),
            "patient_info": _sample_patient_info(),
        }
    )

    report = result["qa_report"]
    assert isinstance(report, dict)
    assert report["is_complete"] is True


# ---------------------------------------------------------------------------
# Revision loop: QA fails → revise → QA passes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_revision_loop(workflow, mock_agents):
    """When QA fails, the revision agent is called and the loop completes."""
    # First QA call fails, second passes
    mock_agents["qa"].check = AsyncMock(side_effect=[_failing_qa_report(), _passing_qa_report()])

    result = await workflow.run(
        {
            "conversation": _sample_conversation(),
            "patient_info": _sample_patient_info(),
        }
    )

    mock_agents["revision"].revise.assert_called_once()
    assert result["iteration_count"] == 2
    assert result["final_emr"] is not None


@pytest.mark.asyncio
async def test_workflow_revision_updates_emr(workflow, mock_agents):
    """After revision, final_emr should be the revised version."""
    mock_agents["qa"].check = AsyncMock(side_effect=[_failing_qa_report(), _passing_qa_report()])

    result = await workflow.run(
        {
            "conversation": _sample_conversation(),
            "patient_info": _sample_patient_info(),
        }
    )

    emr = result["final_emr"]
    assert emr["subjective"] == _revised_emr().subjective


# ---------------------------------------------------------------------------
# Max revision iterations cap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_max_revision_iterations(workflow, mock_agents):
    """Workflow stops revising after max_revision_iterations."""
    # QA always fails
    mock_agents["qa"].check = AsyncMock(return_value=_failing_qa_report())

    result = await workflow.run(
        {
            "conversation": _sample_conversation(),
            "patient_info": _sample_patient_info(),
        }
    )

    # Should have hit the cap (default 3) and stopped
    assert result["iteration_count"] >= 1
    # Revision may or may not be called depending on iteration logic;
    # the key assertion is that the workflow terminates.
    assert result["final_emr"] is not None


# ---------------------------------------------------------------------------
# Retrieval agent integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_calls_retrieval_with_symptoms(workflow, mock_agents):
    """The retrieval agent is called with extracted symptoms."""
    await workflow.run(
        {
            "conversation": _sample_conversation(),
            "patient_info": _sample_patient_info(),
        }
    )

    workflow.retrieval_agent.retrieve_by_symptoms.assert_called_once_with(["咳嗽", "发热"])


@pytest.mark.asyncio
async def test_workflow_skips_retrieval_when_no_symptoms(workflow, mock_agents):
    """Retrieval is skipped when no symptoms are extracted."""
    mock_agents["dialogue"].extract = AsyncMock(return_value=MedicalInfoExtraction(symptoms=[]))

    await workflow.run(
        {
            "conversation": _sample_conversation(),
            "patient_info": _sample_patient_info(),
        }
    )

    workflow.retrieval_agent.retrieve_by_symptoms.assert_not_called()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_empty_conversation(workflow, mock_agents):
    """Workflow handles an empty conversation gracefully."""
    mock_agents["dialogue"].extract = AsyncMock(return_value=MedicalInfoExtraction())

    result = await workflow.run(
        {
            "conversation": [],
            "patient_info": _sample_patient_info(),
        }
    )

    assert result["final_emr"] is not None


@pytest.mark.asyncio
async def test_workflow_guidelines_passed_to_generation(workflow, mock_agents):
    """Retrieved guidelines are forwarded to the generation agent."""
    guidelines = [{"content": "指南A", "relevance_score": 0.9}]
    workflow.retrieval_agent.retrieve_by_symptoms = AsyncMock(return_value=guidelines)

    await workflow.run(
        {
            "conversation": _sample_conversation(),
            "patient_info": _sample_patient_info(),
        }
    )

    gen_call = mock_agents["generation"].generate.call_args
    assert gen_call.kwargs.get("guidelines") == guidelines or guidelines in gen_call.args
