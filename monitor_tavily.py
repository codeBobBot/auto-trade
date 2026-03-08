#!/usr/bin/env python3
"""
Polymarket 套利监控 - Tavily 版本
使用 Tavily API 进行新闻监控和情绪分析
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gamma_client import PolymarketGammaClient
from tavily_monitor import TavilyNewsMonitor
from arbitrage_strategy import ArbitrageStrategy
from datetime import datetime
import time

class ArbitrageMonitor:
    """套利监控系统 - Tavily 版"""
    
    def __init__(self):
        self.polymarket = PolymarketGammaClient()
        self.news = TavilyNewsMonitor()
        self.strategy = ArbitrageStrategy()
        
    def scan_opportunities(self, keywords: list = None):
        """扫描套利机会"""
        if keywords is None:
            keywords = ['Trump election', 'Biden', 'crypto market', 'Bitcoin BTC', 'Ethereum ETH']
        
        print("=" * 70)
        print("🔍 Polymarket 套利扫描 (Tavily 版)")
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        all_opportunities = []
        
        for keyword in keywords:
            print(f"\n📊 扫描关键词: {keyword}")
            print("-" * 70)
            
            # 1. 搜索相关市场
            try:
                markets = self.polymarket.search_markets(keyword, limit=3)
                print(f"   ✅ 找到 {len(markets)} 个相关市场")
            except Exception as e:
                print(f"   ⚠️  搜索失败: {e}")
                continue
            
            # 2. Tavily 情绪分析
            try:
                sentiment_data = self.news.analyze_sentiment(keyword)
                avg_sentiment = sentiment_data['score']
                sentiment_label = sentiment_data['sentiment']
                
                print(f"   ✅ Tavily 情绪分析: {sentiment_label} ({avg_sentiment:+.2f})")
                print(f"   📰 文章数: {sentiment_data['articles_count']}")
                
                # 显示相关新闻标题
                if sentiment_data.get('articles'):
                    print(f"   📰 相关新闻:")
                    for article in sentiment_data['articles'][:2]:
                        print(f"      - {article['title'][:50]}...")
                
            except Exception as e:
                print(f"   ⚠️  情绪分析失败: {e}")
                avg_sentiment = 0
            
            # 3. 套利分析
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
            
            # 避免 API 速率限制
            time.sleep(1)
        
        # 总结
        print("\n" + "=" * 70)
        print(f"📋 扫描完成")
        print(f"   发现 {len(all_opportunities)} 个套利机会")
        print("=" * 70)
        
        return all_opportunities


def main():
    print("\n" + "=" * 70)
    print("🚀 Polymarket 套利监控系统 (Tavily 版)")
    print("=" * 70)
    
    try:
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
        
    except ValueError as e:
        print(f"\n❌ 配置错误: {e}")
        print("\n请检查 config/.env 文件中的 TAVILY_API_KEY 配置")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 运行错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
