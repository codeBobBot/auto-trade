#!/usr/bin/env python3
"""
全球舆情模块
为自动化交易提供多源舆情数据支持
"""

from .data_collectors import (
    BaseCollector,
    NewsCollector,
    TwitterCollector,
    RedditCollector,
    DataCollectorManager
)
from .analyzers import (
    SentimentEngine,
    MultilingualAnalyzer
)
from .trend_tracker import TrendTracker
from .alert_manager import SentimentAlertManager
from .sentiment_cache import SentimentDataCache

__all__ = [
    'BaseCollector',
    'NewsCollector', 
    'TwitterCollector',
    'RedditCollector',
    'DataCollectorManager',
    'SentimentEngine',
    'MultilingualAnalyzer',
    'TrendTracker',
    'SentimentAlertManager',
    'SentimentDataCache'
]
