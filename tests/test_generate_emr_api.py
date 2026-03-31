"""
Tests for the POST /api/generate-emr endpoint.

Uses FastAPI dependency_overrides to inject a mocked workflow,
following the same pattern as test_api_legacy_upload.py.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from src.main import app
from src.api.routes import get_workflow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _workflow_result(
    session_id="sess-123",
    iteration_count=1,
    error_message=None,
):
    """Return a dict matching what MedicalCopilotWorkflow.run() returns."""
    return {
        "session_id": session_id,
        "timestamp": "2025-01-01T00:00:00",
        "patient_info": {"age": 35, "gender": "男"},
        "extracted_info": {
            "symptoms": ["咳嗽", "发热"],
            "duration": "1周",
            "severity": "中等",
            "medications": [],
            "allergies": [],
            "past_history": [],
            "family_history": [],
        },
        "final_emr": {
            "subjective": "35岁男性，咳嗽1周伴发热",
            "objective": "建议查血常规",
            "assessment": "急性上呼吸道感染",
            "plan": "对症治疗",
        },
        "qa_report": {
            "is_complete": True,
            "issues": [],
            "score": 92.0,
        },
        "iteration_count": iteration_count,
        "error_message": error_message,
    }


@pytest.fixture
def mock_workflow():
    """Mock workflow with a default successful result."""
    wf = MagicMock()
    wf.run = AsyncMock(return_value=_workflow_result())
    wf.retrieval_mode = "simple"
    return wf


@pytest.fixture
def client(mock_workflow):
    """TestClient with workflow dependency overridden."""
    app.dependency_overrides[get_workflow] = lambda: mock_workflow
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_workflow, None)


def _valid_payload():
    return {
        "conversation": [
            {"role": "doctor", "content": "今天哪里不舒服？"},
            {"role": "patient", "content": "咳嗽一周了，还有点发热"},
        ],
        "patient_info": {"age": 35, "gender": "男"},
    }


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_generate_emr_happy_path(client, mock_workflow):
    """Successful EMR generation returns 200 with expected fields."""
    response = client.post("/api/generate-emr", json=_valid_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "sess-123"
    assert data["iteration_count"] == 1
    assert data["final_emr"] is not None
    assert data["final_emr"]["subjective"] == "35岁男性，咳嗽1周伴发热"
    assert data["qa_report"]["is_complete"] is True
    assert data["qa_report"]["score"] == 92.0
    mock_workflow.run.assert_called_once()


def test_generate_emr_passes_conversation_to_workflow(client, mock_workflow):
    """Conversation turns are converted to dicts for the workflow."""
    client.post("/api/generate-emr", json=_valid_payload())

    call_args = mock_workflow.run.call_args[0][0]
    assert call_args["conversation"] == [
        {"role": "doctor", "content": "今天哪里不舒服？"},
        {"role": "patient", "content": "咳嗽一周了，还有点发热"},
    ]


def test_generate_emr_passes_patient_info_to_workflow(client, mock_workflow):
    """Patient info is forwarded to the workflow."""
    client.post("/api/generate-emr", json=_valid_payload())

    call_args = mock_workflow.run.call_args[0][0]
    pi = call_args["patient_info"]
    assert pi["age"] == 35
    assert pi["gender"] == "男"


def test_generate_emr_response_includes_patient_info(client, mock_workflow):
    """Response echoes back the patient info from the request."""
    data = client.post("/api/generate-emr", json=_valid_payload()).json()
    assert data["patient_info"]["age"] == 35
    assert data["patient_info"]["gender"] == "男"


def test_generate_emr_with_multiple_turns(client, mock_workflow):
    """Multi-turn conversation is accepted."""
    payload = {
        "conversation": [
            {"role": "doctor", "content": "你好"},
            {"role": "patient", "content": "头疼"},
            {"role": "doctor", "content": "多久了？"},
            {"role": "patient", "content": "三天"},
        ],
        "patient_info": {"age": 28, "gender": "女"},
    }
    response = client.post("/api/generate-emr", json=payload)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Validation error tests
# ---------------------------------------------------------------------------


def test_generate_emr_missing_conversation(client):
    """Missing conversation field returns 422."""
    response = client.post(
        "/api/generate-emr",
        json={"patient_info": {"age": 35, "gender": "男"}},
    )
    assert response.status_code == 422


def test_generate_emr_empty_conversation(client):
    """Empty conversation list returns 422 (min_length=1)."""
    response = client.post(
        "/api/generate-emr",
        json={"conversation": [], "patient_info": {"age": 35, "gender": "男"}},
    )
    assert response.status_code == 422


def test_generate_emr_missing_patient_info(client):
    """Missing patient_info returns 422."""
    response = client.post(
        "/api/generate-emr",
        json={"conversation": [{"role": "doctor", "content": "hi"}]},
    )
    assert response.status_code == 422


def test_generate_emr_invalid_role(client):
    """Invalid conversation role returns 422."""
    response = client.post(
        "/api/generate-emr",
        json={
            "conversation": [{"role": "nurse", "content": "hello"}],
            "patient_info": {"age": 35, "gender": "男"},
        },
    )
    assert response.status_code == 422


def test_generate_emr_invalid_gender(client):
    """Invalid gender returns 422."""
    response = client.post(
        "/api/generate-emr",
        json={
            "conversation": [{"role": "doctor", "content": "hi"}],
            "patient_info": {"age": 35, "gender": "其他"},
        },
    )
    assert response.status_code == 422


def test_generate_emr_empty_content(client):
    """Empty conversation content returns 422 (min_length=1)."""
    response = client.post(
        "/api/generate-emr",
        json={
            "conversation": [{"role": "doctor", "content": ""}],
            "patient_info": {"age": 35, "gender": "男"},
        },
    )
    assert response.status_code == 422


def test_generate_emr_negative_age(client):
    """Negative age returns 422 (ge=0)."""
    response = client.post(
        "/api/generate-emr",
        json={
            "conversation": [{"role": "doctor", "content": "hi"}],
            "patient_info": {"age": -1, "gender": "男"},
        },
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Workflow error tests
# ---------------------------------------------------------------------------


def test_generate_emr_workflow_error_message(client, mock_workflow):
    """When workflow returns an error_message, the endpoint returns 500."""
    mock_workflow.run.return_value = _workflow_result(error_message="提取失败")

    response = client.post("/api/generate-emr", json=_valid_payload())
    assert response.status_code == 500
    assert "提取失败" in response.json()["detail"]


def test_generate_emr_workflow_exception_propagates(client, mock_workflow):
    """Unhandled workflow exception propagates (global handler logs it)."""
    mock_workflow.run.side_effect = RuntimeError("catastrophic failure")

    # In TestClient, unhandled exceptions that the global handler converts to
    # JSONResponse may still propagate as Python exceptions depending on the
    # ASGI transport.  We verify the side-effect is set and the call doesn't
    # silently succeed with a 200.
    try:
        response = client.post("/api/generate-emr", json=_valid_payload())
        # If we get here, the global handler caught it and returned 500.
        assert response.status_code == 500
    except RuntimeError:
        # Also acceptable: TestClient propagates the exception.
        pass


# ---------------------------------------------------------------------------
# Revision loop reflected in response
# ---------------------------------------------------------------------------


def test_generate_emr_reflects_revision_count(client, mock_workflow):
    """iteration_count > 1 in the workflow result is passed through."""
    mock_workflow.run.return_value = _workflow_result(iteration_count=2)

    data = client.post("/api/generate-emr", json=_valid_payload()).json()
    assert data["iteration_count"] == 2


def test_generate_emr_null_final_emr(client, mock_workflow):
    """When final_emr is None, the response field is null."""
    result = _workflow_result()
    result["final_emr"] = None
    mock_workflow.run.return_value = result

    data = client.post("/api/generate-emr", json=_valid_payload()).json()
    assert data["final_emr"] is None


def test_generate_emr_null_qa_report(client, mock_workflow):
    """When qa_report is None, the response field is null."""
    result = _workflow_result()
    result["qa_report"] = None
    mock_workflow.run.return_value = result

    data = client.post("/api/generate-emr", json=_valid_payload()).json()
    assert data["qa_report"] is None
