"""
Tests for SimpleRetrievalAgent scoring semantics and the shared
get_simple_fallback_agent helper.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.agents.retrieval_agent_simple import SimpleRetrievalAgent
from src.retrieval import get_simple_fallback_agent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def guideline_db():
    """Return a small in-memory guideline list used across tests."""
    return [
        {
            "id": "g1",
            "title": "急性上呼吸道感染诊疗指南",
            "content": "咳嗽、发热、鼻塞、咽痛等症状的处理方案",
            "keywords": ["咳嗽", "发热", "上呼吸道感染", "感冒"],
            "metadata": {"category": "呼吸内科"},
        },
        {
            "id": "g2",
            "title": "高血压管理指南",
            "content": "血压控制目标及药物治疗方案",
            "keywords": ["高血压", "血压", "降压"],
            "metadata": {"category": "心血管内科"},
        },
        {
            "id": "g3",
            "title": "糖尿病诊疗指南",
            "content": "血糖监测、饮食控制及胰岛素使用方案",
            "keywords": ["糖尿病", "血糖", "胰岛素"],
            "metadata": {"category": "内分泌科"},
        },
    ]


@pytest.fixture
def agent(guideline_db):
    """Provide a SimpleRetrievalAgent with injected guideline data."""
    with patch.object(SimpleRetrievalAgent, "_load_guidelines"):
        a = SimpleRetrievalAgent()
        a.guidelines = guideline_db
        return a


# ---------------------------------------------------------------------------
# _calculate_relevance scoring semantics
# ---------------------------------------------------------------------------


class TestCalculateRelevance:
    """Lock the exact scoring weights and accumulation rules."""

    def test_keyword_match_weights_2(self, agent, guideline_db):
        """Each keyword match contributes +2.0 to the score."""
        g = guideline_db[0]  # keywords: ["咳嗽", "发热", "上呼吸道感染", "感冒"]
        score = agent._calculate_relevance(["咳嗽"], g)
        # "咳嗽" matches keyword "咳嗽" → 2.0
        # "咳嗽" is in title "急性上呼吸道感染诊疗指南"? No.
        # "咳嗽" is in content? Yes → 0.5
        assert score == 2.0 + 0.5

    def test_title_match_weights_1(self, agent, guideline_db):
        """Each title match contributes +1.0 to the score."""
        g = guideline_db[1]  # title: "高血压管理指南"
        # keywords: ["高血压", "血压", "降压"]
        # content: "血压控制目标及药物治疗方案"
        score = agent._calculate_relevance(["高血压"], g)
        # keyword matches: "高血压" in "高血压" → 2.0
        #                  "血压" in "高血压" → 2.0  (substring match)
        # title: "高血压" in "高血压管理指南" → 1.0
        # content: "高血压" in "血压控制目标..." → No
        assert score == 2.0 + 2.0 + 1.0

    def test_content_match_weights_0_5(self, agent, guideline_db):
        """Content substring match contributes +0.5 per symptom."""
        g = guideline_db[2]  # content: "血糖监测、饮食控制及胰岛素使用方案"
        score = agent._calculate_relevance(["血糖监测"], g)
        # no keyword match for "血糖监测" in keywords ["糖尿病","血糖","胰岛素"]
        #   — but "血糖" is in keyword and "血糖监测" contains "血糖"? Let's check:
        #   symptom "血糖监测" vs keyword "血糖": "血糖" in "血糖监测" → True → 2.0
        # title "糖尿病诊疗指南" does not contain "血糖监测"
        # content "血糖监测、饮食控制及胰岛素使用方案" contains "血糖监测" → 0.5
        assert score == 2.0 + 0.5

    def test_no_match_returns_zero(self, agent, guideline_db):
        """No matches at all yields 0.0."""
        g = guideline_db[0]  # respiratory
        score = agent._calculate_relevance(["骨折"], g)
        assert score == 0.0

    def test_multiple_symptoms_accumulate(self, agent, guideline_db):
        """Multiple matching symptoms each contribute independently."""
        g = guideline_db[0]
        # keywords: ["咳嗽", "发热", "上呼吸道感染", "感冒"]
        # title: "急性上呼吸道感染诊疗指南"
        # content: "咳嗽、发热、鼻塞、咽痛等症状的处理方案"
        score = agent._calculate_relevance(["咳嗽", "发热"], g)
        # "咳嗽": keyword match → 2.0, title? No, content → 0.5  = 2.5
        # "发热": keyword match → 2.0, title? No, content → 0.5  = 2.5
        assert score == 5.0

    def test_cross_match_symptom_in_keyword(self, agent, guideline_db):
        """A short keyword contained in a longer symptom still matches."""
        g = guideline_db[2]  # keywords: ["糖尿病", "血糖", "胰岛素"]
        score = agent._calculate_relevance(["1型糖尿病"], g)
        # "糖尿病" in "1型糖尿病" → True → 2.0
        # title "糖尿病诊疗指南" contains "1型糖尿病"? No
        # content does not contain "1型糖尿病" → 0
        assert score == 2.0

    def test_empty_symptoms_returns_zero(self, agent, guideline_db):
        """Empty symptom list yields 0.0."""
        score = agent._calculate_relevance([], guideline_db[0])
        assert score == 0.0

    def test_empty_guideline_fields_no_error(self, agent):
        """Guideline with empty fields doesn't crash and returns 0.0."""
        g = {"id": "g0", "title": "", "content": "", "keywords": [], "metadata": {}}
        score = agent._calculate_relevance(["anything"], g)
        assert score == 0.0


