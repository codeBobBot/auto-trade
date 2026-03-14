#!/usr/bin/env python3
"""
时间套利策略
利用临近结算时的价格偏差进行套利

核心思路：
1. 监控临近结算的市场
2. 评估真实概率
3. 发现价格偏差
4. 临近结算时套利
"""

import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from gamma_client import PolymarketGammaClient
from clob_client_auto_creds import ClobTradingClientAutoCreds

@dataclass
class TimeArbitrageOpportunity:
    """时间套利机会"""
    market: Dict
    days_to_expiry: int
    current_price: float
    estimated_true_probability: float
    price_discrepancy: float
    expected_return: float
    confidence: float
    urgency: str  # 'high', 'medium', 'low'

class TimeArbitrageStrategy:
    """时间套利策略"""
    
    def __init__(self, enable_trading: bool = False, notification_service=None):
        self.enable_trading = enable_trading
        self.notification_service = notification_service
        
        # 初始化组件
        self.gamma_client = PolymarketGammaClient()
        self.trading_client = ClobTradingClientAutoCreds()
        
        # 发送初始化通知
        if self.notification_service:
            self.notification_service.info("策略初始化", "时间套利策略已初始化")
        
        # 时间套利参数
        self.time_arbitrage_params = {
            'max_days_to_expiry': 30,      # 最大30天到期的市场
            'min_days_to_expiry': 1,       # 最少1天到期的市场
            'min_price_discrepancy': 0.10, # 最小价格差异10%
            'max_price_discrepancy': 0.40, # 最大价格差异40%
            'min_liquidity': 5000,         # 最小流动性5000 USDC
            'min_confidence': 0.6,          # 最小置信度0.6
            'urgency_thresholds': {
                'high': 3,    # 3天内到期
                'medium': 7,  # 7天内到期
                'low': 30     # 30天内到期
            }
        }
        
        # 真实概率评估因子
        self.probability_assessment_factors = {
            'news_sentiment_weight': 0.4,
            'historical_trend_weight': 0.3,
            'market_consensus_weight': 0.2,
            'liquidity_weight': 0.1
        }
    
    def scan_time_arbitrage(self, scan_interval: int = 120):
        """持续扫描时间套利机会"""
        print("🔍 启动时间套利策略...")
        print(f"📊 扫描间隔: {scan_interval}秒")
        print(f"💰 交易模式: {'实盘交易' if self.enable_trading else '模拟模式'}")
        
        while True:
            try:
                # 1. 获取市场数据
                markets = self.gamma_client.get_trending_markets(limit=100)
                
                # 2. 筛选临近到期的市场
                expiry_markets = self.filter_expiry_markets(markets)
                
                # 3. 评估真实概率
                opportunities = self.assess_true_probabilities(expiry_markets)
                
                # 4. 发现套利机会
                arbitrage_opportunities = self.identify_time_arbitrage(opportunities)
                
                # 5. 执行套利
                for opportunity in arbitrage_opportunities:
                    print(f"\n🎯 发现时间套利机会:")
                    print(f"   市场: {opportunity.market['question'][:50]}...")
                    print(f"   到期时间: {opportunity.days_to_expiry}天")
                    print(f"   当前价格: {opportunity.current_price:.2f}")
                    print(f"   真实概率: {opportunity.estimated_true_probability:.2f}")
                    print(f"   价格差异: {opportunity.price_discrepancy:.2%}")
                    print(f"   预期收益: {opportunity.expected_return:.2%}")
                    print(f"   紧急程度: {opportunity.urgency}")
                    
                    if self.enable_trading:
                        self.execute_time_arbitrage(opportunity)
                    else:
                        print("📝 模拟模式：记录套利机会")
                        self.log_arbitrage_opportunity(opportunity)
                
                # 6. 等待下次扫描
                time.sleep(scan_interval)
                
            except KeyboardInterrupt:
                print("\n⏹️ 时间套利策略已停止")
                break
            except Exception as e:
                print(f"❌ 时间套利扫描错误: {e}")
                time.sleep(60)
    
    def filter_expiry_markets(self, markets: List[Dict]) -> List[Dict]:
        """筛选临近到期的市场"""
        expiry_markets = []
        current_date = datetime.now()
        
        for market in markets:
            # 获取到期时间
            end_date = market.get('endDate')
            if not end_date:
                continue
            
            try:
                # 解析到期时间
                if isinstance(end_date, str):
                    expiry_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                else:
                    continue
                
                # 计算到期天数
                days_to_expiry = (expiry_date - current_date).days
                
                # 筛选符合条件的市场
                if (self.time_arbitrage_params['min_days_to_expiry'] <= days_to_expiry <= 
                    self.time_arbitrage_params['max_days_to_expiry']):
                    
                    # 添加到期天数信息
                    market['days_to_expiry'] = days_to_expiry
                    expiry_markets.append(market)
                
            except Exception as e:
                continue
        
        return expiry_markets
    
    def assess_true_probabilities(self, markets: List[Dict]) -> List[Dict]:
        """评估真实概率"""
        assessed_markets = []
        
        for market in markets:
            try:
                # 获取当前价格
                current_price = self.get_market_price(market)
                
                # 评估真实概率
                true_probability = self.calculate_true_probability(market, current_price)
                
                # 添加评估结果
                market['current_price'] = current_price
                market['estimated_true_probability'] = true_probability
                market['price_discrepancy'] = abs(true_probability - current_price) / current_price
                
                assessed_markets.append(market)
                
            except Exception as e:
                continue
        
        return assessed_markets
    
    def calculate_true_probability(self, market: Dict, current_price: float) -> float:
        """计算真实概率"""
        # 1. 新闻情绪评估
        news_sentiment = self.assess_news_sentiment(market)
        
        # 2. 历史趋势评估
        historical_trend = self.assess_historical_trend(market)
        
        # 3. 市场共识评估
        market_consensus = self.assess_market_consensus(market)
        
        # 4. 流动性评估
        liquidity_factor = self.assess_liquidity_factor(market)
        
        # 计算加权真实概率
        true_probability = (
            news_sentiment * self.probability_assessment_factors['news_sentiment_weight'] +
            historical_trend * self.probability_assessment_factors['historical_trend_weight'] +
            market_consensus * self.probability_assessment_factors['market_consensus_weight'] +
            liquidity_factor * self.probability_assessment_factors['liquidity_weight']
        )
        
        # 确保概率在合理范围内
        true_probability = max(0.01, min(0.99, true_probability))
        
        return true_probability
    
    def assess_news_sentiment(self, market: Dict) -> float:
        """评估新闻情绪"""
        question = market.get('question', '').lower()
        
        # 基于关键词快速评估
        positive_keywords = ['win', 'success', 'achieve', 'beat', 'exceed', 'growth', 'approval']
        negative_keywords = ['lose', 'fail', 'decline', 'drop', 'fall', 'rejection', 'opposition']
        
        positive_count = sum(1 for kw in positive_keywords if kw in question)
        negative_count = sum(1 for kw in negative_keywords if kw in question)
        
        if positive_count > negative_count:
            return 0.7  # 偏向正面
        elif negative_count > positive_count:
            return 0.3  # 偏向负面
        else:
            return 0.5  # 中性
    
    def assess_historical_trend(self, market: Dict) -> float:
        """评估历史趋势"""
        # 基于交易量趋势评估
        volume_24hr = float(market.get('volume24hr', 0))
        volume_1wk = float(market.get('volume1wk', 0))
        volume_1mo = float(market.get('volume1mo', 0))
        
        if volume_1wk > 0 and volume_1mo > 0:
            # 计算近期交易量占比
            recent_ratio = volume_24hr / volume_1wk
            weekly_ratio = volume_1wk / volume_1mo
            
            # 如果近期交易量增加，可能表示趋势明确
            if recent_ratio > 0.3 and weekly_ratio > 0.5:
                return 0.6
            else:
                return 0.4
        
        return 0.5
    
    def assess_market_consensus(self, market: Dict) -> float:
        """评估市场共识"""
        # 使用当前价格作为市场共识的基础
        current_price = self.get_market_price(market)
        
        # 基于流动性调整共识强度
        liquidity = float(market.get('liquidity', 0))
        
        if liquidity > 50000:
            # 高流动性，价格更可靠
            return current_price
        elif liquidity > 10000:
            # 中等流动性，价格中等可靠
            return current_price * 0.9 + 0.05
        else:
            # 低流动性，价格不太可靠
            return current_price * 0.8 + 0.1
    
    def assess_liquidity_factor(self, market: Dict) -> float:
        """评估流动性因子"""
        liquidity = float(market.get('liquidity', 0))
        
        if liquidity > 100000:
            return 0.6  # 高流动性支持
        elif liquidity > 50000:
            return 0.5  # 中等流动性
        elif liquidity > 10000:
            return 0.4  # 低流动性
        else:
            return 0.3  # 极低流动性
    
    def get_market_price(self, market: Dict) -> float:
        """获取市场价格"""
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
        
        return 0.5
    
    def identify_time_arbitrage(self, markets: List[Dict]) -> List[TimeArbitrageOpportunity]:
        """识别时间套利机会"""
        opportunities = []
        
        for market in markets:
            current_price = market['current_price']
            true_probability = market['estimated_true_probability']
            price_discrepancy = market['price_discrepancy']
            
            # 检查是否满足套利条件
            if (price_discrepancy >= self.time_arbitrage_params['min_price_discrepancy'] and
                price_discrepancy <= self.time_arbitrage_params['max_price_discrepancy']):
                
                # 确定套利方向
                if true_probability > current_price:
                    # 真实概率高于当前价格，应该买入
                    expected_return = (true_probability - current_price) / current_price
                    direction = 'buy'
                else:
                    # 真实概率低于当前价格，应该卖出
                    expected_return = (current_price - true_probability) / current_price
                    direction = 'sell'
                
                # 计算置信度
                confidence = self.calculate_time_arbitrage_confidence(market)
                
                # 确定紧急程度
                urgency = self.determine_urgency(market['days_to_expiry'])
                
                # 检查最小条件
                if (expected_return > 0.05 and 
                    confidence >= self.time_arbitrage_params['min_confidence'] and
                    float(market.get('liquidity', 0)) >= self.time_arbitrage_params['min_liquidity']):
                    
                    opportunity = TimeArbitrageOpportunity(
                        market=market,
                        days_to_expiry=market['days_to_expiry'],
                        current_price=current_price,
                        estimated_true_probability=true_probability,
                        price_discrepancy=price_discrepancy,
                        expected_return=expected_return,
                        confidence=confidence,
                        urgency=urgency
                    )
                    
                    opportunities.append(opportunity)
        
        # 按预期收益排序
        opportunities.sort(key=lambda x: x.expected_return, reverse=True)
        
        return opportunities
    
    def calculate_time_arbitrage_confidence(self, market: Dict) -> float:
        """计算时间套利置信度"""
        confidence = 0.0
        
        # 1. 时间紧急性 (30%)
        days_to_expiry = market['days_to_expiry']
        if days_to_expiry <= 3:
            time_confidence = 0.3
        elif days_to_expiry <= 7:
            time_confidence = 0.25
        elif days_to_expiry <= 14:
            time_confidence = 0.2
        else:
            time_confidence = 0.15
        
        confidence += time_confidence
        
        # 2. 价格差异幅度 (25%)
        price_discrepancy = market['price_discrepancy']
        if price_discrepancy > 0.25:
            discrepancy_confidence = 0.25
        elif price_discrepancy > 0.15:
            discrepancy_confidence = 0.2
        elif price_discrepancy > 0.10:
            discrepancy_confidence = 0.15
        else:
            discrepancy_confidence = 0.1
        
        confidence += discrepancy_confidence
        
        # 3. 流动性 (25%)
        liquidity = float(market.get('liquidity', 0))
        liquidity_confidence = min(liquidity / 50000, 0.25)
        confidence += liquidity_confidence
        
        # 4. 市场活跃度 (20%)
        volume = float(market.get('volume24hr', 0))
        volume_confidence = min(volume / 30000, 0.2)
        confidence += volume_confidence
        
        return min(confidence, 1.0)
    
    def determine_urgency(self, days_to_expiry: int) -> str:
        """确定紧急程度"""
        if days_to_expiry <= self.time_arbitrage_params['urgency_thresholds']['high']:
            return 'high'
        elif days_to_expiry <= self.time_arbitrage_params['urgency_thresholds']['medium']:
            return 'medium'
        else:
            return 'low'
    
    def execute_time_arbitrage(self, opportunity: TimeArbitrageOpportunity):
        """执行时间套利"""
        print(f"🎯 执行时间套利: {opportunity.days_to_expiry}天到期")
        
        try:
            # 确定交易方向
            if opportunity.estimated_true_probability > opportunity.current_price:
                # 买入
                self.execute_buy_order(opportunity)
            else:
                # 卖出
                self.execute_sell_order(opportunity)
            
            # 记录交易
            self.log_arbitrage_trade(opportunity)
            
        except Exception as e:
            print(f"❌ 时间套利执行失败: {e}")
    
    def execute_buy_order(self, opportunity: TimeArbitrageOpportunity):
        """执行买入订单"""
        position_size = self.calculate_position_size(opportunity)
        
        try:
            order_id = self.trading_client.create_order(
                market_id=opportunity.market['id'],
                price=opportunity.current_price,
                size=position_size,
                side='buy'
            )
            print(f"✅ 买入订单: {order_id} - {opportunity.market['question'][:30]}...")
            
        except Exception as e:
            print(f"❌ 买入失败: {e}")
    
    def execute_sell_order(self, opportunity: TimeArbitrageOpportunity):
        """执行卖出订单"""
        position_size = self.calculate_position_size(opportunity)
        
        try:
            order_id = self.trading_client.create_order(
                market_id=opportunity.market['id'],
                price=opportunity.current_price,
                size=position_size,
                side='sell'
            )
            print(f"✅ 卖出订单: {order_id} - {opportunity.market['question'][:30]}...")
            
        except Exception as e:
            print(f"❌ 卖出失败: {e}")
    
    def calculate_position_size(self, opportunity: TimeArbitrageOpportunity) -> float:
        """计算仓位大小"""
        # 基础仓位
        base_size = 250.0  # USDC
        
        # 根据置信度调整
        confidence_multiplier = opportunity.confidence
        
        # 根据预期收益调整
        return_multiplier = min(opportunity.expected_return * 6, 2.0)
        
        # 根据紧急程度调整
        urgency_multiplier = {
            'high': 1.5,
            'medium': 1.2,
            'low': 1.0
        }.get(opportunity.urgency, 1.0)
        
        # 根据流动性调整
        liquidity = float(opportunity.market.get('liquidity', 5000))
        liquidity_multiplier = min(liquidity / 20000, 1.5)
        
        # 计算最终仓位
        position_size = base_size * confidence_multiplier * return_multiplier * urgency_multiplier * liquidity_multiplier
        
        # 限制最大仓位
        max_position = 3000.0  # 最大3000 USDC
        position_size = min(position_size, max_position)
        
        return round(position_size, 2)
    
    def log_arbitrage_opportunity(self, opportunity: TimeArbitrageOpportunity):
        """记录套利机会"""
        opportunity_data = {
            'timestamp': datetime.now().isoformat(),
            'market_question': opportunity.market['question'],
            'days_to_expiry': opportunity.days_to_expiry,
            'current_price': opportunity.current_price,
            'estimated_true_probability': opportunity.estimated_true_probability,
            'price_discrepancy': opportunity.price_discrepancy,
            'expected_return': opportunity.expected_return,
            'confidence': opportunity.confidence,
            'urgency': opportunity.urgency
        }
        
        print(f"📊 时间套利机会记录: {json.dumps(opportunity_data, indent=2)}")
    
    def log_arbitrage_trade(self, opportunity: TimeArbitrageOpportunity):
        """记录套利交易"""
        trade_record = {
            'timestamp': datetime.now().isoformat(),
            'market_id': opportunity.market['id'],
            'market_question': opportunity.market['question'],
            'days_to_expiry': opportunity.days_to_expiry,
            'current_price': opportunity.current_price,
            'estimated_true_probability': opportunity.estimated_true_probability,
            'expected_return': opportunity.expected_return,
            'position_size': self.calculate_position_size(opportunity),
            'urgency': opportunity.urgency
        }
        
        print(f"💼 时间套利交易记录: {json.dumps(trade_record, indent=2)}")

