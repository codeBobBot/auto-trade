#!/usr/bin/env python3
"""
Telegram通知功能测试脚本
测试所有策略的Telegram通知发送功能
"""

import sys
import os
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from logger_config import get_logger
from notification_service import get_notification_service

def test_telegram_notifications():
    """测试Telegram通知功能"""
    logger = get_logger("telegram_test")
    logger.info("开始测试Telegram通知功能...")
    
    # 初始化通知服务
    notification_config = {
        'enabled_channels': ['telegram', 'console'],
        'telegram': {
            'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID')
        }
    }
    
    notification_service = get_notification_service(notification_config)
    
    if not notification_service or not notification_service.telegram_enabled:
        logger.error("❌ Telegram通知服务未正确配置")
        logger.info("请确保设置了环境变量 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID")
        return False
    
    logger.info("✅ Telegram通知服务初始化成功")
    
    # 测试不同类型的通知
    test_cases = [
        {
            'name': '策略初始化通知',
            'method': 'info',
            'title': '策略测试',
            'message': '这是策略初始化测试通知'
        },
        {
            'name': '信号发现通知',
            'method': 'signal_detected',
            'strategy_name': '测试策略',
            'market': '测试市场 - 这是一个模拟的套利机会',
            'signal': '买入',
            'confidence': 0.85
        },
        {
            'name': '套利详情通知',
            'method': 'info',
            'title': '套利详情',
            'message': '类型: 概率套利\n预期收益: 15.5%\n置信度: 0.85\n动作: buy_all'
        },
        {
            'name': '交易执行通知',
            'method': 'trade_executed',
            'strategy': '概率套利',
            'market': '测试市场',
            'signal': '买入',
            'confidence': 0.85,
            'order_id': 'test_order_12345'
        },
        {
            'name': '成功通知',
            'method': 'success',
            'title': '测试成功',
            'message': '这是一个成功通知的测试'
        },
        {
            'name': '错误通知',
            'method': 'error',
            'title': '测试错误',
            'message': '这是一个错误通知的测试'
        },
        {
            'name': '警告通知',
            'method': 'warning',
            'title': '测试警告',
            'message': '这是一个警告通知的测试'
        },
        {
            'name': '关键通知',
            'method': 'critical',
            'title': '测试关键',
            'message': '这是一个关键通知的测试'
        }
    ]
    
    success_count = 0
    total_count = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        logger.info(f"🧪 测试 {i}/{total_count}: {test_case['name']}")
        
        try:
            method = getattr(notification_service, test_case['method'])
            
            # 根据方法类型调用不同的参数
            if test_case['method'] == 'signal_detected':
                method(
                    strategy=test_case['strategy_name'],
                    market=test_case['market'],
                    signal=test_case['signal'],
                    confidence=test_case['confidence']
                )
            elif test_case['method'] == 'trade_executed':
                method(
                    strategy=test_case['strategy'],
                    market=test_case['market'],
                    signal=test_case['signal'],
                    confidence=test_case['confidence'],
                    order_id=test_case['order_id']
                )
            else:
                method(test_case['title'], test_case['message'])
            
            logger.info(f"✅ {test_case['name']} 发送成功")
            success_count += 1
            
        except Exception as e:
            logger.error(f"❌ {test_case['name']} 发送失败: {e}")
        
        # 等待一秒避免频率限制
        import time
        time.sleep(1)
    
    # 测试结果总结
    logger.info("=" * 60)
    logger.info(f"🧪 Telegram通知测试完成")
    logger.info(f"📊 测试结果: {success_count}/{total_count} 成功")
    logger.info(f"📈 成功率: {success_count/total_count:.1%}")
    
    if success_count == total_count:
        logger.info("🎉 所有Telegram通知功能正常工作！")
        return True
    else:
        logger.warning(f"⚠️ {total_count - success_count} 个通知测试失败")
        return False

def test_strategy_notifications():
    """测试各个策略的通知功能"""
    logger = get_logger("strategy_test")
    logger.info("开始测试策略通知功能...")
    
    # 模拟策略通知
    strategy_notifications = [
        {
            'strategy': '概率套利',
            'opportunity': '发现概率套利机会',
            'details': '类型: probability_arbitrage\n预期收益: 12.5%\n置信度: 0.80'
        },
        {
            'strategy': '跨市场套利',
            'opportunity': '发现跨市场套利机会',
            'details': '类型: buy_low_sell_high\n价格差异: 18.2%\n预期收益: 15.3%'
        },
        {
            'strategy': '时间套利',
            'opportunity': '发现时间套利机会',
            'details': '到期时间: 3天\n价格差异: 22.1%\n预期收益: 18.7%'
        },
        {
            'strategy': '信息优势',
            'opportunity': '发现高置信度机会',
            'details': '新闻: 重要经济数据发布\n方向: buy\n置信度: 0.85'
        }
    ]
    
    notification_config = {
        'enabled_channels': ['telegram', 'console'],
        'telegram': {
            'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID')
        }
    }
    
    notification_service = get_notification_service(notification_config)
    
    for notification in strategy_notifications:
        logger.info(f"🧪 测试 {notification['strategy']} 通知")
        
        # 发送信号发现通知
        notification_service.signal_detected(
            strategy=notification['strategy'],
            market=notification['opportunity'],
            signal='机会',
            confidence=0.8
        )
        
        # 发送详细信息
        notification_service.info(
            f"{notification['strategy']}详情", 
            notification['details']
        )
        
        import time
        time.sleep(2)
    
    logger.info("✅ 策略通知测试完成")

def main():
    """主测试函数"""
    print("=" * 70)
    print("🧪 Telegram通知功能测试")
    print("=" * 70)
    
    # 检查环境变量
    if not os.getenv('TELEGRAM_BOT_TOKEN') or not os.getenv('TELEGRAM_CHAT_ID'):
        print("❌ 缺少必要的环境变量:")
        print("   - TELEGRAM_BOT_TOKEN")
        print("   - TELEGRAM_CHAT_ID")
        print("\n请设置这些环境变量后重新运行测试")
        return
    
    try:
        # 测试基础通知功能
        success = test_telegram_notifications()
        
        if success:
            # 测试策略通知
            test_strategy_notifications()
            
            print("\n" + "=" * 70)
            print("🎉 所有Telegram通知功能测试通过！")
            print("\n📋 功能特性:")
            print("   ✅ 策略初始化通知")
            print("   ✅ 套利机会发现通知")
            print("   ✅ 交易执行通知")
            print("   ✅ 错误和警告通知")
            print("   ✅ 多种通知类型支持")
            print("\n📱 现在所有策略都会通过Telegram发送实时通知！")
            print("=" * 70)
        else:
            print("\n⚠️ 部分通知功能异常，请检查配置")
            
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
