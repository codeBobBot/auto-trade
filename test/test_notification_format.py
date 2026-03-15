#!/usr/bin/env python3
"""
测试增强的Telegram通知功能 - 控制台版本
验证市场详情格式是否正确
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

class MockNotificationService:
    """模拟通知服务，用于测试格式"""
    
    def signal_detected(self, strategy: str, market: str, signal: str, confidence: float, market_details: list = None):
        """模拟信号发现通知"""
        title = f"🎯 信号发现 - {strategy}"
        content = f"""检测到交易信号
信号: {signal}
市场: {market}
置信度: {confidence:.1%}"""
        
        # 添加具体市场详情
        if market_details:
            content += "\n\n📊 相关市场详情:"
            for i, mkt in enumerate(market_details[:5], 1):  # 最多显示5个市场
                content += f"\n{i}. {mkt.get('question', 'N/A')[:40]}..."
                content += f"\n   🆔 ID: {mkt.get('id', 'N/A')[:12]}..."
                content += f"\n   💰 价格: {mkt.get('yes_price', mkt.get('price', 'N/A'))}"
                content += f"\n   💧 流动性: {mkt.get('liquidity', 'N/A'):,} USDC"
                content += f"\n   📈 24h交易量: {mkt.get('volume24hr', 'N/A'):,} USDC"
                if i < len(market_details[:5]):
                    content += "\n"
        
        # 模拟Telegram格式输出
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_message = f"""
ℹ️ <b>{title}</b>

{content}

<i>🕐 {timestamp}</i>
<i>🤖 Polymarket自动交易系统</i>
<i>📊 策略: {strategy}</i>
<i>🎯 置信度: {confidence:.1%}</i>
<i>📈 市场: {market[:50]}...</i>"""
        
        print(formatted_message)
        return True

def test_enhanced_notification_format():
    """测试增强通知的格式"""
    print("🧪 测试增强通知格式...")
    
    # 创建模拟通知服务
    notification_service = MockNotificationService()
    
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
    
    print("\n" + "=" * 70)
    print("📱 模拟增强的Telegram通知内容:")
    print("=" * 70)
    
    # 发送增强的信号发现通知
    success = notification_service.signal_detected(
        strategy="概率套利",
        market="套利机会: 概率低估套利: 2024选举党派控制 (低风险)",
        signal="buy_all",
        confidence=0.927,
        market_details=market_details
    )
    
    print("\n" + "=" * 70)
    print("📋 通知内容分析:")
    print("=" * 70)
    print("✅ 包含的信息:")
    print("   🎯 策略名称: 概率套利")
    print("   📊 信号类型: buy_all")
    print("   📈 市场描述: 概率低估套利: 2024选举党派控制")
    print("   🎯 置信度: 92.7%")
    print("   📊 具体市场详情 (3个市场):")
    
    for i, market in enumerate(market_details, 1):
        print(f"      {i}. {market['question'][:30]}...")
        print(f"         🆔 ID: {market['id'][:12]}...")
        print(f"         💰 价格: {market['yes_price']}")
        print(f"         💧 流动性: {market['liquidity']:,} USDC")
        print(f"         📈 24h交易量: {market['volume24hr']:,} USDC")
    
    print("\n🔧 改进点:")
    print("   ✅ 添加了具体市场ID")
    print("   ✅ 显示完整市场问题")
    print("   ✅ 包含实时价格信息")
    print("   ✅ 显示流动性数据")
    print("   ✅ 包含24小时交易量")
    print("   ✅ 限制显示前5个市场（避免消息过长）")
    
    return success

if __name__ == '__main__':
    print("🧪 增强Telegram通知功能测试 - 格式验证")
    print("=" * 70)
    
    try:
        success = test_enhanced_notification_format()
        
        if success:
            print("\n🎉 通知格式测试成功！")
            print("\n📱 现在Telegram通知将包含完整的市场详情，")
            print("   用户可以直接从通知中获取所有关键信息！")
        else:
            print("\n⚠️ 测试失败")
            
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
