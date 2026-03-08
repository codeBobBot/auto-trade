#!/usr/bin/env python3
"""
套利策略模块
基于新闻情绪和市场价格差异进行套利
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ArbitrageOpportunity:
    """套利机会"""
    market_id: str
    market_question: str
    signal: str  # 'buy_yes', 'buy_no', 'sell_yes', 'sell_no'
    confidence: float  # 0-1
    reason: str
    timestamp: datetime

class ArbitrageStrategy:
    """套利策略"""
    
    def __init__(self):
        self.opportunities = []
        self.min_confidence = 0.7  # 最低置信度
    
    def analyze(self, market_data: Dict, news_sentiment: float) -> Optional[ArbitrageOpportunity]:
        """
        分析套利机会
        
        策略逻辑:
        1. 如果新闻情绪 > 0.5 且市场价格 < 0.6 → 买入 Yes
        2. 如果新闻情绪 < -0.5 且市场价格 > 0.4 → 买入 No
        3. 其他情况 → 观望
        """
        import json
        
        market_id = market_data.get('id')
        question = market_data.get('question', 'Unknown')
        
        # 获取当前价格 (处理字符串或字典格式)
        outcome_prices = market_data.get('outcomePrices', {})
        yes_price = 0.5  # 默认值
        
        if isinstance(outcome_prices, dict):
            yes_price = outcome_prices.get('Yes', 0.5)
        elif isinstance(outcome_prices, str):
            try:
                prices_dict = json.loads(outcome_prices)
                yes_price = prices_dict.get('Yes', 0.5)
            except:
                yes_price = 0.5
        
        # 确保 yes_price 是数字
        try:
            yes_price = float(yes_price)
        except:
            yes_price = 0.5
        
        opportunity = None
        
        if news_sentiment > 0.5 and yes_price < 0.6:
            opportunity = ArbitrageOpportunity(
                market_id=market_id,
                market_question=question,
                signal='buy_yes',
                confidence=min(news_sentiment, 0.95),
                reason=f"积极情绪 ({news_sentiment:.2f}) + 低价 ({yes_price:.2f})",
                timestamp=datetime.now()
            )
        elif news_sentiment < -0.5 and yes_price > 0.4:
            opportunity = ArbitrageOpportunity(
                market_id=market_id,
                market_question=question,
                signal='buy_no',
                confidence=min(abs(news_sentiment), 0.95),
                reason=f"消极情绪 ({news_sentiment:.2f}) + 高价 ({yes_price:.2f})",
                timestamp=datetime.now()
            )
        
        if opportunity and opportunity.confidence >= self.min_confidence:
            self.opportunities.append(opportunity)
            return opportunity
        
        return None
    
    def get_opportunities(self, limit: int = 10) -> List[ArbitrageOpportunity]:
        """获取最近的套利机会"""
        return sorted(
            self.opportunities,
            key=lambda x: x.confidence,
            reverse=True
        )[:limit]


def test_strategy():
    """测试策略"""
    print("\n🎯 测试套利策略...")
    
    strategy = ArbitrageStrategy()
    
    # 模拟数据
    test_cases = [
        {'market': {'id': '1', 'question': 'Will Trump win?', 'outcomePrices': {'Yes': 0.55}}, 'sentiment': 0.8},
        {'market': {'id': '2', 'question': 'Will BTC hit 100k?', 'outcomePrices': {'Yes': 0.3}}, 'sentiment': 0.6},
        {'market': {'id': '3', 'question': 'Will it rain?', 'outcomePrices': {'Yes': 0.7}}, 'sentiment': -0.3},
    ]
    
    for case in test_cases:
        opp = strategy.analyze(case['market'], case['sentiment'])
        if opp:
            print(f"  ✅ 发现机会: {opp.market_question}")
            print(f"     信号: {opp.signal}, 置信度: {opp.confidence:.2f}")
            print(f"     原因: {opp.reason}")
        else:
            print(f"  ⏸️  无机会: {case['market']['question']}")


if __name__ == '__main__':
    test_strategy()