# ---------------------------------------------------------------------------
# retrieve_by_keywords / retrieve / retrieve_by_symptoms integration
# ---------------------------------------------------------------------------


class TestRetrieveEndToEnd:
    """End-to-end tests for the retrieval pipeline with injected data."""

    @pytest.mark.asyncio
    async def test_returns_sorted_by_score(self, agent):
        """Results come back sorted by descending relevance_score."""
        results = await agent.retrieve_by_keywords(["咳嗽", "高血压"])
        assert len(results) > 0
        # Should be sorted descending
        scores = [r["relevance_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_top_k_respected(self, agent):
        """top_k limits the number of returned results."""
        results = await agent.retrieve_by_keywords(["咳嗽", "发热", "血压"], top_k=2)
        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_zero_score_excluded(self, agent):
        """Guidelines with score 0 are not returned."""
        results = await agent.retrieve_by_keywords(["骨折"])
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_retrieve_splits_query(self, agent):
        """retrieve() splits query by whitespace and delegates."""
        results = await agent.retrieve("咳嗽 发热")
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_retrieve_by_symptoms_delegates(self, agent):
        """retrieve_by_symptoms delegates to retrieve_by_keywords."""
        results = await agent.retrieve_by_symptoms(["血糖"])
        assert len(results) > 0
        assert results[0]["metadata"]["id"] == "g3"

    @pytest.mark.asyncio
    async def test_empty_guidelines_returns_empty(self):
        """Agent with no guidelines returns empty list."""
        with patch.object(SimpleRetrievalAgent, "_load_guidelines"):
            a = SimpleRetrievalAgent()
            a.guidelines = []
        results = await a.retrieve_by_keywords(["咳嗽"])
        assert results == []


# ---------------------------------------------------------------------------
# get_simple_fallback_agent helper
# ---------------------------------------------------------------------------


class TestGetSimpleFallbackAgent:
    """Verify the shared fallback factory returns a working agent."""

    def test_returns_simple_retrieval_agent(self):
        """Helper returns a SimpleRetrievalAgent instance."""
        agent = get_simple_fallback_agent()
        assert isinstance(agent, SimpleRetrievalAgent)

    def test_each_call_returns_new_instance(self):
        """Each invocation creates a fresh agent (no hidden singleton)."""
        a1 = get_simple_fallback_agent()
        a2 = get_simple_fallback_agent()
        assert a1 is not a2
