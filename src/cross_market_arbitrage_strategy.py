#!/usr/bin/env python3
"""
跨市场套利策略
利用相关市场的价格差异进行套利

核心思路：
1. 发现相关市场
2. 计算理论价格关系
3. 识别价格差异
4. 自动对冲套利
"""

import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from gamma_client import PolymarketGammaClient
from clob_client_auto_creds import ClobTradingClientAutoCreds
from logger_config import get_strategy_logger

@dataclass
class CorrelatedMarket:
    """相关市场"""
    market1: Dict
    market2: Dict
    correlation_type: str
    theoretical_ratio: float
    actual_ratio: float
    price_discrepancy: float

@dataclass
class ArbitrageSignal:
    """套利信号"""
    type: str  # 'buy_low_sell_high', 'sell_high_buy_low'
    correlated_market: CorrelatedMarket
    expected_return: float
    confidence: float
    description: str

class CrossMarketArbitrageStrategy:
    """跨市场套利策略"""
    
    def __init__(self, enable_trading: bool = False, notification_service=None):
        self.enable_trading = enable_trading
        self.notification_service = notification_service
        
        # 初始化日志记录器
        self.logger = get_strategy_logger("cross_market_arbitrage")
        self.logger.info(f"初始化跨市场套利策略 - 交易模式: {'实盘' if enable_trading else '模拟'}")
        
        # 初始化组件
        self.gamma_client = PolymarketGammaClient()
        self.trading_client = ClobTradingClientAutoCreds()
        
        # 发送初始化通知
        if self.notification_service:
            self.notification_service.info("策略初始化", "跨市场套利策略已初始化")
        
        # 重复下单防护机制
        self.executed_signals = set()  # 存储已执行的套利信号ID
        self.logger.info("重复下单防护机制已启用 - 永久一次下单")
        
        # 相关市场定义
        self.correlated_market_patterns = {
            # 选举相关
            'trump_vs_republicans': {
                'keywords': ['trump', 'republican', 'president', 'election'],
                'correlation_strength': 0.9,
                'theoretical_ratio': 1.0,  # 理论上价格应该相等
                'description': '特朗普获胜 vs 共和党获胜'
            },
            
            'biden_vs_democrats': {
                'keywords': ['biden', 'democrat', 'president', 'election'],
                'correlation_strength': 0.9,
                'theoretical_ratio': 1.0,
                'description': '拜登获胜 vs 民主党获胜'
            },
            
            # 美联储相关
            'rate_hike_vs_inflation': {
                'keywords': ['rate hike', 'inflation', 'fed'],
                'correlation_strength': 0.7,
                'theoretical_ratio': 0.8,  # 加息对通胀的影响
                'description': '加息 vs 通胀'
            },
            
            'rate_cut_vs_growth': {
                'keywords': ['rate cut', 'growth', 'fed'],
                'correlation_strength': 0.7,
                'theoretical_ratio': 1.2,
                'description': '降息 vs 经济增长'
            },
            
            # 加密货币相关
            'bitcoin_vs_crypto': {
                'keywords': ['bitcoin', 'crypto', 'price'],
                'correlation_strength': 0.85,
                'theoretical_ratio': 1.0,
                'description': '比特币 vs 加密货币整体'
            },
            
            'eth_vs_btc': {
                'keywords': ['ethereum', 'bitcoin', 'price'],
                'correlation_strength': 0.8,
                'theoretical_ratio': 0.5,  # ETH通常是BTC价格的一部分
                'description': '以太坊 vs 比特币'
            }
        }
        
        # 套利阈值
        self.arbitrage_thresholds = {
            'min_discrepancy': 0.05,  # 最小价格差异5%
            'max_discrepancy': 0.30,  # 最大价格差异30%
            'min_liquidity': 5000,    # 最小流动性5000 USDC
            'min_correlation': 0.6,   # 最小相关性0.6
            'min_return': 0.03        # 最小预期收益3%
        }
    
    def generate_signal_id(self, signal: ArbitrageSignal) -> str:
        """生成套利信号的唯一ID"""
        # 基于市场ID和类型生成唯一标识
        market1_id = signal.correlated_market.market1.get('id', '')[:8]
        market2_id = signal.correlated_market.market2.get('id', '')[:8]
        return f"{market1_id}_{market2_id}_{signal.type}"
    
    def is_signal_executed(self, signal: ArbitrageSignal) -> bool:
        """检查套利信号是否已执行"""
        signal_id = self.generate_signal_id(signal)
        return signal_id in self.executed_signals
    
    def mark_signal_executed(self, signal: ArbitrageSignal):
        """标记套利信号已执行"""
        signal_id = self.generate_signal_id(signal)
        self.executed_signals.add(signal_id)
        self.logger.debug(f"标记套利信号已执行: {signal_id}")
    
    def scan_cross_market_arbitrage(self, scan_interval: int = 90):
        """持续扫描跨市场套利机会"""
        self.logger.info("启动跨市场套利策略...")
        self.logger.info(f"扫描间隔: {scan_interval}秒")
        self.logger.info(f"交易模式: {'实盘交易' if self.enable_trading else '模拟模式'}")
        
        while True:
            try:
                # 1. 获取市场数据
                markets = self.gamma_client.get_trending_markets(limit=100)
                
                # 2. 发现相关市场
                correlated_markets = self.find_correlated_markets(markets)
                
                # 3. 识别套利机会
                arbitrage_signals = self.identify_arbitrage_opportunities(correlated_markets)
                
                # 4. 执行套利
                for signal in arbitrage_signals:
                    self.logger.info(f"发现跨市场套利机会:")
                    self.logger.info(f"   类型: {signal.type}")
                    self.logger.info(f"   价格差异: {signal.correlated_market.price_discrepancy:.2%}")
                    self.logger.info(f"   预期收益: {signal.expected_return:.2%}")
                    self.logger.info(f"   置信度: {signal.confidence:.2f}")
                    self.logger.info(f"   描述: {signal.description}")
                    
                    # 发送跨市场套利机会通知到Telegram
                    if self.notification_service:
                        # 准备市场详情信息
                        market_details = [
                            {
                                'id': signal.correlated_market.market1.get('id', 'N/A'),
                                'question': signal.correlated_market.market1.get('question', 'N/A'),
                                'yes_price': self.get_market_price(signal.correlated_market.market1),
                                'liquidity': signal.correlated_market.market1.get('liquidity', 0),
                                'volume24hr': signal.correlated_market.market1.get('volume24hr', 0)
                            },
                            {
                                'id': signal.correlated_market.market2.get('id', 'N/A'),
                                'question': signal.correlated_market.market2.get('question', 'N/A'),
                                'yes_price': self.get_market_price(signal.correlated_market.market2),
                                'liquidity': signal.correlated_market.market2.get('liquidity', 0),
                                'volume24hr': signal.correlated_market.market2.get('volume24hr', 0)
                            }
                        ]
                        
                        self.notification_service.signal_detected(
                            strategy="跨市场套利",
                            market=f"套利机会: {signal.description[:50]}...",
                            signal=signal.type,
                            confidence=signal.confidence,
                            market_details=market_details
                        )
                        self.notification_service.info(
                            "跨市场套利详情", 
                            f"类型: {signal.type}\n"
                            f"价格差异: {signal.correlated_market.price_discrepancy:.2%}\n"
                            f"预期收益: {signal.expected_return:.2%}\n"
                            f"置信度: {signal.confidence:.2f}"
                        )
                    
                    # 检查是否已执行过
                    if self.is_signal_executed(signal):
                        self.logger.debug(f"套利信号已执行，跳过: {signal.description[:50]}...")
                        continue
                    
                    if self.enable_trading:
                        self.execute_cross_market_arbitrage(signal)
                        # 标记信号已执行
                        self.mark_signal_executed(signal)
                    else:
                        self.logger.info("模拟模式：记录套利机会")
                        self.log_arbitrage_signal(signal)
                
                # 5. 等待下次扫描
                time.sleep(scan_interval)
                
            except KeyboardInterrupt:
                self.logger.info("跨市场套利策略已停止")
                break
            except Exception as e:
                self.logger.error(f"跨市场套利扫描错误: {e}")
                time.sleep(60)
    
    def find_correlated_markets(self, markets: List[Dict]) -> List[CorrelatedMarket]:
        """发现相关市场"""
        correlated_markets = []
        
        # 遍历所有市场对
        for i, market1 in enumerate(markets):
            for j, market2 in enumerate(markets[i+1:], i+1):
                # 检查是否匹配相关模式
                correlation = self.check_market_correlation(market1, market2)
                
                if correlation:
                    correlated_markets.append(correlation)
        
        return correlated_markets
    
    def check_market_correlation(self, market1: Dict, market2: Dict) -> Optional[CorrelatedMarket]:
        """检查两个市场的相关性"""
        question1 = market1.get('question', '').lower()
        question2 = market2.get('question', '').lower()
        
        # 检查每个相关模式
        for pattern_name, pattern_info in self.correlated_market_patterns.items():
            # 检查关键词匹配
            keywords1 = [kw for kw in pattern_info['keywords'] if kw in question1]
            keywords2 = [kw for kw in pattern_info['keywords'] if kw in question2]
            
            if keywords1 and keywords2:
                # 计算价格比率
                price1 = self.get_market_price(market1)
                price2 = self.get_market_price(market2)
                
                if price1 > 0 and price2 > 0:
                    actual_ratio = price1 / price2
                    theoretical_ratio = pattern_info['theoretical_ratio']
                    
                    # 计算价格差异
                    price_discrepancy = abs(actual_ratio - theoretical_ratio) / theoretical_ratio
                    
                    # 如果差异超过阈值
                    if price_discrepancy > self.arbitrage_thresholds['min_discrepancy']:
                        return CorrelatedMarket(
                            market1=market1,
                            market2=market2,
                            correlation_type=pattern_name,
                            theoretical_ratio=theoretical_ratio,
                            actual_ratio=actual_ratio,
                            price_discrepancy=price_discrepancy
                        )
        
        return None
    
    def get_market_price(self, market: Dict) -> float:
        """获取市场价格"""
        # 尝试多种价格字段
        price_fields = ['yes_price', 'outcomePrices', 'price']
        
        for field in price_fields:
            if field in market:
                price = market[field]
                if isinstance(price, (int, float)):
                    return float(price)
                elif isinstance(price, str):
                    try:
                        return float(price)
                    except:
                        continue
                elif isinstance(price, dict) and 'Yes' in price:
                    try:
                        return float(price['Yes'])
                    except:
                        continue
        
        return 0.5  # 默认价格
    
    def identify_arbitrage_opportunities(self, correlated_markets: List[CorrelatedMarket]) -> List[ArbitrageSignal]:
        """识别套利机会"""
        arbitrage_signals = []
        
        for correlated_market in correlated_markets:
            # 计算套利方向
            if correlated_market.actual_ratio > correlated_market.theoretical_ratio:
                # market1 相对过高，卖出market1，买入market2
                signal_type = 'sell_high_buy_low'
                high_market = correlated_market.market1
                low_market = correlated_market.market2
            else:
                # market1 相对过低，买入market1，卖出market2
                signal_type = 'buy_low_sell_high'
                low_market = correlated_market.market1
                high_market = correlated_market.market2
            
            # 计算预期收益
            expected_return = self.calculate_expected_return(correlated_market)
            
            # 检查是否满足套利条件
            if (expected_return > self.arbitrage_thresholds['min_return'] and
                correlated_market.price_discrepancy < self.arbitrage_thresholds['max_discrepancy']):
                
                # 计算置信度
                confidence = self.calculate_arbitrage_confidence(correlated_market)
                
                # 获取描述
                pattern_info = self.correlated_market_patterns[correlated_market.correlation_type]
                
                arbitrage_signal = ArbitrageSignal(
                    type=signal_type,
                    correlated_market=correlated_market,
                    expected_return=expected_return,
                    confidence=confidence,
                    description=pattern_info['description']
                )
                
                arbitrage_signals.append(arbitrage_signal)
        
        # 按预期收益排序
        arbitrage_signals.sort(key=lambda x: x.expected_return, reverse=True)
        
        return arbitrage_signals
    
    def calculate_expected_return(self, correlated_market: CorrelatedMarket) -> float:
        """计算预期收益"""
        # 基础收益来自价格差异
        base_return = correlated_market.price_discrepancy
        
        # 考虑交易成本（约1-2%）
        trading_cost = 0.02
        
        # 考虑执行风险（约1-3%）
        execution_risk = 0.02
        
        # 净收益
        net_return = base_return - trading_cost - execution_risk
        
        return max(net_return, 0.0)
    
    def calculate_arbitrage_confidence(self, correlated_market: CorrelatedMarket) -> float:
        """计算套利置信度"""
        confidence = 0.0
        
        # 1. 相关性强度 (30%)
        pattern_info = self.correlated_market_patterns[correlated_market.correlation_type]
        correlation_confidence = pattern_info['correlation_strength'] * 0.3
        confidence += correlation_confidence
        
        # 2. 价格差异合理性 (25%)
        discrepancy = correlated_market.price_discrepancy
        if discrepancy < 0.1:
            discrepancy_confidence = 0.25
        elif discrepancy < 0.2:
            discrepancy_confidence = 0.2
        elif discrepancy < 0.3:
            discrepancy_confidence = 0.15
        else:
            discrepancy_confidence = 0.1
        
        confidence += discrepancy_confidence
        
        # 3. 流动性评估 (25%)
        liquidity1 = float(correlated_market.market1.get('liquidity', 0))
        liquidity2 = float(correlated_market.market2.get('liquidity', 0))
        total_liquidity = liquidity1 + liquidity2
        
        liquidity_confidence = min(total_liquidity / 20000, 0.25)
        confidence += liquidity_confidence
        
        # 4. 市场深度 (20%)
        volume1 = float(correlated_market.market1.get('volume24hr', 0))
        volume2 = float(correlated_market.market2.get('volume24hr', 0))
        total_volume = volume1 + volume2
        
        volume_confidence = min(total_volume / 50000, 0.2)
        confidence += volume_confidence
        
        return min(confidence, 1.0)
    
    def execute_cross_market_arbitrage(self, signal: ArbitrageSignal):
        """执行跨市场套利"""
        self.logger.info(f"执行跨市场套利: {signal.type}")
        
        # 发送跨市场套利执行通知
        if self.notification_service:
            self.notification_service.info(
                "跨市场套利执行", 
                f"开始执行 {signal.type}\n"
                f"描述: {signal.description[:50]}...\n"
                f"预期收益: {signal.expected_return:.2%}\n"
                f"价格差异: {signal.correlated_market.price_discrepancy:.2%}"
            )
        
        try:
            if signal.type == 'buy_low_sell_high':
                # 买入低价市场，卖出高价市场
                low_market = signal.correlated_market.market1
                high_market = signal.correlated_market.market2
                
                self.execute_buy_order(low_market, signal)
                self.execute_sell_order(high_market, signal)
            
            elif signal.type == 'sell_high_buy_low':
                # 卖出高价市场，买入低价市场
                high_market = signal.correlated_market.market1
                low_market = signal.correlated_market.market2
                
                self.execute_sell_order(high_market, signal)
                self.execute_buy_order(low_market, signal)
            
            # 记录套利交易
            self.log_arbitrage_trade(signal)
            
            # 发送跨市场套利执行成功通知
            if self.notification_service:
                self.notification_service.success(
                    "跨市场套利执行成功", 
                    f"{signal.type} 执行完成\n"
                    f"描述: {signal.description[:50]}...\n"
                    f"预期收益: {signal.expected_return:.2%}\n"
                    f"价格差异: {signal.correlated_market.price_discrepancy:.2%}"
                )
            
        except Exception as e:
            self.logger.error(f"跨市场套利执行失败: {e}")
            
            # 发送跨市场套利执行失败通知
            if self.notification_service:
                self.notification_service.error(
                    "跨市场套利执行失败", 
                    f"执行 {signal.type} 失败\n"
                    f"错误: {str(e)}\n"
                    f"描述: {signal.description[:50]}..."
                )
    
    def execute_buy_order(self, market: Dict, signal: ArbitrageSignal):
        """执行买入订单"""
        position_size = self.calculate_position_size(market, signal)
        
        try:
            order_id = self.trading_client.create_order(
                market_id=market['id'],
                price=self.get_market_price(market),
                size=position_size,
                side='buy'
            )
            self.logger.info(f"买入订单: {order_id} - {market['question'][:30]}...")
            
        except Exception as e:
            self.logger.error(f"买入失败: {e}")
    
    def execute_sell_order(self, market: Dict, signal: ArbitrageSignal):
        """执行卖出订单"""
        position_size = self.calculate_position_size(market, signal)
        
        try:
            order_id = self.trading_client.create_order(
                market_id=market['id'],
                price=self.get_market_price(market),
                size=position_size,
                side='sell'
            )
            self.logger.info(f"卖出订单: {order_id} - {market['question'][:30]}...")
            
        except Exception as e:
            self.logger.error(f"卖出失败: {e}")
    
    def calculate_position_size(self, market: Dict, signal: ArbitrageSignal) -> float:
        """计算仓位大小"""
        # 基础仓位
        base_size = 150.0  # USDC
        
        # 根据置信度调整
        confidence_multiplier = signal.confidence
        
        # 根据预期收益调整
        return_multiplier = min(signal.expected_return * 8, 2.0)
        
        # 根据流动性调整
        liquidity = float(market.get('liquidity', 5000))
        liquidity_multiplier = min(liquidity / 15000, 1.5)
        
        # 计算最终仓位
        position_size = base_size * confidence_multiplier * return_multiplier * liquidity_multiplier
        
        # 限制最大仓位
        max_position = 1500.0  # 最大1500 USDC
        position_size = min(position_size, max_position)
        
        return round(position_size, 2)
    
    def log_arbitrage_signal(self, signal: ArbitrageSignal):
        """记录套利信号"""
        signal_data = {
            'timestamp': datetime.now().isoformat(),
            'type': signal.type,
            'correlation_type': signal.correlated_market.correlation_type,
            'price_discrepancy': signal.correlated_market.price_discrepancy,
            'expected_return': signal.expected_return,
            'confidence': signal.confidence,
            'theoretical_ratio': signal.correlated_market.theoretical_ratio,
            'actual_ratio': signal.correlated_market.actual_ratio,
            'description': signal.description
        }
        
        print(f"📊 套利信号记录: {json.dumps(signal_data, indent=2)}")
    
    def log_arbitrage_trade(self, signal: ArbitrageSignal):
        """记录套利交易"""
        trade_record = {
            'timestamp': datetime.now().isoformat(),
            'type': signal.type,
            'correlation_type': signal.correlated_market.correlation_type,
            'expected_return': signal.expected_return,
            'confidence': signal.confidence,
            'markets': [
                {
                    'id': signal.correlated_market.market1['id'],
                    'question': signal.correlated_market.market1['question'],
                    'price': self.get_market_price(signal.correlated_market.market1),
                    'position_size': self.calculate_position_size(signal.correlated_market.market1, signal)
                },
                {
                    'id': signal.correlated_market.market2['id'],
                    'question': signal.correlated_market.market2['question'],
                    'price': self.get_market_price(signal.correlated_market.market2),
                    'position_size': self.calculate_position_size(signal.correlated_market.market2, signal)
                }
            ]
        }
        
        print(f"💼 跨市场套利交易记录: {json.dumps(trade_record, indent=2)}")

def test_cross_market_arbitrage():
    """测试跨市场套利策略"""
    print("🧪 测试跨市场套利策略...")
    
    strategy = CrossMarketArbitrageStrategy(enable_trading=False)
    
    # 获取市场数据
    markets = strategy.gamma_client.get_trending_markets(limit=50)
    print(f"📊 获取到 {len(markets)} 个市场")
    
    # 发现相关市场
    correlated_markets = strategy.find_correlated_markets(markets)
    print(f"🔗 发现 {len(correlated_markets)} 对相关市场")
    
    # 识别套利机会
    arbitrage_signals = strategy.identify_arbitrage_opportunities(correlated_markets)
    print(f"🎯 识别 {len(arbitrage_signals)} 个套利机会")
    
    for i, signal in enumerate(arbitrage_signals[:3], 1):
        print(f"\n{i}. {signal.description}")
        print(f"   类型: {signal.type}")
        print(f"   价格差异: {signal.correlated_market.price_discrepancy:.2%}")
        print(f"   预期收益: {signal.expected_return:.2%}")
        print(f"   置信度: {signal.confidence:.2f}")

if __name__ == '__main__':
    test_cross_market_arbitrage()