def test_time_arbitrage():
    """测试时间套利策略"""
    print("🧪 测试时间套利策略...")
    
    strategy = TimeArbitrageStrategy(enable_trading=False)
    
    # 获取市场数据
    markets = strategy.gamma_client.get_trending_markets(limit=100)
    print(f"📊 获取到 {len(markets)} 个市场")
    
    # 筛选临近到期的市场
    expiry_markets = strategy.filter_expiry_markets(markets)
    print(f"⏰ 筛选到 {len(expiry_markets)} 个临近到期市场")
    
    # 评估真实概率
    opportunities = strategy.assess_true_probabilities(expiry_markets)
    
    # 识别套利机会
    arbitrage_opportunities = strategy.identify_time_arbitrage(opportunities)
    print(f"🎯 识别 {len(arbitrage_opportunities)} 个时间套利机会")
    
    for i, opp in enumerate(arbitrage_opportunities[:3], 1):
        print(f"\n{i}. {opp.market['question'][:50]}...")
        print(f"   到期时间: {opp.days_to_expiry}天")
        print(f"   价格差异: {opp.price_discrepancy:.2%}")
        print(f"   预期收益: {opp.expected_return:.2%}")
        print(f"   紧急程度: {opp.urgency}")

if __name__ == '__main__':
    test_time_arbitrage()
