"""LLM 结构化输出适配器。"""

from typing import Any, Generic, Mapping, Optional, Sequence, TypeVar

from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionFunctionToolParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolChoiceOptionParam,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)
from openai.types.shared_params.function_definition import FunctionDefinition
from pydantic import BaseModel
from loguru import logger
import json
import os
import re

T = TypeVar("T", bound=BaseModel)
MessageInput = Mapping[str, object]


class StructuredOutputAdapter(Generic[T]):
    """使用 OpenAI tools 实现结构化输出。"""

    def __init__(
        self,
        response_model: type[T],
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "deepseek-chat",
        temperature: float = 0.7,
    ):
        """
        初始化适配器

        Args:
            response_model: Pydantic 模型类
            api_key: API 密钥，默认从环境变量读取
            base_url: API 基础 URL
            model: 模型名称
            temperature: 温度参数
        """
        self.response_model = response_model
        self.model = model
        self.temperature = temperature

        # 初始化 OpenAI 客户端
        self.client = AsyncOpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"),
        )

        # 生成工具定义
        self.tool_def = self._create_tool_definition()

        logger.info(f"[OK] 初始化 StructuredOutputAdapter，模型: {model}")

    def _create_tool_definition(self) -> ChatCompletionFunctionToolParam:
        """从 Pydantic 模型创建 OpenAI tools 定义。"""
        schema = self.response_model.model_json_schema()
        function_definition: FunctionDefinition = {
            "name": "extract_structured_data",
            "description": f"提取结构化数据: {self.response_model.__doc__ or ''}",
            "parameters": schema,
        }
        return {"type": "function", "function": function_definition}

    @staticmethod
    def _normalize_messages(messages: Sequence[MessageInput]) -> list[ChatCompletionMessageParam]:
        """Normalize lightweight message dicts to OpenAI SDK typed params."""
        normalized: list[ChatCompletionMessageParam] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if not isinstance(role, str):
                raise ValueError("消息 role 必须为字符串")
            if not isinstance(content, str):
                raise ValueError("消息 content 必须为字符串")

            if role == "system":
                system_message: ChatCompletionSystemMessageParam = {
                    "role": "system",
                    "content": content,
                }
                normalized.append(system_message)
            elif role == "user":
                user_message: ChatCompletionUserMessageParam = {
                    "role": "user",
                    "content": content,
                }
                normalized.append(user_message)
            elif role == "assistant":
                assistant_message: ChatCompletionAssistantMessageParam = {
                    "role": "assistant",
                    "content": content,
                }
                normalized.append(assistant_message)
            else:
                raise ValueError(f"不支持的消息角色: {role}")

        return normalized

    @staticmethod
    def _extract_json_from_text(text: str) -> dict:
        """从模型文本输出中提取 JSON 对象"""
        content = (text or "").strip()
        if not content:
            raise ValueError("模型未返回可解析内容")

        # 优先处理 markdown code block
        block_match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
        if block_match:
            content = block_match.group(1).strip()

        # 先尝试整体解析
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # 再尝试提取第一个 JSON 对象
        obj_match = re.search(r"\{[\s\S]*\}", content)
        if obj_match:
            parsed = json.loads(obj_match.group(0))
            if isinstance(parsed, dict):
                return parsed

        raise ValueError("无法从模型输出中提取 JSON 对象")

    async def _ainvoke_fallback(self, messages: Sequence[ChatCompletionMessageParam]) -> T:
        """降级调用：不依赖 tools，仅要求模型返回 JSON 文本"""
        schema_text = json.dumps(self.response_model.model_json_schema(), ensure_ascii=False)
        fallback_instruction = (
            "你当前不使用函数调用。请仅返回一个合法 JSON 对象，不要包含解释文字。\n"
            "返回内容必须严格符合以下 JSON Schema：\n"
            f"{schema_text}"
        )

        fallback_message: ChatCompletionUserMessageParam = {
            "role": "user",
            "content": fallback_instruction,
        }
        fallback_messages = [*messages, fallback_message]
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=fallback_messages,
            temperature=self.temperature,
            timeout=60.0,
        )

        content = response.choices[0].message.content or ""
        parsed = self._extract_json_from_text(content)
        result = self.response_model(**parsed)
        logger.info(f"[OK] 使用降级模式提取结构化数据: {self.response_model.__name__}")
        return result

    async def ainvoke(self, messages: Sequence[MessageInput]) -> T:
        """
        异步调用 LLM 并返回结构化输出

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}, ...]

        Returns:
            结构化的 Pydantic 模型实例
        """
        tool_mode_error: Optional[Exception] = None
        normalized_messages = self._normalize_messages(messages)
        tool_choice: ChatCompletionToolChoiceOptionParam = {
            "type": "function",
            "function": {"name": "extract_structured_data"},
        }

        try:
            # 优先使用 tools（支持 function calling 的模型）
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=normalized_messages,
                tools=[self.tool_def],
                tool_choice=tool_choice,
                temperature=self.temperature,
                timeout=60.0,
            )

            message = response.choices[0].message
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                if not isinstance(tool_call, ChatCompletionMessageFunctionToolCall):
                    raise ValueError("模型返回了非函数类型的 tool call")
                function_args = json.loads(tool_call.function.arguments)
                result = self.response_model(**function_args)
                logger.info(f"[OK] 成功提取结构化数据: {self.response_model.__name__}")
                return result

            tool_mode_error = ValueError("模型响应未包含 tool_calls")
            logger.warning("模型未返回 tool_calls，开始使用降级模式")
        except Exception as e:
            tool_mode_error = e
            logger.warning(f"tools 模式调用失败，开始降级: {str(e)}")

        try:
            return await self._ainvoke_fallback(normalized_messages)
        except Exception as fallback_error:
            logger.error(f"降级模式也失败: {str(fallback_error)}")
            if tool_mode_error is not None:
                raise ValueError(
                    f"结构化输出失败（tools 与降级模式均失败）。"
                    f"tools错误: {tool_mode_error}; 降级错误: {fallback_error}"
                ) from fallback_error
            raise


def create_structured_llm(
    response_model: type[T],
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
) -> StructuredOutputAdapter[T]:
    """
    创建结构化输出适配器的便捷函数

    Args:
        response_model: Pydantic 模型类
        api_key: 可选的 API 密钥
        base_url: 可选的 API 基础 URL
        model: 可选的模型名称，默认从环境变量读取
        temperature: 温度参数

    Returns:
        StructuredOutputAdapter 实例
    """
    return StructuredOutputAdapter(
        response_model=response_model,
        api_key=api_key,
        base_url=base_url,
        model=model or os.getenv("OPENAI_MODEL", "deepseek-chat"),
        temperature=temperature,
    )
