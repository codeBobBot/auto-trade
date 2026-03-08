#!/usr/bin/env python3
"""
Polymarket 手动交易助手
生成交易信号并通过 Telegram 通知，用户手动下单
无需 CLOB API
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gamma_client import PolymarketGammaClient
from tavily_monitor import TavilyNewsMonitor
from arbitrage_strategy import ArbitrageStrategy
from datetime import datetime
import time
import subprocess

class ManualTradingAssistant:
    """手动交易助手"""
    
    def __init__(self):
        self.polymarket = PolymarketGammaClient()
        self.news = TavilyNewsMonitor()
        self.strategy = ArbitrageStrategy()
        self.signals = []
        
    def scan_and_notify(self, keywords: list = None, min_confidence: float = 0.6):
        """扫描并发送交易信号通知"""
        if keywords is None:
            keywords = ['Trump election', 'Biden', 'crypto market', 'Bitcoin BTC', 'Ethereum ETH']
        
        print("=" * 70)
        print("🤖 Polymarket 手动交易助手")
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print("\n💡 模式: 系统分析 → Telegram 通知 → 您手动下单")
        print("=" * 70)
        
        for keyword in keywords:
            print(f"\n📊 扫描关键词: {keyword}")
            print("-" * 70)
            
            # 1. 获取市场数据
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
                
                print(f"   ✅ 情绪分析: {sentiment_label} ({avg_sentiment:+.2f})")
                print(f"   📰 相关文章: {sentiment_data['articles_count']} 篇")
                
                # 显示相关新闻
                if sentiment_data.get('articles'):
                    print(f"   📰 最新动态:")
                    for article in sentiment_data['articles'][:2]:
                        print(f"      - {article['title'][:50]}...")
                
            except Exception as e:
                print(f"   ⚠️  情绪分析失败: {e}")
                avg_sentiment = 0
            
            # 3. 套利分析
            for market in markets[:2]:
                try:
                    opp = self.strategy.analyze(market, avg_sentiment)
                    
                    if opp and opp.confidence >= min_confidence:
                        self.signals.append(opp)
                        
                        print(f"\n   🎯 发现交易机会!")
                        print(f"      市场: {opp.market_question}")
                        print(f"      信号: {opp.signal}")
                        print(f"      置信度: {opp.confidence:.2%}")
                        print(f"      原因: {opp.reason}")
                        
                        # 生成 Polymarket 链接
                        market_id = opp.market_id
                        polymarket_url = f"https://polymarket.com/event/{market_id}"
                        
                        # 发送 Telegram 通知
                        self._send_signal_notification(opp, polymarket_url, sentiment_data)
                        
                except Exception as e:
                    print(f"   ⚠️  分析失败: {e}")
            
            time.sleep(1)
        
        # 总结
        print("\n" + "=" * 70)
        print(f"📋 扫描完成")
        print(f"   发现 {len(self.signals)} 个交易信号")
        print("=" * 70)
        
        if self.signals:
            print("\n💡 请查看 Telegram 获取详细交易建议")
            print("   登录 Polymarket 手动下单")
        
        return self.signals
    
    def _send_signal_notification(self, opp, url, sentiment_data):
        """发送交易信号通知"""
        
        # 解析交易建议
        if opp.signal == 'buy_yes':
            action = "买入 YES"
            side = "Yes"
        elif opp.signal == 'buy_no':
            action = "买入 NO"
            side = "No"
        else:
            action = opp.signal
            side = "Unknown"
        
        # 构建消息
        message = f"""🎯 <b>Polymarket 交易信号</b>

📊 <b>市场:</b>
{opp.market_question[:80]}...

💡 <b>建议操作:</b> {action}
📈 <b>置信度:</b> {opp.confidence:.1%}
💭 <b>分析:</b> {opp.reason}

📰 <b>市场情绪:</b> {sentiment_data['sentiment']} ({sentiment_data['score']:+.2f})
📰 <b>相关文章:</b> {sentiment_data['articles_count']} 篇

🔗 <b>交易链接:</b>
{url}

⚠️ <b>风险提示:</b>
• 请自行判断后下单
• 建议单笔不超过 $2
• 设置止损，控制风险

<i>信号生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>
<i>此信号由 AI 生成，仅供参考</i>"""
        
        try:
            # 发送 Telegram 消息
            result = subprocess.run(
                ['openclaw', 'message', 'send', 
                 '--channel', 'telegram',
                 '--target', '-1003842374341',
                 '--message', message],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print(f"      ✅ Telegram 通知已发送")
            else:
                print(f"      ⚠️  Telegram 发送失败")
                
        except Exception as e:
            print(f"      ⚠️  通知发送失败: {e}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Polymarket 手动交易助手')
    parser.add_argument('--confidence', type=float, default=0.6, 
                        help='最低置信度 (默认 0.6)')
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("🚀 Polymarket 手动交易助手")
    print("=" * 70)
    print("\n💡 无需 CLOB API，系统分析后通过 Telegram 发送交易建议")
    print("   您在 Polymarket 网站手动下单")
    print("=" * 70)
    
    try:
        assistant = ManualTradingAssistant()
        signals = assistant.scan_and_notify(min_confidence=args.confidence)
        
        print("\n" + "=" * 70)
        print("✅ 分析完成")
        print("=" * 70)
        
        if signals:
            print(f"\n📊 共发现 {len(signals)} 个交易信号")
            print("📱 请查看 Telegram 获取详细信息")
            print("\n🔗 Polymarket 网站: https://polymarket.com/")
        else:
            print("\n⏸️  当前未发现高置信度交易机会")
            print("   系统将继续监控...")
        
        print("\n💡 提示:")
        print("   • 建议设置定时任务每小时运行一次")
        print("   • 收到信号后尽快下单，机会可能快速消失")
        print("   • 始终控制风险，不要投入无法承受损失的资金")
        
    except Exception as e:
        print(f"\n❌ 运行错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
