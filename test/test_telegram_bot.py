#!/usr/bin/env python3
"""
Telegram Bot 交互功能测试脚本
验证Bot的命令和交互功能
"""

import sys
import os
import time
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# 加载环境变量
load_dotenv('config/.env')

from telegram_bot_service import TelegramBotService, get_telegram_bot

def test_bot_service():
    """测试Bot服务功能"""
    print("🧪 测试 Telegram Bot 服务...")
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("❌ 环境变量未配置")
        print("   TELEGRAM_BOT_TOKEN:", bot_token[:10] + '...' if bot_token else 'None')
        print("   TELEGRAM_CHAT_ID:", chat_id if chat_id else 'None')
        return False
    
    print(f"✅ 配置正常:")
    print(f"   Token: {bot_token[:10]}...")
    print(f"   Chat ID: {chat_id}")
    
    # 创建Bot服务
    try:
        bot_service = TelegramBotService(bot_token, chat_id, strategy_manager=None)
        print("✅ Bot服务创建成功")
        
        # 测试发送消息
        print("📤 发送测试消息...")
        bot_service.send_message("🧪 *测试消息*\n\nBot服务测试成功！")
        print("✅ 测试消息已发送")
        
        # 启动Bot (仅测试，运行5秒后停止)
        print("🚀 启动Bot轮询(测试5秒)...")
        bot_service.start_bot()
        time.sleep(5)
        
        print("⏹️ 停止Bot...")
        bot_service.stop_bot()
        
        print("✅ Bot服务测试完成")
        return True
        
    except Exception as e:
        print(f"❌ Bot服务测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_commands():
    """测试命令列表"""
    print("\n🧪 测试命令注册...")
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    bot_service = TelegramBotService(bot_token, chat_id, strategy_manager=None)
    
    print(f"📋 已注册 {len(bot_service.commands)} 个命令:")
    for cmd_name, cmd_info in bot_service.commands.items():
        admin_tag = " [管理员]" if cmd_info.admin_only else ""
        print(f"   /{cmd_name} - {cmd_info.description}{admin_tag}")
    
    print("✅ 命令注册测试完成")

def main():
    """主测试函数"""
    print("=" * 70)
    print("🧪 Telegram Bot 交互功能测试")
    print("=" * 70)
    
    # 测试命令列表
    test_commands()
    
    # 询问是否启动Bot测试
    print("\n📢 注意: 如果要测试Bot的实时交互功能:")
    print("   1. 确保已在Telegram中找到您的Bot")
    print("   2. 已向Bot发送 /start 命令")
    print("   3. 然后运行: python run_all_strategies.py")
    
    print("\n✅ Telegram Bot 功能已集成完成!")
    print("\n可用命令:")
    print("  /start, /help, /status, /strategies, /performance")
    print("  /positions, /trades, /risk, /config")
    print("  /set, /restart, /stop, /emergency (管理员)")
    
    print("\n" + "=" * 70)

if __name__ == '__main__':
    main()
