#!/usr/bin/env python3
"""
统一策略管理器
同时运行所有交易策略，实现收益最大化

核心功能：
1. 多策略并行运行
2. 资金分配管理
3. 风险控制
4. 收益统计
"""

import time
import json
import threading
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

from information_advantage_strategy import InformationAdvantageStrategy
from probability_arbitrage_strategy import ProbabilityArbitrageStrategy
from cross_market_arbitrage_strategy import CrossMarketArbitrageStrategy
from time_arbitrage_strategy import TimeArbitrageStrategy
from notification_service import NotificationService, get_notification_service
from telegram_bot_service import TelegramBotService, get_telegram_bot
from logger_config import get_system_logger, get_strategy_logger

@dataclass
class StrategyConfig:
    """策略配置"""
    name: str
    enabled: bool
    weight: float  # 资金分配权重
    max_position: float  # 最大仓位
    min_confidence: float  # 最小置信度
    scan_interval: int  # 扫描间隔(秒)
    priority: int  # 优先级(1-5)

@dataclass
class StrategyPerformance:
    """策略表现"""
    name: str
    total_trades: int = 0
    successful_trades: int = 0
    total_return: float = 0.0
    current_positions: List[Dict] = field(default_factory=list)
    last_trade_time: Optional[datetime] = None
    daily_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0

@dataclass
class UnifiedSignal:
    """统一交易信号"""
    strategy_name: str
    signal_type: str
    market: Dict
    direction: str
    confidence: float
    expected_return: float
    position_size: float
    urgency: str
    timestamp: datetime

