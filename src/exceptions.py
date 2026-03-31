"""
Custom domain exceptions for Medical Copilot.

Provides a structured exception hierarchy so callers can distinguish
between failure modes (retrieval, generation, dialogue extraction, QA)
without parsing free-form error messages.
"""


class MedicalCopilotError(Exception):
    """Base exception for all Medical Copilot domain errors."""


class RetrievalError(MedicalCopilotError):
    """Raised when clinical-guideline retrieval fails.

    Wrapping the underlying cause lets upstream code decide whether to
    retry, fall back, or surface a user-facing error while still
    preserving the original traceback via exception chaining.
    """


class GenerationError(MedicalCopilotError):
    """Raised when SOAP-note generation fails."""


class ASRError(MedicalCopilotError):
    """Raised when audio transcription fails."""


class RAGError(MedicalCopilotError):
    """Raised when RAG ingestion or indexing fails."""


class DialogueError(MedicalCopilotError):
    """Raised when dialogue / medical-info extraction fails."""


class QAError(MedicalCopilotError):
    """Raised when QA / quality-control checking fails."""
