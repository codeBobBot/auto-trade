#!/usr/bin/env python3
"""
Polymarket 自动交易监控 - 定时循环版
每小时执行一次扫描
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from auto_trade import AutoTradingMonitor
from datetime import datetime
import time
import argparse


def run_scheduled_scan(enable_trading: bool = False, confidence: float = 0.3, interval_hours: int = 1):
    """
    定时执行扫描
    
    Args:
        enable_trading: 是否启用真实交易
        confidence: 最低置信度阈值
        interval_hours: 扫描间隔（小时）
    """
    print("\n" + "=" * 70)
    print("🤖 Polymarket 自动交易监控系统 - 定时模式")
    print("=" * 70)
    print(f"⏰ 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔄 扫描间隔: {interval_hours} 小时")
    print(f"📊 置信度阈值: {confidence}")
    print(f"💰 交易模式: {'✅ 实盘' if enable_trading else '⏸️  模拟'}")
    print("=" * 70)
    
    # 初始化监控器
    monitor = AutoTradingMonitor(enable_trading=enable_trading)
    
    scan_count = 0
    total_signals = 0
    
    try:
        while True:
            scan_count += 1
            print(f"\n{'='*70}")
            print(f"📡 第 {scan_count} 次扫描")
            print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print('='*70)
            
            # 执行扫描
            try:
                trades = monitor.scan_and_trade(min_confidence=confidence)
                total_signals += len(trades)
                
                print(f"\n📊 本次扫描发现 {len(trades)} 笔信号")
                print(f"📈 累计发现 {total_signals} 笔信号")
                
            except Exception as e:
                print(f"\n❌ 扫描失败: {e}")
            
            # 等待下次扫描
            next_scan = datetime.now().timestamp() + (interval_hours * 3600)
            next_scan_str = datetime.fromtimestamp(next_scan).strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"\n⏳ 下次扫描: {next_scan_str}")
            print(f"   (按 Ctrl+C 停止)")
            
            time.sleep(interval_hours * 3600)
            
    except KeyboardInterrupt:
        print(f"\n\n{'='*70}")
        print("🛑 用户停止监控")
        print(f"📊 总扫描次数: {scan_count}")
        print(f"📈 总信号数量: {total_signals}")
        print(f"⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print('='*70)


def main():
    parser = argparse.ArgumentParser(description='Polymarket 定时交易监控')
    parser.add_argument('--trade', action='store_true', help='启用真实交易 (默认模拟)')
    parser.add_argument('--confidence', type=float, default=0.3, help='最低置信度 (默认 0.3)')
    parser.add_argument('--interval', type=int, default=1, help='扫描间隔小时数 (默认 1)')
    args = parser.parse_args()
    
    run_scheduled_scan(
        enable_trading=args.trade,
        confidence=args.confidence,
        interval_hours=args.interval
    )


if __name__ == '__main__':
    main()
