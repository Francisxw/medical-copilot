from openai import OpenAI
import json
from typing import List, Dict, Any, Optional

client = OpenAI(
    api_key="你的 DeepSeek key",
    base_url="https://api.deepseek.com"
)

# -------------------------------
#  定义工具（完全自己写，和 OpenAI 格式一样）
# -------------------------------
tools: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "获取指定城市的当前天气状况",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，例如 '北京' 或 'Shanghai'"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "温度单位"
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_places",
            "description": "搜索附近或指定地点的兴趣点",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "location": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    }
]

# -------------------------------
#  工具执行函数（你自己实现）
# -------------------------------
def get_current_weather(city: str, unit: str = "celsius") -> str:
    # 这里只是模拟，实际你要调用真实 API
    return f"{city} 当前温度 22°C，晴天" if unit == "celsius" else f"{city} 当前温度 71.6°F，晴天"

def search_places(query: str, location: str = None) -> str:
    return f"搜索 '{query}' 在 {location or '当前位置'} 的结果：找到了 3 家咖啡店"

tool_map = {
    "get_current_weather": get_current_weather,
    "search_places": search_places
}

# -------------------------------
#  单轮 tool call 示例（最简洁写法）
# -------------------------------
def chat_with_tools(user_message: str, history: List[Dict] = None) -> str:
    if history is None:
        history = []

    messages = history + [{"role": "user", "content": user_message}]

    while True:
        response = client.chat.completions.create(
            model="deepseek-reasoner",          # 或 deepseek-chat
            messages=messages,
            tools=tools,
            tool_choice="auto",                 # 或 "required" / {"type": "function", "function": {"name": "xxx"}}
            temperature=0.6,
            max_tokens=2048,
            # strict=True  # 如果用 beta endpoint 可以开启更严格的 schema 遵守
        )

        message = response.choices[0].message
        messages.append(message)  # 把 assistant 消息加进去

        # 没有 tool calls → 直接返回最终回答
        if not message.tool_calls:
            return message.content

        # 有 tool calls → 执行工具
        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            if func_name in tool_map:
                try:
                    result = tool_map[func_name](**args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": str(result)   # 工具返回的内容必须是字符串
                    })
                except Exception as e:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": f"工具执行失败: {str(e)}"
                    })
            else:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": "未知工具"
                })

# 使用示例
if __name__ == "__main__":
    history = []
    while True:
        user_input = input("你: ")
        if user_input.lower() in ["quit", "exit", "q"]:
            break
        answer = chat_with_tools(user_input, history)
        print("模型:", answer)
        print("-" * 50)