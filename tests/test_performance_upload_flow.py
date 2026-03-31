"""Timing sanity checks for the RAG upload/index flow.

These tests use mocked loaders and an in-memory repository, so the reported numbers are
only lightweight regression signals for API-wrapper overhead. They are intentionally not
treated as real production benchmarks.
"""

from contextlib import contextmanager
import time
import statistics
from types import SimpleNamespace
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from src.main import app
from src.rag import InMemoryDocumentRepository
from src.rag.service import VersionedTenantRAGService, DedupMode
from src.services.rag_service import RAGService
from src.api.routes import get_rag_service, get_versioned_rag_service


MAX_AVG_UPLOAD_MS = 5000.0
MAX_DEDUP_SKIP_MS = 2000.0
MIN_DEDUP_SPEEDUP = 0.5


def _mock_doc() -> SimpleNamespace:
    """Create a mock document with metadata attribute."""
    return SimpleNamespace(metadata={})


def _mock_node(text: str) -> SimpleNamespace:
    """Create a mock node with text and metadata attributes."""
    return SimpleNamespace(text=text, metadata={})


class PerformanceTimer:
    """Simple context manager for timing code blocks."""

    def __init__(self):
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.elapsed: float = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.end_time = time.perf_counter()
        self.elapsed = self.end_time - self.start_time


