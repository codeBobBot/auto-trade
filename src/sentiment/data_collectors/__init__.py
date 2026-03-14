#!/usr/bin/env python3
"""
数据采集器模块
"""

from .base_collector import BaseCollector, CollectedData
from .news_collector import NewsCollector
from .twitter_collector import TwitterCollector
from .reddit_collector import RedditCollector
from .manager import DataCollectorManager

__all__ = [
    'BaseCollector',
    'CollectedData',
    'NewsCollector',
    'TwitterCollector', 
    'RedditCollector',
    'DataCollectorManager'
]
