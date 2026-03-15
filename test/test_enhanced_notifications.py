#!/usr/bin/env python3
"""
测试增强的Telegram通知功能
验证市场详情是否正确显示
"""

import sys
import os
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from notification_service import get_notification_service

def test_enhanced_notification():
    """测试增强的通知功能"""
    print("🧪 测试增强的Telegram通知功能...")
    
    # 初始化通知服务
    notification_config = {
        'enabled_channels': ['telegram', 'console'],
        'telegram': {
            'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID')
        }
    }
    
    notification_service = get_notification_service(notification_config)
    
    # 模拟概率套利机会的市场详情
    market_details = [
        {
            'id': '0x1234567890abcdef1234567890abcdef12345678',
            'question': '特朗普将赢得2024年美国总统选举吗？',
            'yes_price': 0.45,
            'liquidity': 25000,
            'volume24hr': 45000
        },
        {
            'id': '0xfedcba0987654321fedcba0987654321fedcba09',
            'question': '拜登将赢得2024年美国总统选举吗？',
            'yes_price': 0.42,
            'liquidity': 22000,
            'volume24hr': 38000
        },
        {
            'id': '0xabcdef1234567890abcdef1234567890abcdef12',
            'question': '2024年美国总统选举将由共和党赢得吗？',
            'yes_price': 0.48,
            'liquidity': 18000,
            'volume24hr': 32000
        }
    ]
    
    print("📊 测试市场详情:")
    for i, market in enumerate(market_details, 1):
        print(f"   {i}. {market['question']}")
        print(f"      ID: {market['id'][:20]}...")
        print(f"      价格: {market['yes_price']}")
        print(f"      流动性: {market['liquidity']:,} USDC")
        print(f"      24h交易量: {market['volume24hr']:,} USDC")
    
    print("\n📱 发送增强的Telegram通知...")
    
    # 发送增强的信号发现通知
    success = notification_service.signal_detected(
        strategy="概率套利",
        market="套利机会: 概率低估套利: 2024选举党派控制 (低风险)",
        signal="buy_all",
        confidence=0.927,
        market_details=market_details
    )
    
    if success:
        print("✅ 增强通知发送成功！")
        print("\n📋 通知内容包含:")
        print("   ✅ 策略名称")
        print("   ✅ 信号类型")
        print("   ✅ 市场描述")
        print("   ✅ 置信度")
        print("   ✅ 具体市场详情（最多5个）:")
        print("      - 市场问题")
        print("      - 市场ID")
        print("      - Yes价格")
        print("      - 流动性")
        print("      - 24h交易量")
    else:
        print("❌ 通知发送失败")
    
    return success

if __name__ == '__main__':
    print("=" * 70)
    print("🧪 增强Telegram通知功能测试")
    print("=" * 70)
    
    # 检查环境变量
    if not os.getenv('TELEGRAM_BOT_TOKEN') or not os.getenv('TELEGRAM_CHAT_ID'):
        print("❌ 缺少必要的环境变量:")
        print("   - TELEGRAM_BOT_TOKEN")
        print("   - TELEGRAM_CHAT_ID")
        print("\n请设置这些环境变量后重新运行测试")
        exit(1)
    
    try:
        success = test_enhanced_notification()
        
        if success:
            print("\n" + "=" * 70)
            print("🎉 增强通知功能测试通过！")
            print("\n📱 现在Telegram通知将包含:")
            print("   🎯 详细的套利机会信息")
            print("   📊 具体市场列表")
            print("   💰 实时价格数据")
            print("   💧 流动性信息")
            print("   📈 交易量统计")
            print("=" * 70)
        else:
            print("\n⚠️ 通知发送失败，请检查配置")
            
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
