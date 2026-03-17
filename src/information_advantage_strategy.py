#!/usr/bin/env python3
"""
信息优势交易策略
利用新闻速度优势进行自动化交易

核心思路：
1. 监控突发新闻（比市场快1-5分钟）
2. 分析新闻对相关市场的影响
3. 自动执行交易决策
"""

import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from sentiment_service import GlobalSentimentService
from gamma_client import PolymarketGammaClient
from clob_client_auto_creds import ClobTradingClientAutoCreds
from logger_config import get_strategy_logger

@dataclass
class NewsImpact:
    """新闻影响分析结果"""
    direction: str  # 'buy', 'sell', 'hold'
    confidence: float  # 0-1 置信度
    keywords: List[str]
    affected_markets: List[Dict]
    expected_impact: float  # 预期影响程度
    urgency: str  # 'high', 'medium', 'low'

class InformationAdvantageStrategy:
    """信息优势交易策略"""
    
    def __init__(self, enable_trading: bool = False, notification_service=None):
        self.enable_trading = enable_trading
        self.notification_service = notification_service
        
        # 初始化日志记录器
        self.logger = get_strategy_logger("information_advantage")
        self.logger.info(f"初始化信息优势策略 - 交易模式: {'实盘' if enable_trading else '模拟'}")
        
        # 初始化组件
        self.sentiment_service = GlobalSentimentService()
        self.gamma_client = PolymarketGammaClient()
        self.trading_client = ClobTradingClientAutoCreds()
        
        # 发送初始化通知
        if self.notification_service:
            self.notification_service.info("策略初始化", "信息优势策略已初始化")
        
        # 重复下单防护机制
        self.executed_signals = set()  # 存储已执行的交易信号ID
        self.logger.info("重复下单防护机制已启用 - 永久一次下单")
        
        # 交易关键词映射 - 优化版本
        self.keyword_market_mapping = {
            # 政治类 - 高优先级
            'trump': {
                'markets': ['Trump wins election', 'Republicans win presidency', 'Trump to be GOP nominee'],
                'weight': 0.9,
                'urgency': 'high'
            },
            'biden': {
                'markets': ['Biden wins election', 'Democrats win presidency', 'Biden to be Dem nominee'],
                'weight': 0.9,
                'urgency': 'high'
            },
            'election': {
                'markets': ['Trump wins election', 'Biden wins election', '2024 election winner'],
                'weight': 0.85,
                'urgency': 'high'
            },
            'fed': {
                'markets': ['Fed increase rates', 'Fed decrease rates', 'Fed holds rates', 'Fed decision'],
                'weight': 0.95,
                'urgency': 'high'
            },
            'congress': {
                'markets': ['Republicans control House', 'Democrats control House', 'Senate control'],
                'weight': 0.7,
                'urgency': 'medium'
            },
            
            # 经济类 - 高优先级
            'inflation': {
                'markets': ['CPI will be above/below', 'Inflation rate', 'Fed policy impact'],
                'weight': 0.8,
                'urgency': 'high'
            },
            'GDP': {
                'markets': ['GDP growth will be above/below', 'US GDP Q4', 'Economic growth'],
                'weight': 0.75,
                'urgency': 'medium'
            },
            'interest rate': {
                'markets': ['Fed increase/decrease rates', 'Interest rate decision', 'Rate hike/cut'],
                'weight': 0.9,
                'urgency': 'high'
            },
            'unemployment': {
                'markets': ['Unemployment rate will be above/below', 'Jobs report', 'Labor market'],
                'weight': 0.7,
                'urgency': 'medium'
            },
            
            # 科技类 - 中优先级
            'bitcoin': {
                'markets': ['Bitcoin price will be above/below', 'BTC reaches $100k', 'Crypto market'],
                'weight': 0.8,
                'urgency': 'medium'
            },
            'crypto': {
                'markets': ['Bitcoin price will be above/below', 'Crypto regulation', 'ETF approval'],
                'weight': 0.75,
                'urgency': 'medium'
            },
            'AI': {
                'markets': ['AI breakthrough by date', 'AI regulation', 'Tech sector impact'],
                'weight': 0.7,
                'urgency': 'medium'
            },
            'apple': {
                'markets': ['Apple stock price will be above/below', 'iPhone sales', 'Tech earnings'],
                'weight': 0.6,
                'urgency': 'low'
            },
            'tesla': {
                'markets': ['Tesla stock price will be above/below', 'EV sales', 'Auto sector'],
                'weight': 0.6,
                'urgency': 'low'
            },
            'ETF': {
                'markets': ['Bitcoin ETF approved', 'ETF flows', 'Market impact'],
                'weight': 0.85,
                'urgency': 'high'
            },
            
            # 体育类 - 低优先级
            'NBA': {
                'markets': ['NBA championship', 'NBA playoffs', 'Specific NBA games'],
                'weight': 0.5,
                'urgency': 'low'
            },
            'NFL': {
                'markets': ['NFL championship', 'NFL playoffs', 'Super Bowl winner'],
                'weight': 0.5,
                'urgency': 'low'
            },
            'soccer': {
                'markets': ['World Cup', 'Champions League', 'Premier League'],
                'weight': 0.5,
                'urgency': 'low'
            },
        }
        
        # 影响方向映射
        self.direction_mapping = {
            # 正面新闻 -> 买入
            'positive': {
                'trump': 'buy',
                'republican': 'buy',
                'GDP growth': 'buy',
                'economic recovery': 'buy',
                'AI breakthrough': 'buy',
                'tech innovation': 'buy',
                'ETF approval': 'buy',
                'crypto adoption': 'buy',
            },
            # 负面新闻 -> 卖出
            'negative': {
                'inflation': 'sell',
                'recession': 'sell',
                'war': 'sell',
                'conflict': 'sell',
                'regulation': 'sell',
                'crypto ban': 'sell',
            }
        }
        
        # 最近处理过的新闻（避免重复处理）
        self.processed_news = set()
        self.processing_window = timedelta(minutes=30)
    
    def generate_signal_id(self, impact: NewsImpact) -> str:
        """生成交易信号的唯一ID"""
        # 基于关键词、方向和置信度生成唯一标识
        keywords_str = '_'.join(sorted(impact.keywords[:3]))  # 取前3个关键词
        return f"{keywords_str}_{impact.direction}_{impact.confidence:.2f}"
    
    def is_signal_executed(self, impact: NewsImpact) -> bool:
        """检查交易信号是否已执行"""
        signal_id = self.generate_signal_id(impact)
        return signal_id in self.executed_signals
    
    def mark_signal_executed(self, impact: NewsImpact):
        """标记交易信号已执行"""
        signal_id = self.generate_signal_id(impact)
        self.executed_signals.add(signal_id)
        self.logger.debug(f"标记交易信号已执行: {signal_id}")
    
    def monitor_news_continuously(self, check_interval: int = 30):
        """持续监控新闻并自动交易"""
        self.logger.info("启动信息优势交易策略...")
        self.logger.info(f"检查间隔: {check_interval}秒")
        self.logger.info(f"交易模式: {'启用' if self.enable_trading else '模拟模式'}")
        
        while True:
            try:
                # 1. 获取最新新闻
                latest_news = self.get_latest_news(minutes=5)
                
                # 2. 分析每条新闻
                for news in latest_news:
                    if self.should_process_news(news):
                        impact = self.analyze_news_impact(news)
                        
                        if impact.confidence > 0.7:
                            self.logger.info(f"发现高置信度机会: {impact.confidence:.2f}")
                            self.logger.info(f"新闻: {news.get('title', 'N/A')[:50]}...")
                            self.logger.info(f"方向: {impact.direction}")
                            self.logger.info(f"关键词: {', '.join(impact.keywords)}")
                            
                            # 发送信息优势交易机会通知到Telegram
                            if self.notification_service:
                                # 准备市场详情信息
                                market_details = []
                                for market in impact.affected_markets[:5]:  # 最多显示5个市场
                                    market_details.append({
                                        'id': market.get('id', 'N/A'),
                                        'question': market.get('question', 'N/A'),
                                        'yes_price': self.get_market_price(market),
                                        'liquidity': market.get('liquidity', 0),
                                        'volume24hr': market.get('volume24hr', 0)
                                    })
                                
                                self.notification_service.signal_detected(
                                    strategy="信息优势",
                                    market=f"机会: {news.get('title', 'N/A')[:50]}...",
                                    signal=impact.direction,
                                    confidence=impact.confidence,
                                    market_details=market_details
                                )
                                self.notification_service.info(
                                    "信息优势详情", 
                                    f"新闻: {news.get('title', 'N/A')[:40]}...\n"
                                    f"方向: {impact.direction}\n"
                                    f"置信度: {impact.confidence:.2f}\n"
                                    f"关键词: {', '.join(impact.keywords[:3])}"
                                )
                            
                            # 3. 执行交易
                            if self.enable_trading:
                                self.execute_trades(impact)
                            else:
                                self.logger.info("模拟模式：记录交易机会")
                                self.log_trade_opportunity(impact)
                
                # 4. 清理过期新闻记录
                self.cleanup_processed_news()
                
                # 5. 等待下次检查
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                self.logger.info("策略已停止")
                break
            except Exception as e:
                self.logger.error(f"策略执行错误: {e}")
                time.sleep(60)  # 错误后等待1分钟
    
    def get_latest_news(self, minutes: int = 5) -> List[Dict]:
        """获取最新新闻"""
        try:
            # 获取多源新闻
            news_sources = []
            
            # 1. Tavily 新闻（已有）
            tavily_news = self.sentiment_service.get_latest_news(minutes=minutes)
            news_sources.extend(tavily_news)
            
            # 2. Reddit 热门帖子
            reddit_posts = self.sentiment_service.get_latest_reddit_posts(minutes=minutes)
            news_sources.extend(reddit_posts)
            
            # 3. Twitter 热门推文
            twitter_tweets = self.sentiment_service.get_latest_tweets(minutes=minutes)
            news_sources.extend(twitter_tweets)
            
            # 合并并去重
            all_news = []
            seen_urls = set()
            
            for news in news_sources:
                url = news.get('url', '')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_news.append(news)
            
            # 按时间排序
            all_news.sort(key=lambda x: x.get('published_at', ''), reverse=True)
            
            return all_news[:20]  # 返回最新20条
            
        except Exception as e:
            print(f"⚠️ 获取新闻失败: {e}")
            return []
    
    def should_process_news(self, news: Dict) -> bool:
        """判断是否应该处理这条新闻"""
        # 1. 检查是否已处理过
        news_id = self.get_news_id(news)
        if news_id in self.processed_news:
            return False
        
        # 2. 检查新闻时效性
        published_at = news.get('published_at')
        if published_at:
            try:
                pub_time = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                if datetime.now(pub_time.tzinfo) - pub_time > timedelta(minutes=10):
                    return False  # 超过10分钟的新闻不处理
            except:
                pass
        
        # 3. 检查是否包含相关关键词
        content = f"{news.get('title', '')} {news.get('content', '')}".lower()
        
        for keyword_group in self.keyword_market_mapping.keys():
            if keyword_group in content:
                return True
        
        return False
    
    def analyze_news_impact(self, news: Dict) -> NewsImpact:
        """分析新闻对市场的影响"""
        # 1. 提取关键词
        content = f"{news.get('title', '')} {news.get('content', '')}"
        keywords = self.extract_trading_keywords(content)
        
        # 2. 分析情绪
        sentiment_result = self.sentiment_service.analyze(content)
        sentiment_score = sentiment_result.sentiment_score if sentiment_result else 0
        
        # 3. 确定影响方向
        direction = self.determine_direction(keywords, sentiment_score)
        
        # 4. 计算置信度
        confidence = self.calculate_confidence(keywords, sentiment_score, news)
        
        # 5. 找到相关市场
        affected_markets = self.find_affected_markets(keywords)
        
        # 6. 评估紧急程度
        urgency = self.assess_urgency(news, keywords)
        
        # 7. 预期影响程度
        expected_impact = self.estimate_impact(sentiment_score, keywords)
        
        return NewsImpact(
            direction=direction,
            confidence=confidence,
            keywords=keywords,
            affected_markets=affected_markets,
            expected_impact=expected_impact,
            urgency=urgency
        )
    
    def extract_trading_keywords(self, content: str) -> List[str]:
        """提取交易相关关键词"""
        content_lower = content.lower()
        found_keywords = []
        
        for keyword in self.keyword_market_mapping.keys():
            if keyword in content_lower:
                found_keywords.append(keyword)
        
        return found_keywords
    
    def determine_direction(self, keywords: List[str], sentiment_score: float) -> str:
        """确定交易方向"""
        # 基于情绪分数的基础方向
        if sentiment_score > 0.3:
            base_direction = 'buy'
        elif sentiment_score < -0.3:
            base_direction = 'sell'
        else:
            base_direction = 'hold'
        
        # 基于关键词的特殊规则
        for keyword in keywords:
            for sentiment_type, keyword_rules in self.direction_mapping.items():
                if keyword in keyword_rules:
                    if sentiment_type == 'positive' and base_direction == 'buy':
                        return 'buy'
                    elif sentiment_type == 'negative' and base_direction == 'sell':
                        return 'sell'
        
        return base_direction
    
    def calculate_confidence(self, keywords: List[str], sentiment_score: float, news: Dict) -> float:
        """计算置信度 - 优化版本"""
        confidence = 0.0
        
        # 1. 关键词权重匹配 (35%)
        keyword_weight = 0.0
        for keyword in keywords:
            if keyword in self.keyword_market_mapping:
                keyword_weight += self.keyword_market_mapping[keyword]['weight']
        keyword_confidence = min(keyword_weight / len(keywords) * 0.35, 0.35) if keywords else 0
        confidence += keyword_confidence
        
        # 2. 情绪强度 (25%)
        sentiment_intensity = abs(sentiment_score)
        sentiment_confidence = min(sentiment_intensity * 0.25, 0.25)
        confidence += sentiment_confidence
        
        # 3. 新闻源可信度 (20%)
        source_confidence = self.assess_source_credibility(news)
        confidence += source_confidence
        
        # 4. 时效性 (15%)
        time_confidence = self.assess_timeliness(news)
        confidence += time_confidence
        
        # 5. 紧急程度加成 (5%)
        urgency_bonus = self.assess_urgency_bonus(keywords)
        confidence += urgency_bonus
        
        return min(confidence, 1.0)
    
    def assess_source_credibility(self, news: Dict) -> float:
        """评估新闻源可信度"""
        source = news.get('source', '').lower()
        
        high_credibility = ['bloomberg', 'reuters', 'bbc', 'associated press', 'cnbc']
        medium_credibility = ['cnn', 'fox news', 'wsj', 'financial times']
        
        if any(high in source for high in high_credibility):
            return 0.2
        elif any(medium in source for medium in medium_credibility):
            return 0.15
        else:
            return 0.1
    
    def assess_timeliness(self, news: Dict) -> float:
        """评估新闻时效性"""
        published_at = news.get('published_at')
        if not published_at:
            return 0.05
        
        try:
            pub_time = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            age_minutes = (datetime.now(pub_time.tzinfo) - pub_time).total_seconds() / 60
            
            if age_minutes < 1:
                return 0.15
            elif age_minutes < 5:
                return 0.12
            elif age_minutes < 10:
                return 0.08
            elif age_minutes < 30:
                return 0.05
            else:
                return 0.02
        except:
            return 0.05
    
    def assess_urgency_bonus(self, keywords: List[str]) -> float:
        """评估紧急程度加成"""
        if not keywords:
            return 0.0
        
        urgency_scores = []
        for keyword in keywords:
            if keyword in self.keyword_market_mapping:
                urgency = self.keyword_market_mapping[keyword]['urgency']
                if urgency == 'high':
                    urgency_scores.append(0.05)
                elif urgency == 'medium':
                    urgency_scores.append(0.03)
                else:
                    urgency_scores.append(0.01)
        
        return max(urgency_scores) if urgency_scores else 0.0
    
    def find_affected_markets(self, keywords: List[str]) -> List[Dict]:
        """找到受影响的市场"""
        affected_markets = []
        
        # 获取热门市场
        trending_markets = self.gamma_client.get_trending_markets(limit=50)
        
        for keyword in keywords:
            # 1. 直接关键词匹配
            related_market_names = self.keyword_market_mapping.get(keyword, [])
            
            # 2. 在热门市场中搜索
            for market in trending_markets:
                question = market.get('question', '').lower()
                
                # 检查是否匹配相关市场名称
                for market_name in related_market_names:
                    if any(word in question for word in market_name.lower().split()):
                        if market not in affected_markets:
                            affected_markets.append(market)
                
                # 检查是否包含关键词
                if keyword in question:
                    if market not in affected_markets:
                        affected_markets.append(market)
        
        return affected_markets[:5]  # 最多返回5个相关市场
    
    def assess_urgency(self, news: Dict, keywords: List[str]) -> str:
        """评估紧急程度"""
        # 高紧急度关键词
        high_urgency = ['breaking', 'urgent', 'alert', 'emergency', 'war', 'crash']
        
        # 检查新闻标题
        title = news.get('title', '').lower()
        if any(word in title for word in high_urgency):
            return 'high'
        
        # 检查关键词
        if any(keyword in ['fed', 'election', 'war', 'crash'] for keyword in keywords):
            return 'high'
        elif any(keyword in ['GDP', 'inflation', 'interest rate'] for keyword in keywords):
            return 'medium'
        else:
            return 'low'
    
    def estimate_impact(self, sentiment_score: float, keywords: List[str]) -> float:
        """估算影响程度"""
        base_impact = abs(sentiment_score)
        
        # 关键词影响权重
        keyword_weights = {
            'fed': 0.3,
            'election': 0.25,
            'war': 0.35,
            'GDP': 0.2,
            'inflation': 0.25,
            'bitcoin': 0.15,
            'AI': 0.2,
        }
        
        keyword_boost = sum(keyword_weights.get(k, 0.1) for k in keywords)
        
        return min(base_impact + keyword_boost * 0.1, 1.0)
    
    def execute_trades(self, impact: NewsImpact):
        """执行交易"""
        # 检查是否已执行过
        if self.is_signal_executed(impact):
            self.logger.debug(f"交易信号已执行，跳过: {impact.keywords[:3]}...")
            return
        if not impact.affected_markets:
            print("⚠️ 没有找到相关市场")
            return
        
        print(f"🎯 准备执行交易: {impact.direction}")
        
        for market in impact.affected_markets:
            try:
                # 计算仓位大小
                position_size = self.calculate_position_size(market, impact)
                
                # 执行交易
                if impact.direction == 'buy':
                    # 获取token_id（条件代币地址）
                    token_id = self.trading_client.get_market_token_id_enhanced(market)
                    if not token_id:
                        print(f"❌ 无法获取token_id: {market}")
                        continue
                    
                    order_id = self.trading_client.create_order(
                        token_id=token_id,
                        side='BUY',
                        size=position_size,
                        price=market.get('yes_price', 0.5)
                    )
                    print(f"✅ 买入订单: {order_id} - {market['question'][:30]}...")
                
                elif impact.direction == 'sell':
                    # 获取token_id（条件代币地址）
                    token_id = self.trading_client.get_market_token_id_enhanced(market)
                    if not token_id:
                        print(f"❌ 无法获取token_id: {market}")
                        continue
                    
                    order_id = self.trading_client.create_order(
                        token_id=token_id,
                        side='SELL',
                        size=position_size,
                        price=market.get('yes_price', 0.5)
                    )
                    print(f"✅ 卖出订单: {order_id} - {market['question'][:30]}...")
                
                # 记录交易
                self.log_trade(impact, market, order_id)
                
            except Exception as e:
                print(f"❌ 交易执行失败: {e}")
        
        # 标记交易信号已执行
        self.mark_signal_executed(impact)
    
    def calculate_position_size(self, market: Dict, impact: NewsImpact) -> float:
        """计算仓位大小"""
        # 基础仓位
        base_size = 100.0  # USDC
        
        # 根据置信度调整
        confidence_multiplier = impact.confidence
        
        # 根据影响程度调整
        impact_multiplier = impact.expected_impact
        
        # 根据市场流动性调整
        liquidity = float(market.get('liquidity', 10000))
        liquidity_multiplier = min(liquidity / 10000, 2.0)
        
        # 计算最终仓位
        position_size = base_size * confidence_multiplier * impact_multiplier * liquidity_multiplier
        
        # 限制最大仓位
        max_position = 1000.0  # 最大1000 USDC
        position_size = min(position_size, max_position)
        
        return round(position_size, 2)
    
    def log_trade_opportunity(self, impact: NewsImpact):
        """记录交易机会（模拟模式）"""
        opportunity = {
            'timestamp': datetime.now().isoformat(),
            'direction': impact.direction,
            'confidence': impact.confidence,
            'keywords': impact.keywords,
            'affected_markets_count': len(impact.affected_markets),
            'expected_impact': impact.expected_impact,
            'urgency': impact.urgency
        }
        
        print(f"📊 交易机会记录: {json.dumps(opportunity, indent=2)}")
    
    def log_trade(self, impact: NewsImpact, market: Dict, order_id: str):
        """记录实际交易"""
        trade_record = {
            'timestamp': datetime.now().isoformat(),
            'order_id': order_id,
            'market_id': market['id'],
            'market_question': market['question'],
            'direction': impact.direction,
            'confidence': impact.confidence,
            'keywords': impact.keywords,
            'price': market.get('yes_price'),
            'position_size': self.calculate_position_size(market, impact)
        }
        
        # 这里可以保存到数据库或文件
        print(f"💼 交易记录: {json.dumps(trade_record, indent=2)}")
    
    def get_news_id(self, news: Dict) -> str:
        """生成新闻唯一ID"""
        url = news.get('url', '')
        title = news.get('title', '')
        published_at = news.get('published_at', '')
        
        # 使用URL、标题和发布时间生成唯一ID
        import hashlib
        content = f"{url}{title}{published_at}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def cleanup_processed_news(self):
        """清理过期的已处理新闻记录"""
        current_time = datetime.now()
        expired_news = []
        
        for news_id, timestamp in self.processed_news.items():
            if current_time - timestamp > self.processing_window:
                expired_news.append(news_id)
        
        for news_id in expired_news:
            del self.processed_news[news_id]
    
    def get_market_price(self, market: Dict) -> float:
        """获取市场价格"""
        # 尝试多种价格字段
        price_fields = ['yes_price', 'outcomePrices', 'price']
        
        for field in price_fields:
            if field in market:
                price = market[field]
                if isinstance(price, (int, float)):
                    return float(price)
                elif isinstance(price, str):
                    try:
                        return float(price)
                    except:
                        continue
                elif isinstance(price, dict) and 'Yes' in price:
                    try:
                        return float(price['Yes'])
                    except:
                        continue
        
        return 0.5  # 默认价格

def test_strategy():
    """测试信息优势交易策略"""
    print("🧪 测试信息优势交易策略...")
    
    strategy = InformationAdvantageStrategy(enable_trading=False)
    
    # 测试新闻分析
    test_news = {
        'title': 'Federal Reserve announces surprise interest rate cut',
        'content': 'The Fed made an unexpected decision to cut interest rates by 50 basis points',
        'source': 'Bloomberg',
        'published_at': datetime.now().isoformat(),
        'url': 'https://test.com/news/1'
    }
    
    impact = strategy.analyze_news_impact(test_news)
    
    print(f"📊 分析结果:")
    print(f"   方向: {impact.direction}")
    print(f"   置信度: {impact.confidence:.2f}")
    print(f"   关键词: {impact.keywords}")
    print(f"   相关市场: {len(impact.affected_markets)}")
    print(f"   预期影响: {impact.expected_impact:.2f}")
    print(f"   紧急程度: {impact.urgency}")

if __name__ == '__main__':
    test_strategy()
