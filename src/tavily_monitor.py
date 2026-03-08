#!/usr/bin/env python3
"""
Tavily 新闻监控模块
使用 Tavily API 进行 AI 优化搜索
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional
import requests
from dotenv import load_dotenv

load_dotenv('/Users/lsl_mac/.openclaw/workspace/projects/polymarket-arbitrage/config/.env')

class TavilyNewsMonitor:
    """Tavily 新闻监控器"""
    
    BASE_URL = "https://api.tavily.com"
    
    def __init__(self):
        self.api_key = os.getenv('TAVILY_API_KEY')
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY 未配置，请检查 .env 文件")
        
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
    
    def search(self, query: str, search_depth: str = "advanced", 
               include_answer: bool = True, max_results: int = 10) -> Dict:
        """
        使用 Tavily API 搜索
        
        Args:
            query: 搜索关键词
            search_depth: basic 或 advanced
            include_answer: 是否包含 AI 生成的答案
            max_results: 最大结果数
        """
        url = f"{self.BASE_URL}/search"
        
        payload = {
            'api_key': self.api_key,
            'query': query,
            'search_depth': search_depth,
            'include_answer': include_answer,
            'max_results': max_results,
            'include_domains': [
                'twitter.com',
                'reddit.com',
                'news.ycombinator.com',
                'medium.com',
                'substack.com'
            ]
        }
        
        response = self.session.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def search_news(self, query: str, hours: int = 24) -> List[Dict]:
        """搜索最近的新闻"""
        # 添加时间限制到查询
        time_query = f"{query} news past {hours} hours"
        
        result = self.search(time_query, max_results=10)
        
        articles = []
        for item in result.get('results', []):
            articles.append({
                'title': item.get('title', ''),
                'url': item.get('url', ''),
                'content': item.get('content', '')[:500],
                'score': item.get('score', 0),
                'source': item.get('source', 'unknown'),
                'published_date': item.get('published_date', 'unknown')
            })
        
        return articles
    
    def get_ai_answer(self, query: str) -> str:
        """获取 AI 生成的答案摘要"""
        result = self.search(query, include_answer=True, max_results=5)
        return result.get('answer', 'No answer available')
    
    def analyze_sentiment(self, query: str) -> Dict:
        """
        分析特定主题的市场情绪（本地处理，不依赖 Tavily AI）
        
        返回:
            - sentiment: positive/negative/neutral
            - score: -1 到 1
            - summary: 摘要
        """
        # 搜索最新资讯
        news = self.search_news(query, hours=24)
        
        if not news:
            return {
                'sentiment': 'neutral',
                'score': 0.0,
                'summary': 'No recent news found',
                'articles_count': 0
            }
        
        # 增强情绪词典
        positive_words = [
            'surge', 'rally', 'bullish', 'growth', 'win', 'success', 'breakthrough', 'moon',
            'soar', 'jump', 'gain', 'rise', 'up', 'high', 'strong', 'boost', 'surge',
            'approve', 'pass', 'victory', 'positive', 'optimistic', 'bull', 'pump'
        ]
        negative_words = [
            'crash', 'bearish', 'decline', 'loss', 'fail', 'scandal', 'ban', 'fud',
            'drop', 'fall', 'plunge', 'tumble', 'down', 'low', 'weak', 'crash',
            'reject', 'deny', 'defeat', 'negative', 'pessimistic', 'bear', 'dump',
            'concern', 'worry', 'fear', 'risk', 'threat', 'crisis', 'problem'
        ]
        
        # 合并标题和内容进行分析
        text = ' '.join([a['title'] + ' ' + a.get('content', '') for a in news]).lower()
        
        # 计算情绪分数
        score = 0
        matches = []
        
        for word in positive_words:
            count = text.count(word)
            if count > 0:
                score += 0.15 * count
                matches.append(f"+{word}")
        
        for word in negative_words:
            count = text.count(word)
            if count > 0:
                score -= 0.15 * count
                matches.append(f"-{word}")
        
        # 归一化到 [-1, 1]
        score = max(-1, min(1, score))
        
        # 确定情绪标签
        if score > 0.15:
            sentiment = 'positive'
        elif score < -0.15:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'
        
        # 生成摘要
        top_articles = [a['title'][:50] + "..." for a in news[:3]]
        summary = f"关键词匹配: {', '.join(matches[:5])} | 头条: {top_articles[0]}"
        
        return {
            'sentiment': sentiment,
            'score': round(score, 2),
            'summary': summary,
            'articles_count': len(news),
            'articles': news[:3],
            'matches': matches[:5]
        }


def test_tavily():
    """测试 Tavily API"""
    print("\n" + "=" * 70)
    print("🔍 Tavily API 测试")
    print("=" * 70)
    
    try:
        monitor = TavilyNewsMonitor()
        print("✅ Tavily API 初始化成功")
        
        # 测试搜索
        query = "Trump election 2026"
        print(f"\n📊 搜索: {query}")
        
        news = monitor.search_news(query, hours=24)
        print(f"✅ 找到 {len(news)} 条相关新闻")
        
        for i, article in enumerate(news[:3], 1):
            print(f"\n   {i}. {article['title'][:60]}...")
            print(f"      来源: {article['source']} | 相关度: {article['score']:.2f}")
        
        # 测试情绪分析
        print(f"\n💭 情绪分析: {query}")
        sentiment = monitor.analyze_sentiment(query)
        
        print(f"   情绪: {sentiment['sentiment']} ({sentiment['score']:+.2f})")
        print(f"   摘要: {sentiment['summary'][:100]}...")
        print(f"   文章数: {sentiment['articles_count']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    test_tavily()
