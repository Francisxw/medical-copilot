"""
语音识别模块测试
"""

from io import BytesIO
import asyncio
import math
from types import SimpleNamespace
import sys
import wave

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import router
from src.services.asr_service import ASRService, ASRServiceError
from src.services.medical_terms import build_medical_corpus


def build_test_wav(sample_rate: int = 16000, duration_seconds: float = 0.1) -> bytes:
    """构造一个最小可用的 WAV 音频字节流。"""
    frame_count = int(sample_rate * duration_seconds)
    amplitude = 12000
    frames = bytearray()

    for index in range(frame_count):
        sample = int(amplitude * math.sin(2 * math.pi * 440 * index / sample_rate))
        frames.extend(sample.to_bytes(2, byteorder="little", signed=True))

    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(frames))

    return buffer.getvalue()


def create_test_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_build_medical_corpus_contains_core_terms():
    corpus = build_medical_corpus()

    assert "高血压" in corpus
    assert "阿司匹林" in corpus
    assert "咳嗽" in corpus
    assert "CT" in corpus


def test_transcribe_audio_endpoint_returns_transcript(monkeypatch: pytest.MonkeyPatch):
    class FakeASRService:
        async def transcribe_audio(
            self, audio_bytes: bytes, mime_type: str, filename: str
        ) -> str:
            assert audio_bytes.startswith(b"RIFF")
            assert mime_type == "audio/wav"
            assert filename == "voice.wav"
            return "患者发热三天，伴有咳嗽。"

    monkeypatch.setattr("src.api.routes.get_asr_service", lambda: FakeASRService())

    client = create_test_client()
    response = client.post(
        "/api/transcribe-audio",
        files={"audio": ("voice.wav", build_test_wav(), "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json()["text"] == "患者发热三天，伴有咳嗽。"


def test_transcribe_audio_endpoint_returns_503_on_service_error(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeASRService:
        async def transcribe_audio(
            self, audio_bytes: bytes, mime_type: str, filename: str
        ) -> str:
            raise ASRServiceError("ASR 服务暂不可用")

    monkeypatch.setattr("src.api.routes.get_asr_service", lambda: FakeASRService())

    client = create_test_client()
    response = client.post(
        "/api/transcribe-audio",
        files={"audio": ("voice.wav", build_test_wav(), "audio/wav")},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "ASR 服务暂不可用"


def test_asr_service_transcribe_audio_returns_output_text(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_dashscope = SimpleNamespace(
        api_key=None,
        base_http_api_url=None,
        MultiModalConversation=SimpleNamespace(
            call=lambda **kwargs: SimpleNamespace(
                output=SimpleNamespace(text="患者咳嗽伴发热", choices=[])
            )
        ),
    )
    monkeypatch.setitem(sys.modules, "dashscope", fake_dashscope)

    service = ASRService()
    service.settings.asr_api_key = "test-asr-key"
    service.settings.asr_language = "zh"
    service.settings.asr_region = "singapore"
    service.settings.asr_file_model = "qwen3-asr-flash"

    transcript = asyncio.run(
        service.transcribe_audio(
            audio_bytes=build_test_wav(),
            mime_type="audio/wav",
            filename="voice.wav",
        )
    )

    assert transcript == "患者咳嗽伴发热"


def test_asr_service_rejects_unsupported_sample_rate():
    service = ASRService()

    with pytest.raises(ASRServiceError, match="8kHz 或 16kHz"):
        service._validate_wav_audio(
            build_test_wav(sample_rate=44100),
            filename="voice.wav",
            mime_type="audio/wav",
        )
