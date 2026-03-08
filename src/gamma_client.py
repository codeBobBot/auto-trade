#!/usr/bin/env python3
"""
Polymarket 数据获取 - 使用 Gamma API
无需身份验证即可获取市场数据
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Union
import requests
from dotenv import load_dotenv

load_dotenv('/Users/lsl_mac/.openclaw/workspace/projects/polymarket-arbitrage/config/.env')

class PolymarketGammaClient:
    """使用 Gamma API 获取 Polymarket 数据"""
    
    # Gamma API 端点（公开数据）
    GAMMA_API_URL = "https://gamma-api.polymarket.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_markets(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """获取市场列表"""
        url = f"{self.GAMMA_API_URL}/markets"
        params = {
            'limit': limit,
            'offset': offset
        }
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def get_market(self, market_id: str) -> Dict:
        """获取特定市场详情"""
        url = f"{self.GAMMA_API_URL}/markets/{market_id}"
        
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def get_market_orderbook(self, market_id: str) -> Dict:
        """获取市场订单簿"""
        url = f"{self.GAMMA_API_URL}/markets/{market_id}/orderbook"
        
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def get_events(self, limit: int = 50) -> List[Dict]:
        """获取事件列表"""
        url = f"{self.GAMMA_API_URL}/events"
        params = {
            'limit': limit,
            'active': 'true'
        }
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def search_markets(self, query: str, limit: int = 20) -> List[Dict]:
        """搜索市场"""
        url = f"{self.GAMMA_API_URL}/markets"
        params = {
            'limit': limit,
            'search': query,
            'active': 'true'
        }
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()


def test_gamma_api():
    """测试 Gamma API"""
    print("\n🔍 测试 Gamma API (Polymarket 数据源)...")
    
    try:
        client = PolymarketGammaClient()
        
        # 测试获取市场列表
        print("  📊 获取活跃市场列表...")
        markets = client.get_markets(limit=5)
        print(f"  ✅ 成功获取 {len(markets)} 个市场")
        
        # 显示市场信息
        if markets:
            print("\n  📈 热门市场:")
            for i, market in enumerate(markets[:3], 1):
                question = market.get('question', 'N/A')
                volume = market.get('volume', 0)
                liquidity = market.get('liquidity', 0)
                
                # 处理 outcomePrices
                outcome_prices = market.get('outcomePrices', {})
                yes_price = 'N/A'
                if isinstance(outcome_prices, dict):
                    yes_price = outcome_prices.get('Yes', 'N/A')
                elif isinstance(outcome_prices, str):
                    try:
                        prices = json.loads(outcome_prices)
                        yes_price = prices.get('Yes', 'N/A')
                    except:
                        yes_price = 'N/A'
                
                print(f"\n     {i}. {question[:50]}...")
                print(f"        交易量: ${float(volume):,.0f} | 流动性: ${float(liquidity):,.0f}")
                if yes_price != 'N/A':
                    try:
                        print(f"        Yes 价格: {float(yes_price):.2f}")
                    except:
                        print(f"        Yes 价格: {yes_price}")
        
        # 测试搜索
        print("\n  🔎 搜索 'Trump' 相关市场...")
        trump_markets = client.search_markets("Trump", limit=3)
        print(f"  ✅ 找到 {len(trump_markets)} 个相关市场")
        
        for market in trump_markets[:2]:
            print(f"     - {market.get('question', 'N/A')[:40]}...")
        
        return True
        
    except Exception as e:
        print(f"  ❌ API 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    test_gamma_api()
