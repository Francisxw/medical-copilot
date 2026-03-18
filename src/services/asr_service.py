"""阿里云 Qwen ASR 服务封装。"""

from __future__ import annotations

import base64
from io import BytesIO
import wave

from loguru import logger

from src.config import Settings, settings
from src.services.medical_terms import build_medical_corpus


class ASRServiceError(RuntimeError):
    """语音识别服务错误。"""


class ASRService:
    """将音频转写为文本的服务。"""

    def __init__(self, app_settings: Settings | None = None):
        self.settings = app_settings or settings

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/wav",
        filename: str = "audio.wav",
    ) -> str:
        if not audio_bytes:
            raise ASRServiceError("未收到音频内容")

        api_key = self.settings.asr_api_key.strip()
        if not api_key:
            raise ASRServiceError("未配置 ASR_API_KEY 或 DASHSCOPE_API_KEY")

        sample_rate = self._validate_wav_audio(audio_bytes, filename, mime_type)
        data_uri = self._build_audio_data_uri(audio_bytes, mime_type)

        try:
            import dashscope
        except ImportError as exc:
            raise ASRServiceError(
                "未安装 dashscope 依赖，请先执行 pip install -r requirements.txt"
            ) from exc

        dashscope.api_key = api_key
        dashscope.base_http_api_url = self._get_http_api_url()

        try:
            response = dashscope.MultiModalConversation.call(
                api_key=api_key,
                model=self.settings.asr_file_model,
                messages=[{"role": "user", "content": [{"audio": data_uri}]}],
                result_format="message",
                asr_options={
                    "language": self.settings.asr_language,
                    "enable_itn": False,
                    "sample_rate": sample_rate,
                    "corpus_text": self._get_corpus_text(),
                },
            )
        except Exception as exc:
            logger.error(f"ASR 转写失败: {exc}")
            raise ASRServiceError(f"语音识别调用失败: {exc}") from exc

        transcript = self._extract_transcript_from_response(response)
        if transcript:
            return transcript.strip()

        raise ASRServiceError("未识别到有效语音内容，请重试")

    def _get_http_api_url(self) -> str:
        if self.settings.asr_region.lower() == "beijing":
            return "https://dashscope.aliyuncs.com/api/v1"
        return "https://dashscope-intl.aliyuncs.com/api/v1"

    def _get_corpus_text(self) -> str | None:
        if not self.settings.enable_medical_terms:
            return None
        return build_medical_corpus()

    def _validate_wav_audio(
        self,
        audio_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> int:
        if mime_type not in {
            "audio/wav",
            "audio/x-wav",
            "audio/wave",
            "application/octet-stream",
        } and not filename.lower().endswith(".wav"):
            raise ASRServiceError(
                "当前核心版仅支持 WAV 录音，请使用前端录音组件重新录制"
            )

        try:
            with wave.open(BytesIO(audio_bytes), "rb") as wav_file:
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                sample_rate = wav_file.getframerate()
                wav_file.readframes(wav_file.getnframes())
        except wave.Error as exc:
            raise ASRServiceError("上传的音频文件无法解析为有效 WAV") from exc

        if channels != 1:
            raise ASRServiceError("当前核心版仅支持单声道 WAV 录音")
        if sample_width != 2:
            raise ASRServiceError("当前核心版仅支持 16-bit WAV 录音")
        if sample_rate not in {8000, 16000}:
            raise ASRServiceError("当前核心版仅支持 8kHz 或 16kHz WAV 录音")

        return sample_rate

    @staticmethod
    def _build_audio_data_uri(audio_bytes: bytes, mime_type: str) -> str:
        encoded_audio = base64.b64encode(audio_bytes).decode("ascii")
        return f"data:{mime_type};base64,{encoded_audio}"

    @staticmethod
    def _extract_transcript_from_response(response) -> str:
        output = getattr(response, "output", None)
        if output is None:
            return ""

        text = getattr(output, "text", None)
        if isinstance(text, str) and text.strip():
            return text

        choices = getattr(output, "choices", None) or []
        if not choices:
            return ""

        first_choice = choices[0]
        message = getattr(first_choice, "message", None)
        if message is None:
            return ""

        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text_value = item.get("text")
                    if isinstance(text_value, str) and text_value.strip():
                        texts.append(text_value.strip())
                elif isinstance(item, str) and item.strip():
                    texts.append(item.strip())
            return "\n".join(texts)

        return ""
