#!/bin/bash
# Polymarket 套利监控 - 每小时定时任务
# 运行时间: 每小时整点
# 功能: 扫描套利机会，发送 Telegram 通知

set -e

PROJECT_DIR="/Users/lsl_mac/.openclaw/workspace/projects/polymarket-arbitrage"
LOG_DIR="$PROJECT_DIR/logs/cron"
DATE=$(date +%Y%m%d_%H%M%S)

# 确保日志目录存在
mkdir -p "$LOG_DIR"

# 日志文件
LOG_FILE="$LOG_DIR/hourly_scan_$DATE.log"

echo "=========================================" | tee -a "$LOG_FILE"
echo "🚀 Polymarket 每小时扫描" | tee -a "$LOG_FILE"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"
echo "=========================================" | tee -a "$LOG_FILE"

# 进入项目目录
cd "$PROJECT_DIR"

# 激活虚拟环境
source venv/bin/activate

# 运行手动交易助手 (生成信号并发送 Telegram 通知)
echo "🔍 开始扫描..." | tee -a "$LOG_FILE"
python3 manual_trade.py --confidence 0.5 >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 扫描完成" | tee -a "$LOG_FILE"
else
    echo "⚠️  扫描异常 (退出码: $EXIT_CODE)" | tee -a "$LOG_FILE"
fi

echo "=========================================" | tee -a "$LOG_FILE"
echo "下次扫描: $(date -v+1H '+%Y-%m-%d %H:00:00')" | tee -a "$LOG_FILE"
echo "=========================================" | tee -a "$LOG_FILE"

# 清理7天前的日志
find "$LOG_DIR" -name "hourly_scan_*.log" -mtime +7 -delete 2>/dev/null || true

exit $EXIT_CODE
