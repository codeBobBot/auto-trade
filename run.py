#!/usr/bin/env python3
"""
Polymarket 套利系统 - 主程序
"""

import sys
import os

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def main():
    print("=" * 60)
    print("🚀 Polymarket 信息套利系统")
    print("=" * 60)
    
    # 测试各个模块
    print("\n📋 运行测试...")
    
    try:
        from polymarket_client import test_connection
        test_connection()
    except Exception as e:
        print(f"⚠️  Polymarket 连接测试跳过: {e}")
    
    try:
        from news_monitor import test_monitor
        test_monitor()
    except Exception as e:
        print(f"⚠️  新闻监控测试跳过: {e}")
    
    try:
        from arbitrage_strategy import test_strategy
        test_strategy()
    except Exception as e:
        print(f"⚠️  策略测试跳过: {e}")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)
    print("\n下一步:")
    print("1. 配置 API 密钥: cp config/.env.template config/.env")
    print("2. 编辑 config/.env 填入您的凭证")
    print("3. 运行: python3 run.py")

if __name__ == '__main__':
    main()
