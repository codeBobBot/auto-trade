#!/usr/bin/env python3
"""
纯价格驱动策略
不依赖新闻情绪，基于市场数据和技术指标生成信号
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import json

@dataclass
class PriceSignal:
    """价格信号"""
    market_id: str
    market_question: str
    signal: str  # 'buy_yes', 'buy_no', 'sell_yes', 'sell_no'
    confidence: float
    reason: str
    indicators: Dict
    timestamp: datetime

class PriceStrategy:
    """纯价格驱动策略"""
    
    def __init__(self):
        self.signals = []
        self.min_confidence = 0.3
    
    def analyze(self, market_data: Dict) -> Optional[PriceSignal]:
        """
        基于价格数据生成交易信号
        
        策略逻辑:
        1. 价格偏离度分析 - 价格是否偏离合理区间
        2. 流动性分析 - 订单簿深度
        3. 波动率分析 - 近期价格变动
        """
        market_id = market_data.get('id') or market_data.get('conditionId')
        question = market_data.get('question', 'Unknown')
        
        # 获取价格数据
        outcome_prices = market_data.get('outcomePrices', {})
        yes_price = self._extract_price(outcome_prices, 'Yes')
        no_price = self._extract_price(outcome_prices, 'No') or (1 - yes_price)
        
        # 获取成交量和流动性数据（处理字符串格式）
        volume = self._to_float(market_data.get('volume', 0))
        liquidity = self._to_float(market_data.get('liquidity', 0))
        spread = self._to_float(market_data.get('spread', abs(yes_price - no_price)))
        
        indicators = {
            'yes_price': yes_price,
            'no_price': no_price,
            'spread': spread,
            'volume': volume,
            'liquidity': liquidity
        }
        
        signal = None
        confidence = 0.0
        reason = ""
        
        # 策略 1: 极端价格均值回归
        if yes_price < 0.15:
            signal = 'buy_yes'
            confidence = 0.4 + (0.15 - yes_price)  # 价格越低，置信度越高
            reason = f"极端低价 ({yes_price:.2f})，均值回归机会"
        elif yes_price > 0.85:
            signal = 'buy_no'
            confidence = 0.4 + (yes_price - 0.85)
            reason = f"极端高价 ({yes_price:.2f})，反向机会"
        
        # 策略 2: 高流动性 + 窄价差 = 高置信度
        if liquidity > 100000 and spread < 0.05:
            confidence += 0.15
            reason += " | 高流动性窄价差"
        
        # 策略 3: 高成交量 = 市场关注
        if volume > 1000000:
            confidence += 0.1
            reason += " | 高成交量"
        
        # 策略 4: 价格处于中间区域 (0.4-0.6)，双向机会
        if 0.4 <= yes_price <= 0.6 and not signal:
            if yes_price < 0.5:
                signal = 'buy_yes'
                confidence = 0.35
            else:
                signal = 'buy_no'
                confidence = 0.35
            reason = f"价格中性区域 ({yes_price:.2f})，双向博弈"
        
        # 限制置信度上限
        confidence = min(0.95, confidence)
        
        if signal and confidence >= self.min_confidence:
            price_signal = PriceSignal(
                market_id=market_id,
                market_question=question,
                signal=signal,
                confidence=confidence,
                reason=reason,
                indicators=indicators,
                timestamp=datetime.now()
            )
            self.signals.append(price_signal)
            return price_signal
        
        return None
    
    def _extract_price(self, outcome_prices, key: str) -> float:
        """提取价格，处理多种格式"""
        if isinstance(outcome_prices, dict):
            price = outcome_prices.get(key, 0.5)
        elif isinstance(outcome_prices, str):
            try:
                prices_dict = json.loads(outcome_prices)
                price = prices_dict.get(key, 0.5)
            except:
                price = 0.5
        else:
            price = 0.5
        
        return self._to_float(price, 0.5)
    
    def _to_float(self, value, default: float = 0.0) -> float:
        """安全转换为浮点数"""
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def get_signals(self, limit: int = 10) -> List[PriceSignal]:
        """获取最近的价格信号"""
        return sorted(
            self.signals,
            key=lambda x: x.confidence,
            reverse=True
        )[:limit]


def test_price_strategy():
    """测试价格策略"""
    print("\n" + "=" * 70)
    print("💰 纯价格策略测试")
    print("=" * 70)
    
    strategy = PriceStrategy()
    
    # 测试用例
    test_cases = [
        {
            'name': '极端低价',
            'market': {
                'id': '1',
                'question': 'Will BTC hit 100k?',
                'outcomePrices': {'Yes': 0.08, 'No': 0.92},
                'volume': 500000,
                'liquidity': 200000
            }
        },
        {
            'name': '极端高价',
            'market': {
                'id': '2',
                'question': 'Will Trump win?',
                'outcomePrices': {'Yes': 0.92, 'No': 0.08},
                'volume': 2000000,
                'liquidity': 500000
            }
        },
        {
            'name': '中性价格',
            'market': {
                'id': '3',
                'question': 'Will it rain tomorrow?',
                'outcomePrices': {'Yes': 0.52, 'No': 0.48},
                'volume': 50000,
                'liquidity': 10000
            }
        },
        {
            'name': '高流动性',
            'market': {
                'id': '4',
                'question': 'Fed rate cut?',
                'outcomePrices': {'Yes': 0.35, 'No': 0.65},
                'volume': 5000000,
                'liquidity': 1000000
            }
        }
    ]
    
    for case in test_cases:
        print(f"\n📊 {case['name']}")
        signal = strategy.analyze(case['market'])
        if signal:
            print(f"   ✅ 信号: {signal.signal}")
            print(f"   置信度: {signal.confidence:.2%}")
            print(f"   原因: {signal.reason}")
            print(f"   指标: Yes={signal.indicators['yes_price']:.2f}, "
                  f"Vol={signal.indicators['volume']:,.0f}")
        else:
            print(f"   ⏸️  无信号")
            prices = case['market'].get('outcomePrices', {})
            yes = prices.get('Yes', 'N/A') if isinstance(prices, dict) else 'N/A'
            print(f"   价格: Yes={yes}")


if __name__ == '__main__':
    test_price_strategy()
