#!/usr/bin/env python3
"""
全球舆情分析服务
整合数据采集、情绪分析、趋势追踪、预警管理的统一服务
"""

import os
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from dotenv import load_dotenv

try:
    from .sentiment.data_collectors import DataCollectorManager
    from .sentiment.analyzers import SentimentEngine, MultilingualAnalyzer
    from .sentiment.trend_tracker import TrendTracker, TrendSummary
    from .sentiment.alert_manager import SentimentAlertManager, Alert, AlertLevel
    from .sentiment.sentiment_cache import SentimentDataCache, SentimentDataStore
    from .sentiment.analyzers.sentiment_engine import AnalysisResult
except ImportError:
    # 处理相对导入问题
    from sentiment.data_collectors import DataCollectorManager
    from sentiment.analyzers import SentimentEngine, MultilingualAnalyzer
    from sentiment.trend_tracker import TrendTracker, TrendSummary
    from sentiment.alert_manager import SentimentAlertManager, Alert, AlertLevel
    from sentiment.sentiment_cache import SentimentDataCache, SentimentDataStore
    from sentiment.analyzers.sentiment_engine import AnalysisResult

load_dotenv('config/.env')


@dataclass
class SentimentReport:
    """舆情报告"""
    keyword: str
    sentiment_score: float
    sentiment_label: str
    confidence: float
    trend_direction: str
    trend_signal: str
    data_sources: Dict[str, int]
    alerts: List[Dict[str, Any]]
    trading_signal: str
    trading_confidence: float
    description: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'keyword': self.keyword,
            'sentiment_score': self.sentiment_score,
            'sentiment_label': self.sentiment_label,
            'confidence': self.confidence,
            'trend_direction': self.trend_direction,
            'trend_signal': self.trend_signal,
            'data_sources': self.data_sources,
            'alerts': self.alerts,
            'trading_signal': self.trading_signal,
            'trading_confidence': self.trading_confidence,
            'description': self.description,
            'timestamp': self.timestamp.isoformat()
        }


