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

load_dotenv('config/.env')

class PolymarketGammaClient:
    """使用 Gamma API 获取 Polymarket 数据"""
    
    # Gamma API 端点（公开数据）
    GAMMA_API_URL = "https://gamma-api.polymarket.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_markets(self, limit: int = 100, offset: int = 0, active: bool = True, sort_by_volume: bool = True) -> List[Dict]:
        """获取市场列表 - 使用官方推荐的事件端点"""
        # 使用 events 端点获取更全面的数据
        url = f"{self.GAMMA_API_URL}/events"
        params = {
            'limit': limit,
            'offset': offset
        }
        
        # 添加过滤条件
        if active is not None:
            params['active'] = str(active).lower()
        if sort_by_volume:
            params['order'] = 'volume24hr'  # 注意：实际字段名是 volume24hr
            params['ascending'] = 'false'
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        # 返回事件列表，每个事件包含市场信息
        return data if isinstance(data, list) else []
    
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
        url = f"{self.GAMMA_API_URL}/events"
        params = {
            'limit': limit,
            'search': query,
            'order': 'volume24hr',
            'ascending': 'false'
        }
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        events = response.json()
        if not isinstance(events, list):
            return []
        
        # 提取市场信息
        markets = []
        for event in events:
            if isinstance(event, dict):
                event_markets = event.get('markets', [])
                for market in event_markets:
                    if isinstance(market, dict):
                        market['event_title'] = event.get('title', '')
                        market['event_slug'] = event.get('slug', '')
                        markets.append(market)
        
        return markets
    
    def get_markets_by_tag(self, tag_id: str, limit: int = 20, related_tags: bool = False) -> List[Dict]:
        """
        按标签获取市场
        """
        try:
            url = f"{self.GAMMA_API_URL}/events"
            params = {
                'tag_id': tag_id,
                'limit': limit,
                'active': True,
                'closed': False,
                'order': 'volume_24hr',
                'ascending': False
            }
            
            if related_tags:
                params['related_tags'] = 'true'
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            events = response.json()
            if not isinstance(events, list):
                return []
            
            # 提取市场信息
            markets = []
            for event in events:
                if isinstance(event, dict):
                    event_markets = event.get('markets', [])
                    for market in event_markets:
                        if isinstance(market, dict):
                            market['event_title'] = event.get('title', '')
                            market['event_slug'] = event.get('slug', '')
                            markets.append(market)
            
            return markets
            
        except Exception as e:
            print(f"⚠️  按标签获取市场失败: {e}")
            return []
    
    def get_available_tags(self) -> List[Dict]:
        """
        获取可用的标签列表
        """
        try:
            url = f"{self.GAMMA_API_URL}/tags"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            tags = response.json()
            return tags if isinstance(tags, list) else []
            
        except Exception as e:
            print(f"⚠️  获取标签失败: {e}")
            return []
    
    def get_trending_markets(self, limit: int = 20) -> List[Dict]:
        """
        获取实时热门市场列表
        按 24 小时交易量排序，返回最活跃的市场
        """
        try:
            # 使用官方推荐的参数获取热门市场
            url = f"{self.GAMMA_API_URL}/events"
            params = {
                'active': 'true',
                'order': 'volume24hr',
                'ascending': 'false',
                'limit': limit
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            events = response.json()
            if not isinstance(events, list):
                return []
            
            # 提取市场信息
            trending_markets = []
            for event in events:
                if isinstance(event, dict):
                    markets = event.get('markets', [])
                    for market in markets:
                        if isinstance(market, dict):
                            # 添加事件信息到市场数据
                            market['event_title'] = event.get('title', '')
                            market['event_slug'] = event.get('slug', '')
                            trending_markets.append(market)
            
            # 按交易量排序
            trending_markets.sort(key=lambda x: float(x.get('volume24hr', 0)), reverse=True)
            
            print(f"📈 获取到 {len(trending_markets)} 个热门市场")
            return trending_markets[:limit]
            
        except Exception as e:
            print(f"⚠️  获取热门市场失败: {e}")
            return []
    
    def get_trending_keywords(self, limit: int = 8) -> List[str]:
        """
        从 Polymarket 热门市场提取关键词
        返回实时热门话题关键词列表
        """
        keywords = []
        
        try:
            # 获取热门市场
            trending_markets = self.get_trending_markets(limit=15)
            
            print(f"  📊 分析 {len(trending_markets)} 个热门市场")
            
            for market in trending_markets:
                question = market.get('question', '') if isinstance(market, dict) else ''
                if question:
                    words = self._extract_keywords_from_question(question)
                    keywords.extend(words)
            
            # 去重并限制数量
            unique_keywords = list(dict.fromkeys(keywords))
            
            # 如果提取的关键词太少，添加一些默认热门词
            if len(unique_keywords) < 5:
                default_keywords = ['Trump', 'crypto', 'Bitcoin', 'Ethereum', 'AI', 'Fed', 'ETF', 'election']
                for kw in default_keywords:
                    if kw not in unique_keywords:
                        unique_keywords.append(kw)
            
            return unique_keywords[:limit]
            
        except Exception as e:
            print(f"⚠️  获取热门关键词失败: {e}")
            import traceback
            traceback.print_exc()
            # 返回默认关键词
            return ['Trump', 'crypto', 'Bitcoin', 'Ethereum', 'AI', 'Fed', 'ETF', 'election']
    
    def _extract_keywords_from_question(self, question: str) -> List[str]:
        """从市场问题中提取关键词"""
        import re
        
        if not question:
            return []
        
        # 定义重要关键词映射（大写 -> 原始格式）
        important_keywords = {
            'TRUMP': 'Trump',
            'BIDEN': 'Biden', 
            'CRYPTO': 'crypto',
            'BITCOIN': 'Bitcoin',
            'ETHEREUM': 'Ethereum',
            'BTC': 'Bitcoin',
            'ETH': 'Ethereum',
            'AI': 'AI',
            'ELON': 'Elon',
            'MUSK': 'Musk',
            'FED': 'Fed',
            'SEC': 'SEC',
            'CHINA': 'China',
            'RUSSIA': 'Russia',
            'UKRAINE': 'Ukraine',
            'ISRAEL': 'Israel',
            'GAZA': 'Gaza',
            'IRAN': 'Iran',
            'ELECTION': 'election',
            'VOTE': 'vote',
            'PRESIDENT': 'President',
            'CONGRESS': 'Congress',
            'SENATE': 'Senate',
            'ETF': 'ETF',
            'APPROVAL': 'approval',
            'LAUNCH': 'launch',
            'IPO': 'IPO',
            'TESLA': 'Tesla',
            'APPLE': 'Apple',
            'AMAZON': 'Amazon',
            'GOOGLE': 'Google',
            'MICROSOFT': 'Microsoft',
            'META': 'Meta',
            'RECESSION': 'recession',
            'INFLATION': 'inflation',
            'GDP': 'GDP',
            'NASDAQ': 'NASDAQ',
            'SP500': 'S&P 500',
            'NVIDIA': 'NVIDIA',
        }
        
        keywords = []
        question_upper = question.upper()
        
        # 直接匹配关键词
        for key, value in important_keywords.items():
            if key in question_upper:
                keywords.append(value)
        
        # 如果没有匹配到，提取前3个重要单词
        if not keywords:
            words = question.split()
            # 过滤停用词和短词
            stop_words = {'THE', 'A', 'AN', 'IN', 'ON', 'AT', 'TO', 'FOR', 'OF', 'AND', 'OR', 
                         'BY', 'WILL', 'BE', 'IS', 'ARE', 'THIS', 'THAT', 'WITH', 'HAVE', 
                         'HAS', 'HAD', 'DO', 'DOES', 'DID', 'CAN', 'COULD', 'WOULD', 'SHOULD'}
            content_words = [w.strip('?.,!;:') for w in words 
                           if len(w) > 3 and w.upper() not in stop_words]
            
            # 取前3个并首字母大写
            for word in content_words[:3]:
                if word:
                    keywords.append(word.capitalize())
        
        return keywords


def test_gamma_api():
    """测试 Gamma API"""
    print("\n🔍 测试 Gamma API (Polymarket 数据源)...")
    
    try:
        client = PolymarketGammaClient()
        
        # 测试获取实时热门市场
        print("  📊 获取实时热门市场...")
        trending_markets = client.get_trending_markets(limit=5)
        print(f"  ✅ 成功获取 {len(trending_markets)} 个热门市场")
        
        # 显示热门市场信息
        if trending_markets:
            print("\n  🔥 实时热门市场:")
            for i, market in enumerate(trending_markets[:3], 1):
                question = market.get('question', 'N/A')
                event_title = market.get('event_title', 'N/A')
                volume_24hr = market.get('volume24hr', 0)
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
                
                print(f"\n     {i}. {question[:60]}...")
                print(f"        事件: {event_title}")
                print(f"        24h交易量: ${float(volume_24hr):,.0f} | 流动性: ${float(liquidity):,.0f}")
                if yes_price != 'N/A':
                    try:
                        print(f"        Yes 价格: {float(yes_price):.2f}")
                    except:
                        print(f"        Yes 价格: {yes_price}")
        
        # 测试获取可用标签
        print("\n  🏷️ 获取可用标签...")
        tags = client.get_available_tags()
        print(f"  ✅ 成功获取 {len(tags)} 个标签")
        
        # 显示前几个标签
        if tags:
            print("\n  📋 热门标签:")
            for i, tag in enumerate(tags[:5], 1):
                tag_name = tag.get('name', 'N/A')
                tag_slug = tag.get('slug', 'N/A')
                print(f"     {i}. {tag_name} ({tag_slug})")
        
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
