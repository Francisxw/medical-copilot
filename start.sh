#!/bin/bash

echo "===================================="
echo "Medical Copilot 快速启动"
echo "===================================="
echo ""

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "[1/4] 创建虚拟环境..."
    python3 -m venv venv
    echo "✅ 虚拟环境创建完成"
else
    echo "✅ 虚拟环境已存在"
fi

# 激活虚拟环境
echo ""
echo "[2/4] 激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo ""
echo "[3/4] 安装依赖..."
pip install -q -r requirements.txt
echo "✅ 依赖安装完成"

# 检查环境变量
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  警告: .env 文件不存在"
    echo "请复制 .env.example 为 .env 并填入你的 OpenAI API 密钥"
    cp .env.example .env
    echo ""
    echo "请编辑 .env 文件后重新运行此脚本"
    exit 1
fi

# 准备数据
echo ""
echo "[4/4] 准备示例数据..."
python scripts/prepare_data.py

# 构建RAG索引
echo ""
echo "构建向量索引..."
python scripts/build_rag_index.py

echo ""
echo "===================================="
echo "✅ 所有设置已完成！"
echo "===================================="
echo ""
echo "启动服务:"
echo ""
echo "后端服务:"
echo "  uvicorn src.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "前端界面:"
echo "  streamlit run frontend/app.py"
echo ""
