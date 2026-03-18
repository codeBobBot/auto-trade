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
    
    # 从环境变量读取总资金
    total_capital = float(os.getenv('TOTAL_CAPITAL_USD', '1000'))
    print(f"💰 总资金: ${total_capital:,.2f}")
    
    # 初始化通知服务
    notification_service = get_notification_service({
        'enabled_channels': ['telegram', 'console'],
        'telegram': {
            'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID')
        }
    })
    
    # 初始化并启动Telegram Bot交互服务
    telegram_bot = None
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if bot_token and chat_id:
        try:
            from telegram_bot_service import init_telegram_bot
            
            # 创建一个简单的策略管理器用于单独策略模式
            class SimpleStrategyManager:
                def __init__(self, strategy, strategy_name, enable_trading, total_capital):
                    self.strategy = strategy
                    self.strategy_name = strategy_name
                    self.enable_trading = enable_trading
                    self.is_running = True
                    self.start_time = datetime.now()
                    self.total_capital = total_capital  # 使用传入的资金
                    self.daily_stats = {
                        'total_trades': 0,
                        'successful_trades': 0,
                        'total_pnl': 0.0
                    }
                    self.strategies = {strategy_name: strategy}
                    
                    # 添加缺失的属性
                    self.strategy_performances = {
                        strategy_name: {
                            'total_trades': 0,
                            'successful_trades': 0,
                            'total_pnl': 0.0,
                            'win_rate': 0.0,
                            'avg_return': 0.0,
                            'max_drawdown': 0.0,
                            'total_return': 0.0,
                            'current_positions': [],
                            'sharpe_ratio': 0.0
                        }
                    }
                    
                    # 从环境变量读取风险参数
                    self.risk_params = {
                        'max_trade_size': float(os.getenv('MAX_TRADE_AMOUNT_USD', '10')),
                        'max_daily_loss': float(os.getenv('MAX_DAILY_LOSS_USD', '50')),
                        'stop_loss_percentage': float(os.getenv('STOP_LOSS_PERCENTAGE', '10')),
                        'max_position_size': float(os.getenv('MAX_POSITION_SIZE', '0.3'))
                    }
                    
                    # 从环境变量读取策略配置
                    strategy_configs = {}
                    
                    # 单策略模式 - 权重默认为100%
                    if strategy_name == 'probability_arbitrage':
                        # 单策略模式时忽略环境变量，使用100%权重
                        weight = 1.0
                        min_confidence = float(os.getenv('PROBABILITY_ARBITRAGE_MIN_CONFIDENCE', '0.7'))
                        strategy_name_display = 'Probability Arbitrage'
                    # 信息优势策略
                    elif strategy_name == 'information_advantage':
                        weight = 1.0
                        min_confidence = float(os.getenv('INFORMATION_ADVANTAGE_MIN_CONFIDENCE', '0.6'))
                        strategy_name_display = 'Information Advantage'
                    # 跨市场套利策略
                    elif strategy_name == 'cross_market_arbitrage':
                        weight = 1.0
                        min_confidence = float(os.getenv('CROSS_MARKET_ARBITRAGE_MIN_CONFIDENCE', '0.6'))
                        strategy_name_display = 'Cross Market Arbitrage'
                    # 时间套利策略
                    elif strategy_name == 'time_arbitrage':
                        weight = 1.0
                        min_confidence = float(os.getenv('TIME_ARBITRAGE_MIN_CONFIDENCE', '0.6'))
                        strategy_name_display = 'Time Arbitrage'
                    else:
                        # 默认配置
                        weight = 1.0
                        min_confidence = 0.7
                        strategy_name_display = strategy_name.replace('_', ' ').title()
                    
                    self.strategy_configs = {
                        strategy_name: {
                            'weight': weight,
                            'min_confidence': min_confidence,
                            'max_position_size': 0.3,
                            'enabled': weight > 0,  # 权重为0时禁用策略
                            'name': strategy_name_display
                        }
                    }
                
                def get_strategy_status(self):
                    """获取策略状态"""
                    return {
                        'name': self.strategy_name,
                        'running': self.is_running,
                        'trading_enabled': self.enable_trading,
                        'start_time': self.start_time
                    }
            
            # 先创建策略实例
            strategy_instance = None
            
            if strategy_name == 'information_advantage':
                from information_advantage_strategy import InformationAdvantageStrategy
                strategy_instance = InformationAdvantageStrategy(
                    enable_trading=enable_trading,
                    notification_service=notification_service
                )
            elif strategy_name == 'probability_arbitrage':
                from probability_arbitrage_strategy import ProbabilityArbitrageStrategy
                strategy_instance = ProbabilityArbitrageStrategy(
                    enable_trading=enable_trading,
                    notification_service=notification_service
                )
            elif strategy_name == 'cross_market_arbitrage':
                from cross_market_arbitrage_strategy import CrossMarketArbitrageStrategy
                strategy_instance = CrossMarketArbitrageStrategy(
                    enable_trading=enable_trading,
                    notification_service=notification_service
                )
            elif strategy_name == 'time_arbitrage':
                from time_arbitrage_strategy import TimeArbitrageStrategy
                strategy_instance = TimeArbitrageStrategy(
                    enable_trading=enable_trading,
                    notification_service=notification_service
                )
            
            if strategy_instance:
                # 创建简单策略管理器
                simple_manager = SimpleStrategyManager(strategy_instance, strategy_name, enable_trading, total_capital)
                
                # 初始化Bot并连接策略管理器
                telegram_bot = init_telegram_bot(bot_token, chat_id, simple_manager)
                telegram_bot.start_bot()
                print("🤖 Telegram Bot交互服务已启动")
                notification_service.info("Bot启动", f"🤖 Telegram Bot交互服务已启动\n\n📋 **可用命令:**\n/start - 开始使用\n/help - 查看帮助\n/status - 系统状态\n/strategies - 策略信息\n/performance - 策略表现\n/positions - 当前持仓\n/trades - 交易历史\n/risk - 风险状态\n/config - 系统配置\n\n💡 **试试发送 /status 查看系统状态！**")
            else:
                print("❌ 策略实例创建失败")
                
        except Exception as e:
            print(f"❌ Telegram Bot启动失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 发送启动通知
    notification_service.info("策略启动", f"正在启动策略: {strategy_name}")
    
    # 启动策略（如果已经创建了策略实例）
    if strategy_instance:
        if strategy_name == 'information_advantage':
            strategy_instance.monitor_news_continuously(check_interval=30)
        elif strategy_name == 'probability_arbitrage':
            strategy_instance.scan_arbitrage_opportunities(scan_interval=60)
        elif strategy_name == 'cross_market_arbitrage':
            strategy_instance.scan_cross_market_arbitrage(scan_interval=90)
        elif strategy_name == 'time_arbitrage':
            strategy_instance.scan_time_arbitrage(scan_interval=120)
    else:
        print(f"❌ 策略实例未创建")
        print("可用策略: information_advantage, probability_arbitrage, cross_market_arbitrage, time_arbitrage")

def run_all_strategies(enable_trading: bool = False, total_capital: float = None):
    """运行所有策略"""
    global manager, running
    
    # 从环境变量读取总资金
    if total_capital is None:
        total_capital = float(os.getenv('TOTAL_CAPITAL_USD', '1000'))
    
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
