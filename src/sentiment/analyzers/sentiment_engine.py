#!/usr/bin/env python3
"""
情绪分析引擎
综合多源数据的情绪分析，支持多种分析方法
"""

import os
import re
import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum
from dotenv import load_dotenv

from ..data_collectors.base_collector import CollectedData, DataSource

load_dotenv('config/.env')


class SentimentLabel(Enum):
    """情绪标签"""
    VERY_BEARISH = "very_bearish"      # 极度悲观 -1.0 ~ -0.6
    BEARISH = "bearish"                 # 悲观 -0.6 ~ -0.2
    NEUTRAL = "neutral"                 # 中性 -0.2 ~ 0.2
    BULLISH = "bullish"                 # 乐观 0.2 ~ 0.6
    VERY_BULLISH = "very_bullish"       # 极度乐观 0.6 ~ 1.0


class SentimentIntensity(Enum):
    """情绪强度"""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


@dataclass
class SentimentScore:
    """情绪分数"""
    score: float  # -1 到 1
    label: SentimentLabel
    intensity: SentimentIntensity
    confidence: float  # 0 到 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'score': self.score,
            'label': self.label.value,
            'intensity': self.intensity.value,
            'confidence': self.confidence
        }


@dataclass
class AnalysisResult:
    """分析结果"""
    keyword: str
    overall_sentiment: SentimentScore
    by_source: Dict[str, SentimentScore]
    by_time: Dict[str, SentimentScore]  # 按时间段分解
    trending_keywords: List[str]
    total_items: int
    time_range: Dict[str, datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'keyword': self.keyword,
            'overall_sentiment': self.overall_sentiment.to_dict(),
            'by_source': {k: v.to_dict() for k, v in self.by_source.items()},
            'by_time': {k: v.to_dict() for k, v in self.by_time.items()},
            'trending_keywords': self.trending_keywords,
            'total_items': self.total_items,
            'time_range': {
                'start': self.time_range['start'].isoformat(),
                'end': self.time_range['end'].isoformat()
            },
            'timestamp': self.timestamp.isoformat()
        }


