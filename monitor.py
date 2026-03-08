#!/usr/bin/env python3
"""
Polymarket 套利监控 - 完整版
整合新闻监控、情绪分析、套利检测
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gamma_client import PolymarketGammaClient
from news_monitor import NewsMonitor
from arbitrage_strategy import ArbitrageStrategy
from datetime import datetime
import time

class ArbitrageMonitor:
    """套利监控系统"""
    
    def __init__(self):
        self.polymarket = PolymarketGammaClient()
        self.news = NewsMonitor()
        self.strategy = ArbitrageStrategy()
        
    def scan_opportunities(self, keywords: list = None):
        """扫描套利机会"""
        if keywords is None:
            keywords = ['Trump', 'Biden', 'election', 'crypto', 'BTC', 'ETH']
        
        print("=" * 70)
        print("🔍 Polymarket 套利扫描")
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        all_opportunities = []
        
        for keyword in keywords:
            print(f"\n📊 扫描关键词: {keyword}")
            print("-" * 70)
            
            # 1. 搜索相关市场
            try:
                markets = self.polymarket.search_markets(keyword, limit=3)
                print(f"   找到 {len(markets)} 个相关市场")
            except Exception as e:
                print(f"   ⚠️  搜索失败: {e}")
                continue
            
            # 2. 搜索相关新闻
            try:
                news_results = self.news.search(keyword, sources=['reddit'])
                reddit_posts = news_results.get('reddit', [])
                print(f"   找到 {len(reddit_posts)} 条相关新闻")
            except Exception as e:
                print(f"   ⚠️  新闻搜索失败: {e}")
                reddit_posts = []
            
            # 3. 情绪分析
            sentiment_scores = []
            for post in reddit_posts[:5]:
                title = post.get('title', '')
                score = self.news.detect_sentiment(title)
                sentiment_scores.append(score)
            
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
            print(f"   平均情绪: {avg_sentiment:+.2f} ({'积极' if avg_sentiment > 0 else '消极' if avg_sentiment < 0 else '中性'})")
            
            # 4. 套利分析
            for market in markets[:2]:  # 只分析前2个市场
                try:
                    opp = self.strategy.analyze(market, avg_sentiment)
                    if opp:
                        all_opportunities.append(opp)
                        print(f"\n   🎯 发现套利机会!")
                        print(f"      市场: {opp.market_question[:40]}...")
                        print(f"      信号: {opp.signal}")
                        print(f"      置信度: {opp.confidence:.2%}")
                        print(f"      原因: {opp.reason}")
                except Exception as e:
                    print(f"   ⚠️  分析失败: {e}")
        
        # 总结
        print("\n" + "=" * 70)
        print(f"📋 扫描完成")
        print(f"   发现 {len(all_opportunities)} 个套利机会")
        print("=" * 70)
        
        return all_opportunities


def main():
    print("\n" + "=" * 70)
    print("🚀 Polymarket 套利监控系统")
    print("=" * 70)
    
    monitor = ArbitrageMonitor()
    
    # 运行扫描
    opportunities = monitor.scan_opportunities()
    
    # 显示最佳机会
    if opportunities:
        print("\n💎 最佳套利机会:")
        for i, opp in enumerate(sorted(opportunities, key=lambda x: x.confidence, reverse=True)[:3], 1):
            print(f"\n   {i}. {opp.market_question[:50]}...")
            print(f"      操作: {opp.signal} | 置信度: {opp.confidence:.2%}")
    else:
        print("\n⏸️  当前未发现高置信度套利机会")
    
    print("\n" + "=" * 70)
    print("✅ 监控完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