class TestUploadPerformance:
    """Timing sanity checks for upload endpoints."""

    @staticmethod
    def _summarize_timings(timings: list[float]) -> dict[str, float]:
        avg_time = statistics.mean(timings)
        min_time = min(timings)
        max_time = max(timings)
        stdev_time = statistics.stdev(timings) if len(timings) > 1 else 0.0
        return {
            "avg_ms": avg_time * 1000,
            "min_ms": min_time * 1000,
            "max_ms": max_time * 1000,
            "stdev_ms": stdev_time * 1000,
        }

    @staticmethod
    @contextmanager
    def _create_test_client():
        """Create a TestClient with mocked services for performance testing."""
        # Create shared repository
        shared_repository = InMemoryDocumentRepository()

        # Create mocked loader
        mock_loader = MagicMock()
        mock_loader.load_from_json.return_value = [_mock_doc()]
        mock_loader.load_from_directory.return_value = [_mock_doc()]
        mock_loader.create_nodes.return_value = [_mock_node("chunk-1"), _mock_node("chunk-2")]
        mock_loader.build_index.return_value = None

        # Create services
        versioned_service = VersionedTenantRAGService(
            repository=shared_repository, loader=mock_loader
        )

        legacy_service = RAGService()
        legacy_service._core_service = versioned_service
        legacy_service._loader = versioned_service._loader

        app.dependency_overrides[get_rag_service] = lambda: legacy_service
        app.dependency_overrides[get_versioned_rag_service] = lambda: versioned_service
        try:
            with TestClient(app) as client:
                yield client, shared_repository, mock_loader
        finally:
            app.dependency_overrides.pop(get_rag_service, None)
            app.dependency_overrides.pop(get_versioned_rag_service, None)

    def test_legacy_upload_performance(self):
        """Record timing sanity for the legacy upload endpoint."""
        iterations = 10
        timings = []

        with self._create_test_client() as (client, repo, loader):
            for i in range(iterations):
                file_content = f"test content for iteration {i}".encode()

                with PerformanceTimer() as timer:
                    response = client.post(
                        "/api/rag/upload",
                        files={"file": (f"test_{i}.txt", file_content, "text/plain")},
                    )

                assert response.status_code == 200
                timings.append(timer.elapsed)

        summary = self._summarize_timings(timings)
        print("\n=== Legacy Upload Timing Sanity ===")
        print(f"Iterations: {iterations}")
        print(f"Average: {summary['avg_ms']:.2f}ms")
        print(f"Min: {summary['min_ms']:.2f}ms")
        print(f"Max: {summary['max_ms']:.2f}ms")
        assert summary["avg_ms"] > 0
        assert summary["avg_ms"] < MAX_AVG_UPLOAD_MS
        assert summary["max_ms"] >= summary["min_ms"]

    def test_versioned_upload_performance(self):
        """Record timing sanity for the versioned upload endpoint."""
        iterations = 10
        timings = []

        with self._create_test_client() as (client, repo, loader):
            for i in range(iterations):
                file_content = f"versioned content for iteration {i}".encode()

                with PerformanceTimer() as timer:
                    response = client.post(
                        "/api/rag/upload-versioned",
                        files={"file": (f"versioned_{i}.txt", file_content, "text/plain")},
                        headers={"X-Tenant-ID": "tenant-perf", "X-KB-ID": "kb-perf"},
                    )

                assert response.status_code == 200
                timings.append(timer.elapsed)

        summary = self._summarize_timings(timings)
        print("\n=== Versioned Upload Timing Sanity ===")
        print(f"Iterations: {iterations}")
        print(f"Average: {summary['avg_ms']:.2f}ms")
        print(f"Min: {summary['min_ms']:.2f}ms")
        print(f"Max: {summary['max_ms']:.2f}ms")
        assert summary["avg_ms"] > 0
        assert summary["avg_ms"] < MAX_AVG_UPLOAD_MS
        assert summary["max_ms"] >= summary["min_ms"]

    def test_dedup_skip_performance(self):
        """Record timing sanity for repeated versioned upload with dedup skip."""
        iterations = 10
        first_upload_timings = []
        dedup_timings = []

        with self._create_test_client() as (client, repo, loader):
            # First upload (baseline)
            file_content = b"identical content for dedup performance test"

            for i in range(iterations):
                # First upload (creates document)
                with PerformanceTimer() as timer:
                    response = client.post(
                        "/api/rag/upload-versioned",
                        files={"file": (f"dedup_test_{i}.txt", file_content, "text/plain")},
                        headers={"X-Tenant-ID": f"tenant-dedup-{i}", "X-KB-ID": "kb-dedup"},
                    )
                assert response.status_code == 200
                first_upload_timings.append(timer.elapsed)

                # Second upload (should trigger dedup skip)
                with PerformanceTimer() as timer:
                    response = client.post(
                        "/api/rag/upload-versioned",
                        files={"file": (f"dedup_test_{i}.txt", file_content, "text/plain")},
                        headers={"X-Tenant-ID": f"tenant-dedup-{i}", "X-KB-ID": "kb-dedup"},
                    )
                assert response.status_code == 200
                data = response.json()
                assert data["dedup_hit"] is True  # Verify dedup was triggered
                dedup_timings.append(timer.elapsed)

        first_avg = statistics.mean(first_upload_timings)
        dedup_avg = statistics.mean(dedup_timings)
        speedup = first_avg / dedup_avg if dedup_avg > 0 else float("inf")

        print(f"\n=== Dedup Skip Timing Sanity ===")
        print(f"Iterations: {iterations}")
        print(f"First Upload Avg: {first_avg * 1000:.2f}ms")
        print(f"Dedup Skip Avg: {dedup_avg * 1000:.2f}ms")
        print(f"Relative Speedup: {speedup:.2f}x")
        assert first_avg > 0
        assert dedup_avg > 0
        assert dedup_avg * 1000 < MAX_DEDUP_SKIP_MS
        assert speedup > MIN_DEDUP_SPEEDUP

    def test_combined_performance_summary(self):
        """Generate one mocked timing summary without calling other test methods."""
        print("\n" + "=" * 50)
        print("RAG UPLOAD TIMING SANITY SUMMARY")
        print("=" * 50)

        with self._create_test_client() as (client, repo, loader):
            legacy_timings = []
            versioned_timings = []
            dedup_timings = []
            first_upload_timings = []

            for i in range(5):
                file_content = f"summary-content-{i}".encode()

                with PerformanceTimer() as timer:
                    legacy_response = client.post(
                        "/api/rag/upload",
                        files={"file": (f"legacy_{i}.txt", file_content, "text/plain")},
                    )
                assert legacy_response.status_code == 200
                legacy_timings.append(timer.elapsed)

                with PerformanceTimer() as timer:
                    versioned_response = client.post(
                        "/api/rag/upload-versioned",
                        files={"file": (f"versioned_{i}.txt", file_content, "text/plain")},
                        headers={"X-Tenant-ID": "tenant-summary", "X-KB-ID": f"kb-{i}"},
                    )
                assert versioned_response.status_code == 200
                versioned_timings.append(timer.elapsed)

                with PerformanceTimer() as timer:
                    first_response = client.post(
                        "/api/rag/upload-versioned",
                        files={"file": (f"dedup_{i}.txt", b"repeat", "text/plain")},
                        headers={"X-Tenant-ID": f"tenant-dedup-{i}", "X-KB-ID": "kb-summary"},
                    )
                assert first_response.status_code == 200
                first_upload_timings.append(timer.elapsed)

                with PerformanceTimer() as timer:
                    dedup_response = client.post(
                        "/api/rag/upload-versioned",
                        files={"file": (f"dedup_{i}.txt", b"repeat", "text/plain")},
                        headers={"X-Tenant-ID": f"tenant-dedup-{i}", "X-KB-ID": "kb-summary"},
                    )
                assert dedup_response.status_code == 200
                assert dedup_response.json()["dedup_hit"] is True
                dedup_timings.append(timer.elapsed)

        results = {
            "legacy": self._summarize_timings(legacy_timings),
            "versioned": self._summarize_timings(versioned_timings),
            "dedup_first": self._summarize_timings(first_upload_timings),
            "dedup_skip": self._summarize_timings(dedup_timings),
        }

        print("\n" + "=" * 50)
        print("COMBINED TIMING SANITY SUMMARY")
        print("=" * 50)

        print(f"\n1. Legacy Upload (/api/rag/upload):")
        print(f"   Average: {results['legacy']['avg_ms']:.2f}ms")

        print(f"\n2. Versioned Upload (/api/rag/upload-versioned):")
        print(f"   Average: {results['versioned']['avg_ms']:.2f}ms")

        print(f"\n3. Dedup Skip Performance:")
        print(f"   First Upload: {results['dedup_first']['avg_ms']:.2f}ms")
        print(f"   Dedup Skip: {results['dedup_skip']['avg_ms']:.2f}ms")

        legacy_avg = results["legacy"]["avg_ms"]
        versioned_avg = results["versioned"]["avg_ms"]
        overhead = ((versioned_avg - legacy_avg) / legacy_avg * 100) if legacy_avg > 0 else 0

        print(f"\n4. Versioned vs Legacy Overhead:")
        print(f"   Overhead: {overhead:.1f}%")
        print("   Note: mocked timing sanity only, not a production benchmark")

        print("\n" + "=" * 50)
        assert results["legacy"]["avg_ms"] > 0
        assert results["versioned"]["avg_ms"] > 0
        assert results["dedup_skip"]["avg_ms"] > 0
        assert results["legacy"]["avg_ms"] < MAX_AVG_UPLOAD_MS
        assert results["versioned"]["avg_ms"] < MAX_AVG_UPLOAD_MS
        assert results["dedup_skip"]["avg_ms"] < MAX_DEDUP_SKIP_MS
