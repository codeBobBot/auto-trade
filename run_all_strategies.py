#!/usr/bin/env python3
"""
全策略启动脚本
同时运行所有交易策略，实现收益最大化

使用方法:
- 模拟模式: python run_all_strategies.py
- 实盘交易: python run_all_strategies.py --trade
- 单独策略: python run_all_strategies.py --strategy information_advantage
- 查看状态: python run_all_strategies.py --status

Telegram Bot 交互命令 (启动后可用):
基础命令:
  /start - 启动Bot并显示帮助
  /help - 显示所有命令
  /status - 查看实时系统状态
  /strategies - 查看策略详细信息
  /performance - 查看策略表现统计
  /positions - 查看当前持仓
  /trades - 查看最近交易历史
  /risk - 查看风险状态
  /config - 查看系统配置

管理员命令:
  /set 参数=值 - 动态调整参数 (如: /set capital=15000)
  /restart - 重启所有策略
  /stop - 停止所有策略
  /emergency - 紧急停止所有交易
"""

import sys
import os
import argparse
import signal
import time
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv('config/.env')

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from unified_strategy_manager import UnifiedStrategyManager
from information_advantage_strategy import test_strategy
from probability_arbitrage_strategy import test_arbitrage_strategy
from cross_market_arbitrage_strategy import test_cross_market_arbitrage
from time_arbitrage_strategy import test_time_arbitrage
from notification_service import get_notification_service

# 全局变量
manager = None
running = True

def signal_handler(signum, frame):
    """信号处理器"""
    global running, manager
    print(f"\n⏹️ 收到停止信号，正在关闭策略...")
    running = False
    if manager:
        manager.is_running = False
    sys.exit(0)

def run_single_strategy(strategy_name: str, enable_trading: bool = False):
    """运行单个策略（支持Telegram通知）"""
    print(f"🚀 启动单个策略: {strategy_name}")
    
    # 初始化通知服务
    notification_service = get_notification_service({
        'enabled_channels': ['telegram', 'console'],
        'telegram': {
            'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID')
        }
    })
    
    # 发送启动通知
    notification_service.info("策略启动", f"正在启动策略: {strategy_name}")
    
    if strategy_name == 'information_advantage':
        from information_advantage_strategy import InformationAdvantageStrategy
        strategy = InformationAdvantageStrategy(
            enable_trading=enable_trading,
            notification_service=notification_service
        )
        strategy.monitor_news_continuously(check_interval=30)
    
    elif strategy_name == 'probability_arbitrage':
        from probability_arbitrage_strategy import ProbabilityArbitrageStrategy
        strategy = ProbabilityArbitrageStrategy(
            enable_trading=enable_trading,
            notification_service=notification_service
        )
        strategy.scan_arbitrage_opportunities(scan_interval=60)
    
    elif strategy_name == 'cross_market_arbitrage':
        from cross_market_arbitrage_strategy import CrossMarketArbitrageStrategy
        strategy = CrossMarketArbitrageStrategy(
            enable_trading=enable_trading,
            notification_service=notification_service
        )
        strategy.scan_cross_market_arbitrage(scan_interval=90)
    
    elif strategy_name == 'time_arbitrage':
        from time_arbitrage_strategy import TimeArbitrageStrategy
        strategy = TimeArbitrageStrategy(
            enable_trading=enable_trading,
            notification_service=notification_service
        )
        strategy.scan_time_arbitrage(scan_interval=120)
    
    else:
        print(f"❌ 未知策略: {strategy_name}")
        print("可用策略: information_advantage, probability_arbitrage, cross_market_arbitrage, time_arbitrage")

def run_all_strategies(enable_trading: bool = False, total_capital: float = 10000.0):
    """运行所有策略"""
    global manager, running
    
    print("🚀 启动全策略交易系统")
    print(f"💰 总资金: ${total_capital:,.2f}")
    print(f"🎯 交易模式: {'实盘交易' if enable_trading else '模拟模式'}")
    
    # 创建统一管理器
    manager = UnifiedStrategyManager(enable_trading=enable_trading, total_capital=total_capital)
    
    # 启动所有策略
    try:
        manager.start_all_strategies()
    except KeyboardInterrupt:
        print("\n⏹️ 用户停止，正在关闭...")
        manager.is_running = False
    except Exception as e:
        print(f"❌ 策略运行错误: {e}")
        manager.is_running = False

