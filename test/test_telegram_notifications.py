#!/usr/bin/env python3
"""
Telegram通知功能测试脚本
测试自动交易系统的Telegram通知集成
"""

import sys
import os
from dotenv import load_dotenv
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# 加载环境变量
load_dotenv('config/.env')

from notification_service import NotificationService, NotificationLevel
from datetime import datetime

def test_basic_notifications():
    """测试基本通知功能"""
    print("🧪 测试基本通知功能...")
    
    # 初始化通知服务
    notification_service = NotificationService({
        'enabled_channels': ['telegram', 'console'],
        'telegram': {
            'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID')
        }
    })
    
    # 测试不同级别的通知
    notification_service.info("测试信息", "这是一条测试信息通知")
    notification_service.success("测试成功", "这是一条测试成功通知")
    notification_service.warning("测试警告", "这是一条测试警告通知")
    notification_service.error("测试错误", "这是一条测试错误通知")
    notification_service.critical("测试严重", "这是一条测试严重通知")
    
    print("✅ 基本通知功能测试完成")

def test_trading_notifications():
    """测试交易相关通知"""
    print("🧪 测试交易相关通知...")
    
    notification_service = NotificationService({
        'enabled_channels': ['telegram', 'console'],
        'telegram': {
            'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID')
        }
    })
    
    # 测试信号发现通知
    notification_service.signal_detected(
        strategy="信息优势交易",
        market="特朗普赢得2024年总统选举",
        signal="buy",
        confidence=0.85
    )
    
    # 测试交易执行通知
    notification_service.trade_executed(
        strategy="概率套利",
        market="Bitcoin年底价格超过50000美元",
        signal="sell",
        confidence=0.78,
        order_id="order_12345"
    )
    
    print("✅ 交易相关通知测试完成")

def test_risk_notifications():
    """测试风险预警通知"""
    print("🧪 测试风险预警通知...")
    
    notification_service = NotificationService({
        'enabled_channels': ['telegram', 'console'],
        'telegram': {
            'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID')
        }
    })
    
    # 测试不同级别的风险预警
    notification_service.risk_alert(
        alert_type="情绪极端",
        description="关键词'Trump'情绪达到极端水平（分数: +0.85）",
        level=NotificationLevel.WARNING
    )
    
    notification_service.risk_alert(
        alert_type="异常波动",
        description="关键词'crypto'检测到异常波动（Z-score: 2.5）",
        level=NotificationLevel.CRITICAL
    )
    
    print("✅ 风险预警通知测试完成")

def test_system_notifications():
    """测试系统状态通知"""
    print("🧪 测试系统状态通知...")
    
    notification_service = NotificationService({
        'enabled_channels': ['telegram', 'console'],
        'telegram': {
            'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID')
        }
    })
    
    # 测试系统状态通知
    notification_service.system_status("系统启动", "自动交易系统已启动，模式：模拟交易")
    notification_service.system_status("策略初始化", "成功初始化 4/4 个交易策略")
    
    # 测试每日总结
    daily_stats = {
        'total_trades': 15,
        'successful_trades': 12,
        'total_return': 0.085,
        'current_positions': ['特朗普选举', 'Bitcoin价格']
    }
    notification_service.daily_summary(
        date=datetime.now().strftime('%Y-%m-%d'),
        stats=daily_stats
    )
    
    print("✅ 系统状态通知测试完成")

def test_notification_stats():
    """测试通知统计功能"""
    print("🧪 测试通知统计功能...")
    
    notification_service = NotificationService({
        'enabled_channels': ['telegram', 'console'],
        'telegram': {
            'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID')
        }
    })
    
    # 发送一些测试通知
    notification_service.info("统计测试1", "测试通知1")
    notification_service.warning("统计测试2", "测试通知2")
    notification_service.success("统计测试3", "测试通知3")
    
    # 获取统计信息
    stats = notification_service.get_notification_stats()
    print(f"📊 通知统计信息:")
    print(f"   总通知数: {stats['total_notifications']}")
    print(f"   按级别分布: {stats['by_level']}")
    print(f"   启用渠道: {stats['enabled_channels']}")
    print(f"   Telegram启用: {stats['telegram_enabled']}")
    
    print("✅ 通知统计功能测试完成")

def main():
    """主测试函数"""
    print("=" * 70)
    print("🧪 Telegram通知功能测试")
    print("=" * 70)
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    try:
        # 运行各项测试
        test_basic_notifications()
        print()
        
        test_trading_notifications()
        print()
        
        test_risk_notifications()
        print()
        
        test_system_notifications()
        print()
        
        test_notification_stats()
        print()
        
        print("=" * 70)
        print("🎉 所有测试完成！")
        print("请检查Telegram频道是否收到所有测试通知")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
