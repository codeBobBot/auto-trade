#!/usr/bin/env python3
"""
测试实时热门市场功能
展示更新后的 Gamma 客户端能力
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gamma_client import PolymarketGammaClient
import json

def test_realtime_markets():
    """测试实时热门市场功能"""
    print("=" * 70)
    print("🔥 实时热门市场测试")
    print("=" * 70)
    
    client = PolymarketGammaClient()
    
    # 测试1: 获取实时热门市场
    print("\n📊 获取实时热门市场...")
    trending_markets = client.get_trending_markets(limit=10)
    
    if trending_markets:
        print(f"✅ 成功获取 {len(trending_markets)} 个热门市场")
        print("\n🔥 TOP 5 热门市场:")
        print("-" * 50)
        
        for i, market in enumerate(trending_markets[:5], 1):
            question = market.get('question', 'N/A')
            event_title = market.get('event_title', 'N/A')
            volume_24hr = market.get('volume24hr', 0)
            liquidity = market.get('liquidity', 0)
            
            # 处理价格
            outcome_prices = market.get('outcomePrices', {})
            yes_price = 'N/A'
            if isinstance(outcome_prices, dict) and 'Yes' in outcome_prices:
                try:
                    yes_price = f"{float(outcome_prices['Yes']):.2f}"
                except:
                    yes_price = str(outcome_prices['Yes'])
            
            print(f"\n{i}. {question[:70]}...")
            print(f"   📅 事件: {event_title}")
            print(f"   💰 24h交易量: ${float(volume_24hr):,.0f}")
            print(f"   💧 流动性: ${float(liquidity):,.0f}")
            if yes_price != 'N/A':
                print(f"   📈 Yes价格: ${yes_price}")
    else:
        print("❌ 未获取到热门市场")
    
    # 测试2: 搜索特定主题
    print("\n" + "=" * 50)
    print("🔍 搜索测试")
    print("=" * 50)
    
    search_terms = ['Fed', 'crypto', 'Trump', 'AI']
    
    for term in search_terms:
        print(f"\n🔎 搜索 '{term}' 相关市场...")
        try:
            markets = client.search_markets(term, limit=3)
            print(f"   ✅ 找到 {len(markets)} 个相关市场")
            
            for market in markets[:2]:
                question = market.get('question', 'N/A')
                volume = market.get('volume24hr', 0)
                print(f"   - {question[:60]}... (${float(volume):,.0f})")
                
        except Exception as e:
            print(f"   ❌ 搜索失败: {e}")
    
    # 测试3: 获取热门关键词
    print("\n" + "=" * 50)
    print("🏷️ 热门关键词")
    print("=" * 50)
    
    keywords = client.get_trending_keywords(limit=10)
    print(f"✅ 提取到 {len(keywords)} 个热门关键词:")
    print("   " + " | ".join(keywords))
    
    # 测试4: 获取可用标签
    print("\n" + "=" * 50)
    print("🏷️ 可用标签")
    print("=" * 50)
    
    try:
        tags = client.get_available_tags()
        print(f"✅ 获取到 {len(tags)} 个标签")
        
        # 显示前10个标签
        print("\n📋 热门标签 (前10个):")
        for i, tag in enumerate(tags[:10], 1):
            tag_name = tag.get('name', 'N/A')
            tag_slug = tag.get('slug', 'N/A')
            print(f"   {i}. {tag_name} ({tag_slug})")
            
    except Exception as e:
        print(f"❌ 获取标签失败: {e}")
    
    print("\n" + "=" * 70)
    print("🎉 实时市场测试完成！")
    print("=" * 70)
    print("\n💡 主要改进:")
    print("✅ 使用官方 events 端点")
    print("✅ 按 volume24hr 实时排序")
    print("✅ 获取真实市场数据")
    print("✅ 支持标签和搜索功能")

if __name__ == '__main__':
    test_realtime_markets()
