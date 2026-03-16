#!/bin/bash

# Polymarket 套利系统部署脚本

echo "🚀 开始部署 Polymarket 套利系统..."

# 检查 Python 版本
python --version
if [ $? -ne 0 ]; then
    echo "❌ 请先安装 Python 3.8+"
    exit 1
fi

# 创建新的虚拟环境
echo "📦 创建虚拟环境..."
python -m venv venv

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source venv/bin/activate

# 升级 pip
echo "⬆️ 升级 pip..."
pip install --upgrade pip

# 安装依赖
echo "📚 安装项目依赖..."
pip install -r requirements.txt

echo "✅ 部署完成！"
echo ""
echo "📝 下一步操作："
echo "1. 复制配置文件: cp config/.env.template config/.env"
echo "2. 编辑配置文件: 填入你的 API 凭证"
echo "3. 运行测试: source venv/bin/activate && python run.py"
echo ""
echo "🎯 运行定时监控:"
echo "source venv/bin/activate && python scheduled_monitor.py"