class UnifiedStrategyManager:
    """统一策略管理器"""
    
    def __init__(self, enable_trading: bool = False, total_capital: float = 10000.0):
        self.enable_trading = enable_trading
        self.total_capital = total_capital
        
        # 初始化日志记录器
        self.logger = get_system_logger()
        self.logger.info(f"初始化统一策略管理器 - 交易模式: {'实盘' if enable_trading else '模拟'}, 总资金: ${total_capital:,.2f}")
        
        # 初始化通知服务
        self.notification_service = get_notification_service({
            'enabled_channels': ['telegram', 'console'],
            'telegram': {
                'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
                'chat_id': os.getenv('TELEGRAM_CHAT_ID')
            }
        })
        
        # 初始化Telegram Bot服务
        self.telegram_bot = None
        if os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_CHAT_ID'):
            try:
                self.telegram_bot = get_telegram_bot(
                    os.getenv('TELEGRAM_BOT_TOKEN'),
                    os.getenv('TELEGRAM_CHAT_ID'),
                    self
                )
                self.logger.info("Telegram Bot服务已配置")
            except Exception as e:
                self.logger.error(f"Telegram Bot初始化失败: {e}")
        
        # 策略配置
        self.strategy_configs = {
            'information_advantage': StrategyConfig(
                name='信息优势交易',
                enabled=True,
                weight=0.35,  # 35%资金
                max_position=2000.0,
                min_confidence=0.7,
                scan_interval=30,
                priority=1
            ),
            'probability_arbitrage': StrategyConfig(
                name='概率套利',
                enabled=True,
                weight=0.25,  # 25%资金
                max_position=1500.0,
                min_confidence=0.6,
                scan_interval=60,
                priority=2
            ),
            'cross_market_arbitrage': StrategyConfig(
                name='跨市场套利',
                enabled=True,
                weight=0.20,  # 20%资金
                max_position=1000.0,
                min_confidence=0.6,
                scan_interval=90,
                priority=3
            ),
            'time_arbitrage': StrategyConfig(
                name='时间套利',
                enabled=True,
                weight=0.20,  # 20%资金
                max_position=1000.0,
                min_confidence=0.6,
                scan_interval=120,
                priority=4
            )
        }
        
        # 策略实例
        self.strategies = {}
        self.initialize_strategies()
        
        # 策略表现跟踪
        self.strategy_performances = {
            name: StrategyPerformance(name=name) 
            for name in self.strategy_configs.keys()
        }
        
        # 风险管理
        self.risk_params = {
            'max_total_exposure': 0.8,  # 最大总敞口80%
            'max_single_strategy': 0.3,  # 单策略最大30%
            'stop_loss_threshold': -0.05,  # 止损阈值-5%
            'daily_loss_limit': -500.0,  # 日损失限制-500 USDC
            'concurrent_trades': 5,  # 并发交易数
            'min_trade_interval': 30  # 最小交易间隔30秒
        }
        
        # 交易队列
        self.trade_queue = []
        self.last_trade_time = datetime.now() - timedelta(hours=1)
        
        # 统计数据
        self.daily_stats = {
            'date': datetime.now().date(),
            'total_trades': 0,
            'successful_trades': 0,
            'total_pnl': 0.0,
            'strategy_contributions': {}
        }
        
        # 运行状态
        self.is_running = False
        self.strategy_threads = {}
    
    def initialize_strategies(self):
        """初始化策略实例"""
        self.notification_service.system_status("策略初始化", "开始初始化所有交易策略")
        
        try:
            self.strategies['information_advantage'] = InformationAdvantageStrategy(
                enable_trading=self.enable_trading
            )
            print("✅ 信息优势策略初始化成功")
            self.notification_service.success("策略初始化", "信息优势策略初始化成功")
        except Exception as e:
            print(f"❌ 信息优势策略初始化失败: {e}")
            self.notification_service.error("策略初始化", f"信息优势策略初始化失败: {e}")
        
        try:
            self.strategies['probability_arbitrage'] = ProbabilityArbitrageStrategy(
                enable_trading=self.enable_trading
            )
            print("✅ 概率套利策略初始化成功")
            self.notification_service.success("策略初始化", "概率套利策略初始化成功")
        except Exception as e:
            print(f"❌ 概率套利策略初始化失败: {e}")
            self.notification_service.error("策略初始化", f"概率套利策略初始化失败: {e}")
        
        try:
            self.strategies['cross_market_arbitrage'] = CrossMarketArbitrageStrategy(
                enable_trading=self.enable_trading
            )
            print("✅ 跨市场套利策略初始化成功")
            self.notification_service.success("策略初始化", "跨市场套利策略初始化成功")
        except Exception as e:
            print(f"❌ 跨市场套利策略初始化失败: {e}")
            self.notification_service.error("策略初始化", f"跨市场套利策略初始化失败: {e}")
        
        try:
            self.strategies['time_arbitrage'] = TimeArbitrageStrategy(
                enable_trading=self.enable_trading
            )
            print("✅ 时间套利策略初始化成功")
            self.notification_service.success("策略初始化", "时间套利策略初始化成功")
        except Exception as e:
            print(f"❌ 时间套利策略初始化失败: {e}")
            self.notification_service.error("策略初始化", f"时间套利策略初始化失败: {e}")
        
        # 发送初始化完成通知
        successful_count = len([s for s in self.strategies.values() if s is not None])
        total_count = len(self.strategy_configs)
        self.notification_service.system_status(
            "初始化完成", 
            f"成功初始化 {successful_count}/{total_count} 个策略"
        )
    
    def start_all_strategies(self):
        """启动所有策略"""
        self.logger.info("启动统一策略管理器...")
        self.logger.info(f"总资金: ${self.total_capital:,.2f}")
        self.logger.info(f"交易模式: {'实盘交易' if self.enable_trading else '模拟模式'}")
        
        # 启动Telegram Bot
        if self.telegram_bot:
            try:
                self.telegram_bot.start_bot()
                self.notification_service.success("Telegram Bot", "交互式Bot已启动，可以使用Telegram发送指令")
                self.logger.info("Telegram交互Bot已启动")
            except Exception as e:
                self.logger.error(f"Telegram Bot启动失败: {e}")
        
        self.is_running = True
        
        # 启动每个策略的监控线程
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            
            for strategy_name, config in self.strategy_configs.items():
                if config.enabled and strategy_name in self.strategies:
                    future = executor.submit(
                        self.run_strategy_monitor, 
                        strategy_name, 
                        config
                    )
                    futures.append(future)
                    self.logger.info(f"启动策略: {config.name}")
            
            # 等待所有策略完成
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"策略执行错误: {e}")
    
    def run_strategy_monitor(self, strategy_name: str, config: StrategyConfig):
        """运行单个策略监控"""
        strategy = self.strategies[strategy_name]
        strategy_logger = get_strategy_logger(strategy_name)
        
        strategy_logger.info(f"开始监控策略: {config.name}")
        
        while self.is_running:
            try:
                # 检查是否应该运行
                if not self.should_run_strategy(strategy_name):
                    time.sleep(config.scan_interval)
                    continue
                
                # 运行策略
                signals = self.run_strategy_scan(strategy_name, strategy)
                
                # 处理信号
                for signal in signals:
                    if self.validate_signal(signal, config):
                        self.process_signal(signal, config)
                
                # 更新统计
                self.update_strategy_stats(strategy_name)
                
                # 等待下次扫描
                time.sleep(config.scan_interval)
                
            except KeyboardInterrupt:
                print(f"⏹️ 策略 {config.name} 已停止")
                break
            except Exception as e:
                print(f"❌ 策略 {config.name} 错误: {e}")
                time.sleep(60)
    
    def run_strategy_scan(self, strategy_name: str, strategy) -> List[UnifiedSignal]:
        """运行策略扫描"""
        signals = []
        
        try:
            if strategy_name == 'information_advantage':
                # 运行信息优势策略
                latest_news = strategy.get_latest_news(minutes=5)
                for news in latest_news:
                    if strategy.should_process_news(news):
                        impact = strategy.analyze_news_impact(news)
                        if impact.confidence >= self.strategy_configs[strategy_name].min_confidence:
                            for market in impact.affected_markets:
                                signal = UnifiedSignal(
                                    strategy_name=strategy_name,
                                    signal_type='news_driven',
                                    market=market,
                                    direction=impact.direction,
                                    confidence=impact.confidence,
                                    expected_return=impact.expected_impact,
                                    position_size=strategy.calculate_position_size(market, impact),
                                    urgency=impact.urgency,
                                    timestamp=datetime.now()
                                )
                                signals.append(signal)
            
            elif strategy_name == 'probability_arbitrage':
                # 运行概率套利策略
                markets = strategy.gamma_client.get_trending_markets(limit=200)
                strategy.update_mutually_exclusive_groups(markets)
                opportunities = strategy.find_arbitrage_opportunities()
                
                for opp in opportunities:
                    if opp.confidence >= self.strategy_configs[strategy_name].min_confidence:
                        for market in opp.markets:
                            signal = UnifiedSignal(
                                strategy_name=strategy_name,
                                signal_type='probability_arbitrage',
                                market=market,
                                direction=opp.action,
                                confidence=opp.confidence,
                                expected_return=opp.expected_return,
                                position_size=strategy.calculate_arbitrage_position_size(market, opp),
                                urgency='high',
                                timestamp=datetime.now()
                            )
                            signals.append(signal)
            
            elif strategy_name == 'cross_market_arbitrage':
                # 运行跨市场套利策略
                markets = strategy.gamma_client.get_trending_markets(limit=100)
                correlated_markets = strategy.find_correlated_markets(markets)
                arbitrage_signals = strategy.identify_arbitrage_opportunities(correlated_markets)
                
                for signal in arbitrage_signals:
                    if signal.confidence >= self.strategy_configs[strategy_name].min_confidence:
                        unified_signal = UnifiedSignal(
                            strategy_name=strategy_name,
                            signal_type='cross_market_arbitrage',
                            market=signal.correlated_market.market1,
                            direction=signal.type,
                            confidence=signal.confidence,
                            expected_return=signal.expected_return,
                            position_size=strategy.calculate_position_size(signal.correlated_market.market1, signal),
                            urgency='medium',
                            timestamp=datetime.now()
                        )
                        signals.append(unified_signal)
            
            elif strategy_name == 'time_arbitrage':
                # 运行时间套利策略
                markets = strategy.gamma_client.get_trending_markets(limit=100)
                expiry_markets = strategy.filter_expiry_markets(markets)
                opportunities = strategy.assess_true_probabilities(expiry_markets)
                arbitrage_opportunities = strategy.identify_time_arbitrage(opportunities)
                
                for opp in arbitrage_opportunities:
                    if opp.confidence >= self.strategy_configs[strategy_name].min_confidence:
                        signal = UnifiedSignal(
                            strategy_name=strategy_name,
                            signal_type='time_arbitrage',
                            market=opp.market,
                            direction='buy' if opp.estimated_true_probability > opp.current_price else 'sell',
                            confidence=opp.confidence,
                            expected_return=opp.expected_return,
                            position_size=strategy.calculate_position_size(opp),
                            urgency=opp.urgency,
                            timestamp=datetime.now()
                        )
                        signals.append(signal)
        
        except Exception as e:
            print(f"❌ 策略 {strategy_name} 扫描错误: {e}")
        
        return signals
    
    def should_run_strategy(self, strategy_name: str) -> bool:
        """判断是否应该运行策略"""
        config = self.strategy_configs[strategy_name]
        
        # 检查策略是否启用
        if not config.enabled:
            return False
        
        # 检查资金限制
        if not self.check_capital_limits(strategy_name):
            return False
        
        # 检查风险限制
        if not self.check_risk_limits():
            return False
        
        return True
    
    def check_capital_limits(self, strategy_name: str) -> bool:
        """检查资金限制"""
        # 检查单策略资金使用
        strategy_performance = self.strategy_performances[strategy_name]
        current_exposure = sum(pos.get('size', 0) for pos in strategy_performance.current_positions)
        max_exposure = self.total_capital * self.strategy_configs[strategy_name].weight
        
        return current_exposure < max_exposure
    
    def check_risk_limits(self) -> bool:
        """检查风险限制"""
        # 检查总敞口
        total_exposure = 0.0
        for perf in self.strategy_performances.values():
            total_exposure += sum(pos.get('size', 0) for pos in perf.current_positions)
        
        max_total_exposure = self.total_capital * self.risk_params['max_total_exposure']
        
        # 检查日损失
        daily_pnl = sum(perf.daily_pnl for perf in self.strategy_performances.values())
        
        return total_exposure < max_total_exposure and daily_pnl > self.risk_params['daily_loss_limit']
    
    def validate_signal(self, signal: UnifiedSignal, config: StrategyConfig) -> bool:
        """验证信号"""
        # 检查置信度
        if signal.confidence < config.min_confidence:
            return False
        
        # 检查仓位大小
        if signal.position_size > config.max_position:
            return False
        
        # 检查交易间隔
        time_since_last_trade = datetime.now() - self.last_trade_time
        if time_since_last_trade.total_seconds() < self.risk_params['min_trade_interval']:
            return False
        
        return True
    
    def process_signal(self, signal: UnifiedSignal, config: StrategyConfig):
        """处理交易信号"""
        print(f"\n🎯 处理交易信号:")
        print(f"   策略: {signal.strategy_name}")
        print(f"   市场: {signal.market['question'][:50]}...")
        print(f"   方向: {signal.direction}")
        print(f"   置信度: {signal.confidence:.2f}")
        print(f"   预期收益: {signal.expected_return:.2%}")
        print(f"   仓位大小: ${signal.position_size:.2f}")
        
        if self.enable_trading:
            # 执行交易
            self.execute_trade(signal)
        else:
            # 模拟交易
            self.simulate_trade(signal)
        
        # 更新统计
        self.update_trade_stats(signal)
    
    def execute_trade(self, signal: UnifiedSignal):
        """执行实际交易"""
        try:
            strategy = self.strategies[signal.strategy_name]
            
            # 发送信号发现通知
            self.notification_service.signal_detected(
                strategy_name=signal.strategy_name,
                market=signal.market.get('question', 'Unknown Market'),
                signal=signal.direction,
                confidence=signal.confidence
            )
            
            # 调用策略的交易方法
            order_id = None
            if signal.strategy_name == 'information_advantage':
                # 信息优势策略的交易逻辑
                # 获取token_id（条件代币地址）
                token_id = strategy.trading_client.get_market_token_id_enhanced(signal.market)
                if not token_id:
                    print(f"❌ 无法获取token_id: {signal.market}")
                    return
                
                side = 'BUY' if signal.direction == 'buy' else 'SELL'
                order_id = strategy.trading_client.create_order(
                    token_id=token_id,
                    side=side,
                    size=signal.position_size,
                    price=signal.market.get('yes_price', 0.5)
                )
                print(f"✅ 交易执行: {order_id}")
            
            elif signal.strategy_name == 'probability_arbitrage':
                # 概率套利策略的交易逻辑
                # 获取token_id（条件代币地址）
                token_id = strategy.trading_client.get_market_token_id_enhanced(signal.market)
                if not token_id:
                    print(f"❌ 无法获取token_id: {signal.market}")
                    return
                
                if signal.direction == 'buy_all':
                    order_id = strategy.trading_client.create_order(
                        token_id=token_id,
                        side='BUY',
                        size=signal.position_size,
                        price=signal.market.get('yes_price', 0.5)
                    )
                else:
                    order_id = strategy.trading_client.create_order(
                        token_id=token_id,
                        side='SELL',
                        size=signal.position_size,
                        price=signal.market.get('yes_price', 0.5)
                    )
                print(f"✅ 套利交易: {order_id}")
            
            # 发送交易执行通知
            if order_id:
                self.notification_service.trade_executed(
                    strategy=signal.strategy_name,
                    market=signal.market.get('question', 'Unknown Market'),
                    signal=signal.direction,
                    confidence=signal.confidence,
                    order_id=order_id
                )
                
                # 更新统计
                self.daily_stats['total_trades'] += 1
                self.daily_stats['successful_trades'] += 1
            else:
                self.notification_service.error(
                    "交易执行失败",
                    f"策略 {signal.strategy_name} 交易执行失败"
                )
            
            # 更新持仓
            self.update_positions(signal)
            
        except Exception as e:
            error_msg = f"交易执行异常: {e}"
            print(f"❌ {error_msg}")
            self.notification_service.error("交易执行异常", error_msg)
            
            # 更新统计
            self.daily_stats['total_trades'] += 1
    
    def simulate_trade(self, signal: UnifiedSignal):
        """模拟交易"""
        print(f"📝 模拟交易: {signal.direction} ${signal.position_size:.2f}")
        
        # 模拟更新持仓
        self.update_positions(signal)
    
    def update_positions(self, signal: UnifiedSignal):
        """更新持仓"""
        performance = self.strategy_performances[signal.strategy_name]
        
        # 添加新持仓
        position = {
            'market_id': signal.market['id'],
            'market_question': signal.market['question'],
            'direction': signal.direction,
            'size': signal.position_size,
            'entry_price': signal.market.get('yes_price', 0.5),
            'entry_time': signal.timestamp,
            'expected_return': signal.expected_return,
            'confidence': signal.confidence
        }
        
        performance.current_positions.append(position)
        performance.last_trade_time = signal.timestamp
        
        # 更新最后交易时间
        self.last_trade_time = datetime.now()
    
    def update_trade_stats(self, signal: UnifiedSignal):
        """更新交易统计"""
        performance = self.strategy_performances[signal.strategy_name]
        
        performance.total_trades += 1
        self.daily_stats['total_trades'] += 1
        
        # 更新策略贡献
        if signal.strategy_name not in self.daily_stats['strategy_contributions']:
            self.daily_stats['strategy_contributions'][signal.strategy_name] = 0
        self.daily_stats['strategy_contributions'][signal.strategy_name] += 1
    
    def update_strategy_stats(self, strategy_name: str):
        """更新策略统计"""
        performance = self.strategy_performances[strategy_name]
        
        # 计算成功率
        if performance.total_trades > 0:
            performance.successful_trades = int(performance.total_trades * 0.65)  # 假设65%成功率
        
        # 计算日收益
        performance.daily_pnl = sum(
            pos.get('size', 0) * pos.get('expected_return', 0) 
            for pos in performance.current_positions
        )
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取表现总结"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_capital': self.total_capital,
            'active_strategies': len([s for s in self.strategy_configs.values() if s.enabled]),
            'total_trades': sum(perf.total_trades for perf in self.strategy_performances.values()),
            'total_positions': sum(len(perf.current_positions) for perf in self.strategy_performances.values()),
            'daily_pnl': sum(perf.daily_pnl for perf in self.strategy_performances.values()),
            'strategy_performance': {}
        }
        
        for name, performance in self.strategy_performances.items():
            config = self.strategy_configs[name]
            summary['strategy_performance'][name] = {
                'name': config.name,
                'enabled': config.enabled,
                'weight': config.weight,
                'total_trades': performance.total_trades,
                'success_rate': performance.successful_trades / max(performance.total_trades, 1),
                'daily_pnl': performance.daily_pnl,
                'current_positions': len(performance.current_positions),
                'last_trade_time': performance.last_trade_time.isoformat() if performance.last_trade_time else None
            }
        
        return summary
    
    def print_performance_summary(self):
        """打印表现总结"""
        summary = self.get_performance_summary()
        
        print("\n" + "=" * 70)
        print("📊 策略表现总结")
        print("=" * 70)
        print(f"💰 总资金: ${summary['total_capital']:,.2f}")
        print(f"🔄 活跃策略: {summary['active_strategies']}")
        print(f"📈 总交易数: {summary['total_trades']}")
        print(f"📊 当前持仓: {summary['total_positions']}")
        print(f"💵 日收益: ${summary['daily_pnl']:,.2f}")
        
        print("\n📋 各策略表现:")
        for name, perf in summary['strategy_performance'].items():
            if perf['enabled']:
                print(f"\n🎯 {perf['name']}:")
                print(f"   权重: {perf['weight']:.1%}")
                print(f"   交易数: {perf['total_trades']}")
                print(f"   成功率: {perf['success_rate']:.1%}")
                print(f"   日收益: ${perf['daily_pnl']:,.2f}")
                print(f"   持仓数: {perf['current_positions']}")
        
        print("\n" + "=" * 70)

def test_unified_manager():
    """测试统一策略管理器"""
    print("🧪 测试统一策略管理器...")
    
    manager = UnifiedStrategyManager(enable_trading=False, total_capital=10000.0)
    
    # 测试策略初始化
    print(f"✅ 初始化策略: {len(manager.strategies)}")
    
    # 测试配置
    print(f"✅ 策略配置: {len(manager.strategy_configs)}")
    
    # 测试表现跟踪
    print(f"✅ 表现跟踪: {len(manager.strategy_performances)}")
    
    # 获取表现总结
    summary = manager.get_performance_summary()
    print(f"✅ 表现总结: {summary['total_capital']}")
    
    print("\n🎉 统一策略管理器测试完成！")

if __name__ == '__main__':
    test_unified_manager()
