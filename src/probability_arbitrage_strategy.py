#!/usr/bin/env python3
"""
概率套利策略
发现并利用市场定价错误进行套利

核心思路：
1. 识别互斥事件组
2. 计算概率总和
3. 发现定价错误
4. 自动套利交易
"""

import time
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from src.gamma_client import PolymarketGammaClient
from src.clob_client_auto_creds import ClobTradingClientAutoCreds, MAX_TRADE_AMOUNT_USD
from src.logger_config import get_strategy_logger

@dataclass
class ArbitrageOpportunity:
    """套利机会"""
    type: str  # 'probability_arbitrage', 'cross_market'
    action: str  # 'buy_all', 'sell_all', 'buy_low_sell_high'
    markets: List[Dict]
    expected_return: float
    confidence: float
    total_probability: float
    description: str

class ProbabilityArbitrageStrategy:
    """概率套利策略"""
    
    def __init__(self, enable_trading: bool = False, notification_service=None):
        self.enable_trading = enable_trading
        self.notification_service = notification_service
        
        # 初始化日志记录器
        self.logger = get_strategy_logger("probability_arbitrage")
        self.logger.info(f"初始化概率套利策略 - 交易模式: {'实盘' if enable_trading else '模拟'}")
        
        # 初始化组件
        self.gamma_client = PolymarketGammaClient()
        self.trading_client = ClobTradingClientAutoCreds()
        
        # 发送初始化通知
        if self.notification_service:
            self.notification_service.info("策略初始化", "概率套利策略已初始化")
        
        # 重复下单防护机制
        self.executed_opportunities = set()  # 存储已执行的套利机会ID
        self.logger.info("重复下单防护机制已启用 - 永久一次下单")
        
        # 智能互斥事件组定义
        self.mutually_exclusive_groups = {
            # 选举相关 - 精细化分组
            'election_2024_winner': {
                'keywords': ['election', 'president', 'winner', '2024'],
                'exclusion_patterns': ['trump', 'biden', 'republican', 'democrat'],
                'markets': [],
                'description': '2024总统选举获胜者',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'election_2024_party': {
                'keywords': ['election', 'president', 'party', 'control'],
                'exclusion_patterns': ['republican', 'democrat', 'house', 'senate'],  # 保持原有排除模式
                'regions': ['us', 'america', 'united states'],  # 限制地区
                'markets': [],
                'description': '2024选举党派控制',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            # 新增：伊朗政治事件组
            'iran_political_transition': {
                'keywords': ['reza pahlavi', 'enter', 'iran', 'return', 'opposition'],
                'exclusion_patterns': ['forces', 'military', 'invasion', 'attack', 'troops'],
                'regions': ['iran', 'tehran', 'persian'],
                'markets': [],
                'description': '伊朗政治过渡',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            # 新增：伊朗军事事件组
            'iran_military_intervention': {
                'keywords': ['forces', 'military', 'enter', 'iran', 'intervention'],
                'exclusion_patterns': ['reza pahlavi', 'opposition', 'political', 'return'],
                'regions': ['iran', 'tehran', 'persian'],
                'markets': [],
                'description': '伊朗军事干预',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            # 新增：欧洲选举组
            'european_parliamentary_elections': {
                'keywords': ['election', 'parliamentary', 'party', 'seats', 'win', 'vote'],
                'exclusion_patterns': ['us', 'america', 'iran', 'kharg', 'control'],
                'regions': ['europe', 'slovenia', 'slovenian'],
                'markets': [],
                'description': '欧洲议会选举',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            
            # 美联储决策 - 多维度分组
            'fed_rate_decision': {
                'keywords': ['fed', 'interest rate', 'decision', 'meeting'],
                'exclusion_patterns': ['hike', 'cut', 'hold', 'increase', 'decrease'],
                'markets': [],
                'description': '美联储利率决策',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'fed_rate_size': {
                'keywords': ['fed', 'rate', 'basis points', '25', '50', '75'],
                'exclusion_patterns': ['25bps', '50bps', '75bps', '100bps'],
                'markets': [],
                'description': '美联储加息幅度',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            
            # 娱乐文化 - 细化分组
            'oscar_best_picture': {
                'keywords': ['best picture', 'picture', 'film', 'movie', 'academy awards', 'oscar'],
                'exclusion_patterns': ['win', 'lose', 'nominate', 'best actor', 'best actress', 'best director'],
                'markets': [],
                'description': '奥斯卡最佳影片奖',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'oscar_best_actor': {
                'keywords': ['best actor', 'actor', 'male lead', 'academy awards', 'oscar'],
                'exclusion_patterns': ['win', 'lose', 'nominate', 'best actress', 'best supporting', 'best picture'],
                'markets': [],
                'description': '奥斯卡最佳男主角奖',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'oscar_best_actress': {
                'keywords': ['best actress', 'actress', 'female lead', 'academy awards', 'oscar'],
                'exclusion_patterns': ['win', 'lose', 'nominate', 'best actor', 'best supporting', 'best picture'],
                'markets': [],
                'description': '奥斯卡最佳女主角奖',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'oscar_best_supporting_actor': {
                'keywords': ['best supporting actor', 'supporting actor', 'male supporting', 'academy awards', 'oscar'],
                'exclusion_patterns': ['win', 'lose', 'nominate', 'best supporting actress', 'best actor', 'best picture'],
                'markets': [],
                'description': '奥斯卡最佳男配角奖',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'oscar_best_supporting_actress': {
                'keywords': ['best supporting actress', 'supporting actress', 'female supporting', 'academy awards', 'oscar'],
                'exclusion_patterns': ['win', 'lose', 'nominate', 'best supporting actor', 'best actress', 'best picture'],
                'markets': [],
                'description': '奥斯卡最佳女配角奖',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'oscar_best_director': {
                'keywords': ['best director', 'director', 'filmmaking', 'academy awards', 'oscar'],
                'exclusion_patterns': ['win', 'lose', 'nominate', 'best picture', 'best actor', 'best actress'],
                'markets': [],
                'description': '奥斯卡最佳导演奖',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'oscar_best_short_film': {
                'keywords': ['best short film', 'short film', 'live action short', 'animated short', 'academy awards', 'oscar'],
                'exclusion_patterns': ['win', 'lose', 'nominate', 'best picture', 'best documentary', 'feature film'],
                'markets': [],
                'description': '奥斯卡最佳短片奖',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'oscar_other_categories': {
                'keywords': ['academy awards', 'oscar', 'best screenplay', 'original screenplay', 'adapted screenplay', 'best documentary', 'best international'],
                'exclusion_patterns': ['win', 'lose', 'nominate'],
                'markets': [],
                'description': '奥斯卡其他奖项',
                'mutual_exclusive': False,  # 不同子类别可能不互斥
                'expected_total_probability': 1.5  # 允许更高的总概率
            },
            'other_awards': {
                'keywords': ['golden globe', 'emmy', 'grammy', 'bafta', 'award', 'winner'],
                'exclusion_patterns': ['win', 'lose', 'nominate', 'oscar', 'academy awards'],
                'markets': [],
                'description': '其他奖项（金球奖、艾美奖、格莱美等）',
                'mutual_exclusive': False,  # 不同奖项不互斥
                'expected_total_probability': 2.0  # 允许更高的总概率
            },
            'entertainment_box_office': {
                'keywords': ['box office', 'movie', 'film', 'revenue', 'opening', 'gross', 'billion'],
                'exclusion_patterns': ['million', 'dollar', 'weekend', 'domestic', 'worldwide'],
                'markets': [],
                'description': '电影票房',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'entertainment_streaming': {
                'keywords': ['streaming', 'netflix', 'disney+', 'spotify', 'subscribers', 'views', 'chart'],
                'exclusion_patterns': ['million', 'billion', 'top', 'number', 'rank'],
                'markets': [],
                'description': '流媒体平台',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            
            # 科技商业 - 新增分组
            'tech_stock_price': {
                'keywords': ['stock', 'price', 'reach', 'apple', 'google', 'tesla', 'microsoft', 'amazon', 'meta', 'share'],
                'exclusion_patterns': ['100', '200', '300', 'trillion', 'billion', 'market cap'],
                'markets': [],
                'description': '科技公司股价',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'tech_product_launch': {
                'keywords': ['launch', 'release', 'product', 'iphone', 'ai', 'chatgpt', 'vision pro', 'tesla', 'cybertruck'],
                'exclusion_patterns': ['delay', 'cancel', 'postpone', 'recall', '2024', '2025'],
                'markets': [],
                'description': '科技产品发布',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'tech_earnings': {
                'keywords': ['earnings', 'revenue', 'profit', 'quarterly', 'q1', 'q2', 'q3', 'q4', 'guidance'],
                'exclusion_patterns': ['beat', 'miss', 'meet', 'estimate', 'analyst'],
                'markets': [],
                'description': '科技公司财报',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            
            # AI相关 - 新增分组
            'ai_development': {
                'keywords': ['ai', 'artificial intelligence', 'agi', 'gpt', 'openai', 'claude', 'gemini', 'llm'],
                'exclusion_patterns': ['achieve', 'reach', 'surpass', 'human', 'level', '2024', '2025'],
                'markets': [],
                'description': 'AI发展里程碑',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'ai_regulation': {
                'keywords': ['ai regulation', 'ai act', 'safety', 'ethics', 'congress', 'eu', 'britain', 'law'],
                'exclusion_patterns': ['pass', 'reject', 'delay', 'implement', 'ban'],
                'markets': [],
                'description': 'AI监管政策',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'ai_companies': {
                'keywords': ['openai', 'anthropic', 'google', 'microsoft', 'meta', 'nvidia', 'amd', 'competition'],
                'exclusion_patterns': ['win', 'lead', 'dominate', 'acquire', 'merge', 'partnership'],
                'markets': [],
                'description': 'AI公司竞争',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            
            # 地缘政治 - 重新设计的精细化分组
            'geopolitical_iran_political': {
                'keywords': ['iran', 'reza pahlavi', 'opposition', 'government', 'regime', 'political', 'return', 'exile', 'tehran'],
                'exclusion_patterns': ['forces', 'military', 'intervention', 'invasion', 'attack', 'troops', 'us', 'israel'],
                'event_types': ['political_transition', 'regime_change', 'opposition_activity', 'exile_return'],
                'actors': ['individual', 'opposition', 'political_group'],
                'regions': ['iran', 'middle_east'],
                'markets': [],
                'description': '伊朗政治事件',
                'mutual_exclusive': True,  # 政治结果通常互斥
                'expected_total_probability': 1.0,
                'requires_event_type_consistency': True,
                'requires_actor_consistency': True,
                'requires_regional_consistency': True
            },
            'geopolitical_iran_military': {
                'keywords': ['iran', 'forces', 'military', 'intervention', 'invasion', 'attack', 'troops', 'war', 'conflict', 'strike'],
                'exclusion_patterns': ['reza pahlavi', 'opposition', 'political', 'return', 'exile', 'diplomacy', 'negotiation'],
                'event_types': ['military_intervention', 'armed_conflict', 'military_strike', 'invasion'],
                'actors': ['military', 'foreign_power', 'state'],
                'regions': ['iran', 'middle_east'],
                'markets': [],
                'description': '伊朗军事干预',
                'mutual_exclusive': True,  # 军事行动通常互斥
                'expected_total_probability': 1.0,
                'requires_event_type_consistency': True,
                'requires_actor_consistency': True,
                'requires_regional_consistency': True
            },
            'geopolitical_iran_diplomatic': {
                'keywords': ['iran', 'nuclear', 'deal', 'sanctions', 'diplomacy', 'negotiation', 'treaty', 'agreement', 'vienna', 'jcpoa'],
                'exclusion_patterns': ['forces', 'military', 'attack', 'invasion', 'reza pahlavi', 'opposition'],
                'event_types': ['diplomatic_negotiation', 'sanctions_policy', 'nuclear_agreement', 'international_relations'],
                'actors': ['government', 'international_organization', 'diplomatic_body'],
                'regions': ['iran', 'middle_east', 'global'],
                'markets': [],
                'description': '伊朗外交事务',
                'mutual_exclusive': True,  # 外交结果通常互斥
                'expected_total_probability': 1.0,
                'requires_event_type_consistency': True,
                'requires_actor_consistency': True,
                'requires_regional_consistency': False
            },
            'geopolitical_taiwan_military': {
                'keywords': ['taiwan', 'china', 'invasion', 'attack', 'military', 'conflict', 'strait', 'beijing', 'taipei', 'forces'],
                'exclusion_patterns': ['trade', 'economy', 'diplomacy', 'relations', 'sanctions'],
                'event_types': ['military_conflict', 'invasion', 'armed_attack', 'strait_conflict'],
                'actors': ['military', 'state'],
                'regions': ['taiwan', 'china', 'asia_pacific'],
                'markets': [],
                'description': '台海军事冲突',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0,
                'requires_event_type_consistency': True,
                'requires_actor_consistency': True,
                'requires_regional_consistency': True
            },
            'geopolitical_ukraine_military': {
                'keywords': ['russia', 'ukraine', 'ceasefire', 'peace', 'negotiation', 'war', 'conflict', 'invasion', 'moscow', 'kyiv', 'forces'],
                'exclusion_patterns': ['trade', 'economy', 'diplomacy', 'relations'],
                'event_types': ['military_conflict', 'ceasefire', 'peace_talk', 'armed_conflict'],
                'actors': ['military', 'state', 'government'],
                'regions': ['ukraine', 'russia', 'europe'],
                'markets': [],
                'description': '俄乌军事冲突',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0,
                'requires_event_type_consistency': True,
                'requires_actor_consistency': True,
                'requires_regional_consistency': True
            },
            'geopolitical_middle_east_conflicts': {
                'keywords': ['israel', 'palestine', 'gaza', 'hamas', 'hezbollah', 'syria', 'lebanon', 'war', 'conflict', 'ceasefire'],
                'exclusion_patterns': ['iran', 'reza pahlavi', 'nuclear', 'diplomacy'],
                'event_types': ['military_conflict', 'ceasefire', 'peace_talk', 'regional_war'],
                'actors': ['military', 'non_state_actor', 'government'],
                'regions': ['israel', 'palestine', 'gaza', 'middle_east'],
                'markets': [],
                'description': '中东地区冲突',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0,
                'requires_event_type_consistency': True,
                'requires_actor_consistency': True,
                'requires_regional_consistency': True
            },
            'geopolitical_global_diplomacy': {
                'keywords': ['nato', 'eu', 'alliance', 'treaty', 'sanction', 'trade war', 'diplomacy', 'summit', 'un'],
                'exclusion_patterns': ['invasion', 'attack', 'ceasefire', 'war', 'forces', 'military'],
                'event_types': ['diplomatic_relations', 'economic_sanctions', 'alliance_changes', 'international_cooperation'],
                'actors': ['international_organization', 'state', 'alliance'],
                'regions': ['global', 'europe', 'asia', 'america'],
                'markets': [],
                'description': '全球外交关系',
                'mutual_exclusive': False,  # 不同地区的外交行动可以共存
                'expected_total_probability': 1.5,
                'requires_event_type_consistency': False,
                'requires_actor_consistency': False,
                'requires_regional_consistency': False
            }
            ,
            'global_economy': {
                'keywords': ['recession', 'inflation', 'gdp', 'global', 'world bank', 'imf', 'crisis', 'recovery'],
                'exclusion_patterns': ['enter', 'exit', 'avoid', 'experience', '2024', '2025'],
                'markets': [],
                'description': '全球经济',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            
            # 体育比赛 - 重新设计的精细化分组
            'nba_mvp_awards': {
                'keywords': ['nba', 'mvp', 'most valuable player', 'award', 'trophy', 'devin booker', 'lebron james', 'jokic', 'embiid'],
                'exclusion_patterns': ['finals', 'championship', 'team', 'franchise', 'win', 'lose', 'game'],
                'event_types': ['individual_award', 'mvp', 'player_honor'],
                'award_categories': ['mvp', 'most valuable player'],
                'markets': [],
                'description': 'NBA个人MVP奖项',
                'mutual_exclusive': True,  # 只有一个MVP
                'expected_total_probability': 1.0,
                'requires_event_type_consistency': True
            },
            'nba_championship': {
                'keywords': ['nba', 'finals', 'championship', 'title', 'winner', 'team', 'franchise', 'portland trail blazers', 'lakers', 'warriors', 'celtics'],
                'exclusion_patterns': ['mvp', 'player', 'individual', 'award', 'trophy', 'devin booker', 'lebron james'],
                'event_types': ['team_achievement', 'championship', 'title'],
                'award_categories': [],
                'markets': [],
                'description': 'NBA总冠军',
                'mutual_exclusive': True,  # 只有一个冠军
                'expected_total_probability': 1.0,
                'requires_event_type_consistency': True
            },
            'nba_player_awards': {
                'keywords': ['nba', 'player', 'rookie', 'defensive', 'sixth man', 'most improved', 'all star', 'award', 'trophy'],
                'exclusion_patterns': ['finals', 'championship', 'team', 'franchise', 'mvp'],
                'event_types': ['individual_award', 'player_honor', 'rookie_award', 'defensive_award'],
                'award_categories': ['rookie', 'defensive player', 'sixth man', 'most improved'],
                'markets': [],
                'description': 'NBA其他球员奖项',
                'mutual_exclusive': False,  # 不同奖项可以不同人获得
                'expected_total_probability': 1.5,
                'requires_event_type_consistency': False
            },
            'nba_season_performance': {
                'keywords': ['nba', 'season', 'record', 'standing', 'playoffs', 'games', 'wins', 'losses', 'performance'],
                'exclusion_patterns': ['mvp', 'award', 'trophy', 'championship', 'finals'],
                'event_types': ['season_metrics', 'team_performance', 'playoff_qualification'],
                'award_categories': [],
                'markets': [],
                'description': 'NBA赛季表现和记录',
                'mutual_exclusive': False,  # 不同表现指标不互斥
                'expected_total_probability': 1.2,
                'requires_event_type_consistency': False
            },
            'nba_game_results': {
                'keywords': ['nba', 'game', 'match', 'win', 'lose', 'beat', 'defeat', 'victory', 'score', 'points'],
                'exclusion_patterns': ['mvp', 'award', 'trophy', 'championship', 'season', 'playoffs'],
                'event_types': ['single_game', 'game_result', 'match_outcome'],
                'award_categories': [],
                'markets': [],
                'description': 'NBA单场比赛结果',
                'mutual_exclusive': True,  # 单场比赛结果互斥
                'expected_total_probability': 1.0,
                'requires_event_type_consistency': True
            },
            'nba_playoff_predictions': {
                'keywords': ['nba', 'playoffs', 'postseason', 'series', 'advance', 'eliminate', 'bracket'],
                'exclusion_patterns': ['mvp', 'award', 'trophy', 'regular season', 'game'],
                'event_types': ['playoff_series', 'postseason', 'bracket_predictions'],
                'award_categories': [],
                'markets': [],
                'description': 'NBA季后赛预测',
                'mutual_exclusive': True,  # 季后赛结果互斥
                'expected_total_probability': 1.0,
                'requires_event_type_consistency': True
            },
            'sports_nfl': {
                'keywords': ['nfl', 'american football', 'super bowl', 'playoffs', 'chiefs', 'eagles', '49ers'],
                'exclusion_patterns': ['win', 'lose', 'cover', 'spread', 'sb', 'champion'],
                'markets': [],
                'description': 'NFL比赛结果',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'sports_soccer': {
                'keywords': ['soccer', 'association football', 'premier league', 'champions league', 'world cup', 'messi', 'ronaldo', 'galatasaray', 'glimt'],
                'exclusion_patterns': ['win', 'lose', 'draw', 'score', 'goal', 'transfer'],
                'markets': [],
                'description': '足球比赛结果',
                'mutual_exclusive': False,  # 不同赛事的球队不互斥，需要动态检查
                'expected_total_probability': 0.8  # 调整预期概率
            },
            
            # 加密货币 - 重新设计的精细化分组
            'crypto_price_levels_btc': {
                'keywords': ['bitcoin', 'BTC', 'price', 'reach', 'above', 'below', '65,000', '70,000', '60,000', '75,000', '80,000', '50,000', '100k', '150k', '200k'],
                'exclusion_patterns': ['up', 'down', 'rise', 'fall', 'direction', 'trend', 'volatile', 'swing'],
                'event_types': ['price_level', 'price_target', 'price_threshold'],
                'time_sensitivity': ['daily', 'weekly', 'monthly', 'quarterly'],
                'markets': [],
                'description': '比特币具体价格水平',
                'mutual_exclusive': False,  # 不同价格水平不互斥
                'expected_total_probability': 1.2,  # 考虑多个价格水平的可能性
                'requires_time_consistency': False
            },
            'crypto_direction_btc': {
                'keywords': ['bitcoin', 'BTC', 'up', 'down', 'rise', 'fall', 'direction', 'trend', 'bullish', 'bearish'],
                'exclusion_patterns': ['65,000', '70,000', '60,000', '75,000', '80,000', '50,000', '100k', 'specific', 'level', 'target'],
                'event_types': ['price_direction', 'movement', 'trend'],
                'time_sensitivity': ['daily', 'weekly', 'monthly'],
                'markets': [],
                'description': '比特币涨跌方向',
                'mutual_exclusive': True,  # 涨跌互斥
                'expected_total_probability': 1.0,
                'requires_time_consistency': True  # 需要时间一致性
            },
            'crypto_volatility_btc': {
                'keywords': ['bitcoin', 'BTC', 'volatile', 'volatility', 'swing', 'fluctuation', 'range', 'choppy', 'stable'],
                'exclusion_patterns': ['up', 'down', 'rise', 'fall', 'specific', 'level', 'target', 'direction'],
                'event_types': ['volatility', 'price_stability', 'range_bound'],
                'time_sensitivity': ['daily', 'weekly', 'monthly'],
                'markets': [],
                'description': '比特币波动性',
                'mutual_exclusive': False,  # 不同波动性状态不互斥
                'expected_total_probability': 1.0,
                'requires_time_consistency': False
            },
            'crypto_price_levels_eth': {
                'keywords': ['ethereum', 'ETH', 'price', 'reach', 'above', 'below', '5k', '10k', '3k', '8k', '4k', '6k', '2k'],
                'exclusion_patterns': ['up', 'down', 'rise', 'fall', 'direction', 'trend', 'volatile', 'swing'],
                'event_types': ['price_level', 'price_target', 'price_threshold'],
                'time_sensitivity': ['daily', 'weekly', 'monthly', 'quarterly'],
                'markets': [],
                'description': '以太坊具体价格水平',
                'mutual_exclusive': False,
                'expected_total_probability': 1.2,
                'requires_time_consistency': False
            },
            'crypto_direction_eth': {
                'keywords': ['ethereum', 'ETH', 'up', 'down', 'rise', 'fall', 'direction', 'trend', 'bullish', 'bearish'],
                'exclusion_patterns': ['5k', '10k', '3k', '8k', '4k', '6k', '2k', 'specific', 'level', 'target'],
                'event_types': ['price_direction', 'movement', 'trend'],
                'time_sensitivity': ['daily', 'weekly', 'monthly'],
                'markets': [],
                'description': '以太坊涨跌方向',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0,
                'requires_time_consistency': True
            },
            'crypto_regulation': {
                'keywords': ['crypto', 'bitcoin', 'ethereum', 'etf', 'sec', 'approval', 'regulation', 'ban', 'china', 'us', 'eu'],
                'exclusion_patterns': ['price', 'up', 'down', 'rise', 'fall', 'volatility'],
                'event_types': ['regulatory_action', 'policy_change', 'legal_framework'],
                'time_sensitivity': ['monthly', 'quarterly', 'yearly'],
                'markets': [],
                'description': '加密货币监管政策',
                'mutual_exclusive': True,  # 不同的监管决定通常互斥
                'expected_total_probability': 1.0,
                'requires_time_consistency': False
            },
            'crypto_adoption': {
                'keywords': ['adoption', 'institutional', 'mainstream', 'integration', 'payment', 'acceptance', 'usage'],
                'exclusion_patterns': ['price', 'volatility', 'regulation'],
                'event_types': ['adoption_milestone', 'institutional_investment', 'mainstream_acceptance'],
                'time_sensitivity': ['quarterly', 'yearly'],
                'markets': [],
                'description': '加密货币采用和普及',
                'mutual_exclusive': False,  # 不同采用指标不互斥
                'expected_total_probability': 1.5,
                'requires_time_consistency': False
            },
            
            # 经济数据 - 扩展分组
            'economic_inflation': {
                'keywords': ['inflation', 'CPI', 'price index', 'year over year', 'consumer prices'],
                'exclusion_patterns': ['above', 'below', 'higher', 'lower', '3%', '4%', '5%'],
                'markets': [],
                'description': '通胀数据预测',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'economic_employment': {
                'keywords': ['employment', 'jobs', 'unemployment', 'payroll', 'rate'],
                'exclusion_patterns': ['above', 'below', 'higher', 'lower', '4%', '5%', '6%'],
                'markets': [],
                'description': '就业数据预测',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'economic_gdp': {
                'keywords': ['gdp', 'growth', 'recession', 'economy', 'quarterly', 'annual'],
                'exclusion_patterns': ['positive', 'negative', 'above', 'below', '2%', '3%', '4%'],
                'markets': [],
                'description': 'GDP增长预测',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            
            # 社交媒体趋势 - 新增分组
            'social_media_trends': {
                'keywords': ['tiktok', 'twitter', 'instagram', 'facebook', 'followers', 'users', 'downloads'],
                'exclusion_patterns': ['billion', 'million', 'decline', 'growth', '2024'],
                'markets': [],
                'description': '社交媒体趋势',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            
            # 气候环境 - 新增分组
            'climate_weather': {
                'keywords': ['climate', 'weather', 'temperature', 'hurricane', 'el nino', 'la nina', '2024'],
                'exclusion_patterns': ['record', 'above', 'below', 'average', 'hot', 'cold'],
                'markets': [],
                'description': '气候天气事件',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            
            # 体育博彩 - 重新设计的精细化分组
            'sports_game_results': {
                'keywords': ['vs', 'win', 'lose', 'beat', 'defeat', 'victory', 'winner', 'loser', 'game', 'match'],
                'exclusion_patterns': ['over', 'under', 'o/u', 'total', 'spread', 'cover', 'handicap', 'points', 'player'],
                'betting_types': ['moneyline', 'match_result', 'head_to_head'],
                'event_types': ['game_outcome', 'winner_prediction'],
                'markets': [],
                'description': '体育比赛胜负结果',
                'mutual_exclusive': True,  # 只有一个赢家
                'expected_total_probability': 1.0,
                'requires_betting_type_consistency': True
            },
            'sports_totals_betting': {
                'keywords': ['over', 'under', 'o/u', 'total', 'points', 'combined', 'score', 'sum'],
                'exclusion_patterns': ['win', 'lose', 'beat', 'defeat', 'victory', 'spread', 'cover', 'handicap', 'player'],
                'betting_types': ['over_under', 'totals', 'points_betting'],
                'event_types': ['total_points', 'score_prediction'],
                'markets': [],
                'description': '体育总分博彩(Over/Under)',
                'mutual_exclusive': True,  # Over/Under 互斥
                'expected_total_probability': 1.0,
                'requires_betting_type_consistency': True
            },
            'sports_spread_betting': {
                'keywords': ['spread', 'cover', 'handicap', 'points', '-', '+', 'advantage', 'disadvantage'],
                'exclusion_patterns': ['over', 'under', 'o/u', 'total', 'win', 'lose', 'beat', 'defeat', 'player'],
                'betting_types': ['point_spread', 'handicap_betting', 'spread_betting'],
                'event_types': ['spread_coverage', 'handicap_result'],
                'markets': [],
                'description': '体育让分盘博彩',
                'mutual_exclusive': True,  # 让分盘互斥
                'expected_total_probability': 1.0,
                'requires_betting_type_consistency': True
            },
            'sports_player_props': {
                'keywords': ['player', 'score', 'points', 'rebounds', 'assists', '30+', '20+', 'double', 'triple', 'performance'],
                'exclusion_patterns': ['vs', 'win', 'lose', 'beat', 'defeat', 'over', 'under', 'spread', 'cover'],
                'betting_types': ['player_props', 'individual_performance', 'player_betting'],
                'event_types': ['player_performance', 'individual_stats'],
                'markets': [],
                'description': '体育球员表现博彩',
                'mutual_exclusive': False,  # 不同球员表现可以同时发生
                'expected_total_probability': 1.5,
                'requires_betting_type_consistency': False
            },
            'sports_team_props': {
                'keywords': ['team', 'record', 'standing', 'season', 'playoffs', 'championship', 'title', 'franchise'],
                'exclusion_patterns': ['vs', 'win', 'lose', 'beat', 'defeat', 'over', 'under', 'spread', 'player'],
                'betting_types': ['team_props', 'franchise_betting', 'season_betting'],
                'event_types': ['team_performance', 'season_achievements'],
                'markets': [],
                'description': '体育团队表现博彩',
                'mutual_exclusive': False,  # 不同团队指标可以同时达成
                'expected_total_probability': 1.5,
                'requires_betting_type_consistency': False
            },
            'sports_live_betting': {
                'keywords': ['live', 'in-game', 'real-time', 'current', 'moment', 'now', 'playing'],
                'exclusion_patterns': ['pre-game', 'before', 'preview', 'prediction'],
                'betting_types': ['live_betting', 'in_play', 'real_time'],
                'event_types': ['live_events', 'in_game_actions'],
                'markets': [],
                'description': '体育现场博彩',
                'mutual_exclusive': True,  # 现场事件通常互斥
                'expected_total_probability': 1.0,
                'requires_betting_type_consistency': True
            }
        }
        
        # 优化套利阈值 - 更严格的设置
        self.arbitrage_thresholds = {
            'high_probability': 1.05,  # 概率总和超过5%（更严格）
            'low_probability': 0.95,   # 概率总和低于5%（更严格）
            'min_return': 0.02,        # 最小预期收益2%（提高门槛）
            'min_liquidity': 20000,     # 最小流动性20000 USDC（提高门槛）
            'max_price_deviation': 0.6, # 最大价格偏差60%
            'min_markets_count': 2,    # 最小市场数量
            'max_markets_count': 10,   # 最大市场数量（减少复杂性）
            'probability_confidence': 0.7 # 概率置信度阈值（提高要求）
        }
        
        # 多层次风险控制参数
        self.risk_controls = {
            'max_position_size': 2000,      # 单个市场最大仓位
            'max_total_exposure': 0.3,     # 最大总敞口30%
            'max_correlation_exposure': 0.15, # 最大相关性敞口15%
            'stop_loss_threshold': -0.03,  # 止损阈值-3%
            'profit_target': 0.05,         # 止盈目标5%
            'max_concurrent_trades': 3,    # 最大并发交易数
            'min_time_between_trades': 60,  # 交易间隔60秒
            'liquidity_requirement': 0.1,  # 流动性要求10%
            'volatility_threshold': 0.2    # 波动率阈值20%
        }
    
    def scan_arbitrage_opportunities(self, scan_interval: int = 60):
        """持续扫描套利机会"""
        self.logger.info("启动概率套利策略...")
        self.logger.info(f"扫描间隔: {scan_interval}秒")
        self.logger.info(f"交易模式: {'实盘交易' if self.enable_trading else '模拟模式'}")
        
        while True:
            try:
                # 1. 获取市场数据
                markets = self.gamma_client.get_trending_markets(limit=200)
                
                # 2. 识别互斥事件组
                self.update_mutually_exclusive_groups(markets)
                
                # 3. 发现套利机会
                opportunities = self.find_arbitrage_opportunities()
                
                # 4. 执行套利
                for opportunity in opportunities:
                    self.logger.info(f"发现套利机会:")
                    self.logger.info(f"   类型: {opportunity.type}")
                    self.logger.info(f"   动作: {opportunity.action}")
                    self.logger.info(f"   预期收益: {opportunity.expected_return:.2%}")
                    self.logger.info(f"   置信度: {opportunity.confidence:.2f}")
                    self.logger.info(f"   描述: {opportunity.description}")
                    
                    # 发送套利机会通知到Telegram
                    if self.notification_service:
                        # 准备市场详情信息
                        market_details = []
                        for market in opportunity.markets:
                            market_details.append({
                                'id': market.get('id', 'N/A'),
                                'question': market.get('question', 'N/A'),
                                'yes_price': self.get_market_yes_price(market),
                                'liquidity': market.get('liquidity', 0),
                                'volume24hr': market.get('volume24hr', 0)
                            })
                        
                        self.notification_service.signal_detected(
                            strategy="概率套利",
                            market=f"套利机会: {opportunity.description[:50]}...",
                            signal=opportunity.action,
                            confidence=opportunity.confidence,
                            market_details=market_details
                        )
                        """ self.notification_service.info(
                            "套利详情", 
                            f"类型: {opportunity.type}\n"
                            f"预期收益: {opportunity.expected_return:.2%}\n"
                            f"置信度: {opportunity.confidence:.2f}\n"
                            f"动作: {opportunity.action}"
                        ) """
                    
                    if self.enable_trading:
                        self.execute_arbitrage(opportunity)
                    else:
                        self.logger.info("模拟模式：记录套利机会")
                        self.log_arbitrage_opportunity(opportunity)
                
                # 5. 等待下次扫描
                time.sleep(scan_interval)
                
            except KeyboardInterrupt:
                self.logger.info("套利策略已停止")
                break
            except Exception as e:
                self.logger.error(f"套利扫描错误: {e}")
                time.sleep(60)
    
    def update_mutually_exclusive_groups(self, markets: List[Dict]):
        """智能更新互斥事件组 - 增强版本"""
        self.logger.info(f"开始更新互斥事件组，共 {len(markets)} 个市场")
        
        # 1. 计算覆盖率
        coverage_stats = self.calculate_coverage_rate(markets)
        self.logger.info(f"当前市场覆盖率: {coverage_stats['overall_coverage']:.1%}")
        
        for category, stats in coverage_stats['by_category'].items():
            if stats['total'] > 0:
                self.logger.info(f"  {category}: {stats['covered']}/{stats['total']} ({stats['coverage_rate']:.1%})")
        
        # 2. 学习新的关键词模式
        self.learn_keywords_from_markets(markets)
        
        # 3. 使用自适应分组算法
        final_groups = self.adaptive_grouping(markets)
        
        # 4. 更新互斥组
        for group_name, group_data in final_groups.items():
            if group_name in self.mutually_exclusive_groups:
                # 更新现有组 - group_data可能是列表或字典
                if isinstance(group_data, list):
                    self.mutually_exclusive_groups[group_name]['markets'] = group_data
                elif isinstance(group_data, dict) and 'markets' in group_data:
                    self.mutually_exclusive_groups[group_name]['markets'] = group_data['markets']
            elif isinstance(group_data, dict) and 'is_dynamic' in group_data and group_data['is_dynamic']:
                # 添加动态组 - group_data是字典
                self.mutually_exclusive_groups[group_name] = group_data
        
        # 5. 验证互斥性
        self.validate_mutual_exclusivity()
        
        # 6. 统计结果
        total_grouped = sum(len(group['markets']) for group in self.mutually_exclusive_groups.values())
        self.logger.info(f"分组完成: {total_grouped}/{len(markets)} 个市场被分组")
        
        # 7. 显示分组统计
        for group_name, group_info in self.mutually_exclusive_groups.items():
            markets_count = len(group_info['markets'])
            if markets_count > 0:
                self.logger.debug(f"  {group_name}: {markets_count} 个市场 - {group_info['description']}")
    
    def find_arbitrage_opportunities(self) -> List[ArbitrageOpportunity]:
        """发现套利机会 - 增强版本"""
        opportunities = []
        
        self.logger.debug(f"检查 {len(self.mutually_exclusive_groups)} 个互斥事件组")
        
        for group_name, group_info in self.mutually_exclusive_groups.items():
            markets = group_info['markets']
            
            # 跳过动态组的特殊处理
            is_dynamic = group_info.get('is_dynamic', False)
            if is_dynamic:
                self.logger.debug(f"跳过动态组 {group_name}")
                continue
            
            self.logger.debug(f"组 {group_name}: {len(markets)} 个市场")
            
            if len(markets) < self.arbitrage_thresholds['min_markets_count']:
                self.logger.debug(f"市场数量不足，跳过组 {group_name}")
                continue
            
            if len(markets) > self.arbitrage_thresholds['max_markets_count']:
                self.logger.debug(f"市场数量过多，跳过组 {group_name}")
                continue
            
            # 计算概率总和
            total_probability = self.calculate_total_probability(markets)
            self.logger.debug(f"概率总和: {total_probability:.3f}")
            
            # 发现概率套利
            prob_arbitrage = self.find_probability_arbitrage(markets, total_probability, group_info)
            if prob_arbitrage:
                opportunities.append(prob_arbitrage)
                # 输出详细的市场信息
                market_details = []
                for market in markets[:3]:  # 只显示前3个市场避免日志过长
                    market_id = market.get('id', 'N/A')[:8]  # 只显示前8个字符
                    question = market.get('question', 'N/A')[:40]  # 只显示前40个字符
                    market_details.append(f"{market_id}({question})")
                
                markets_summary = ", ".join(market_details)
                if len(markets) > 3:
                    markets_summary += f" ... (+{len(markets)-3} more)"
                
                self.logger.info(f"发现套利机会: {prob_arbitrage.description}")
                self.logger.info(f"  包含市场: {markets_summary}")
            else:
                self.logger.debug("未发现套利机会")
            
            # 发现跨市场套利
            cross_arbitrage = self.find_cross_market_arbitrage(markets, group_info)
            if cross_arbitrage:
                opportunities.append(cross_arbitrage)
        
        # 按预期收益排序
        opportunities.sort(key=lambda opportunity: opportunity.expected_return, reverse=True)
        
        return opportunities
    
    def calculate_market_quality(self, market: Dict) -> float:
        """计算市场质量分数"""
        quality = 0.0
        
        # 1. 流动性评分 (40%)
        liquidity = float(market.get('liquidity', 0))
        liquidity_score = min(liquidity / 50000, 1.0) * 0.4
        quality += liquidity_score
        
        # 2. 交易量评分 (30%)
        volume = float(market.get('volume24hr', 0))
        volume_score = min(volume / 30000, 1.0) * 0.3
        quality += volume_score
        
        # 3. 价格稳定性评分 (20%)
        price = self.get_market_yes_price(market)
        if 0.1 <= price <= 0.9:  # 合理价格范围
            price_score = 0.2
        else:
            price_score = 0.1
        quality += price_score
        
        # 4. 市场活跃度评分 (10%)
        if volume > 1000 and liquidity > 1000:
            activity_score = 0.1
        else:
            activity_score = 0.05
        quality += activity_score
        
        return min(quality, 1.0)
    
    def find_best_matching_group(self, question: str, market: Dict) -> Optional[str]:
        """找到最佳匹配的组 - 增强版本，增加NBA事件类型检查"""
        best_group = None
        best_score = 0.0
        
        # 1. 传统关键词匹配 (40%权重)
        keyword_scores = {}
        for group_name, group_info in self.mutually_exclusive_groups.items():
            keyword_score = self.calculate_keyword_score(question, group_info)
            keyword_scores[group_name] = keyword_score
            
            if keyword_score > best_score and keyword_score > 0.1:
                best_score = keyword_score
                best_group = group_name
            elif keyword_score == best_score and keyword_score > 0.1:
                # 如果分数相同，优先选择更具体的分组
                if best_group is None or self.is_more_specific_group(group_name, best_group):
                    best_group = group_name
        
        # 2. 语义相似度匹配 (35%权重)
        semantic_scores = self.calculate_semantic_similarity_scores(question)
        for group_name, semantic_score in semantic_scores.items():
            combined_score = keyword_scores.get(group_name, 0) * 0.4 + semantic_score * 0.35
            
            if combined_score > best_score and combined_score > 0.15:
                best_score = combined_score
                best_group = group_name
            elif combined_score == best_score and combined_score > 0.15:
                # 如果分数相同，优先选择更具体的分组
                if best_group is None or self.is_more_specific_group(group_name, best_group):
                    best_group = group_name
        
        # 2. 体育博彩事件类型一致性检查 (15%权重)
        if best_group and 'sports' in best_group:
            if not self.validate_single_sports_betting_consistency(question, best_group):
                self.logger.debug(f"体育博彩市场 {question[:30]}... 与组 {best_group} 不一致")
                return None
        
        # 3. 地缘政治事件类型一致性检查 (15%权重)
        if best_group and 'geopolitical' in best_group:
            if not self.validate_single_geopolitical_event_consistency(question, best_group):
                self.logger.debug(f"地缘政治市场 {question[:30]}... 与组 {best_group} 不一致")
                return None
        
        # 4. NBA事件类型一致性检查 (10%权重)
        if best_group and 'nba' in best_group:
            if not self.validate_single_nba_event_consistency(question, best_group):
                self.logger.debug(f"NBA市场 {question[:30]}... 与组 {best_group} 不一致")
                return None
        
        # 5. 加密货币事件类型一致性检查 (10%权重)
        if best_group and 'crypto' in best_group:
            if not self.validate_single_crypto_event_consistency(question, best_group):
                self.logger.debug(f"加密货币市场 {question[:30]}... 与组 {best_group} 不一致")
                return None
        
        # 6. 地区一致性检查 (5%权重) - 针对地缘政治事件
        if best_group and 'geopolitical' in best_group:
            if not self.validate_single_market_regional_consistency(question, best_group):
                self.logger.debug(f"市场 {question[:30]}... 与组 {best_group} 地区不一致")
                return None
        
        # 7. 市场质量调整 (5%权重)
        if best_group:
            market_quality = self.calculate_market_quality(market)
            adjusted_score = best_score * (0.95 + market_quality * 0.05)
            
            if adjusted_score > 0.2:
                return best_group
        
        return best_group
    
    def validate_single_sports_betting_consistency(self, question: str, group_name: str) -> bool:
        """验证单个体育博彩市场与目标组的一致性"""
        # 提取问题的博彩类型
        betting_types = self.extract_sports_betting_types([{'question': question}])
        
        # 检查组的博彩类型要求
        group_info = self.mutually_exclusive_groups.get(group_name, {})
        expected_betting_types = group_info.get('betting_types', [])
        
        # 如果没有指定博彩类型，允许通过
        if not expected_betting_types:
            return True
        
        # 检查博彩类型是否匹配
        for betting_type in betting_types:
            if betting_type in expected_betting_types:
                return True
        
        # 检查是否有冲突的博彩类型
        if 'moneyline' in betting_types and 'over_under' in expected_betting_types:
            return False  # 胜负盘不应该匹配到大小盘组
        
        if 'over_under' in betting_types and 'moneyline' in expected_betting_types:
            return False  # 大小盘不应该匹配到胜负盘组
        
        if 'point_spread' in betting_types and 'player_props' in expected_betting_types:
            return False  # 让分盘不应该匹配到球员盘组
        
        return True
    
    def validate_single_geopolitical_event_consistency(self, question: str, group_name: str) -> bool:
        """验证单个地缘政治市场与目标组的一致性"""
        # 提取问题的事件类型
        event_types = self.extract_geopolitical_event_types([{'question': question}])
        
        # 检查组的事件类型要求
        group_info = self.mutually_exclusive_groups.get(group_name, {})
        expected_event_types = group_info.get('event_types', [])
        
        # 如果没有指定事件类型，允许通过
        if not expected_event_types:
            return True
        
        # 检查事件类型是否匹配
        for event_type in event_types:
            if event_type in expected_event_types:
                return True
        
        # 检查是否有冲突的事件类型
        if 'political_transition' in event_types and 'military_intervention' in expected_event_types:
            return False  # 政治过渡不应该匹配到军事干预组
        
        if 'military_intervention' in event_types and 'political_transition' in expected_event_types:
            return False  # 军事干预不应该匹配到政治过渡组
        
        # 检查行为主体一致性
        if not self.validate_single_geopolitical_actor_consistency(question, group_name):
            return False
        
        return True
    
    def validate_single_geopolitical_actor_consistency(self, question: str, group_name: str) -> bool:
        """验证单个地缘政治市场的行为主体一致性"""
        # 提取问题的行为主体
        actor_keywords = {
            'individual': ['reza pahlavi', 'opposition', 'exile', 'person'],
            'military': ['forces', 'military', 'troops', 'army', 'soldiers'],
            'government': ['government', 'regime', 'state', 'administration'],
            'international_organization': ['nato', 'eu', 'un', 'international'],
            'non_state_actor': ['hamas', 'hezbollah', 'opposition', 'rebels']
        }
        
        question_lower = question.lower()
        detected_actors = []
        
        for actor, keywords in actor_keywords.items():
            if any(keyword in question_lower for keyword in keywords):
                detected_actors.append(actor)
        
        if not detected_actors:
            return True  # 没有检测到主体，允许通过
        
        # 检查组的行为主体要求
        group_info = self.mutually_exclusive_groups.get(group_name, {})
        expected_actors = group_info.get('actors', [])
        
        if not expected_actors:
            return True  # 没有指定主体要求，允许通过
        
        # 检查主体是否匹配
        for actor in detected_actors:
            if actor in expected_actors:
                return True
        
        # 检查是否有冲突的主体
        if 'individual' in detected_actors and 'military' in expected_actors:
            return False  # 个人主体不应该匹配到军事组
        
        if 'military' in detected_actors and 'individual' in expected_actors:
            return False  # 军事主体不应该匹配到个人组
        
        return True
    
    def validate_single_nba_event_consistency(self, question: str, group_name: str) -> bool:
        """验证单个NBA市场与目标组的一致性"""
        # 提取问题的事件类型
        event_types = self.extract_sports_event_types([{'question': question}])
        
        # 检查组的事件类型要求
        group_info = self.mutually_exclusive_groups.get(group_name, {})
        expected_event_types = group_info.get('event_types', [])
        
        # 如果没有指定事件类型，允许通过
        if not expected_event_types:
            return True
        
        # 检查事件类型是否匹配
        for event_type in event_types:
            if event_type in expected_event_types:
                return True
        
        # 检查是否有冲突的事件类型
        if 'mvp_award' in event_types and 'championship' in expected_event_types:
            return False  # MVP奖项不应该匹配到冠军组
        
        if 'championship' in event_types and 'mvp_award' in expected_event_types:
            return False  # 冠军事件不应该匹配到MVP组
        
        # 检查维度一致性（个人 vs 团队）
        individual_keywords = ['mvp', 'player', 'rookie', 'defensive', 'sixth man', 'most improved', 'devin booker', 'lebron james', 'jokic', 'embiid']
        team_keywords = ['team', 'franchise', 'championship', 'finals', 'lakers', 'warriors', 'celtics', 'portland trail blazers']
        
        question_lower = question.lower()
        individual_count = sum(1 for kw in individual_keywords if kw in question_lower)
        team_count = sum(1 for kw in team_keywords if kw in question_lower)
        
        # 如果是个人事件，不应该匹配到团队组
        if individual_count > team_count and 'championship' in expected_event_types:
            return False
        
        # 如果是团队事件，不应该匹配到个人组
        if team_count > individual_count and 'mvp' in expected_event_types:
            return False
        
        return True
    
    def validate_single_crypto_event_consistency(self, question: str, group_name: str) -> bool:
        """验证单个加密货币市场与目标组的一致性"""
        # 提取问题的事件类型
        event_types = self.extract_crypto_event_types([{'question': question}])
        
        # 检查组的事件类型要求
        group_info = self.mutually_exclusive_groups.get(group_name, {})
        expected_event_types = group_info.get('event_types', [])
        
        # 如果没有指定事件类型，允许通过
        if not expected_event_types:
            return True
        
        # 检查事件类型是否匹配
        for event_type in event_types:
            if event_type in expected_event_types:
                return True
        
        # 检查是否有冲突的事件类型
        if 'price_level' in event_types and 'price_direction' in expected_event_types:
            return False  # 价格水平事件不应该匹配到价格方向组
        
        if 'price_direction' in event_types and 'price_level' in expected_event_types:
            return False  # 价格方向事件不应该匹配到价格水平组
        
        return True
    
    def validate_single_market_regional_consistency(self, question: str, group_name: str) -> bool:
        """验证单个市场与目标组的地区一致性"""
        # 定义各组对应的地区
        group_regions = {
            'geopolitical_taiwan': ['taiwan', 'taipei', 'china', 'beijing', 'strait'],
            'geopolitical_ukraine': ['ukraine', 'kyiv', 'russia', 'moscow', 'europe'],
            'geopolitical_middle_east': ['israel', 'palestine', 'gaza', 'iran', 'syria', 'lebanon', 'hamas', 'hezbollah'],
            'geopolitical_global_tensions': ['nato', 'eu', 'un', 'global', 'worldwide']
        }
        
        if group_name not in group_regions:
            return True  # 非地缘政治组，不需要地区检查
        
        question_lower = question.lower()
        expected_regions = group_regions[group_name]
        
        # 检查问题是否包含预期的地区关键词
        has_expected_region = any(region in question_lower for region in expected_regions)
        
        # 检查是否包含其他地区的关键词（冲突检查）
        all_regions = set()
        for regions in group_regions.values():
            all_regions.update(regions)
        
        other_regions = all_regions - set(expected_regions)
        has_other_region = any(region in question_lower for region in other_regions)
        
        # 如果有预期地区且没有其他地区，则通过验证
        return has_expected_region and not has_other_region
    
    def is_more_specific_group(self, group1: str, group2: str) -> bool:
        """判断哪个分组更具体"""
        # 定义分组的具体性优先级
        specificity_priority = {
            'sports_soccer': 10,      # 最具体的足球分组
            'sports_nfl': 8,           # 美式足球
            'sports_nba': 8,           # 篮球
            'election_2024_winner': 5,   # 选举
            'crypto_btc_levels': 3,       # 加密货币
            'entertainment_awards': 2,    # 娱乐奖项
            'tech_stock_price': 1,         # 科技股价
        }
        
        priority1 = specificity_priority.get(group1, 0)
        priority2 = specificity_priority.get(group2, 0)
        
        return priority1 > priority2
    
    def calculate_keyword_score(self, question: str, group_info: Dict) -> float:
        """计算关键词匹配分数 - 平衡版本，既排除假阳性又保留合理套利"""
        question_lower = question.lower()
        
        # 检查是否是动态组（没有keywords键）
        if 'keywords' not in group_info:
            return 0.0
        
        # 地区一致性检查 - 只对有明确地区要求的组进行检查
        if 'regions' in group_info and group_info['regions']:
            required_regions = group_info['regions']
            region_match = any(region in question_lower for region in required_regions)
            if not region_match:
                # 如果不包含要求的地区关键词，降低分数但不是完全排除
                return 0.08  # 较低的分数，但不是0
        
        # 关键词匹配分数 (60%)
        keyword_matches = sum(1 for kw in group_info['keywords'] if kw in question_lower)
        keyword_score = (keyword_matches / len(group_info['keywords'])) * 0.6
        
        # 排除模式匹配分数 (40%) - 只对强排除模式进行严格排除
        exclusion_patterns = group_info.get('exclusion_patterns', [])
        if exclusion_patterns:
            exclusion_matches = sum(1 for pattern in exclusion_patterns if pattern in question_lower)
            # 如果匹配到强排除模式，大幅降低分数
            if exclusion_matches >= 2:  # 需要匹配至少2个排除模式才严格排除
                return 0.02
            elif exclusion_matches == 1:
                keyword_score *= 0.3  # 匹配1个排除模式，降低分数
        
        return keyword_score
    
    def calculate_semantic_similarity_scores(self, question: str) -> Dict[str, float]:
        """计算语义相似度分数"""
        # 简化的语义匹配算法（实际应用中可以使用词向量模型）
        semantic_groups = {
            'entertainment_awards': ['award', 'oscar', 'grammy', 'emmy', 'music', 'movie', 'film', 'winner', 'nominee', 'ceremony'],
            'entertainment_box_office': ['box office', 'movie', 'film', 'revenue', 'opening', 'gross', 'ticket', 'theater', 'cinema'],
            'tech_stock_price': ['stock', 'price', 'share', 'market cap', 'trading', 'wall street', 'nasdaq', 'company value'],
            'ai_development': ['artificial intelligence', 'machine learning', 'neural network', 'automation', 'robotics', 'algorithm'],
            'international_relations': ['diplomacy', 'foreign policy', 'international', 'treaty', 'alliance', 'summit', 'negotiation'],
            'geopolitical_conflicts': ['war', 'conflict', 'military', 'tension', 'crisis', 'dispute', 'battle'],
            'climate_weather': ['temperature', 'weather', 'climate', 'environment', 'global warming', 'carbon', 'emissions']
        }
        
        question_words = set(question.lower().split())
        semantic_scores = {}
        
        for group_name, semantic_keywords in semantic_groups.items():
            semantic_set = set(semantic_keywords)
            # 计算Jaccard相似度
            intersection = len(question_words & semantic_set)
            union = len(question_words | semantic_set)
            
            if union > 0:
                similarity = intersection / union
                semantic_scores[group_name] = similarity
            else:
                semantic_scores[group_name] = 0.0
        
        return semantic_scores
    
    def learn_keywords_from_markets(self, markets: List[Dict]):
        """从市场中学习新的关键词模式"""
        # 分析高频词汇
        word_frequency = {}
        category_keywords = {}
        
        for market in markets:
            question = market.get('question', '').lower()
            words = question.split()
            
            # 统计词频
            for word in words:
                if len(word) > 3:  # 过滤短词
                    word_frequency[word] = word_frequency.get(word, 0) + 1
            
            # 基于现有分组分类学习
            best_group = self.find_best_matching_group(question, market)
            if best_group:
                if best_group not in category_keywords:
                    category_keywords[best_group] = []
                
                # 提取潜在的新关键词
                for word in words:
                    if (word not in self.mutually_exclusive_groups[best_group]['keywords'] and
                        word_frequency.get(word, 0) > 2):  # 出现频率较高的词
                        category_keywords[best_group].append(word)
        
        # 更新关键词库（这里可以设置阈值避免误添加）
        for group_name, new_keywords in category_keywords.items():
            if len(new_keywords) > 0:
                self.logger.debug(f"为组 {group_name} 发现潜在新关键词: {new_keywords[:5]}")
                
                # 可以选择性地添加新关键词
                # self.mutually_exclusive_groups[group_name]['keywords'].extend(new_keywords[:3])
    
    def adaptive_grouping(self, markets: List[Dict]) -> Dict[str, List[Dict]]:
        """自适应分组算法"""
        # 1. 传统分组
        traditional_groups = {}
        for group_name in self.mutually_exclusive_groups:
            traditional_groups[group_name] = []
        
        # 2. 为每个市场分配到最佳组
        unassigned_markets = []
        
        for market in markets:
            question = market.get('question', '').lower()
            market_quality = self.calculate_market_quality(market)
            
            if market_quality < 0.1:
                continue
            
            best_group = self.find_best_matching_group(question, market)
            
            if best_group:
                traditional_groups[best_group].append(market)
            else:
                unassigned_markets.append(market)
        
        # 3. 处理未分配的市场 - 尝试动态分组
        dynamic_groups = self.create_dynamic_groups(unassigned_markets)
        
        # 4. 合并结果
        final_groups = {**traditional_groups, **dynamic_groups}
        
        return final_groups
    
    def create_dynamic_groups(self, unassigned_markets: List[Dict]) -> Dict[str, List[Dict]]:
        """为未分配的市场创建动态分组"""
        dynamic_groups = {}
        
        if len(unassigned_markets) < 2:
            return dynamic_groups
        
        # 功能性词汇过滤
        function_words = {
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'by', 'for',
            'with', 'without', 'to', 'from', 'up', 'down', 'out', 'off', 'over',
            'under', 'above', 'below', 'between', 'among', 'through', 'during',
            'before', 'after', 'since', 'until', 'while', 'when', 'where', 'why',
            'how', 'what', 'which', 'who', 'whom', 'whose', 'this', 'that',
            'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'its',
            'our', 'their', 'be', 'been', 'being', 'am', 'is', 'are', 'was',
            'were', 'have', 'has', 'had', 'do', 'does', 'did', 'of'
        }
        
        def filter_question_words(question: str) -> set:
            """过滤问题中的功能性词汇"""
            import re
            words = question.lower().split()
            filtered = set()
            for word in words:
                clean_word = re.sub(r'[^\w]', '', word)
                if clean_word not in function_words and not clean_word.isdigit() and clean_word:
                    filtered.add(clean_word)
            return filtered
        
        # 改进的聚类算法 - 基于语义词汇相似度
        market_clusters = {}
        
        for i, market1 in enumerate(unassigned_markets):
            question1 = market1.get('question', '')
            words1 = filter_question_words(question1)
            
            cluster_id = None
            max_similarity = 0.0
            
            # 检查是否应该加入现有聚类
            for existing_cluster_id, cluster_markets in market_clusters.items():
                for market2 in cluster_markets:
                    question2 = market2.get('question', '')
                    words2 = filter_question_words(question2)
                    
                    # 计算语义相似度
                    intersection = len(words1 & words2)
                    union = len(words1 | words2)
                    
                    if union > 0:
                        similarity = intersection / union
                        
                        # 提高相似度阈值，确保只有真正相关的市场才会被分组
                        if similarity > max_similarity and similarity > 0.4:  # 提高到0.4
                            max_similarity = similarity
                            cluster_id = existing_cluster_id
            
            if cluster_id is not None:
                market_clusters[cluster_id].append(market1)
            else:
                # 创建新聚类
                new_cluster_id = f"dynamic_{len(market_clusters)}"
                market_clusters[new_cluster_id] = [market1]
        
        # 转换为动态组格式，添加额外的验证
        for cluster_id, cluster_markets in market_clusters.items():
            if len(cluster_markets) >= 2:  # 至少需要2个市场
                # 验证这个聚类是否真正有意义
                if self.validate_dynamic_cluster(cluster_markets):
                    dynamic_groups[cluster_id] = {
                        'markets': cluster_markets,
                        'description': f'动态分组: {cluster_id}',
                        'mutual_exclusive': True,
                        'expected_total_probability': 1.0,
                        'is_dynamic': True
                    }
        
        return dynamic_groups
    
    def validate_geopolitical_event_consistency(self, markets: List[Dict]) -> bool:
        """验证地缘政治事件的一致性 - 确保事件类型、主体和地区匹配"""
        if len(markets) < 2:
            return True
        
        # 1. 检查事件类型一致性
        event_types = self.extract_geopolitical_event_types(markets)
        if not self.validate_geopolitical_event_type_compatibility(event_types):
            self.logger.debug(f"地缘政治事件类型不兼容: {event_types}")
            return False
        
        # 2. 检查行为主体一致性
        if not self.validate_geopolitical_actor_consistency(markets):
            self.logger.debug("地缘政治事件主体不一致")
            return False
        
        # 3. 检查地区一致性
        if not self.validate_regional_consistency(markets):
            self.logger.debug("地缘政治事件地区不一致")
            return False
        
        return True
    
    def extract_geopolitical_event_types(self, markets: List[Dict]) -> List[str]:
        """提取地缘政治事件类型"""
        event_type_keywords = {
            'political_transition': ['political', 'regime', 'opposition', 'government', 'return', 'exile', 'reza pahlavi'],
            'military_intervention': ['forces', 'military', 'intervention', 'invasion', 'attack', 'troops', 'war', 'strike'],
            'diplomatic_negotiation': ['nuclear', 'deal', 'sanctions', 'diplomacy', 'negotiation', 'treaty', 'agreement', 'jcpoa'],
            'armed_conflict': ['war', 'conflict', 'ceasefire', 'peace', 'battle', 'fighting'],
            'international_relations': ['nato', 'eu', 'alliance', 'summit', 'un', 'cooperation']
        }
        
        market_event_types = []
        for market in markets:
            question = market.get('question', '').lower()
            detected_types = []
            
            for event_type, keywords in event_type_keywords.items():
                if any(keyword in question for keyword in keywords):
                    detected_types.append(event_type)
            
            if not detected_types:
                detected_types.append('unknown')
            
            market_event_types.extend(detected_types)
        
        return list(set(market_event_types))
    
    def validate_geopolitical_event_type_compatibility(self, event_types: List[str]) -> bool:
        """验证地缘政治事件类型的兼容性"""
        # 定义兼容的事件类型组合
        compatible_combinations = {
            frozenset(['political_transition']),  # 纯政治过渡
            frozenset(['military_intervention']),  # 纯军事干预
            frozenset(['diplomatic_negotiation']),  # 纯外交谈判
            frozenset(['armed_conflict']),  # 纯武装冲突
            frozenset(['international_relations']),  # 纯国际关系
            frozenset(['unknown']),  # 未知类型
            # 某些组合可能兼容
            frozenset(['political_transition', 'diplomatic_negotiation']),  # 政治过渡与外交谈判
            frozenset(['military_intervention', 'armed_conflict']),  # 军事干预与武装冲突
            frozenset(['diplomatic_negotiation', 'international_relations']),  # 外交谈判与国际关系
        }
        
        # 检查当前组合是否兼容
        event_types_set = frozenset(event_types)
        return event_types_set in compatible_combinations
    
    def validate_geopolitical_actor_consistency(self, markets: List[Dict]) -> bool:
        """验证地缘政治事件的主体一致性"""
        actor_keywords = {
            'individual': ['reza pahlavi', 'opposition', 'exile', 'person'],
            'military': ['forces', 'military', 'troops', 'army', 'soldiers'],
            'government': ['government', 'regime', 'state', 'administration'],
            'international_organization': ['nato', 'eu', 'un', 'international'],
            'non_state_actor': ['hamas', 'hezbollah', 'opposition', 'rebels']
        }
        
        market_actors = []
        for market in markets:
            question = market.get('question', '').lower()
            detected_actors = []
            
            for actor, keywords in actor_keywords.items():
                if any(keyword in question for keyword in keywords):
                    detected_actors.append(actor)
            
            if not detected_actors:
                detected_actors.append('unknown')
            
            market_actors.extend(detected_actors)
        
        unique_actors = set(actor for actor in market_actors if actor != 'unknown')
        
        # 如果所有都是unknown，允许通过
        if len(unique_actors) == 0:
            return True
        
        # 如果只有一个主体类型，通过验证
        if len(unique_actors) == 1:
            return True
        
        # 检查是否是兼容的主体组合
        compatible_actor_combinations = {
            frozenset(['government', 'military']),  # 政府与军队
            frozenset(['international_organization', 'government']),  # 国际组织与政府
            frozenset(['non_state_actor', 'military']),  # 非国家行为体与军队
        }
        
        return frozenset(unique_actors) in compatible_actor_combinations
    
    def validate_sports_betting_consistency(self, markets: List[Dict]) -> bool:
        """验证体育博彩事件的一致性 - 确保博彩类型和事件匹配"""
        if len(markets) < 2:
            return True
        
        # 1. 检查博彩类型一致性
        betting_types = self.extract_sports_betting_types(markets)
        if not self.validate_sports_betting_type_compatibility(betting_types):
            self.logger.debug(f"体育博彩类型不兼容: {betting_types}")
            return False
        
        # 2. 检查事件一致性（同一比赛/同一事件）
        if not self.validate_sports_event_consistency(markets):
            self.logger.debug("体育博彩事件不一致")
            return False
        
        # 3. 检查博彩市场互斥性
        if not self.validate_betting_market_mutual_exclusivity(markets):
            self.logger.debug("体育博彩市场互斥性检查失败")
            return False
        
        return True
    
    def extract_sports_betting_types(self, markets: List[Dict]) -> List[str]:
        """提取体育博彩类型"""
        betting_type_keywords = {
            'moneyline': ['vs', 'win', 'lose', 'beat', 'defeat', 'victory', 'winner', 'loser'],
            'over_under': ['over', 'under', 'o/u', 'total', 'points', 'combined', 'score', 'sum'],
            'point_spread': ['spread', 'cover', 'handicap', 'points', '-', '+', 'advantage', 'disadvantage'],
            'player_props': ['player', 'score', 'points', 'rebounds', 'assists', '30+', '20+', 'double', 'triple'],
            'team_props': ['team', 'record', 'standing', 'season', 'playoffs', 'championship', 'title'],
            'live_betting': ['live', 'in-game', 'real-time', 'current', 'moment', 'now', 'playing']
        }
        
        market_betting_types = []
        for market in markets:
            question = market.get('question', '').lower()
            detected_types = []
            
            for betting_type, keywords in betting_type_keywords.items():
                if any(keyword in question for keyword in keywords):
                    detected_types.append(betting_type)
            
            if not detected_types:
                detected_types.append('unknown')
            
            market_betting_types.extend(detected_types)
        
        return list(set(market_betting_types))
    
    def validate_sports_betting_type_compatibility(self, betting_types: List[str]) -> bool:
        """验证体育博彩类型的兼容性"""
        # 定义兼容的博彩类型组合
        compatible_combinations = {
            frozenset(['moneyline']),  # 纯胜负盘
            frozenset(['over_under']),  # 纯大小盘
            frozenset(['point_spread']),  # 纯让分盘
            frozenset(['player_props']),  # 纯球员盘
            frozenset(['team_props']),  # 纯团队盘
            frozenset(['live_betting']),  # 纯现场博彩
            frozenset(['unknown']),  # 未知类型
            # 某些组合可能兼容
            frozenset(['player_props', 'team_props']),  # 球员与团队表现
            frozenset(['live_betting', 'moneyline']),  # 现场与胜负
            frozenset(['live_betting', 'over_under']),  # 现场与大小
        }
        
        # 检查当前组合是否兼容
        betting_types_set = frozenset(betting_types)
        return betting_types_set in compatible_combinations
    
    def validate_betting_market_mutual_exclusivity(self, markets: List[Dict]) -> bool:
        """验证博彩市场的互斥性"""
        if len(markets) < 2:
            return True
        
        # 提取每个市场的博彩类型
        market_types = []
        for market in markets:
            question = market.get('question', '').lower()
            
            if 'vs' in question and not any(x in question for x in ['over', 'under', 'o/u', 'total', 'spread', 'cover']):
                market_types.append('moneyline')
            elif any(x in question for x in ['over', 'under', 'o/u', 'total']):
                market_types.append('over_under')
            elif 'spread' in question or 'cover' in question or 'handicap' in question:
                market_types.append('point_spread')
            elif 'player' in question and any(x in question for x in ['score', 'points', 'rebounds', 'assists']):
                market_types.append('player_props')
            else:
                market_types.append('unknown')
        
        unique_types = set(market_types)
        
        # 如果所有市场都是同一类型，检查是否互斥
        if len(unique_types) == 1:
            market_type = list(unique_types)[0]
            
            if market_type == 'moneyline':
                # 胜负盘通常是互斥的（A赢 vs B赢）
                return True
            elif market_type == 'over_under':
                # Over/Under 是互斥的
                return True
            elif market_type == 'point_spread':
                # 让分盘是互斥的
                return True
            elif market_type == 'player_props':
                # 球员盘通常不互斥（不同球员可以同时达成）
                return False
            elif market_type == 'team_props':
                # 团队盘通常不互斥
                return False
        
        # 如果有不同类型的市场，通常不构成套利
        return False
    
    def validate_sports_event_consistency(self, markets: List[Dict]) -> bool:
        """验证体育事件的一致性 - 确保事件类型和维度匹配"""
        if len(markets) < 2:
            return True
        
        # 1. 检查事件类型一致性
        event_types = self.extract_sports_event_types(markets)
        if not self.validate_sports_event_type_compatibility(event_types):
            self.logger.debug(f"体育事件类型不兼容: {event_types}")
            return False
        if not self.validate_sports_dimension_consistency(markets):
            self.logger.debug("体育事件维度不一致")
            return False
        
        # 3. 检查时间一致性
        if not self.validate_sports_time_consistency(markets):
            self.logger.debug("体育事件时间不一致")
            return False
        
        return True
    
    def extract_sports_event_types(self, markets: List[Dict]) -> List[str]:
        """提取体育事件类型"""
        event_type_keywords = {
            'mvp_award': ['mvp', 'most valuable player', 'award', 'trophy'],
            'championship': ['championship', 'finals', 'title', 'winner'],
            'player_award': ['player', 'rookie', 'defensive', 'sixth man', 'most improved'],
            'season_performance': ['season', 'record', 'standing', 'playoffs', 'games', 'wins', 'losses'],
            'game_result': ['win', 'lose', 'beat', 'defeat', 'victory', 'game', 'match'],
            'playoff_series': ['playoffs', 'postseason', 'series', 'advance', 'eliminate', 'bracket']
        }
        
        market_event_types = []
        for market in markets:
            question = market.get('question', '').lower()
            detected_types = []
            
            for event_type, keywords in event_type_keywords.items():
                if any(keyword in question for keyword in keywords):
                    detected_types.append(event_type)
            
            if not detected_types:
                detected_types.append('unknown')
            
            market_event_types.extend(detected_types)
        
        return list(set(market_event_types))
    
    def validate_sports_event_type_compatibility(self, event_types: List[str]) -> bool:
        """验证体育事件类型的兼容性"""
        # 定义兼容的事件类型组合
        compatible_combinations = {
            frozenset(['mvp_award']),  # 纯MVP奖项
            frozenset(['championship']),  # 纯冠军相关
            frozenset(['player_award']),  # 纯其他球员奖项
            frozenset(['season_performance']),  # 纯赛季表现
            frozenset(['game_result']),  # 纯比赛结果
            frozenset(['playoff_series']),  # 纯季后赛系列
            frozenset(['unknown']),  # 未知类型
            # 某些组合可能兼容
            frozenset(['player_award', 'season_performance']),  # 球员奖项与赛季表现
            frozenset(['game_result', 'season_performance']),  # 比赛结果与赛季表现
            frozenset(['playoff_series', 'championship']),  # 季后赛与冠军
        }
        
        # 检查当前组合是否兼容
        event_types_set = frozenset(event_types)
        return event_types_set in compatible_combinations
    
    def validate_sports_dimension_consistency(self, markets: List[Dict]) -> bool:
        """验证体育事件的维度一致性（个人 vs 团队）"""
        individual_keywords = ['mvp', 'player', 'rookie', 'defensive', 'sixth man', 'most improved', 'devin booker', 'lebron james', 'jokic', 'embiid']
        team_keywords = ['team', 'franchise', 'championship', 'finals', 'lakers', 'warriors', 'celtics', 'portland trail blazers']
        
        market_dimensions = []
        for market in markets:
            question = market.get('question', '').lower()
            
            individual_count = sum(1 for kw in individual_keywords if kw in question)
            team_count = sum(1 for kw in team_keywords if kw in question)
            
            if individual_count > team_count:
                market_dimensions.append('individual')
            elif team_count > individual_count:
                market_dimensions.append('team')
            else:
                market_dimensions.append('unknown')
        
        unique_dimensions = set(dim for dim in market_dimensions if dim != 'unknown')
        
        # 如果所有都是unknown，允许通过
        if len(unique_dimensions) == 0:
            return True
        
        # 如果只有一个维度，通过验证
        if len(unique_dimensions) == 1:
            return True
        
        # 如果有多个维度，检查是否是兼容的组合
        # 个人和团队事件通常不兼容，除非是特殊组合
        return False
    
    def validate_sports_time_consistency(self, markets: List[Dict]) -> bool:
        """验证体育事件的时间一致性"""
        import re
        
        def extract_time_period(question: str) -> str:
            """提取时间周期"""
            question_lower = question.lower()
            
            # 日级时间
            if re.search(r'\b(today|tonight|tonight\'s|today\'s)\b', question_lower):
                return 'daily'
            
            # 周级时间
            if re.search(r'\b(this week|week|weekly)\b', question_lower):
                return 'weekly'
            
            # 月级时间
            if re.search(r'\b(month|monthly|march|april|may|june|july|august|september|october|november|december|january|february)\b', question_lower):
                return 'monthly'
            
            # 赛季相关
            if re.search(r'\b(season|2025-2026|2026|playoffs|postseason)\b', question_lower):
                return 'season'
            
            return 'unknown'
        
        time_periods = [extract_time_period(market.get('question', '')) for market in markets]
        unique_periods = set(period for period in time_periods if period != 'unknown')
        
        # 如果所有都是unknown，允许通过
        if len(unique_periods) == 0:
            return True
        
        # 如果只有一个时间周期，通过验证
        if len(unique_periods) == 1:
            return True
        
        # 检查是否是兼容的时间周期组合
        compatible_time_combinations = {
            frozenset(['daily', 'weekly']),  # 日级和周级可以兼容
            frozenset(['weekly', 'monthly']),  # 周级和月级可以兼容
            frozenset(['monthly', 'season']),  # 月级和赛季可以兼容
        }
        
        return frozenset(unique_periods) in compatible_time_combinations
    
    def validate_crypto_event_consistency(self, markets: List[Dict]) -> bool:
        """验证加密货币事件的一致性 - 确保事件类型和时间匹配"""
        if len(markets) < 2:
            return True
        
        # 1. 检查事件类型一致性
        event_types = self.extract_crypto_event_types(markets)
        if not self.validate_event_type_compatibility(event_types):
            self.logger.debug(f"加密货币事件类型不兼容: {event_types}")
            return False
        
        # 2. 检查时间一致性（对于需要时间一致性的组）
        if not self.validate_time_consistency(markets):
            self.logger.debug("加密货币事件时间不一致")
            return False
        
        # 3. 检查资产一致性
        if not self.validate_asset_consistency(markets):
            self.logger.debug("加密货币事件资产不一致")
            return False
        
        return True
    
    def extract_crypto_event_types(self, markets: List[Dict]) -> List[str]:
        """提取加密货币事件类型"""
        event_type_keywords = {
            'price_level': ['reach', 'above', 'below', 'level', 'target', '65,000', '70,000', '60,000', '75,000', '80,000', '50,000', '100k', '150k', '200k', '5k', '10k', '3k', '8k', '4k', '6k', '2k'],
            'price_direction': ['up', 'down', 'rise', 'fall', 'direction', 'trend', 'bullish', 'bearish'],
            'volatility': ['volatile', 'volatility', 'swing', 'fluctuation', 'range', 'choppy', 'stable'],
            'regulatory': ['regulation', 'etf', 'sec', 'approval', 'ban', 'legal', 'policy'],
            'adoption': ['adoption', 'institutional', 'mainstream', 'integration', 'payment', 'acceptance']
        }
        
        market_event_types = []
        for market in markets:
            question = market.get('question', '').lower()
            detected_types = []
            
            for event_type, keywords in event_type_keywords.items():
                if any(keyword in question for keyword in keywords):
                    detected_types.append(event_type)
            
            # 如果没有检测到特定类型，默认为unknown
            if not detected_types:
                detected_types.append('unknown')
            
            market_event_types.extend(detected_types)
        
        return list(set(market_event_types))
    
    def validate_event_type_compatibility(self, event_types: List[str]) -> bool:
        """验证事件类型的兼容性"""
        # 定义兼容的事件类型组合
        compatible_combinations = {
            frozenset(['price_level']),  # 纯价格水平事件
            frozenset(['price_direction']),  # 纯价格方向事件
            frozenset(['volatility']),  # 纯波动性事件
            frozenset(['regulatory']),  # 纯监管事件
            frozenset(['adoption']),  # 纯采用事件
            frozenset(['unknown']),  # 未知类型
            # 某些组合可能兼容，但需要谨慎处理
            frozenset(['price_level', 'volatility']),  # 价格水平与波动性
            frozenset(['price_direction', 'volatility']),  # 价格方向与波动性
        }
        
        # 检查当前组合是否兼容
        event_types_set = frozenset(event_types)
        return event_types_set in compatible_combinations
    
    def validate_time_consistency(self, markets: List[Dict]) -> bool:
        """验证时间一致性"""
        import re
        
        def extract_time_period(question: str) -> str:
            """提取时间周期"""
            question_lower = question.lower()
            
            # 日级时间
            if re.search(r'\b(daily|today|tomorrow|\d+st|\d+nd|\d+rd|\d+th)\b', question_lower):
                return 'daily'
            
            # 周级时间
            if re.search(r'\b(week|weekly|this week|next week)\b', question_lower):
                return 'weekly'
            
            # 月级时间
            if re.search(r'\b(month|monthly|march|april|may|june|july|august|september|october|november|december|january|february)\b', question_lower):
                return 'monthly'
            
            # 季级时间
            if re.search(r'\b(quarter|quarterly|q1|q2|q3|q4)\b', question_lower):
                return 'quarterly'
            
            # 年级时间
            if re.search(r'\b(year|yearly|annual|2024|2025|2026)\b', question_lower):
                return 'yearly'
            
            return 'unknown'
        
        time_periods = [extract_time_period(market.get('question', '')) for market in markets]
        unique_periods = set(period for period in time_periods if period != 'unknown')
        
        # 如果所有都是unknown，允许通过
        if len(unique_periods) == 0:
            return True
        
        # 如果只有一个时间周期，通过验证
        if len(unique_periods) == 1:
            return True
        
        # 检查是否是兼容的时间周期组合
        compatible_time_combinations = {
            frozenset(['daily', 'weekly']),  # 日级和周级可以兼容
            frozenset(['weekly', 'monthly']),  # 周级和月级可以兼容
            frozenset(['monthly', 'quarterly']),  # 月级和季级可以兼容
            frozenset(['quarterly', 'yearly']),  # 季级和年级可以兼容
        }
        
        return frozenset(unique_periods) in compatible_time_combinations
    
    def validate_asset_consistency(self, markets: List[Dict]) -> bool:
        """验证资产一致性"""
        asset_keywords = {
            'bitcoin': ['bitcoin', 'btc'],
            'ethereum': ['ethereum', 'eth'],
            'crypto_general': ['crypto', 'cryptocurrency']
        }
        
        market_assets = []
        for market in markets:
            question = market.get('question', '').lower()
            detected_asset = None
            
            for asset, keywords in asset_keywords.items():
                if any(keyword in question for keyword in keywords):
                    detected_asset = asset
                    break
            
            if detected_asset:
                market_assets.append(detected_asset)
        
        unique_assets = set(market_assets)
        
        # 如果没有检测到特定资产，或者只有一种资产，通过验证
        if len(unique_assets) <= 1:
            return True
        
        # 如果有crypto_general，可以与其他资产兼容
        if 'crypto_general' in unique_assets and len(unique_assets) == 2:
            return True
        
        return False
    
    def validate_dynamic_cluster(self, cluster_markets: List[Dict]) -> bool:
        """验证动态聚类是否有意义 - 增强版本"""
        if len(cluster_markets) < 2:
            return False
        
        # 新增：检查是否是政治选举事件
        if self.is_political_election_cluster(cluster_markets):
            return self.validate_political_election_consistency(cluster_markets)
        
        # 新增：检查是否是军事冲突事件
        if self.is_military_conflict_cluster(cluster_markets):
            return self.validate_military_conflict_consistency(cluster_markets)
        
        # 1. 检查是否是体育博彩事件
        if self.is_sports_betting_cluster(cluster_markets):
            return self.validate_sports_betting_consistency(cluster_markets)
        
        # 2. 检查是否是地缘政治事件
        if self.is_geopolitical_cluster(cluster_markets):
            return self.validate_geopolitical_event_consistency(cluster_markets)
        
        # 3. 检查是否是NBA事件
        if self.is_nba_cluster(cluster_markets):
            return self.validate_sports_event_consistency(cluster_markets)
        
        # 4. 检查是否是加密货币事件
        if self.is_crypto_cluster(cluster_markets):
            return self.validate_crypto_event_consistency(cluster_markets)
        
        # 5. 检查地区一致性（针对地缘政治事件）
        if not self.validate_regional_consistency(cluster_markets):
            self.logger.debug("动态聚类地区一致性检查失败")
            return False
        
        # 6. 检查事件类型相关性
        if not self.validate_event_type_correlation(cluster_markets):
            self.logger.debug("动态聚类事件类型相关性检查失败")
            return False
        
        # 7. 检查是否有足够的语义关联
        questions = [market.get('question', '') for market in cluster_markets]
        
        # 计算所有市场对之间的平均相似度
        similarities = []
        for i in range(len(questions)):
            for j in range(i + 1, len(questions)):
                similarity = self.calculate_semantic_similarity(questions[i], questions[j])
                similarities.append(similarity)
        
        if not similarities:
            return False
        
        avg_similarity = sum(similarities) / len(similarities)
        
        # 8. 综合判断：提高相似度阈值，减少错误聚类
        return avg_similarity > 0.6  # 从0.4提高到0.6
    
    def is_political_election_cluster(self, markets: List[Dict]) -> bool:
        """判断是否是政治选举聚类"""
        election_keywords = ['election', 'parliamentary', 'vote', 'party', 'seat', 'candidate', 'president', 'slovenia', 'slovenian']
        
        for market in markets:
            question = market.get('question', '').lower()
            if any(keyword in question for keyword in election_keywords):
                return True
        
        return False
    
    def is_military_conflict_cluster(self, markets: List[Dict]) -> bool:
        """判断是否是军事冲突聚类"""
        military_keywords = ['military', 'conflict', 'invasion', 'attack', 'control', 'island', 'territory', 'iran', 'kharg']
        
        for market in markets:
            question = market.get('question', '').lower()
            if any(keyword in question for keyword in military_keywords):
                return True
        
        return False
    
    def validate_political_election_consistency(self, markets: List[Dict]) -> bool:
        """验证政治选举事件的一致性"""
        if len(markets) < 2:
            return True
        
        # 检查是否都是同一国家的选举
        countries = set()
        for market in markets:
            question = market.get('question', '').lower()
            if 'slovenia' in question or 'slovenian' in question:
                countries.add('slovenia')
            elif 'iran' in question or 'iranian' in question:
                countries.add('iran')
            else:
                # 尝试提取其他国家名称
                words = question.split()
                for word in words:
                    if word.endswith('ia') or word.endswith('land') or word.endswith('stan'):
                        countries.add(word)
                        break
        
        # 只允许同一国家的选举事件组合
        if len(countries) > 1:
            self.logger.debug(f"不同国家的选举事件不允许组合: {countries}")
            return False
        
        return True
    
    def validate_military_conflict_consistency(self, markets: List[Dict]) -> bool:
        """验证军事冲突事件的一致性"""
        if len(markets) < 2:
            return True
        
        # 检查是否都是同一地区或相关方的军事事件
        regions = set()
        for market in markets:
            question = market.get('question', '').lower()
            if 'iran' in question or 'kharg' in question or 'persian' in question:
                regions.add('iran')
            elif 'israel' in question or 'gaza' in question:
                regions.add('middle_east')
            elif 'ukraine' in question or 'russia' in question:
                regions.add('eastern_europe')
            else:
                regions.add('unknown')
        
        # 只允许同一地区或相关方的军事事件组合
        if len(regions) > 1 and 'unknown' not in regions:
            self.logger.debug(f"不同地区的军事事件不允许组合: {regions}")
            return False
        
        return True
    
    def is_sports_betting_cluster(self, markets: List[Dict]) -> bool:
        """判断是否是体育博彩聚类"""
        sports_betting_keywords = ['vs', 'win', 'lose', 'over', 'under', 'o/u', 'total', 'spread', 'cover', 'player', 'points', 'rebounds', 'assists']
        
        for market in markets:
            question = market.get('question', '').lower()
            if any(keyword in question for keyword in sports_betting_keywords):
                return True
        
        return False
    
    def is_geopolitical_cluster(self, markets: List[Dict]) -> bool:
        """判断是否是地缘政治聚类"""
        geopolitical_keywords = ['iran', 'taiwan', 'china', 'russia', 'ukraine', 'israel', 'palestine', 'gaza', 'syria', 'lebanon', 'nato', 'eu', 'un', 'reza pahlavi']
        
        for market in markets:
            question = market.get('question', '').lower()
            if any(keyword in question for keyword in geopolitical_keywords):
                return True
        
        return False
    
    def is_nba_cluster(self, markets: List[Dict]) -> bool:
        """判断是否是NBA聚类"""
        nba_keywords = ['nba', 'basketball', 'mvp', 'finals', 'championship', 'devin booker', 'lebron james', 'lakers', 'warriors', 'celtics']
        
        for market in markets:
            question = market.get('question', '').lower()
            if any(keyword in question for keyword in nba_keywords):
                return True
        
        return False
    
    def is_crypto_cluster(self, markets: List[Dict]) -> bool:
        """判断是否是加密货币聚类"""
        crypto_keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency']
        
        for market in markets:
            question = market.get('question', '').lower()
            if any(keyword in question for keyword in crypto_keywords):
                return True
        
        return False
    
    def validate_regional_consistency(self, markets: List[Dict]) -> bool:
        """验证地区一致性 - 防止不同地区的事件被错误分组"""
        # 定义地区关键词映射 - 更精确的识别
        region_keywords = {
            'slovenia': ['slovenia', 'slovenian', 'ljubljana'],  # 新增斯洛文尼亚
            'iran': ['iran', 'iranian', 'tehran', 'kharg', 'persian'],  # 修改伊朗相关
            'middle_east': ['israel', 'palestine', 'gaza', 'syria', 'lebanon', 'hamas', 'hezbollah', 'iraq', 'afghanistan'],
            'taiwan': ['taiwan', 'taipei', 'china', 'beijing', 'strait'],
            'ukraine': ['ukraine', 'kyiv', 'russia', 'moscow', 'europe'],
            'europe': ['europe', 'european', 'eu', 'nato'],  # 扩展欧洲地区
            'global': ['un', 'worldwide', 'international']  # 更严格的全球定义
        }
        
        # 为每个市场识别地区
        market_regions = []
        for market in markets:
            question = market.get('question', '').lower()
            market_region = None
            
            for region, keywords in region_keywords.items():
                if any(keyword in question for keyword in keywords):
                    market_region = region
                    break
            
            market_regions.append(market_region)
        
        # 检查是否所有市场都属于同一地区
        unique_regions = set(region for region in market_regions if region)
        
        # 如果没有识别出地区，进行更严格的检查
        if len(unique_regions) == 0:
            # 对于没有明确地区关键词的市场，检查是否包含国家名称
            countries = set()
            for market in markets:
                question = market.get('question', '').lower()
                # 简单的国家名称检测
                if 'slovenia' in question:
                    countries.add('slovenia')
                elif 'iran' in question:
                    countries.add('iran')
                elif any(country in question for country in ['china', 'russia', 'ukraine', 'taiwan', 'israel', 'syria']):
                    countries.add('other_geopolitical')
            
            # 如果检测到不同国家，不允许分组
            if len(countries) > 1:
                self.logger.debug(f"检测到不同国家，不允许分组: {countries}")
                return False
            return True
        
        # 如果所有市场都属于同一地区，通过验证
        if len(unique_regions) == 1:
            return True
        
        # 如果有多个地区，严格禁止（除非是真正的全球事件）
        # 只有在所有市场都明确包含'global'或'international'关键词时才允许
        all_global = all('global' in market.get('question', '').lower() or 
                       'international' in market.get('question', '').lower() 
                       for market in markets)
        
        if all_global and len(unique_regions) <= 2:
            return True
        
        self.logger.debug(f"地区不一致，禁止分组: {unique_regions}")
        return False
    
    def validate_event_type_correlation(self, markets: List[Dict]) -> bool:
        """验证事件类型相关性 - 确保事件之间存在逻辑关联"""
        # 定义事件类型关键词 - 更精确的分类
        event_types = {
            'election_political': ['election', 'parliamentary', 'vote', 'party', 'seat', 'win', 'candidate', 'president'],
            'military_conflict': ['invasion', 'attack', 'war', 'military', 'conflict', 'escalation', 'control', 'island', 'territory'],
            'peace_process': ['ceasefire', 'peace', 'negotiation', 'talk', 'agreement', 'treaty'],
            'diplomatic_relations': ['diplomacy', 'relations', 'summit', 'meeting', 'alliance'],
            'economic_sanctions': ['sanction', 'trade', 'economy', 'embargo', 'restriction']
        }
        
        # 为每个市场识别事件类型
        market_event_types = []
        for market in markets:
            question = market.get('question', '').lower()
            market_type = None
            
            # 优先级检查：某些关键词具有更高优先级
            if 'election' in question or 'parliamentary' in question or 'party' in question:
                market_type = 'election_political'
            elif any(keyword in question for keyword in ['invasion', 'attack', 'military', 'control']):
                market_type = 'military_conflict'
            else:
                for event_type, keywords in event_types.items():
                    if any(keyword in question for keyword in keywords):
                        market_type = event_type
                        break
            
            market_event_types.append(market_type)
        
        # 检查事件类型的相关性
        unique_types = set(event_type for event_type in market_event_types if event_type)
        
        # 如果没有识别出事件类型，进行更严格的检查
        if len(unique_types) == 0:
            # 检查是否包含明显不同类型的事件关键词
            has_election = any('election' in m.get('question', '').lower() or 
                            'parliamentary' in m.get('question', '').lower() 
                            for m in markets)
            has_military = any('military' in m.get('question', '').lower() or 
                             'control' in m.get('question', '').lower() or 
                             'island' in m.get('question', '').lower() 
                             for m in markets)
            
            # 如果同时存在选举和军事事件，不允许分组
            if has_election and has_military:
                self.logger.debug("检测到选举和军事事件混合，不允许分组")
                return False
            return True
        
        # 定义严格兼容的事件类型组合
        compatible_combinations = {
            frozenset(['election_political']),  # 纯选举事件
            frozenset(['military_conflict']),  # 纯军事冲突
            frozenset(['peace_process']),     # 纯和平进程
            frozenset(['military_conflict', 'peace_process']),  # 冲突与和平相关
            frozenset(['diplomatic_relations']),  # 纯外交关系
            frozenset(['economic_sanctions']),     # 纯经济制裁
            frozenset(['diplomatic_relations', 'economic_sanctions'])  # 外交与经济相关
        }
        
        # 检查当前组合是否兼容
        if frozenset(unique_types) in compatible_combinations:
            return True
        
        # 特别检查：选举和军事事件绝对不能组合
        if 'election_political' in unique_types and 'military_conflict' in unique_types:
            self.logger.debug(f"选举和军事事件不能组合: {unique_types}")
            return False
        
        self.logger.debug(f"事件类型不兼容: {unique_types}")
        return False
    
    def calculate_semantic_similarity(self, question1: str, question2: str) -> float:
        """计算两个问题的语义相似度"""
        # 使用改进的词汇过滤
        function_words = {
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'by', 'for',
            'with', 'without', 'to', 'from', 'up', 'down', 'out', 'off', 'over',
            'under', 'above', 'below', 'between', 'among', 'through', 'during',
            'before', 'after', 'since', 'until', 'while', 'when', 'where', 'why',
            'how', 'what', 'which', 'who', 'whom', 'whose', 'this', 'that',
            'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'its',
            'our', 'their', 'be', 'been', 'being', 'am', 'is', 'are', 'was',
            'were', 'have', 'has', 'had', 'do', 'does', 'did', 'of'
        }
        
        import re
        def filter_words(question: str) -> set:
            words = question.lower().split()
            filtered = set()
            for word in words:
                clean_word = re.sub(r'[^\w]', '', word)
                if clean_word not in function_words and not clean_word.isdigit() and clean_word:
                    filtered.add(clean_word)
            return filtered
        
        words1 = filter_words(question1)
        words2 = filter_words(question2)
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def calculate_coverage_rate(self, markets: List[Dict]) -> Dict[str, float]:
        """计算各类市场的覆盖率"""
        total_markets = len(markets)
        if total_markets == 0:
            return {'overall_coverage': 0.0, 'by_category': {}}
        
        category_stats = {}
        covered_markets = 0
        
        # 定义分类映射
        category_mapping = {
            'politics': ['election_2024_winner', 'election_2024_party'],
            'economy': ['fed_rate_decision', 'fed_rate_size', 'economic_inflation', 'economic_employment', 'economic_gdp'],
            'entertainment': ['oscar_best_picture', 'oscar_best_actor', 'oscar_best_actress', 'oscar_best_supporting_actor', 'oscar_best_supporting_actress', 'oscar_best_director', 'oscar_best_short_film', 'oscar_other_categories', 'other_awards', 'entertainment_box_office', 'entertainment_streaming'],
            'technology': ['tech_stock_price', 'tech_product_launch', 'tech_earnings'],
            'ai': ['ai_development', 'ai_regulation', 'ai_companies'],
            'international': ['international_relations', 'geopolitical_conflicts', 'global_economy'],
            'sports': ['sports_nba', 'sports_nfl', 'sports_soccer'],
            'crypto': ['crypto_btc_levels', 'crypto_eth_levels', 'crypto_regulation'],
            'social_media': ['social_media_trends'],
            'climate': ['climate_weather']
        }
        
        # 初始化分类统计
        for category in category_mapping:
            category_stats[category] = {'total': 0, 'covered': 0}
        
        # 统计每个分类的覆盖率
        for market in markets:
            question = market.get('question', '').lower()
            market_category = self.classify_market_category(question, category_mapping)
            
            if market_category:
                category_stats[market_category]['total'] += 1
                
                # 检查是否被覆盖
                is_covered = False
                for group_name in category_mapping[market_category]:
                    if self.is_market_in_group(market, group_name):
                        is_covered = True
                        break
                
                if is_covered:
                    category_stats[market_category]['covered'] += 1
                    covered_markets += 1
        
        # 计算覆盖率
        for category in category_stats:
            stats = category_stats[category]
            if stats['total'] > 0:
                stats['coverage_rate'] = stats['covered'] / stats['total']
            else:
                stats['coverage_rate'] = 0.0
        
        return {
            'overall_coverage': covered_markets / total_markets,
            'by_category': category_stats
        }
    
    def classify_market_category(self, question: str, category_mapping: Dict[str, List[str]]) -> Optional[str]:
        """分类市场到具体类别"""
        for category, group_names in category_mapping.items():
            for group_name in group_names:
                if group_name in self.mutually_exclusive_groups:
                    group_info = self.mutually_exclusive_groups[group_name]
                    # 检查是否是动态组（没有keywords键）
                    if 'keywords' in group_info:
                        if any(keyword in question for keyword in group_info['keywords']):
                            return category
        return None
    
    def is_market_in_group(self, market: Dict, group_name: str) -> bool:
        """检查市场是否在指定组中"""
        if group_name not in self.mutually_exclusive_groups:
            return False
        
        group_markets = self.mutually_exclusive_groups[group_name]['markets']
        market_id = market.get('id')
        
        return any(m.get('id') == market_id for m in group_markets)
    
    def validate_mutual_exclusivity(self):
        """验证互斥性"""
        for group_name, group_info in self.mutually_exclusive_groups.items():
            if not group_info['mutual_exclusive']:
                continue
            
            markets = group_info['markets']
            if len(markets) < 2:
                continue
            
            # 检查是否真的互斥
            questions = [m.get('question', '').lower() for m in markets]
            
            # 移除明显不互斥的市场
            filtered_markets = []
            for i, market in enumerate(markets):
                is_mutually_exclusive = True
                
                for j, other_question in enumerate(questions):
                    if i != j:
                        # 检查是否有重叠
                        if self.check_market_overlap(questions[i], other_question):
                            is_mutually_exclusive = False
                            break
                
                if is_mutually_exclusive:
                    filtered_markets.append(market)
            
            group_info['markets'] = filtered_markets
    
    def check_market_overlap(self, question1: str, question2: str) -> bool:
        """检查两个市场是否重叠（改进版本）"""
        # 移除标点符号并转换为小写
        import re
        q1 = re.sub(r'[^\w\s]', ' ', question1.lower()).strip()
        q2 = re.sub(r'[^\w\s]', ' ', question2.lower()).strip()
        
        # 过滤掉功能性词汇
        function_words = {
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'by', 'for',
            'with', 'without', 'to', 'from', 'up', 'down', 'out', 'off', 'over',
            'under', 'above', 'below', 'between', 'among', 'through', 'during',
            'before', 'after', 'since', 'until', 'while', 'when', 'where', 'why',
            'how', 'what', 'which', 'who', 'whom', 'whose', 'this', 'that',
            'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'its',
            'our', 'their', 'be', 'been', 'being', 'am', 'is', 'are', 'was',
            'were', 'have', 'has', 'had', 'do', 'does', 'did', 'of'
        }
        
        # 过滤掉数字（年份等）
        def filter_words(words):
            filtered = []
            for word in words:
                # 移除标点符号后检查
                clean_word = re.sub(r'[^\w]', '', word)
                if clean_word not in function_words and not clean_word.isdigit() and clean_word:
                    filtered.append(clean_word)
            return filtered
        
        words1 = set(filter_words(q1.split()))
        words2 = set(filter_words(q2.split()))
        
        # 基础词汇重叠检查
        if len(words1 | words2) == 0:
            return True
        
        overlap = len(words1 & words2) / len(words1 | words2)
        print(f'过滤后词汇重叠度: {overlap:.2f}')
        print(f'过滤后共同词汇: {words1 & words2}')
        
        # 对于加密货币市场，降低重叠度阈值，因为它们经常有相似的关键词
        if self.is_crypto_market(question1) and self.is_crypto_market(question2):
            if overlap > 0.2:  # 加密货币市场使用更低的阈值
                return self.are_mutually_exclusive_crypto_markets(question1, question2)
            return False
        
        # 如果重叠度很低，认为是互斥的
        if overlap < 0.3:
            return False
        
        # 如果重叠度很高，需要进一步检查市场类型
        if overlap > 0.5:
            # 检查是否为体育博彩市场
            if self.is_sports_market(question1) and self.is_sports_market(question2):
                return self.are_mutually_exclusive_sports_markets(question1, question2)
            
            # 检查是否为奖项市场
            if self.is_award_market(question1) and self.is_award_market(question2):
                return self.are_mutually_exclusive_award_markets(question1, question2)
            
            # 其他情况，保守处理
            return True
        
        # 对于体育市场，使用更宽松的阈值
        if self.is_sports_market(question1) and self.is_sports_market(question2):
            if overlap >= 0.3:  # 使用>=包含边界情况
                # are_mutually_exclusive_sports_markets返回True表示互斥，False表示不互斥
                # 但check_market_overlap需要返回True表示重叠（不互斥），False表示不重叠（互斥）
                # 所以需要反转逻辑
                is_exclusive = self.are_mutually_exclusive_sports_markets(question1, question2)
                return not is_exclusive  # 反转：互斥->不重叠，不互斥->重叠
            else:
                return False  # 重叠度低，可能互斥（不重叠）
        
        # 中等重叠度，保守处理
        return overlap > 0.6
    
    def is_sports_market(self, question: str) -> bool:
        """检查是否为体育市场"""
        question_lower = question.lower()
        sports_keywords = [
            # 体育项目
            'nba', 'nfl', 'mlb', 'nhl', 'soccer', 'football', 'basketball',
            'baseball', 'hockey', 'tennis', 'golf', 'boxing', 'mma', 'ufc',
            
            # NBA球队
            'lakers', 'warriors', 'celtics', 'heat', 'spurs', 'bulls',
            'timberwolves', 'thunder', 'jazz', 'blazers', 'clippers',
            
            # 足球赛事
            'champions league', 'premier league', 'la liga', 'serie a', 'bundesliga',
            'ligue 1', 'eredivisie', 'world cup', 'euro championship', 'copa america',
            
            # 足球队
            'glimt', 'bodo', 'bodø/glimt', 'aston villa', 'villa', 'barcelona', 
            'real madrid', 'manchester city', 'manchester united', 'liverpool', 
            'chelsea', 'arsenal', 'tottenham', 'bayern munich', 'psg', 'juventus',
            'inter milan', 'ac milan', 'napoli', 'roma', 'ajax', 'feyenoord', 'psv',
            'benfica', 'porto', 'galatasaray', 'dortmund', 'leverkusen',
            
            # 其他体育词汇
            'win', 'league', 'championship', 'cup', 'match', 'game', 'team',
            'player', 'score', 'goal', 'point', 'season', 'tournament'
        ]
        return any(keyword in question_lower for keyword in sports_keywords)
    
    def is_award_market(self, question: str) -> bool:
        """检查是否为奖项市场"""
        question_lower = question.lower()
        award_keywords = [
            'academy awards', 'oscar', 'oscars', 'golden globe', 'emmy', 'grammy',
            'best picture', 'best actor', 'best actress', 'best director',
            'best supporting actor', 'best supporting actress', 'best screenplay'
        ]
        return any(keyword in question_lower for keyword in award_keywords)
    
    def is_crypto_market(self, question: str) -> bool:
        """检查是否为加密货币市场"""
        question_lower = question.lower()
        crypto_keywords = [
            'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency',
            'dogecoin', 'doge', 'solana', 'sol', 'cardano', 'ada'
        ]
        return any(keyword in question_lower for keyword in crypto_keywords)
    
    def are_mutually_exclusive_crypto_markets(self, question1: str, question2: str) -> bool:
        """检查两个加密货币市场是否真正互斥"""
        import re
        q1 = question1.lower()
        q2 = question2.lower()
        
        # 提取价格目标
        def extract_price_target(question):
            # 查找价格数字
            prices = re.findall(r'\$?([0-9,]+)', question)
            if prices:
                try:
                    # 移除逗号并转换为整数
                    price = int(prices[0].replace(',', ''))
                    return price
                except:
                    pass
            return None
        
        price1 = extract_price_target(question1)
        price2 = extract_price_target(question2)
        
        if price1 and price2:
            # 首先检查价格包含关系（优先级最高）
            if price1 > price2 * 1.5:  # 价格1是价格2的1.5倍以上
                return False  # 不互斥（包含关系）
            elif price2 > price1 * 1.5:  # 价格2是价格1的1.5倍以上
                return False  # 不互斥（包含关系）
            
            # 检查是否为相反方向的价格预测
            # 例如："above $X" vs "below $X"
            if 'above' in q1 and 'below' in q2 and price1 == price2:
                return True  # 互斥（相反方向）
            elif 'below' in q1 and 'above' in q2 and price1 == price2:
                return True  # 互斥（相反方向）
            
            # 检查相近价格的处理逻辑（改进版本）
            price_diff_ratio = abs(price1 - price2) / max(price1, price2)
            price_inclusion_ratio = abs(price1 - price2) / min(price1, price2)
            
            if price_diff_ratio < 0.1:  # 价格相差10%以内
                # 进一步检查是否为真正的相似价格目标
                if price_inclusion_ratio < 0.05:  # 价格相差5%以内
                    # 非常相近的价格，可能是同一目标的不同表述
                    return True  # 可能互斥（相似目标）
                else:
                    # 相近但差异明显的价格，需要考虑包含关系
                    # 检查时间范围是否相同
                    time_match = self.check_crypto_time_compatibility(question1, question2)
                    if not time_match:
                        return False  # 时间范围不同，不互斥
                    else:
                        # 时间范围相同但价格有差异，可能不互斥
                        return False  # 保守处理，不互斥
        
        # 检查是否为不同时间范围的市场
        time_compatible = self.check_crypto_time_compatibility(question1, question2)
        if not time_compatible:
            return False  # 不同时间范围，不互斥
        
        # 其他情况保守处理
        return True
    
    def check_crypto_time_compatibility(self, question1: str, question2: str) -> bool:
        """检查加密货币市场的时间兼容性"""
        import re
        q1 = question1.lower()
        q2 = question2.lower()
        
        # 提取时间信息
        def extract_time_info(question):
            q = question.lower()
            time_info = {
                'months': [],
                'dates': [],
                'year': None,
                'is_range': False
            }
            
            # 查找月份
            months = ['january', 'february', 'march', 'april', 'may', 'june',
                      'july', 'august', 'september', 'october', 'november', 'december']
            for month in months:
                if month in q:
                    time_info['months'].append(month)
            
            # 查找具体日期
            date_ranges = re.findall(r'(\d{1,2})-(\d{1,2})', q)
            single_dates = re.findall(r'(\d{1,2})(?:st|nd|rd|th)?', q)
            
            if date_ranges:
                # 展平元组列表
                for start, end in date_ranges:
                    time_info['dates'].extend([int(start), int(end)])
                time_info['is_range'] = True
            elif single_dates:
                time_info['dates'].extend([int(d) for d in single_dates])
            
            # 查找年份
            year_match = re.search(r'20(\d{2,4})', q)
            if year_match:
                time_info['year'] = year_match.group(1)
            
            return time_info
        
        time1 = extract_time_info(question1)
        time2 = extract_time_info(question2)
        
        # 检查年份是否相同
        if time1['year'] and time2['year'] and time1['year'] != time2['year']:
            return False  # 不同年份，不兼容
        
        # 检查月份是否相同
        if time1['months'] and time2['months']:
            common_months = set(time1['months']) & set(time2['months'])
            if not common_months:
                return False  # 没有共同月份，不兼容
        
        # 检查日期重叠
        if time1['dates'] and time2['dates']:
            if time1['is_range'] and time2['is_range']:
                # 两个都是日期范围，检查是否有重叠
                range1 = (min(time1['dates']), max(time1['dates']))
                range2 = (min(time2['dates']), max(time2['dates']))
                overlap = not (range1[1] < range2[0] or range2[1] < range1[0])
                return overlap
            elif time1['is_range'] or time2['is_range']:
                # 一个是范围，一个是具体日期
                if time1['is_range']:
                    range_dates = time1['dates']
                    single_date = time2['dates'][0] if time2['dates'] else None
                else:
                    range_dates = time2['dates']
                    single_date = time1['dates'][0] if time1['dates'] else None
                
                if single_date and range_dates:
                    return min(range_dates) <= single_date <= max(range_dates)
            else:
                # 两个都是具体日期
                return len(set(time1['dates']) & set(time2['dates'])) > 0
        
        # 如果时间信息不完整，假设兼容
        return True
    
    def are_mutually_exclusive_sports_markets(self, question1: str, question2: str) -> bool:
        """检查两个体育市场是否真正互斥"""
        q1 = question1.lower()
        q2 = question2.lower()
        
        # 提取队伍名称（增强版本）
        def extract_teams(question):
            # 常见体育队伍名称 - 更完整的列表
            teams = [
                # 足球队 - 欧洲主要联赛
                'galatasaray', 'glimt', 'bodo', 'bodø/glimt', 'brann', 'molde', 'rosenborg', 'viking',
                'barcelona', 'real madrid', 'atletico madrid', 'sevilla', 'valencia', 'athletic bilbao',
                'manchester city', 'manchester united', 'liverpool', 'chelsea', 'arsenal', 'tottenham',
                'aston villa', 'villa', 'everton', 'newcastle', 'west ham', 'leicester', 'leeds',
                'bayern munich', 'bayern', 'borussia dortmund', 'dortmund', 'rb leipzig', 'leverkusen',
                'psg', 'paris saint-germain', 'lyon', 'marseille', 'monaco', 'lille',
                'juventus', 'juve', 'inter milan', 'inter', 'ac milan', 'milan', 'napoli', 'roma', 'fiorentina',
                'ajax', 'feyenoord', 'psv', 'utrecht', 'az alkmaar', 'twente',
                'benfica', 'porto', 'sporting cp', 'braga', 'guimaraes',
                
                # 足球队 - 南美
                'boca juniors', 'river plate', 'flamengo', 'palmeiras', 'corinthians', 'santos',
                'independiente', 'racing club', 'velez sarsfield',
                
                # 足球队 - 其他
                'celtic', 'rangers', 'ajax', 'feyenoord', 'psv', 'shakhtar donetsk', 'dynamo kyiv',
                'red star belgrade', 'partizan belgrade', 'dinamo zagreb', 'hajduk split',
                'basaksehir', 'fenerbahce', 'trabzonspor', 'besiktas',
                'olympiacos', 'panathinaikos', 'aek athens', 'paok',
                'salzburg', 'lask', 'sturm graz', 'rapid wien',
                'sparta prague', 'slavia prague', 'viktoria plzen',
                'copenhagen', 'brondby', 'midtjylland', 'nordsjaelland',
                'malmo', 'djurgarden', 'hacken', 'elfsborg',
                'legia warsaw', 'lech poznan', 'rakow czestochowa',
                
                # NBA队伍
                'lakers', 'warriors', 'celtics', 'heat', 'spurs', 'bulls', 
                'nuggets', 'suns', 'bucks', 'sixers', '76ers', 'nets', 'mavericks',
                'timberwolves', 'thunder', 'jazz', 'blazers', 'trail blazers', 'clippers',
                'grizzlies', 'pelicans', 'kings', 'hornets', 'magic',
                'pacers', 'pistons', 'raptors', 'wizards', 'hawks',
                'knicks', 'cavaliers', 'pacers', 'hornets',
                
                # NFL队伍
                'chiefs', 'eagles', '49ers', '49 ers', 'cowboys', 'patriots', 'packers',
                'bills', 'bengals', 'ravens', 'steelers', 'browns', 'jets',
                'giants', 'dolphins', 'colts', 'jaguars', 'texans', 'titans',
                'broncos', 'raiders', 'chargers', 'bears', 'lions', 'vikings',
                'falcons', 'panthers', 'saints', 'buccaneers', 'cardinals', 'seahawks', 'rams',
                
                # 其他常见队伍
                'yankees', 'red sox', 'dodgers', 'giants', 'cardinals', 'cubs',
                'real madrid', 'barca', 'man city', 'man utd', 'fc barcelona'
            ]
            
            found_teams = []
            q_lower = question.lower()
            
            for team in teams:
                if team in q_lower:
                    found_teams.append(team)
            
            return found_teams
        
        teams1 = extract_teams(q1)
        teams2 = extract_teams(q2)
        
        # 如果涉及不同的队伍，可能是互斥的
        if set(teams1) != set(teams2):
            # 检查是否为同一赛事的不同竞争者
            if self.are_same_event_competitors(question1, question2, teams1, teams2):
                return True  # 同一赛事的不同竞争者，互斥
            else:
                return False  # 不同赛事，可能不互斥
        
        # 如果涉及相同队伍，检查市场类型
        if set(teams1) == set(teams2) and len(teams1) > 0:
            # 检查是否为不同类型的投注
            types1 = []
            types2 = []
            
            # 胜负市场关键词
            if any(word in q1 for word in ['win', 'winner', 'beat', 'defeat', 'vs', 'victory']):
                types1.append('moneyline')
            if any(word in q2 for word in ['win', 'winner', 'beat', 'defeat', 'vs', 'victory']):
                types2.append('moneyline')
            
            # 大小分市场关键词
            if any(word in q1 for word in ['over', 'under', 'o/u', 'total', 'points', 'score']):
                types1.append('total_points')
            if any(word in q2 for word in ['over', 'under', 'o/u', 'total', 'points', 'score']):
                types2.append('total_points')
            
            # 让分市场关键词
            if any(word in q1 for word in ['spread', 'handicap', '-', '+']):
                types1.append('spread')
            if any(word in q2 for word in ['spread', 'handicap', '-', '+']):
                types2.append('spread')
            
            # 如果是不同类型的投注市场，则不互斥
            if types1 and types2 and set(types1) != set(types2):
                return False
        
        # 默认情况下，认为是重叠的（不互斥）
        return True
    
    def are_same_event_competitors(self, question1: str, question2: str, teams1: list, teams2: list) -> bool:
        """检查是否为同一赛事的不同竞争者"""
        # 提取赛事信息
        def extract_event_info(question):
            q = question.lower()
            
            # 查找年份
            import re
            year_match = re.search(r'20(\d{2})', q)
            year = year_match.group(1) if year_match else None
            
            # 查找具体赛事类型 - 更精确的识别
            event_type = None
            specific_event = None
            
            # 足球赛事识别
            if 'champions league' in q:
                event_type = 'football'
                specific_event = 'champions_league'
            elif 'premier league' in q:
                event_type = 'football'
                specific_event = 'premier_league'
            elif 'la liga' in q:
                event_type = 'football'
                specific_event = 'la_liga'
            elif 'serie a' in q:
                event_type = 'football'
                specific_event = 'serie_a'
            elif 'bundesliga' in q:
                event_type = 'football'
                specific_event = 'bundesliga'
            elif 'ligue 1' in q:
                event_type = 'football'
                specific_event = 'ligue_1'
            elif 'eredivisie' in q:
                event_type = 'football'
                specific_event = 'eredivisie'
            elif 'world cup' in q:
                event_type = 'football'
                specific_event = 'world_cup'
            elif 'euro' in q and 'championship' in q:
                event_type = 'football'
                specific_event = 'euro_championship'
            elif 'copa america' in q:
                event_type = 'football'
                specific_event = 'copa_america'
            
            # 篮球赛事识别
            elif 'nba' in q:
                event_type = 'basketball'
                specific_event = 'nba'
            elif 'euroleague basketball' in q:
                event_type = 'basketball'
                specific_event = 'euroleague'
            
            # 美式足球赛事识别
            elif 'super bowl' in q:
                event_type = 'american_football'
                specific_event = 'super_bowl'
            elif 'nfl' in q:
                event_type = 'american_football'
                specific_event = 'nfl'
            
            # 通用赛事类型（作为后备）
            elif 'champion' in q or 'championship' in q or 'title' in q:
                event_type = 'general'
                specific_event = 'championship'
            elif 'cup' in q:
                event_type = 'general'
                specific_event = 'cup'
            elif 'league' in q:
                event_type = 'general'
                specific_event = 'league'
            
            return {
                'year': year,
                'event_type': event_type,
                'specific_event': specific_event,
                'has_competition_keywords': any(word in q for word in ['vs', 'against', 'beat', 'defeat', 'win'])
            }
        
        info1 = extract_event_info(question1)
        info2 = extract_event_info(question2)
        
        # 只有在同一具体赛事中才考虑互斥
        if (info1['specific_event'] and info2['specific_event'] and 
            info1['specific_event'] == info2['specific_event'] and
            info1['event_type'] == info2['event_type'] and
            info1['year'] == info2['year'] and
            info1['has_competition_keywords'] and info2['has_competition_keywords']):
            
            # 同一具体赛事的不同竞争者，互斥
            return True
        
        # 不同赛事类型或不同具体赛事，不互斥
        return False
    
    def are_mutually_exclusive_award_markets(self, question1: str, question2: str) -> bool:
        """检查两个奖项市场是否真正互斥"""
        q1 = question1.lower()
        q2 = question2.lower()
        
        # 提取奖项类别 - 更精确的匹配
        def extract_award_category(question):
            categories = []
            
            # 奥斯卡具体奖项类别 - 更严格的匹配
            if 'best picture' in question and 'academy awards' in question:
                categories.append('best_picture')
            if 'best actor' in question and 'academy awards' in question and 'supporting' not in question:
                categories.append('best_actor')
            if 'best actress' in question and 'academy awards' in question and 'supporting' not in question:
                categories.append('best_actress')
            if 'best supporting actor' in question and 'academy awards' in question:
                categories.append('best_supporting_actor')
            if 'best supporting actress' in question and 'academy awards' in question:
                categories.append('best_supporting_actress')
            if 'best director' in question and 'academy awards' in question:
                categories.append('best_director')
            if 'best short film' in question and 'academy awards' in question:
                categories.append('best_short_film')
            if ('live action short' in question or 'short film' in question) and 'academy awards' in question:
                categories.append('best_short_film')
            
            # 其他奥斯卡奖项
            if ('screenplay' in question or 'documentary' in question or 'international' in question) and 'academy awards' in question:
                categories.append('other_oscar')
            
            # 其他奖项体系
            if 'golden globe' in question:
                categories.append('golden_globes')
            if 'emmy' in question:
                categories.append('emmys')
            if 'grammy' in question:
                categories.append('grammys')
            
            return categories
        
        categories1 = extract_award_category(q1)
        categories2 = extract_award_category(q2)
        
        # 如果是不同的奖项类别，肯定不互斥
        if categories1 and categories2 and set(categories1) != set(categories2):
            return False
        
        # 如果是相同的奖项类别，检查是否为不同的提名者
        if categories1 and categories2 and set(categories1) == set(categories2):
            # 提取提名者/电影名称 - 改进的提取逻辑
            def extract_nominee(question):
                words = question.split()
                nominees = []
                
                # 查找人名/电影名模式 - 通常在 "win" 前面
                for i, word in enumerate(words):
                    if word == 'win' and i > 0:
                        # 向前查找可能的提名者（最多5个词）
                        for j in range(max(0, i-5), i):
                            candidate = words[j]
                            # 过滤掉常见词汇
                            if candidate not in ['will', 'the', 'a', 'an', 'at', 'in', 'for', 'of', 'and', 'or', 'but']:
                                nominees.append(candidate)
                
                # 特殊处理：查找特定人名模式
                import re
                # 查找大写开头的词（可能是人名）
                capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', question)
                for word in capitalized_words:
                    if word not in ['Will', 'The', 'A', 'An', 'At', 'In', 'For', 'Of', 'And', 'Or', 'But', 'Best', 'Academy', 'Awards']:
                        nominees.append(word)
                
                return list(set(nominees))  # 去重
            
            nominees1 = extract_nominee(q1)
            nominees2 = extract_nominee(q2)
            
            # 如果是不同的提名者竞争同一奖项，则互斥
            if nominees1 and nominees2 and set(nominees1) != set(nominees2):
                return True
            
            # 如果提名者相同，可能是重复市场，不互斥
            if nominees1 and nominees2 and set(nominees1) == set(nominees2):
                return False
        
        # 默认情况下，认为不互斥（保守策略）
        return False
    
    def generate_opportunity_id(self, opportunity: ArbitrageOpportunity) -> str:
        """生成套利机会的唯一ID"""
        # 基于市场ID和动作生成唯一标识
        market_ids = sorted([m.get('id', '') for m in opportunity.markets])
        market_str = '_'.join(market_ids[:3])  # 取前3个市场ID
        action = opportunity.action
        return f"{market_str}_{action}_{opportunity.type}"
    
    def is_opportunity_executed(self, opportunity: ArbitrageOpportunity) -> bool:
        """检查套利机会是否已执行"""
        opportunity_id = self.generate_opportunity_id(opportunity)
        return opportunity_id in self.executed_opportunities
    
    def mark_opportunity_executed(self, opportunity: ArbitrageOpportunity):
        """标记套利机会已执行"""
        opportunity_id = self.generate_opportunity_id(opportunity)
        self.executed_opportunities.add(opportunity_id)
        self.logger.debug(f"标记套利机会已执行: {opportunity_id}")
    
    def find_arbitrage_opportunities(self) -> List[ArbitrageOpportunity]:
        """发现套利机会"""
        opportunities = []
        
        self.logger.debug(f"检查 {len(self.mutually_exclusive_groups)} 个互斥事件组")
        
        for group_name, group_info in self.mutually_exclusive_groups.items():
            markets = group_info['markets']
            
            self.logger.debug(f"组 {group_name}: {len(markets)} 个市场")
            
            if len(markets) < 2:
                self.logger.debug(f"市场数量不足，跳过组 {group_name}")
                continue  # 至少需要2个市场才能形成套利
            
            # 计算概率总和
            total_probability = self.calculate_total_probability(markets)
            self.logger.debug(f"概率总和: {total_probability:.3f}")
            
            # 发现概率套利
            prob_arbitrage = self.find_probability_arbitrage(markets, total_probability, group_info)
            if prob_arbitrage:
                opportunities.append(prob_arbitrage)
                # 输出详细的市场信息
                market_details = []
                for market in markets[:3]:  # 只显示前3个市场避免日志过长
                    market_id = market.get('id', 'N/A')[:8]  # 只显示前8个字符
                    question = market.get('question', 'N/A')[:40]  # 只显示前40个字符
                    market_details.append(f"{market_id}({question})")
                
                markets_summary = ", ".join(market_details)
                if len(markets) > 3:
                    markets_summary += f" ... (+{len(markets)-3} more)"
                
                self.logger.info(f"发现套利机会: {prob_arbitrage.description}")
                self.logger.info(f"  包含市场: {markets_summary}")
            else:
                self.logger.debug("未发现套利机会")
            
            # 发现跨市场套利
            cross_arbitrage = self.find_cross_market_arbitrage(markets, group_info)
            if cross_arbitrage:
                opportunities.append(cross_arbitrage)
        
        # 按预期收益排序
        opportunities.sort(key=lambda opportunity: opportunity.expected_return, reverse=True)
        
        return opportunities
    
    def calculate_total_probability(self, markets: List[Dict]) -> float:
        """精确计算概率总和 - 增强版本，考虑互斥性"""
        total_prob = 0.0
        valid_prices = []
        
        for market in markets:
            try:
                # 获取Yes价格
                yes_price = self.get_market_yes_price(market)
                
                # 价格有效性检查
                if self.is_valid_price(yes_price, market):
                    valid_prices.append(yes_price)
                    total_prob += yes_price
                    
            except Exception as e:
                continue
        
        # 初始化互斥性标志
        are_mutually_exclusive = False
        
        # 检查市场是否互斥
        if len(markets) >= 2 and valid_prices:
            # 检查所有市场对之间的互斥性
            are_mutually_exclusive = True
            for i in range(len(markets)):
                for j in range(i + 1, len(markets)):
                    q1 = markets[i].get('question', '')
                    q2 = markets[j].get('question', '')
                    
                    # 使用改进的互斥性检查
                    if self.check_market_overlap(q1, q2):
                        # 如果重叠（不互斥），则不是完全互斥的
                        are_mutually_exclusive = False
                        break
                if not are_mutually_exclusive:
                    break
        
        # 如果市场是互斥的，限制总概率不超过预期值
        if are_mutually_exclusive and len(valid_prices) >= 2:
            # 获取预期总概率（从分组信息中）
            expected_total = 1.0  # 默认值，互斥事件的概率总和应该是1.0
            
            # 如果总概率超过预期值，则限制为预期值
            if total_prob > expected_total:
                self.logger.debug(f"互斥市场概率超限: {total_prob:.3f} -> {expected_total:.3f}")
                return expected_total
        
        # 基于有效价格计算加权平均
        if valid_prices:
            # 使用流动性权重调整概率
            weighted_prob = self.calculate_weighted_probability(markets, valid_prices)
            return weighted_prob
        
        return total_prob
    
    def is_valid_price(self, price: float, market: Dict) -> bool:
        """检查价格有效性"""
        # 1. 价格范围检查
        if not (0.01 <= price <= 0.99):
            return False
        
        # 2. 流动性检查
        liquidity = float(market.get('liquidity', 0))
        if liquidity < self.arbitrage_thresholds['min_liquidity']:
            return False
        
        # 3. 交易量检查
        volume = float(market.get('volume24hr', 0))
        if volume < 100:  # 最小交易量
            return False
        
        # 4. 价格稳定性检查
        price_deviation = abs(price - 0.5)
        if price_deviation > self.arbitrage_thresholds['max_price_deviation']:
            return False
        
        return True
    
    def calculate_weighted_probability(self, markets: List[Dict], prices: List[float]) -> float:
        """计算加权概率"""
        total_weight = 0.0
        weighted_sum = 0.0
        
        for i, price in enumerate(prices):
            if i < len(markets):
                market = markets[i]
                
                # 计算权重
                liquidity_weight = float(market.get('liquidity', 0))
                volume_weight = float(market.get('volume24hr', 0))
                
                # 综合权重
                weight = (liquidity_weight * 0.6 + volume_weight * 0.4)
                total_weight += weight
                weighted_sum += price * weight
        
        if total_weight > 0:
            return weighted_sum / total_weight
        else:
            return sum(prices) / len(prices)
    
    def assess_liquidity_depth(self, markets: List[Dict]) -> Dict[str, float]:
        """评估流动性深度"""
        liquidity_metrics = {
            'total_liquidity': 0.0,
            'average_liquidity': 0.0,
            'liquidity_score': 0.0,
            'execution_risk': 0.0
        }
        
        if not markets:
            return liquidity_metrics
        
        liquidities = []
        for market in markets:
            liquidity = float(market.get('liquidity', 0))
            liquidities.append(liquidity)
            liquidity_metrics['total_liquidity'] += liquidity
        
        liquidity_metrics['average_liquidity'] = sum(liquidities) / len(liquidities)
        
        # 流动性评分 (0-1)
        min_required = self.arbitrage_thresholds['min_liquidity']
        liquidity_metrics['liquidity_score'] = min(
            liquidity_metrics['average_liquidity'] / (min_required * 5), 1.0
        )
        
        # 执行风险评估（使用默认值）
        total_position = sum(self.estimate_position_size(m) for m in markets)
        liquidity_ratio = total_position / liquidity_metrics['total_liquidity'] if liquidity_metrics['total_liquidity'] > 0 else 0
        liquidity_metrics['execution_risk'] = min(liquidity_ratio, 1.0)
        
        return liquidity_metrics
    
    def estimate_position_size(self, market: Dict) -> float:
        """估算仓位大小（用于风险评估）"""
        # 使用简单的估算方法
        liquidity = float(market.get('liquidity', 2000))
        base_position = min(liquidity * 0.1, 500.0)  # 流动性的10%或最大500
        return base_position
    
    def get_market_yes_price(self, market: Dict) -> float:
        """获取市场Yes价格"""
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
        
        # 默认返回0.5
        return 0.5
    
    def find_probability_arbitrage(self, markets: List[Dict], total_probability: float, group_info: Dict) -> Optional[ArbitrageOpportunity]:
        """发现概率套利机会 - 增强版"""
        # 0. 首先检查市场是否真正互斥
        if len(markets) >= 2:
            are_mutually_exclusive = True
            for i in range(len(markets)):
                for j in range(i + 1, len(markets)):
                    q1 = markets[i].get('question', '')
                    q2 = markets[j].get('question', '')
                    
                    # 使用改进的互斥性检查
                    if self.check_market_overlap(q1, q2):
                        # 如果重叠（不互斥），则不是完全互斥的
                        are_mutually_exclusive = False
                        break
                if not are_mutually_exclusive:
                    break
            
            # 如果市场不是真正互斥的，不进行概率套利检测
            if not are_mutually_exclusive:
                self.logger.debug(f"市场不互斥，跳过概率套利检测")
                return None
        
        # 1. 流动性评估
        liquidity_metrics = self.assess_liquidity_depth(markets)
        
        # 2. 风险检查
        if not self.pass_risk_checks(markets, liquidity_metrics):
            return None
        
        # 3. 概率偏差分析
        expected_total = group_info.get('expected_total_probability', 1.0)
        probability_deviation = abs(total_probability - expected_total)
        
        # 4. 套利机会识别
        arbitrage_opportunity = None
        
        if total_probability > self.arbitrage_thresholds['high_probability']:
            # 概率高估，卖出所有
            expected_return = self.calculate_sell_return(total_probability, expected_total)
            
            if expected_return > self.arbitrage_thresholds['min_return']:
                arbitrage_opportunity = ArbitrageOpportunity(
                    type='probability_arbitrage',
                    action='sell_all',
                    markets=markets,
                    expected_return=expected_return,
                    confidence=self.calculate_enhanced_confidence(markets, 'sell', liquidity_metrics),
                    total_probability=total_probability,
                    description=f"概率高估套利: {group_info['description']}"
                )
        
        elif total_probability < self.arbitrage_thresholds['low_probability']:
            # 概率低估，买入所有
            expected_return = self.calculate_buy_return(total_probability, expected_total)
            
            if expected_return > self.arbitrage_thresholds['min_return']:
                arbitrage_opportunity = ArbitrageOpportunity(
                    type='probability_arbitrage',
                    action='buy_all',
                    markets=markets,
                    expected_return=expected_return,
                    confidence=self.calculate_enhanced_confidence(markets, 'buy', liquidity_metrics),
                    total_probability=total_probability,
                    description=f"概率低估套利: {group_info['description']}"
                )
        
        # 5. 最终风险控制
        if arbitrage_opportunity:
            arbitrage_opportunity = self.apply_risk_controls(arbitrage_opportunity, liquidity_metrics)
        
        return arbitrage_opportunity
    
    def pass_risk_checks(self, markets: List[Dict], liquidity_metrics: Dict[str, float]) -> bool:
        """多层次风险检查"""
        # 1. 市场数量检查
        if not (self.arbitrage_thresholds['min_markets_count'] <= len(markets) <= self.arbitrage_thresholds['max_markets_count']):
            return False
        
        # 2. 流动性检查
        if liquidity_metrics['liquidity_score'] < 0.3:
            return False
        
        # 3. 执行风险检查
        if liquidity_metrics['execution_risk'] > 0.8:
            return False
        
        # 4. 单个市场风险检查
        for market in markets:
            if not self.check_individual_market_risk(market):
                return False
        
        return True
    
    def check_individual_market_risk(self, market: Dict) -> bool:
        """检查单个市场风险"""
        # 1. 价格风险
        price = self.get_market_yes_price(market)
        if price < 0.05 or price > 0.95:
            return False
        
        # 2. 流动性风险
        liquidity = float(market.get('liquidity', 0))
        if liquidity < self.arbitrage_thresholds['min_liquidity']:
            return False
        
        # 3. 波动性风险
        volume = float(market.get('volume24hr', 0))
        if volume > 1000000:  # 过高交易量可能表示高波动
            return False
        
        return True
    
    def calculate_sell_return(self, total_probability: float, expected_total: float) -> float:
        """计算卖出套利收益"""
        if total_probability <= 0:
            return 0.0
        
        # 考虑交易成本和滑点
        trading_cost = 0.02  # 2%交易成本
        slippage = min(total_probability * 0.01, 0.05)  # 1%滑点或最大5%
        
        gross_return = (total_probability - expected_total) / total_probability
        net_return = gross_return - trading_cost - slippage
        
        return max(net_return, 0.0)
    
    def calculate_buy_return(self, total_probability: float, expected_total: float) -> float:
        """计算买入套利收益"""
        # 考虑交易成本和滑点
        trading_cost = 0.02  # 2%交易成本
        slippage = min((1.0 - total_probability) * 0.01, 0.05)  # 1%滑点或最大5%
        
        gross_return = (expected_total - total_probability) / (2.0 - total_probability)
        net_return = gross_return - trading_cost - slippage
        
        return max(net_return, 0.0)
    
    def calculate_enhanced_confidence(self, markets: List[Dict], action: str, liquidity_metrics: Dict[str, float]) -> float:
        """计算增强置信度"""
        confidence = 0.0
        
        # 1. 基础置信度 (30%)
        base_confidence = self.calculate_arbitrage_confidence(markets, action)
        confidence += base_confidence * 0.3
        
        # 2. 流动性置信度 (25%)
        liquidity_confidence = liquidity_metrics['liquidity_score']
        confidence += liquidity_confidence * 0.25
        
        # 3. 执行风险置信度 (20%)
        execution_confidence = 1.0 - liquidity_metrics['execution_risk']
        confidence += execution_confidence * 0.2
        
        # 4. 市场质量置信度 (15%)
        quality_confidence = self.calculate_markets_quality_score(markets)
        confidence += quality_confidence * 0.15
        
        # 5. 历史表现置信度 (10%)
        historical_confidence = self.get_historical_confidence()
        confidence += historical_confidence * 0.1
        
        return min(confidence, 1.0)
    
    def calculate_markets_quality_score(self, markets: List[Dict]) -> float:
        """计算市场质量分数"""
        if not markets:
            return 0.0
        
        quality_scores = []
        for market in markets:
            score = self.calculate_market_quality(market)
            quality_scores.append(score)
        
        return sum(quality_scores) / len(quality_scores)
    
    def get_historical_confidence(self) -> float:
        """获取历史置信度（模拟）"""
        # 这里可以基于历史交易记录计算
        # 暂时返回默认值
        return 0.7
    
    def apply_risk_controls(self, opportunity: ArbitrageOpportunity, liquidity_metrics: Dict[str, float]) -> ArbitrageOpportunity:
        """应用风险控制"""
        # 1. 调整预期收益（考虑风险）
        risk_adjusted_return = opportunity.expected_return * (1 - liquidity_metrics['execution_risk'] * 0.5)
        opportunity.expected_return = risk_adjusted_return
        
        # 2. 调整置信度
        risk_adjusted_confidence = opportunity.confidence * (1 - liquidity_metrics['execution_risk'] * 0.3)
        opportunity.confidence = risk_adjusted_confidence
        
        # 3. 添加风险标签
        if liquidity_metrics['execution_risk'] > 0.6:
            opportunity.description += " (高风险)"
        elif liquidity_metrics['execution_risk'] > 0.3:
            opportunity.description += " (中风险)"
        else:
            opportunity.description += " (低风险)"
        
        return opportunity
    
    def find_cross_market_arbitrage(self, markets: List[Dict], group_info: Dict) -> Optional[ArbitrageOpportunity]:
        """发现跨市场套利机会 - 增强版本，考虑互斥性"""
        if len(markets) < 2:
            return None
        
        # 首先检查市场是否互斥
        are_mutually_exclusive = False
        if len(markets) >= 2:
            are_mutually_exclusive = True
            for i in range(len(markets)):
                for j in range(i + 1, len(markets)):
                    q1 = markets[i].get('question', '')
                    q2 = markets[j].get('question', '')
                    
                    # 使用改进的互斥性检查
                    if self.check_market_overlap(q1, q2):
                        # 如果重叠（不互斥），则不是完全互斥的
                        are_mutually_exclusive = False
                        break
                if not are_mutually_exclusive:
                    break
        
        # 如果市场是互斥的，不产生跨市场套利机会
        if are_mutually_exclusive:
            self.logger.debug(f"跳过互斥市场的跨市场套利检查")
            return None
        
        # 计算价格差异
        prices = []
        for market in markets:
            price = self.get_market_yes_price(market)
            liquidity = float(market.get('liquidity', 0))
            prices.append({
                'market': market,
                'price': price,
                'liquidity': liquidity
            })
        
        # 按价格排序
        prices.sort(key=lambda price_item: price_item['price'])
        
        # 检查价格差异
        low_price = prices[0]
        high_price = prices[-1]
        
        price_diff = high_price['price'] - low_price['price']
        price_diff_pct = price_diff / low_price['price']
        
        # 如果价格差异超过阈值
        if price_diff_pct > 0.05:  # 5%差异
            expected_return = price_diff_pct * 0.8  # 考虑交易成本
            
            if expected_return > self.arbitrage_thresholds['min_return']:
                return ArbitrageOpportunity(
                    type='cross_market_arbitrage',
                    action='buy_low_sell_high',
                    markets=[low_price['market'], high_price['market']],
                    expected_return=expected_return,
                    confidence=self.calculate_arbitrage_confidence([low_price['market'], high_price['market']], 'cross'),
                    total_probability=low_price['price'] + high_price['price'],
                    description=f"跨市场套利: {group_info['description']}"
                )
        
        return None
    
    def calculate_arbitrage_confidence(self, markets: List[Dict], arbitrage_type: str) -> float:
        """计算套利置信度"""
        confidence = 0.0
        
        # 1. 流动性评估 (40%)
        total_liquidity = sum(float(m.get('liquidity', 0)) for m in markets)
        liquidity_confidence = min(total_liquidity / 50000, 0.4)  # 50k USDC为满分
        confidence += liquidity_confidence
        
        # 2. 市场数量 (20%)
        market_count_confidence = min(len(markets) * 0.1, 0.2)
        confidence += market_count_confidence
        
        # 3. 价格稳定性 (20%)
        price_stability = self.assess_price_stability(markets)
        confidence += price_stability
        
        # 4. 套利类型 (20%)
        if arbitrage_type == 'sell_all':
            type_confidence = 0.2  # 卖出套利更安全
        elif arbitrage_type == 'buy_all':
            type_confidence = 0.15
        else:
            type_confidence = 0.1
        confidence += type_confidence
        
        return min(confidence, 1.0)
    
    def assess_price_stability(self, markets: List[Dict]) -> float:
        """评估价格稳定性"""
        # 基于交易量评估价格稳定性
        total_volume = sum(float(m.get('volume24hr', 0)) for m in markets)
        
        if total_volume > 100000:
            return 0.2
        elif total_volume > 50000:
            return 0.15
        elif total_volume > 10000:
            return 0.1
        else:
            return 0.05
    
    def execute_arbitrage(self, opportunity: ArbitrageOpportunity):
        """执行套利交易"""
        # 检查是否已执行过
        if self.is_opportunity_executed(opportunity):
            self.logger.debug(f"套利机会已执行，跳过: {opportunity.description[:50]}...")
            return
        
        self.logger.info(f"执行套利: {opportunity.action}")
        
        # 发送套利执行通知
        if self.notification_service:
            self.notification_service.info(
                "套利执行", 
                f"开始执行 {opportunity.action}\n"
                f"描述: {opportunity.description[:50]}...\n"
                f"预期收益: {opportunity.expected_return:.2%}"
            )
        
        try:
            if opportunity.action == 'sell_all':
                # 卖出所有市场
                for market in opportunity.markets:
                    self.execute_sell_order(market, opportunity)
            
            elif opportunity.action == 'buy_all':
                # 买入所有市场
                for market in opportunity.markets:
                    self.execute_buy_order(market, opportunity)
            
            elif opportunity.action == 'buy_low_sell_high':
                # 买入低价，卖出高价
                low_market = opportunity.markets[0]
                high_market = opportunity.markets[1]
                
                self.execute_buy_order(low_market, opportunity)
                self.execute_sell_order(high_market, opportunity)
            
            # 记录套利交易
            self.log_arbitrage_trade(opportunity)
            
            # 标记套利机会已执行
            self.mark_opportunity_executed(opportunity)
            
            # 发送套利执行成功通知
            if self.notification_service:
                self.notification_service.success(
                    "套利执行成功", 
                    f"{opportunity.action} 执行完成\n"
                    f"描述: {opportunity.description[:50]}...\n"
                    f"预期收益: {opportunity.expected_return:.2%}"
                )
            
        except Exception as e:
            self.logger.error(f"套利执行失败: {e}")
            
            # 发送套利执行失败通知
            if self.notification_service:
                self.notification_service.error(
                    "套利执行失败", 
                    f"执行 {opportunity.action} 失败\n"
                    f"错误: {str(e)}\n"
                    f"描述: {opportunity.description[:50]}..."
                )
    
    def get_market_token_id(self, market: Dict) -> Optional[str]:
        """从市场数据中提取token_id"""
        try:
            # 方法1: 检查clobTokenIds字段
            if 'clobTokenIds' in market and market['clobTokenIds']:
                token_ids = market['clobTokenIds']
                if isinstance(token_ids, list) and len(token_ids) > 0:
                    return str(token_ids[0])
                elif isinstance(token_ids, str):
                    try:
                        import json
                        parsed = json.loads(token_ids)
                        if isinstance(parsed, list) and len(parsed) > 0:
                            return str(parsed[0])
                    except (json.JSONDecodeError, TypeError):
                        return token_ids
            
            # 方法2: 检查嵌套的markets数组
            if 'markets' in market and isinstance(market['markets'], list) and len(market['markets']) > 0:
                nested_market = market['markets'][0]
                return self.get_market_token_id(nested_market)
            
            # 方法3: 直接查找常见字段
            direct_fields = ['clobTokenId', 'token_id', 'tokenAddress', 'condition_id', 'outcomeTokenId']
            for field in direct_fields:
                if field in market and market[field]:
                    return str(market[field])
            
            # 方法4: 检查outcomeTokens结构
            if 'outcomeTokens' in market:
                outcome_tokens = market['outcomeTokens']
                if isinstance(outcome_tokens, list) and len(outcome_tokens) > 0:
                    # 查找"Yes"代币
                    for token in outcome_tokens:
                        if isinstance(token, dict):
                            if token.get('outcome') == 'Yes' or 'yes' in str(token.get('outcome', '')).lower():
                                return token.get('address') or token.get('token_id')
                    # 如果没找到Yes，返回第一个
                    first_token = outcome_tokens[0]
                    return first_token.get('address') or first_token.get('token_id')
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取token_id失败: {e}")
            return None
    
    def execute_buy_order(self, market: Dict, opportunity: ArbitrageOpportunity):
        """执行买入订单"""
        position_size = self.calculate_arbitrage_position_size(market, opportunity)
        
        try:
            # 获取token_id（条件代币地址）
            token_id = self.get_market_token_id(market)
            if not token_id:
                self.logger.error(f"无法获取token_id for market: {market.get('id', 'unknown')}")
                return
            
            # 直接创建订单
            result = self.trading_client.create_order(
                token_id=token_id,
                side='BUY',
                size=position_size,
                price=self.get_market_yes_price(market)
            )
            
            if result.get('success'):
                order_id = result.get('order_id')
                self.logger.info(f"买入订单: {order_id} - {market['question'][:30]}...")
            else:
                self.logger.error(f"买入失败: {result.get('error')}")
            
        except Exception as e:
            self.logger.error(f"买入失败: {e}")
    
    def execute_sell_order(self, market: Dict, opportunity: ArbitrageOpportunity):
        """执行卖出订单"""
        position_size = self.calculate_arbitrage_position_size(market, opportunity)
        
        try:
            # 获取token_id（条件代币地址）
            token_id = self.get_market_token_id(market)
            if not token_id:
                self.logger.error(f"无法获取token_id for market: {market.get('id', 'unknown')}")
                return
            
            # 直接创建订单
            result = self.trading_client.create_order(
                token_id=token_id,
                side='SELL',
                size=position_size,
                price=self.get_market_yes_price(market)
            )
            
            if result.get('success'):
                order_id = result.get('order_id')
                self.logger.info(f"卖出订单: {order_id} - {market['question'][:30]}...")
            else:
                self.logger.error(f"卖出失败: {result.get('error')}")
            
        except Exception as e:
            self.logger.error(f"卖出失败: {e}")
    
    def calculate_arbitrage_position_size(self, market: Dict, opportunity: ArbitrageOpportunity) -> float:
        """动态计算套利仓位大小 - 应用用户配置的风险限制"""
        # 1. 检查日损失限制
        MAX_DAILY_LOSS_USD = float(os.getenv('MAX_DAILY_LOSS_USD', 50))
        if hasattr(self, 'daily_pnl') and self.daily_pnl < -MAX_DAILY_LOSS_USD:
            self.logger.warning(f"日损失 ${abs(self.daily_pnl):.2f} 已超过限制 ${MAX_DAILY_LOSS_USD:.2f}，停止交易")
            return 0.0
        
        # 2. 基础仓位计算 - 使用用户配置的最大交易金额
        base_size = min(200.0, MAX_TRADE_AMOUNT_USD)  # 不超过用户配置的最大交易金额
        
        # 3. 置信度调整 (30%)
        confidence_multiplier = opportunity.confidence
        
        # 4. 预期收益调整 (25%) - 应用止损百分比
        STOP_LOSS_PERCENTAGE = float(os.getenv('STOP_LOSS_PERCENTAGE', 10))
        return_multiplier = min(opportunity.expected_return * 8, 2.0)
        # 如果预期收益小于止损百分比，大幅降低仓位
        if opportunity.expected_return < STOP_LOSS_PERCENTAGE / 100:
            return_multiplier *= 0.1
        
        # 5. 流动性调整 (20%)
        liquidity = float(market.get('liquidity', 5000))
        liquidity_multiplier = min(liquidity / 15000, 1.5)
        
        # 6. 市场质量调整 (15%)
        quality_score = self.calculate_market_quality(market)
        quality_multiplier = 0.5 + quality_score * 0.5
        
        # 7. 风险调整 (10%)
        risk_multiplier = self.calculate_risk_multiplier(market, opportunity)
        
        # 8. 动态市场条件调整
        market_condition_multiplier = self.calculate_market_condition_multiplier(market)
        
        # 计算最终仓位
        position_size = (
            base_size * 
            confidence_multiplier * 
            return_multiplier * 
            liquidity_multiplier * 
            quality_multiplier * 
            risk_multiplier * 
            market_condition_multiplier
        )
        
        # 9. 应用用户配置的最大交易金额限制
        position_size = min(position_size, MAX_TRADE_AMOUNT_USD)
        
        # 10. 风险限制
        position_size = self.apply_position_limits(position_size, market, opportunity)
        
        self.logger.info(f"计算仓位大小: ${position_size:.2f} (基础: ${base_size:.2f}, 限制: ${MAX_TRADE_AMOUNT_USD:.2f})")
        
        return round(position_size, 2)
    
    def calculate_risk_multiplier(self, market: Dict, opportunity: ArbitrageOpportunity) -> float:
        """计算风险调整倍数"""
        risk_multiplier = 1.0
        
        # 1. 价格风险
        price = self.get_market_yes_price(market)
        if price < 0.1 or price > 0.9:
            risk_multiplier *= 0.5
        
        # 2. 流动性风险
        liquidity = float(market.get('liquidity', 0))
        if liquidity < self.arbitrage_thresholds['min_liquidity']:
            risk_multiplier *= 0.7
        
        # 3. 波动性风险
        volume = float(market.get('volume24hr', 0))
        if volume > 500000:  # 高波动性
            risk_multiplier *= 0.8
        
        # 4. 集中度风险
        if opportunity.action == 'buy_all' and len(opportunity.markets) > 5:
            risk_multiplier *= 0.9
        
        return risk_multiplier
    
    def calculate_market_condition_multiplier(self, market: Dict) -> float:
        """计算市场条件调整倍数"""
        multiplier = 1.0
        
        # 1. 时间因素
        end_date = market.get('endDate')
        if end_date:
            try:
                expiry_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                days_to_expiry = (expiry_date - datetime.now(expiry_date.tzinfo)).days
                
                # 临近到期，降低仓位
                if days_to_expiry < 7:
                    multiplier *= 0.8
                elif days_to_expiry < 30:
                    multiplier *= 0.9
            except:
                pass
        
        # 2. 市场热度
        volume = float(market.get('volume24hr', 0))
        if volume > 100000:  # 高热度市场
            multiplier *= 1.1
        elif volume < 1000:  # 低热度市场
            multiplier *= 0.9
        
        # 3. 价格稳定性
        price = self.get_market_yes_price(market)
        if 0.4 <= price <= 0.6:  # 价格稳定区间
            multiplier *= 1.05
        elif price < 0.2 or price > 0.8:  # 价格极端区间
            multiplier *= 0.95
        
        return multiplier
    
    def apply_position_limits(self, position_size: float, market: Dict, opportunity: ArbitrageOpportunity) -> float:
        """应用仓位限制 - 包括用户配置的风险限制"""
        # 1. 应用用户配置的最大交易金额限制
        position_size = min(position_size, MAX_TRADE_AMOUNT_USD)
        
        # 2. 单个市场最大仓位
        max_single_position = self.risk_controls['max_position_size']
        position_size = min(position_size, max_single_position)
        
        # 3. 基于流动性的仓位限制
        liquidity = float(market.get('liquidity', 0))
        liquidity_limit = liquidity * self.risk_controls['liquidity_requirement']
        position_size = min(position_size, liquidity_limit)
        
        # 4. 基于预期收益的仓位限制 - 应用止损百分比
        STOP_LOSS_PERCENTAGE = float(os.getenv('STOP_LOSS_PERCENTAGE', 10))
        if opportunity.expected_return < STOP_LOSS_PERCENTAGE / 100:  # 低收益且低于止损，限制仓位
            position_size *= 0.5
        elif opportunity.expected_return > 0.1:  # 高收益可以增加仓位
            position_size *= 1.2
        
        # 5. 最小仓位要求 - 但不超过用户配置的最大金额
        min_position = min(50.0, MAX_TRADE_AMOUNT_USD)  # 最小仓位不超过用户配置
        position_size = max(position_size, min_position)
        
        self.logger.info(f"应用仓位限制: ${position_size:.2f} (最大: ${MAX_TRADE_AMOUNT_USD:.2f}, 最小: ${min_position:.2f})")
        
        return position_size
    
    def log_arbitrage_opportunity(self, opportunity: ArbitrageOpportunity):
        """记录套利机会"""
        opportunity_data = {
            'timestamp': datetime.now().isoformat(),
            'type': opportunity.type,
            'action': opportunity.action,
            'expected_return': opportunity.expected_return,
            'confidence': opportunity.confidence,
            'total_probability': opportunity.total_probability,
            'markets_count': len(opportunity.markets),
            'description': opportunity.description
        }
        
        self.logger.debug(f"套利机会记录: {json.dumps(opportunity_data)}")
    
    def log_arbitrage_trade(self, opportunity: ArbitrageOpportunity):
        """记录套利交易"""
        trade_record = {
            'timestamp': datetime.now().isoformat(),
            'type': opportunity.type,
            'action': opportunity.action,
            'expected_return': opportunity.expected_return,
            'confidence': opportunity.confidence,
            'markets': [
                {
                    'id': market['id'],
                    'question': market['question'],
                    'price': self.get_market_yes_price(market),
                    'position_size': self.calculate_arbitrage_position_size(market, opportunity)
                }
                for market in opportunity.markets
            ]
        }
        
        self.logger.info(f"套利交易记录: {json.dumps(trade_record)}")

def test_arbitrage_strategy():
    """测试概率套利策略"""
    print("🧪 测试概率套利策略...")
    
    strategy = ProbabilityArbitrageStrategy(enable_trading=False)
    
    # 获取市场数据
    markets = strategy.gamma_client.get_trending_markets(limit=50)
    print(f"📊 获取到 {len(markets)} 个市场")
    
    # 更新互斥事件组
    strategy.update_mutually_exclusive_groups(markets)
    
    # 发现套利机会
    opportunities = strategy.find_arbitrage_opportunities()
    
    print(f"🎯 发现 {len(opportunities)} 个套利机会")
    
    for i, opp in enumerate(opportunities[:3], 1):
        print(f"\n{i}. {opp.description}")
        print(f"   类型: {opp.type}")
        print(f"   动作: {opp.action}")
        print(f"   预期收益: {opp.expected_return:.2%}")
        print(f"   置信度: {opp.confidence:.2f}")
        print(f"   市场数量: {len(opp.markets)}")

if __name__ == '__main__':
    test_arbitrage_strategy()
