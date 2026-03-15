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
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from gamma_client import PolymarketGammaClient
from clob_client_auto_creds import ClobTradingClientAutoCreds
from logger_config import get_strategy_logger

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
                'exclusion_patterns': ['republican', 'democrat', 'house', 'senate'],
                'markets': [],
                'description': '2024选举党派控制',
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
            
            # 体育比赛 - 按赛事分组
            'sports_nba': {
                'keywords': ['nba', 'basketball', 'game', 'match'],
                'exclusion_patterns': ['win', 'lose', 'cover', 'spread'],
                'markets': [],
                'description': 'NBA比赛结果',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'sports_nfl': {
                'keywords': ['nfl', 'football', 'super bowl', 'playoffs'],
                'exclusion_patterns': ['win', 'lose', 'cover', 'spread'],
                'markets': [],
                'description': 'NFL比赛结果',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            
            # 加密货币价格 - 按价格区间分组
            'crypto_btc_levels': {
                'keywords': ['bitcoin', 'BTC', 'price', 'reach'],
                'exclusion_patterns': ['100k', '150k', '200k', '50k', '25k'],
                'markets': [],
                'description': '比特币价格水平',
                'mutual_exclusive': False,  # 不是完全互斥
                'expected_total_probability': 0.8  # 考虑其他可能性
            },
            
            # 经济数据 - 按数据类型分组
            'economic_inflation': {
                'keywords': ['inflation', 'CPI', 'price index', 'year over year'],
                'exclusion_patterns': ['above', 'below', 'higher', 'lower'],
                'markets': [],
                'description': '通胀数据预测',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            },
            'economic_employment': {
                'keywords': ['employment', 'jobs', 'unemployment', 'payroll'],
                'exclusion_patterns': ['above', 'below', 'higher', 'lower'],
                'markets': [],
                'description': '就业数据预测',
                'mutual_exclusive': True,
                'expected_total_probability': 1.0
            }
        }
        
        # 优化套利阈值
        self.arbitrage_thresholds = {
            'high_probability': 1.01,  # 概率总和超过2%（更敏感）
            'low_probability': 0.99,   # 概率总和低于2%（更敏感）
            'min_return': 0.005,       # 最小预期收益0.5%（降低门槛）
            'min_liquidity': 10000,     # 最小流动性10000 USDC（降低门槛）
            'max_price_deviation': 0.7, # 最大价格偏差70%
            'min_markets_count': 2,    # 最小市场数量
            'max_markets_count': 15,   # 最大市场数量
            'probability_confidence': 0.5 # 概率置信度阈值（降低）
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
                        self.notification_service.info(
                            "套利详情", 
                            f"类型: {opportunity.type}\n"
                            f"预期收益: {opportunity.expected_return:.2%}\n"
                            f"置信度: {opportunity.confidence:.2f}\n"
                            f"动作: {opportunity.action}"
                        )
                    
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
        """智能更新互斥事件组"""
        # 清空现有市场
        for group in self.mutually_exclusive_groups.values():
            group['markets'] = []
        
        # 智能分类市场
        for market in markets:
            question = market.get('question', '').lower()
            
            # 计算市场质量分数
            market_quality = self.calculate_market_quality(market)
            if market_quality < 0.1:  # 降低质量门槛
                continue
            
            # 智能匹配到最合适的组
            best_group = self.find_best_matching_group(question, market)
            if best_group:
                self.mutually_exclusive_groups[best_group]['markets'].append(market)
        
        # 验证互斥性
        self.validate_mutual_exclusivity()
    
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
        """找到最佳匹配的组"""
        best_group = None
        best_score = 0.0
        
        for group_name, group_info in self.mutually_exclusive_groups.items():
            score = 0.0
            
            # 关键词匹配分数 (60%)
            keyword_matches = sum(1 for kw in group_info['keywords'] if kw in question)
            keyword_score = (keyword_matches / len(group_info['keywords'])) * 0.6
            
            # 排除模式匹配分数 (40%)
            exclusion_matches = sum(1 for pattern in group_info['exclusion_patterns'] if pattern in question)
            exclusion_score = (exclusion_matches / len(group_info['exclusion_patterns'])) * 0.4
            
            total_score = keyword_score + exclusion_score
            
            if total_score > best_score and total_score > 0.1:  # 降低匹配阈值
                best_score = total_score
                best_group = group_name
        
        return best_group
    
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
        """检查两个市场是否重叠"""
        # 简单的重叠检查
        words1 = set(question1.split())
        words2 = set(question2.split())
        
        # 如果重叠度超过50%，认为不互斥
        overlap = len(words1 & words2) / len(words1 | words2)
        return overlap > 0.5
    
    def find_arbitrage_opportunities(self) -> List[ArbitrageOpportunity]:
        """发现套利机会"""
        opportunities = []
        
        self.logger.debug(f"检查 {len(self.mutually_exclusive_groups)} 个互斥事件组")
        
        for group_name, group_info in self.mutually_exclusive_groups.items():
            markets = group_info['markets']
            
            self.logger.debug(f"组 {group_name}: {len(markets)} 个市场")
            
            if len(markets) < 2:
                self.logger.warning(f"市场数量不足，跳过组 {group_name}")
                continue  # 至少需要2个市场才能形成套利
            
            # 计算概率总和
            total_probability = self.calculate_total_probability(markets)
            self.logger.debug(f"概率总和: {total_probability:.3f}")
            
            # 发现概率套利
            prob_arbitrage = self.find_probability_arbitrage(markets, total_probability, group_info)
            if prob_arbitrage:
                opportunities.append(prob_arbitrage)
                self.logger.info(f"发现套利机会: {prob_arbitrage.description}")
            else:
                self.logger.debug("未发现套利机会")
            
            # 发现跨市场套利
            cross_arbitrage = self.find_cross_market_arbitrage(markets, group_info)
            if cross_arbitrage:
                opportunities.append(cross_arbitrage)
        
        # 按预期收益排序
        opportunities.sort(key=lambda x: x.expected_return, reverse=True)
        
        return opportunities
    
    def calculate_total_probability(self, markets: List[Dict]) -> float:
        """精确计算概率总和"""
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
        """发现跨市场套利机会"""
        if len(markets) < 2:
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
        prices.sort(key=lambda x: x['price'])
        
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
    
    def execute_buy_order(self, market: Dict, opportunity: ArbitrageOpportunity):
        """执行买入订单"""
        position_size = self.calculate_arbitrage_position_size(market, opportunity)
        
        try:
            order_id = self.trading_client.create_order(
                market_id=market['id'],
                price=self.get_market_yes_price(market),
                size=position_size,
                side='buy'
            )
            self.logger.info(f"买入订单: {order_id} - {market['question'][:30]}...")
            
        except Exception as e:
            self.logger.error(f"买入失败: {e}")
    
    def execute_sell_order(self, market: Dict, opportunity: ArbitrageOpportunity):
        """执行卖出订单"""
        position_size = self.calculate_arbitrage_position_size(market, opportunity)
        
        try:
            order_id = self.trading_client.create_order(
                market_id=market['id'],
                price=self.get_market_yes_price(market),
                size=position_size,
                side='sell'
            )
            self.logger.info(f"卖出订单: {order_id} - {market['question'][:30]}...")
            
        except Exception as e:
            self.logger.error(f"卖出失败: {e}")
    
    def calculate_arbitrage_position_size(self, market: Dict, opportunity: ArbitrageOpportunity) -> float:
        """动态计算套利仓位大小"""
        # 1. 基础仓位计算
        base_size = 200.0  # USDC
        
        # 2. 置信度调整 (30%)
        confidence_multiplier = opportunity.confidence
        
        # 3. 预期收益调整 (25%)
        return_multiplier = min(opportunity.expected_return * 8, 2.0)
        
        # 4. 流动性调整 (20%)
        liquidity = float(market.get('liquidity', 5000))
        liquidity_multiplier = min(liquidity / 15000, 1.5)
        
        # 5. 市场质量调整 (15%)
        quality_score = self.calculate_market_quality(market)
        quality_multiplier = 0.5 + quality_score * 0.5
        
        # 6. 风险调整 (10%)
        risk_multiplier = self.calculate_risk_multiplier(market, opportunity)
        
        # 7. 动态市场条件调整
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
        
        # 8. 风险限制
        position_size = self.apply_position_limits(position_size, market, opportunity)
        
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
                from datetime import datetime
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
        """应用仓位限制"""
        # 1. 单个市场最大仓位
        max_single_position = self.risk_controls['max_position_size']
        position_size = min(position_size, max_single_position)
        
        # 2. 基于流动性的仓位限制
        liquidity = float(market.get('liquidity', 0))
        liquidity_limit = liquidity * self.risk_controls['liquidity_requirement']
        position_size = min(position_size, liquidity_limit)
        
        # 3. 基于预期收益的仓位限制
        if opportunity.expected_return < 0.02:  # 低收益限制仓位
            position_size *= 0.7
        elif opportunity.expected_return > 0.1:  # 高收益可以增加仓位
            position_size *= 1.2
        
        # 4. 最小仓位要求
        min_position = 50.0  # 最小50 USDC
        position_size = max(position_size, min_position)
        
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
