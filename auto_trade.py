#!/usr/bin/env python3
"""
Polymarket 自动交易监控 - 完整版
整合 Tavily 新闻、Gamma 市场数据、CLOB 交易执行
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gamma_client import PolymarketGammaClient
from tavily_monitor import TavilyNewsMonitor
from arbitrage_strategy import ArbitrageStrategy
from price_strategy import PriceStrategy
from clob_client import TradingExecutor
from datetime import datetime
import time
import json

class AutoTradingMonitor:
    """自动交易监控器 - 双策略模式"""
    
    def __init__(self, enable_trading: bool = False, use_price_strategy: bool = True):
        self.polymarket = PolymarketGammaClient()
        self.news = TavilyNewsMonitor()
        self.sentiment_strategy = ArbitrageStrategy()
        self.price_strategy = PriceStrategy()
        self.use_price_strategy = use_price_strategy
        self.enable_trading = enable_trading
        
        if enable_trading:
            try:
                self.executor = TradingExecutor()
                print("✅ 交易执行器已启用")
            except ValueError as e:
                print(f"⚠️  交易执行器未启用: {e}")
                print("   请配置 CLOB API 以启用自动交易")
                self.enable_trading = False
        
        self.trade_history = []
        
    def scan_and_trade(self, keywords: list = None, min_confidence: float = 0.7):
        """扫描并执行交易 - 双策略模式"""
        # 如果没有提供关键词，从 Polymarket 获取实时热门关键词
        if keywords is None:
            try:
                print("🔍 正在从 Polymarket 获取实时热门关键词...")
                keywords = self.polymarket.get_trending_keywords(limit=8)
                print(f"✅ 获取到 {len(keywords)} 个热门关键词: {', '.join(keywords)}")
            except Exception as e:
                print(f"⚠️  获取热门关键词失败，使用默认关键词: {e}")
                keywords = ['Trump', 'crypto', 'Bitcoin', 'Ethereum', 'AI', 'election', 'Fed', 'ETF']
        
        print("=" * 70)
        print("🚀 Polymarket 自动交易监控")
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔄 交易模式: {'✅ 启用' if self.enable_trading else '⏸️  模拟'}")
        print(f"📊 策略模式: {'价格驱动 + 情绪分析' if self.use_price_strategy else '仅情绪分析'}")
        print("=" * 70)
        
        executed_trades = []
        
        for keyword in keywords:
            print(f"\n📊 扫描关键词: {keyword}")
            print("-" * 70)
            
            # 1. 获取市场数据
            try:
                markets = self.polymarket.search_markets(keyword, limit=3)
                print(f"   ✅ 找到 {len(markets)} 个相关市场")
            except Exception as e:
                print(f"   ⚠️  市场搜索失败: {e}")
                continue
            
            # 2. Tavily 情绪分析
            avg_sentiment = 0
            sentiment_label = 'neutral'
            try:
                sentiment_data = self.news.analyze_sentiment(keyword)
                avg_sentiment = sentiment_data['score']
                sentiment_label = sentiment_data['sentiment']
                
                print(f"   ✅ 情绪分析: {sentiment_label} ({avg_sentiment:+.2f})")
                print(f"   📰 相关文章: {sentiment_data['articles_count']} 篇")
                if sentiment_data.get('matches'):
                    print(f"   🔑 关键词: {', '.join(sentiment_data['matches'])}")
                
            except Exception as e:
                print(f"   ⚠️  情绪分析失败: {e}")
            
            # 3. 策略分析和交易执行
            for market in markets[:2]:
                signals_found = []
                
                # 策略 A: 情绪驱动（如果情绪有效）
                if abs(avg_sentiment) >= 0.15:
                    try:
                        opp = self.sentiment_strategy.analyze(market, avg_sentiment)
                        if opp and opp.confidence >= min_confidence:
                            signals_found.append(('情绪', opp))
                    except Exception as e:
                        print(f"   ⚠️  情绪策略失败: {e}")
                
                # 策略 B: 价格驱动（始终运行）
                if self.use_price_strategy:
                    try:
                        price_sig = self.price_strategy.analyze(market)
                        if price_sig and price_sig.confidence >= min_confidence:
                            signals_found.append(('价格', price_sig))
                    except Exception as e:
                        print(f"   ⚠️  价格策略失败: {e}")
                
                # 执行最佳信号
                if signals_found:
                    # 选择置信度最高的信号
                    best_strategy, best_signal = max(signals_found, key=lambda x: x[1].confidence)
                    
                    print(f"\n   🎯 发现套利机会! [{best_strategy}策略]")
                    print(f"      市场: {best_signal.market_question[:45]}...")
                    print(f"      信号: {best_signal.signal}")
                    print(f"      置信度: {best_signal.confidence:.2%}")
                    print(f"      原因: {best_signal.reason}")
                    
                    # 执行交易
                    if self.enable_trading:
                        order = self.executor.execute_signal(
                            signal=best_signal.signal,
                            market_id=best_signal.market_id,
                            market_question=best_signal.market_question,
                            confidence=best_signal.confidence,
                            max_size=1.0
                        )
                        
                        if order:
                            executed_trades.append({
                                'timestamp': datetime.now().isoformat(),
                                'keyword': keyword,
                                'market': best_signal.market_question,
                                'signal': best_signal.signal,
                                'confidence': best_signal.confidence,
                                'strategy': best_strategy,
                                'order_id': order.get('id')
                            })
                            print(f"      ✅ 交易已执行!")
                        else:
                            print(f"      ❌ 交易执行失败")
                    else:
                        print(f"      ⏸️  模拟模式: 记录信号")
                        executed_trades.append({
                            'timestamp': datetime.now().isoformat(),
                            'keyword': keyword,
                            'market': best_signal.market_question,
                            'signal': best_signal.signal,
                            'confidence': best_signal.confidence,
                            'strategy': best_strategy,
                            'status': 'simulated'
                        })
            
            # 避免 API 速率限制
            time.sleep(1)
        
        # 总结
        print("\n" + "=" * 70)
        print(f"📋 扫描完成")
        print(f"   发现信号: {len(executed_trades)} 笔")
        print("=" * 70)
        
        return executed_trades


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Polymarket 自动交易监控')
    parser.add_argument('--trade', action='store_true', help='启用实际交易 (默认模拟)')
    parser.add_argument('--confidence', type=float, default=0.7, help='最低置信度 (默认 0.7)')
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("🚀 Polymarket 自动交易监控系统")
    print("=" * 70)
    
    try:
        monitor = AutoTradingMonitor(enable_trading=args.trade)
        
        # 运行扫描和交易
        trades = monitor.scan_and_trade(min_confidence=args.confidence)
        
        # 显示结果
        if trades:
            print("\n💎 交易记录:")
            for i, trade in enumerate(trades, 1):
                print(f"\n   {i}. {trade['market'][:50]}...")
                print(f"      信号: {trade['signal']} | 置信度: {trade['confidence']:.2%}")
                if 'order_id' in trade:
                    print(f"      订单: {trade['order_id']}")
        else:
            print("\n⏸️  未执行任何交易")
        
        print("\n" + "=" * 70)
        print("✅ 监控完成")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n❌ 运行错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
