#!/bin/bash
# Polymarket 套利系统状态检查

echo "========================================="
echo "📊 Polymarket 套利系统状态"
echo "========================================="
echo ""

PROJECT_DIR="/Users/lsl_mac/.openclaw/workspace/projects/polymarket-arbitrage"

echo "⏰ 当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

echo "📁 项目目录: $PROJECT_DIR"
echo ""

# 检查 cron 任务
echo "🕐 Cron 任务状态:"
if crontab -l | grep -q "polymarket-arbitrage"; then
    echo "  ✅ 定时任务已配置"
    echo "  📅 执行时间: 每小时整点 (0 * * * *)"
    NEXT_RUN=$(date -v+1H -v0M '+%H:00')
    echo "  ⏭️  下次运行: $NEXT_RUN"
else
    echo "  ❌ 定时任务未配置"
fi
echo ""

# 检查日志
echo "📝 最近日志:"
LOG_DIR="$PROJECT_DIR/logs/cron"
if [ -d "$LOG_DIR" ]; then
    LATEST_LOG=$(ls -t "$LOG_DIR"/hourly_scan_*.log 2>/dev/null | head -1)
    if [ -n "$LATEST_LOG" ]; then
        echo "  📄 最新日志: $(basename $LATEST_LOG)"
        echo "  📊 日志内容摘要:"
        tail -5 "$LATEST_LOG" | sed 's/^/    /'
    else
        echo "  ⏸️  暂无日志文件"
    fi
else
    echo "  ⏸️  日志目录不存在"
fi
echo ""

# 检查配置文件
echo "⚙️  配置检查:"
if [ -f "$PROJECT_DIR/config/.env" ]; then
    echo "  ✅ 配置文件存在"
    
    # 检查 Tavily API
    if grep -q "TAVILY_API_KEY=" "$PROJECT_DIR/config/.env" | grep -qv "your_"; then
        echo "  ✅ Tavily API: 已配置"
    else
        echo "  ⚠️  Tavily API: 未配置"
    fi
    
    # 检查 CLOB API
    if grep -q "CLOB_API_KEY=" "$PROJECT_DIR/config/.env" | grep -qv '^CLOB_API_KEY=""$'; then
        echo "  ✅ CLOB API: 已配置 (自动交易可用)"
    else
        echo "  ⏸️  CLOB API: 未配置 (仅手动模式可用)"
    fi
else
    echo "  ❌ 配置文件不存在"
fi
echo ""

# 检查虚拟环境
echo "🐍 Python 环境:"
if [ -d "$PROJECT_DIR/venv" ]; then
    echo "  ✅ 虚拟环境存在"
else
    echo "  ❌ 虚拟环境不存在"
fi
echo ""

# 检查脚本
echo "📜 脚本检查:"
if [ -f "$PROJECT_DIR/manual_trade.py" ]; then
    echo "  ✅ manual_trade.py: 存在"
else
    echo "  ❌ manual_trade.py: 不存在"
fi

if [ -f "$PROJECT_DIR/auto_trade.py" ]; then
    echo "  ✅ auto_trade.py: 存在"
else
    echo "  ❌ auto_trade.py: 不存在"
fi
echo ""

echo "========================================="
echo "💡 使用提示"
echo "========================================="
echo ""
echo "手动运行扫描:"
echo "  cd $PROJECT_DIR"
echo "  source venv/bin/activate"
echo "  python3 manual_trade.py"
echo ""
echo "查看日志:"
echo "  tail -f $PROJECT_DIR/logs/cron/hourly_scan_*.log"
echo ""
echo "停止定时任务:"
echo "  crontab -l | grep -v polymarket | crontab -"
echo ""
echo "========================================="