class SentimentEngine:
    """情绪分析引擎"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # 情绪词汇库
        self.lexicon = self._load_lexicon()
        
        # 否定词
        self.negators = {
            'en': ['not', 'no', 'never', 'neither', 'nobody', 'nothing', "don't", "doesn't", "didn't", "won't", "wouldn't"],
            'zh': ['不', '没', '无', '非', '未', '莫', '别']
        }
        
        # 强化词
        self.intensifiers = {
            'en': ['very', 'extremely', 'highly', 'incredibly', 'absolutely', 'totally', 'completely'],
            'zh': ['非常', '极其', '特别', '相当', '十分', '格外']
        }
        
        # 来源权重
        self.source_weights = {
            DataSource.NEWS: 1.0,
            DataSource.TWITTER: 0.7,
            DataSource.REDDIT: 0.6,
            DataSource.WEB: 0.5
        }
        
        # 时间衰减参数
        self.time_decay_hours = self.config.get('time_decay_hours', 24)
        
        # 情绪强度阈值
        self.intensity_thresholds = {
            'weak': 0.3,
            'moderate': 0.6,
            'strong': 0.8
        }
    
    def analyze(self, data: List[CollectedData], keyword: str = "") -> AnalysisResult:
        """
        分析数据情绪
        
        Args:
            data: 采集的数据列表
            keyword: 分析关键词
        
        Returns:
            AnalysisResult: 分析结果
        """
        if not data:
            return self._empty_result(keyword)
        
        # 计算时间范围
        timestamps = [d.timestamp for d in data]
        time_range = {
            'start': min(timestamps),
            'end': max(timestamps)
        }
        
        # 分析每条数据的情绪
        scored_data = []
        for item in data:
            score = self._analyze_single(item)
            scored_data.append((item, score))
        
        # 计算综合情绪
        overall = self._calculate_overall_sentiment(scored_data)
        
        # 按来源分解
        by_source = self._analyze_by_source(scored_data)
        
        # 按时间分解
        by_time = self._analyze_by_time(scored_data)
        
        # 提取趋势关键词
        trending = self._extract_trending_keywords(data)
        
        return AnalysisResult(
            keyword=keyword,
            overall_sentiment=overall,
            by_source=by_source,
            by_time=by_time,
            trending_keywords=trending,
            total_items=len(data),
            time_range=time_range,
            metadata={
                'analysis_method': 'lexicon_weighted',
                'sources_analyzed': list(set(d.source.value for d in data))
            }
        )
    
    def analyze_single(self, text: str, language: str = 'en') -> SentimentScore:
        """
        分析单条文本的情绪
        
        Args:
            text: 文本内容
            language: 语言代码
        
        Returns:
            SentimentScore: 情绪分数
        """
        return self._analyze_text(text, language)
    
    def _analyze_single(self, data: CollectedData) -> SentimentScore:
        """分析单条数据"""
        text = f"{data.title} {data.content}".strip()
        return self._analyze_text(text, data.language)
    
    def _analyze_text(self, text: str, language: str = 'en') -> SentimentScore:
        """分析文本情绪"""
        text_lower = text.lower()
        
        # 获取词汇库
        positive_words = self.lexicon.get('positive', {}).get(language, [])
        negative_words = self.lexicon.get('negative', {}).get(language, [])
        
        # 计算情绪词出现次数
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        # 处理否定词
        negators = self.negators.get(language, [])
        has_negator = any(neg in text_lower for neg in negators)
        if has_negator:
            positive_count, negative_count = negative_count, positive_count
        
        # 处理强化词
        intensifiers = self.intensifiers.get(language, [])
        intensity_factor = 1.0
        for intensifier in intensifiers:
            if intensifier in text_lower:
                intensity_factor *= 1.3
        
        # 计算情绪分数
        total = positive_count + negative_count
        if total == 0:
            score = 0.0
            confidence = 0.0
        else:
            score = (positive_count - negative_count) / total
            score = max(-1.0, min(1.0, score * intensity_factor))
            confidence = min(1.0, total / 10)  # 10个情绪词为满分
        
        # 确定标签和强度
        label = self._score_to_label(score)
        intensity = self._score_to_intensity(abs(score), confidence)
        
        return SentimentScore(
            score=score,
            label=label,
            intensity=intensity,
            confidence=confidence
        )
    
    def _calculate_overall_sentiment(self, scored_data: List[Tuple[CollectedData, SentimentScore]]) -> SentimentScore:
        """计算综合情绪分数"""
        if not scored_data:
            return SentimentScore(
                score=0.0,
                label=SentimentLabel.NEUTRAL,
                intensity=SentimentIntensity.WEAK,
                confidence=0.0
            )
        
        weighted_sum = 0.0
        total_weight = 0.0
        confidences = []
        
        now = datetime.now()
        
        for data, score in scored_data:
            # 来源权重
            source_weight = self.source_weights.get(data.source, 0.5)
            
            # 时间衰减权重
            hours_old = (now - data.timestamp).total_seconds() / 3600
            time_weight = 0.5 ** (hours_old / self.time_decay_hours)
            
            # 互动权重
            engagement = data.likes + data.shares * 2 + data.comments * 3
            engagement_weight = min(2.0, 1 + engagement / 500)
            
            # 综合权重
            weight = source_weight * time_weight * engagement_weight * score.confidence
            
            weighted_sum += score.score * weight
            total_weight += weight
            confidences.append(score.confidence)
        
        if total_weight == 0:
            final_score = 0.0
        else:
            final_score = weighted_sum / total_weight
        
        # 综合置信度
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        label = self._score_to_label(final_score)
        intensity = self._score_to_intensity(abs(final_score), avg_confidence)
        
        return SentimentScore(
            score=final_score,
            label=label,
            intensity=intensity,
            confidence=avg_confidence
        )
    
    def _analyze_by_source(self, scored_data: List[Tuple[CollectedData, SentimentScore]]) -> Dict[str, SentimentScore]:
        """按来源分析情绪"""
        source_data = defaultdict(list)
        
        for data, score in scored_data:
            source_data[data.source.value].append((data, score))
        
        result = {}
        for source, items in source_data.items():
            result[source] = self._calculate_overall_sentiment(items)
        
        return result
    
    def _analyze_by_time(self, scored_data: List[Tuple[CollectedData, SentimentScore]]) -> Dict[str, SentimentScore]:
        """按时间段分析情绪"""
        time_data = defaultdict(list)
        
        now = datetime.now()
        
        for data, score in scored_data:
            hours_old = (now - data.timestamp).total_seconds() / 3600
            
            if hours_old <= 1:
                period = '1h'
            elif hours_old <= 6:
                period = '6h'
            elif hours_old <= 12:
                period = '12h'
            elif hours_old <= 24:
                period = '24h'
            else:
                period = 'older'
            
            time_data[period].append((data, score))
        
        result = {}
        for period, items in time_data.items():
            result[period] = self._calculate_overall_sentiment(items)
        
        return result
    
    def _extract_trending_keywords(self, data: List[CollectedData]) -> List[str]:
        """提取趋势关键词"""
        # 简化版本：提取高频词
        word_freq = defaultdict(int)
        
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 
                      'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                      'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                      'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                      'as', 'into', 'through', 'during', 'before', 'after',
                      'above', 'below', 'between', 'under', 'again', 'further',
                      'then', 'once', 'here', 'there', 'when', 'where', 'why',
                      'how', 'all', 'each', 'few', 'more', 'most', 'other',
                      'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same',
                      'so', 'than', 'too', 'very', 'just', 'and', 'but', 'if',
                      'or', 'because', 'until', 'while', 'this', 'that', 'these',
                      'those', 'it', 'its', 'they', 'them', 'their', 'we', 'our',
                      'you', 'your', 'he', 'she', 'his', 'her'}
        
        for item in data:
            text = f"{item.title} {item.content}".lower()
            # 提取单词
            words = re.findall(r'\b[a-z]{3,}\b', text)
            
            for word in words:
                if word not in stop_words:
                    word_freq[word] += 1
        
        # 返回高频词
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:10]]
    
    def _score_to_label(self, score: float) -> SentimentLabel:
        """分数转标签"""
        if score <= -0.6:
            return SentimentLabel.VERY_BEARISH
        elif score <= -0.2:
            return SentimentLabel.BEARISH
        elif score <= 0.2:
            return SentimentLabel.NEUTRAL
        elif score <= 0.6:
            return SentimentLabel.BULLISH
        else:
            return SentimentLabel.VERY_BULLISH
    
    def _score_to_intensity(self, abs_score: float, confidence: float) -> SentimentIntensity:
        """分数转强度"""
        combined = (abs_score + confidence) / 2
        
        if combined >= self.intensity_thresholds['strong']:
            return SentimentIntensity.STRONG
        elif combined >= self.intensity_thresholds['moderate']:
            return SentimentIntensity.MODERATE
        else:
            return SentimentIntensity.WEAK
    
    def _empty_result(self, keyword: str) -> AnalysisResult:
        """返回空结果"""
        now = datetime.now()
        return AnalysisResult(
            keyword=keyword,
            overall_sentiment=SentimentScore(
                score=0.0,
                label=SentimentLabel.NEUTRAL,
                intensity=SentimentIntensity.WEAK,
                confidence=0.0
            ),
            by_source={},
            by_time={},
            trending_keywords=[],
            total_items=0,
            time_range={'start': now, 'end': now}
        )
    
    def _load_lexicon(self) -> Dict[str, Dict[str, List[str]]]:
        """加载情绪词汇库"""
        # 英文词汇
        en_positive = [
            'good', 'great', 'excellent', 'positive', 'success', 'win', 'gain',
            'profit', 'growth', 'increase', 'rise', 'boost', 'improve', 'better',
            'strong', 'bullish', 'optimistic', 'confident', 'hope', 'promising',
            'up', 'high', 'surge', 'rally', 'breakthrough', 'achieve', 'advance',
            'beat', 'exceed', 'outperform', 'upgrade', 'buy', 'long', 'support',
            'recovery', 'expansion', 'boom', 'thrive', 'prosper', 'soar', 'jump',
            'skyrocket', 'outstanding', 'remarkable', 'exceptional', 'solid'
        ]
        
        en_negative = [
            'bad', 'terrible', 'negative', 'fail', 'failure', 'loss', 'decrease',
            'fall', 'drop', 'decline', 'weak', 'bearish', 'pessimistic', 'crisis',
            'risk', 'threat', 'danger', 'concern', 'worry', 'problem', 'issue',
            'down', 'low', 'crash', 'plunge', 'collapse', 'recession', 'contraction',
            'miss', 'underperform', 'downgrade', 'sell', 'short', 'resistance',
            'uncertainty', 'volatility', 'turmoil', 'struggle', 'slump', 'tumble',
            'disappointing', 'worst', 'dismal', 'grim', 'bleak', 'severe'
        ]
        
        # 中文词汇
        zh_positive = [
            '好', '优秀', '成功', '赢', '增长', '上涨', '提升', '改善',
            '强劲', '乐观', '信心', '希望', '突破', '上涨', '牛市',
            '利好', '增长', '繁荣', '发展', '进步', '收益', '盈利',
            '反弹', '回升', '走强', '看涨', '买入', '增持', '推荐'
        ]
        
        zh_negative = [
            '坏', '差', '失败', '亏损', '下跌', '下降', '疲软', '悲观',
            '危机', '风险', '威胁', '担忧', '问题', '熊市', '利空',
            '衰退', '萎缩', '暴跌', '崩盘', '动荡', '不确定', '下滑',
            '走弱', '看跌', '卖出', '减持', '警告', '恶化', '亏损'
        ]
        
        return {
            'positive': {
                'en': en_positive,
                'zh': zh_positive
            },
            'negative': {
                'en': en_negative,
                'zh': zh_negative
            }
        }
    
    def get_sentiment_description(self, result: AnalysisResult) -> str:
        """生成情绪分析描述"""
        overall = result.overall_sentiment
        
        # 基础描述
        label_desc = {
            SentimentLabel.VERY_BULLISH: "极度乐观",
            SentimentLabel.BULLISH: "乐观",
            SentimentLabel.NEUTRAL: "中性",
            SentimentLabel.BEARISH: "悲观",
            SentimentLabel.VERY_BEARISH: "极度悲观"
        }
        
        intensity_desc = {
            SentimentIntensity.STRONG: "强烈",
            SentimentIntensity.MODERATE: "中等",
            SentimentIntensity.WEAK: "微弱"
        }
        
        desc = f"舆情整体{label_desc[overall.label]}（分数: {overall.score:+.2f}），"
        desc += f"强度{intensity_desc[overall.intensity]}，"
        desc += f"置信度{overall.confidence:.1%}。"
        
        # 来源分解
        if result.by_source:
            source_parts = []
            for source, score in result.by_source.items():
                source_parts.append(f"{source}:{score.score:+.2f}")
            desc += f"各来源情绪: {', '.join(source_parts)}。"
        
        # 时间趋势
        if result.by_time:
            time_parts = []
            for period in ['1h', '6h', '12h', '24h']:
                if period in result.by_time:
                    score = result.by_time[period]
                    time_parts.append(f"{period}:{score.score:+.2f}")
            if time_parts:
                desc += f"时间趋势: {', '.join(time_parts)}。"
        
        return desc