def show_status():
    """显示系统状态"""
    print("📊 系统状态检查")
    print("=" * 50)
    
    # 测试各个组件
    print("\n🔍 测试系统组件...")
    
    try:
        # 测试信息优势策略
        print("1. 信息优势策略...")
        test_strategy()
        print("   ✅ 正常")
    except Exception as e:
        print(f"   ❌ 错误: {e}")
    
    try:
        # 测试概率套利策略
        print("2. 概率套利策略...")
        test_arbitrage_strategy()
        print("   ✅ 正常")
    except Exception as e:
        print(f"   ❌ 错误: {e}")
    
    try:
        # 测试跨市场套利策略
        print("3. 跨市场套利策略...")
        test_cross_market_arbitrage()
        print("   ✅ 正常")
    except Exception as e:
        print(f"   ❌ 错误: {e}")
    
    try:
        # 测试时间套利策略
        print("4. 时间套利策略...")
        test_time_arbitrage()
        print("   ✅ 正常")
    except Exception as e:
        print(f"   ❌ 错误: {e}")
    
    try:
        # 测试统一管理器
        print("5. 统一策略管理器...")
        from unified_strategy_manager import test_unified_manager
        test_unified_manager()
        print("   ✅ 正常")
    except Exception as e:
        print(f"   ❌ 错误: {e}")
    
    print("\n🎉 系统状态检查完成！")

def show_strategy_info():
    """显示策略信息"""
    print("📋 策略信息")
    print("=" * 50)
    
    strategies = {
        'information_advantage': {
            'name': '信息优势交易',
            'description': '利用新闻速度优势进行交易',
            'expected_return': '10-20%/月',
            'risk_level': '中等',
            'scan_interval': '30秒',
            'priority': 1
        },
        'probability_arbitrage': {
            'name': '概率套利',
            'description': '发现并利用市场定价错误',
            'expected_return': '15-30%/月',
            'risk_level': '低',
            'scan_interval': '60秒',
            'priority': 2
        },
        'cross_market_arbitrage': {
            'name': '跨市场套利',
            'description': '利用相关市场价格差异',
            'expected_return': '8-15%/月',
            'risk_level': '中等',
            'scan_interval': '90秒',
            'priority': 3
        },
        'time_arbitrage': {
            'name': '时间套利',
            'description': '临近结算时的价格偏差',
            'expected_return': '8-12%/月',
            'risk_level': '低',
            'scan_interval': '120秒',
            'priority': 4
        }
    }
    
    for key, info in strategies.items():
        print(f"\n🎯 {info['name']} ({key})")
        print(f"   描述: {info['description']}")
        print(f"   预期收益: {info['expected_return']}")
        print(f"   风险等级: {info['risk_level']}")
        print(f"   扫描间隔: {info['scan_interval']}")
        print(f"   优先级: {info['priority']}")

def main():
    parser = argparse.ArgumentParser(description='Polymarket 全策略交易系统')
    parser.add_argument('--trade', action='store_true', help='启用实盘交易（默认模拟模式）')
    parser.add_argument('--capital', type=float, default=10000.0, help='总资金（默认10000 USDC）')
    parser.add_argument('--strategy', type=str, help='运行单个策略')
    parser.add_argument('--status', action='store_true', help='显示系统状态')
    parser.add_argument('--info', action='store_true', help='显示策略信息')
    parser.add_argument('--test', action='store_true', help='运行测试模式')
    
    args = parser.parse_args()
    
    # 设置信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 70)
    print("🚀 Polymarket 全策略交易系统")
    print("=" * 70)
    print(f"⏰ 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 总资金: ${args.capital:,.2f}")
    print(f"🎯 交易模式: {'实盘交易' if args.trade else '模拟模式'}")
    
    # 显示Telegram Bot状态
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if bot_token and chat_id:
        print(f"🤖 Telegram Bot: ✅ 已启用 (命令: /help)")
    else:
        print(f"🤖 Telegram Bot: ❌ 未配置")
    
    print("=" * 70)
    
    if args.status:
        show_status()
        return
    
    if args.info:
        show_strategy_info()
        return
    
    if args.test:
        print("🧪 运行测试模式...")
        show_status()
        return
    
    if args.strategy:
        # 运行单个策略
        run_single_strategy(args.strategy, args.trade)
    else:
        # 运行所有策略
        run_all_strategies(args.trade, args.capital)

if __name__ == '__main__':
    main()