class GlobalSentimentService:
    """全球舆情分析服务"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # 初始化各组件
        self.collector = DataCollectorManager(self.config.get('collector', {}))
        self.analyzer = SentimentEngine(self.config.get('analyzer', {}))
        self.multilingual = MultilingualAnalyzer(self.config.get('multilingual', {}))
        self.trend_tracker = TrendTracker(self.config.get('trend', {}))
        self.alert_manager = SentimentAlertManager(self.config.get('alert', {}))
        self.cache = SentimentDataCache(self.config.get('cache', {}))
        self.store = SentimentDataStore(self.config.get('store', {}))
        
        # 监控的关键词列表
        self.monitored_keywords: List[str] = self.config.get('keywords', [])
        
        # 回调函数
        self._alert_callbacks: List = []
        
        # 注册预警回调
        self.alert_manager.register_callback(self._handle_alert)
    
    def analyze(self, keyword: str, 
                max_items: int = 50,
                time_range: Dict[str, datetime] = None,
                use_cache: bool = True) -> SentimentReport:
        """
        分析指定关键词的舆情
        
        Args:
            keyword: 关键词
            max_items: 最大采集数量
            time_range: 时间范围
            use_cache: 是否使用缓存
        
        Returns:
            SentimentReport: 舆情报告
        """
        # 检查缓存
        cache_key = self.cache.generate_key('analyze', keyword, max_items)
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        
        # 1. 采集数据
        collection_result = self.collector.collect_all(
            keywords=[keyword],
            max_items_per_source=max_items,
            time_range=time_range
        )
        
        # 2. 情绪分析
        analysis_result = self.analyzer.analyze(
            data=collection_result.data,
            keyword=keyword
        )
        
        # 3. 更新趋势
        trend_analysis = self.trend_tracker.update(
            keyword=keyword,
            sentiment_score=analysis_result.overall_sentiment.score,
            confidence=analysis_result.overall_sentiment.confidence,
            volume=len(collection_result.data)
        )
        
        # 4. 检查预警
        alerts = self.alert_manager.check(
            keyword=keyword,
            data={
                'sentiment_score': analysis_result.overall_sentiment.score,
                'signal': trend_analysis.signal.value,
                'direction': trend_analysis.direction.value,
                'volatility': trend_analysis.volatility,
                'is_anomaly': trend_analysis.is_anomaly,
                'anomaly_score': trend_analysis.anomaly_score,
                'change': trend_analysis.change
            }
        )
        
        # 5. 生成交易信号
        trading_signal, trading_confidence = self._generate_trading_signal(
            analysis_result, trend_analysis
        )
        
        # 6. 生成报告
        report = SentimentReport(
            keyword=keyword,
            sentiment_score=analysis_result.overall_sentiment.score,
            sentiment_label=analysis_result.overall_sentiment.label.value,
            confidence=analysis_result.overall_sentiment.confidence,
            trend_direction=trend_analysis.direction.value,
            trend_signal=trend_analysis.signal.value,
            data_sources=collection_result.by_source,
            alerts=[a.to_dict() for a in alerts],
            trading_signal=trading_signal,
            trading_confidence=trading_confidence,
            description=self._generate_description(analysis_result, trend_analysis)
        )
        
        # 缓存结果
        if use_cache:
            self.cache.set(cache_key, report, data_type='analysis_result')
        
        # 保存数据
        self.store.save_collection(keyword, collection_result.data)
        self.store.save_analysis(keyword, analysis_result)
        
        return report
    
    def analyze_batch(self, keywords: List[str],
                      max_items_per_keyword: int = 30) -> List[SentimentReport]:
        """批量分析多个关键词"""
        reports = []
        
        for keyword in keywords:
            try:
                report = self.analyze(keyword, max_items_per_keyword)
                reports.append(report)
            except Exception as e:
                print(f"分析 '{keyword}' 失败: {e}")
        
        return reports
    
    def get_trend_summary(self, keyword: str) -> Optional[TrendSummary]:
        """获取趋势摘要"""
        return self.trend_tracker.get_summary(keyword)
    
    def get_alerts(self, level: str = None) -> List[Alert]:
        """获取预警列表"""
        from .sentiment.alert_manager import AlertLevel
        level_enum = AlertLevel(level) if level else None
        return self.alert_manager.get_active_alerts(level_enum)
    
    def add_monitored_keyword(self, keyword: str):
        """添加监控关键词"""
        if keyword not in self.monitored_keywords:
            self.monitored_keywords.append(keyword)
    
    def remove_monitored_keyword(self, keyword: str):
        """移除监控关键词"""
        if keyword in self.monitored_keywords:
            self.monitored_keywords.remove(keyword)
    
    def register_alert_callback(self, callback):
        """注册预警回调"""
        self._alert_callbacks.append(callback)
    
    def _handle_alert(self, alert: Alert):
        """处理预警"""
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                print(f"预警回调执行失败: {e}")
    
    def _generate_trading_signal(self, analysis: AnalysisResult, trend) -> tuple:
        """生成交易信号"""
        sentiment_score = analysis.overall_sentiment.score
        confidence = analysis.overall_sentiment.confidence
        
        # 基于情绪分数和趋势
        if sentiment_score > 0.3 and trend.direction.value in ['up', 'strong_up']:
            signal = 'BUY_YES'
            trading_confidence = min(0.9, confidence * 1.2)
        elif sentiment_score < -0.3 and trend.direction.value in ['down', 'strong_down']:
            signal = 'BUY_NO'
            trading_confidence = min(0.9, confidence * 1.2)
        elif sentiment_score > 0.5:
            signal = 'BUY_YES'
            trading_confidence = confidence * 0.8
        elif sentiment_score < -0.5:
            signal = 'BUY_NO'
            trading_confidence = confidence * 0.8
        else:
            signal = 'HOLD'
            trading_confidence = confidence * 0.5
        
        return signal, trading_confidence
    
    def _generate_description(self, analysis: AnalysisResult, trend) -> str:
        """生成描述"""
        return self.analyzer.get_sentiment_description(analysis)
    
    def get_service_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        return {
            'collectors': self.collector.get_stats(),
            'cache': self.cache.get_stats(),
            'alerts': self.alert_manager.get_alert_stats(),
            'data_store': self.store.get_data_summary(),
            'monitored_keywords': self.monitored_keywords,
            'timestamp': datetime.now().isoformat()
        }
    
    def health_check(self) -> Dict[str, bool]:
        """健康检查"""
        return {
            'collectors': len(self.collector.get_available_sources()) > 0,
            'analyzer': True,
            'trend_tracker': True,
            'alert_manager': True,
            'cache': True,
            'store': os.path.exists(self.store.data_dir)
        }


# 便捷函数：创建服务实例
def create_sentiment_service(keywords: List[str] = None,
                             config: Dict[str, Any] = None) -> GlobalSentimentService:
    """
    创建舆情分析服务
    
    Args:
        keywords: 监控的关键词列表
        config: 配置字典
    
    Returns:
        GlobalSentimentService 实例
    """
    full_config = config or {}
    if keywords:
        full_config['keywords'] = keywords
    
    return GlobalSentimentService(full_config)


# 用于交易系统集成的简化接口
class SentimentSignalProvider:
    """舆情信号提供者 - 用于交易系统集成"""
    
    def __init__(self, service: GlobalSentimentService = None):
        self.service = service or GlobalSentimentService()
    
    def get_signal(self, keyword: str) -> Dict[str, Any]:
        """
        获取交易信号
        
        Returns:
            {
                'signal': 'BUY_YES' | 'BUY_NO' | 'HOLD',
                'confidence': 0.0 - 1.0,
                'sentiment_score': -1.0 - 1.0,
                'trend_direction': str,
                'alerts_count': int
            }
        """
        report = self.service.analyze(keyword)
        
        return {
            'signal': report.trading_signal,
            'confidence': report.trading_confidence,
            'sentiment_score': report.sentiment_score,
            'trend_direction': report.trend_direction,
            'trend_signal': report.trend_signal,
            'alerts_count': len(report.alerts),
            'timestamp': report.timestamp.isoformat()
        }
    
    def get_signals_batch(self, keywords: List[str]) -> Dict[str, Dict]:
        """批量获取信号"""
        signals = {}
        for keyword in keywords:
            signals[keyword] = self.get_signal(keyword)
        return signals
    
    def should_trade(self, keyword: str, 
                     min_confidence: float = 0.3) -> tuple:
        """
        判断是否应该交易
        
        Returns:
            (should_trade: bool, signal: str, confidence: float)
        """
        signal_data = self.get_signal(keyword)
        
        should_trade = (
            signal_data['signal'] != 'HOLD' and
            signal_data['confidence'] >= min_confidence
        )
        
        return should_trade, signal_data['signal'], signal_data['confidence']
