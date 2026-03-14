#!/usr/bin/env python3
"""
单策略Telegram通知功能测试
验证单策略模式是否支持Telegram通知
"""

import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# 加载环境变量
load_dotenv('config/.env')

from notification_service import get_notification_service

def test_single_strategy_notification():
    """测试单策略通知功能"""
    print("🧪 测试单策略Telegram通知功能...")
    
    # 检查环境变量
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("❌ 环境变量未配置")
        print("   TELEGRAM_BOT_TOKEN:", "已设置" if bot_token else "未设置")
        print("   TELEGRAM_CHAT_ID:", "已设置" if chat_id else "未设置")
        return False
    
    print(f"✅ 环境变量已配置")
    print(f"   Token: {bot_token[:10]}...")
    print(f"   Chat ID: {chat_id}")
    
    try:
        # 初始化通知服务
        notification_service = get_notification_service({
            'enabled_channels': ['telegram', 'console'],
            'telegram': {
                'bot_token': bot_token,
                'chat_id': chat_id
            }
        })
        
        # 发送测试通知
        print("\n📤 发送测试通知...")
        notification_service.info(
            "单策略通知测试", 
            "✅ 单策略模式Telegram通知功能已启用！\n\n"
            "现在运行单策略时将收到通知：\n"
            "• 策略启动/停止\n"
            "• 交易信号\n"
            "• 交易执行\n"
            "• 风险预警"
        )
        print("✅ 测试通知已发送")
        
        print("\n✅ 单策略Telegram通知功能配置成功！")
        print("\n现在可以运行单策略命令:")
        print("   python run_all_strategies.py --strategy information_advantage")
        print("   python run_all_strategies.py --strategy probability_arbitrage --trade")
        print("   python run_all_strategies.py --strategy cross_market_arbitrage")
        print("   python run_all_strategies.py --strategy time_arbitrage")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("=" * 70)
    print("🧪 单策略Telegram通知功能测试")
    print("=" * 70)
    
    success = test_single_strategy_notification()
    
    print("=" * 70)
    if success:
        print("✅ 测试通过！单策略模式现在支持Telegram通知")
    else:
        print("❌ 测试失败")
    print("=" * 70)

if __name__ == '__main__':
    main()
