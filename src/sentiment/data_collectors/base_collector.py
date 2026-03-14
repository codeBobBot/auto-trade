#!/usr/bin/env python3
"""
基础数据采集器
定义数据采集的统一接口和数据结构
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class DataSource(Enum):
    """数据来源类型"""
    NEWS = "news"
    TWITTER = "twitter"
    REDDIT = "reddit"
    TELEGRAM = "telegram"
    WEB = "web"


@dataclass
class CollectedData:
    """采集的数据结构"""
    source: DataSource
    title: str
    content: str
    url: str
    timestamp: datetime
    author: Optional[str] = None
    language: str = "en"
    metadata: Dict[str, Any] = field(default_factory=dict)
    # 社交媒体特有字段
    likes: int = 0
    shares: int = 0
    comments: int = 0
    followers: int = 0  # 作者粉丝数
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'source': self.source.value,
            'title': self.title,
            'content': self.content,
            'url': self.url,
            'timestamp': self.timestamp.isoformat(),
            'author': self.author,
            'language': self.language,
            'metadata': self.metadata,
            'likes': self.likes,
            'shares': self.shares,
            'comments': self.comments,
            'followers': self.followers
        }


@dataclass
class CollectionResult:
    """采集结果"""
    success: bool
    data: List[CollectedData] = field(default_factory=list)
    error: Optional[str] = None
    total_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __len__(self) -> int:
        return len(self.data)


class BaseCollector(ABC):
    """基础采集器抽象类"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.source_type: DataSource = DataSource.WEB
        self.is_initialized = False
        self.last_collection_time: Optional[datetime] = None
        self.collection_count = 0
        self.error_count = 0
    
    @abstractmethod
    def collect(self, keywords: List[str], max_items: int = 50, 
                time_range: Dict[str, datetime] = None) -> CollectionResult:
        """
        采集数据
        
        Args:
            keywords: 关键词列表
            max_items: 最大采集数量
            time_range: 时间范围 {'start': datetime, 'end': datetime}
        
        Returns:
            CollectionResult: 采集结果
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """检查采集器健康状态"""
        pass
    
    def get_source_type(self) -> DataSource:
        """获取数据源类型"""
        return self.source_type
    
    def get_stats(self) -> Dict[str, Any]:
        """获取采集器统计信息"""
        return {
            'source': self.source_type.value,
            'is_initialized': self.is_initialized,
            'last_collection_time': self.last_collection_time.isoformat() if self.last_collection_time else None,
            'total_collections': self.collection_count,
            'total_errors': self.error_count,
            'success_rate': (self.collection_count - self.error_count) / max(1, self.collection_count)
        }
    
    def _calculate_engagement_score(self, data: CollectedData) -> float:
        """
        计算互动分数
        
        综合考虑点赞、分享、评论、粉丝数
        """
        # 基础互动分
        engagement = data.likes + data.shares * 2 + data.comments * 3
        
        # 考虑作者影响力
        if data.followers > 0:
            influence_factor = min(2.0, 1 + data.followers / 10000)
            engagement *= influence_factor
        
        return engagement
    
    def _filter_by_time_range(self, data: List[CollectedData], 
                               time_range: Dict[str, datetime]) -> List[CollectedData]:
        """按时间范围过滤数据"""
        if not time_range:
            return data
        
        start = time_range.get('start')
        end = time_range.get('end')
        
        filtered = []
        for item in data:
            if start and item.timestamp < start:
                continue
            if end and item.timestamp > end:
                continue
            filtered.append(item)
        
        return filtered
