#!/usr/bin/env python3
"""
数据采集管理器
统一管理多源数据采集，提供聚合接口
"""

import os
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

from .base_collector import BaseCollector, CollectedData, CollectionResult, DataSource
from .news_collector import NewsCollector
from .twitter_collector import TwitterCollector
from .reddit_collector import RedditCollector

load_dotenv('config/.env')


@dataclass
class AggregatedResult:
    """聚合采集结果"""
    total_items: int
    by_source: Dict[str, int]
    data: List[CollectedData]
    collection_time: float  # 采集耗时（秒）
    errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def get_top_items(self, n: int = 10) -> List[CollectedData]:
        """获取互动量最高的 N 条数据"""
        sorted_data = sorted(
            self.data,
            key=lambda x: (x.likes + x.shares * 2 + x.comments * 3),
            reverse=True
        )
        return sorted_data[:n]
    
    def filter_by_source(self, source: DataSource) -> List[CollectedData]:
        """按来源过滤"""
        return [d for d in self.data if d.source == source]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'total_items': self.total_items,
            'by_source': self.by_source,
            'collection_time': self.collection_time,
            'errors': self.errors,
            'timestamp': self.timestamp.isoformat(),
            'items': [d.to_dict() for d in self.data]
        }


class DataCollectorManager:
    """数据采集管理器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # 初始化各采集器
        self.collectors: Dict[DataSource, BaseCollector] = {}
        
        # 启用的数据源
        self.enabled_sources = self.config.get('enabled_sources', [
            DataSource.NEWS,
            DataSource.TWITTER,
            DataSource.REDDIT
        ])
        
        # 采集配置
        self.max_workers = self.config.get('max_workers', 3)
        self.default_max_items = self.config.get('default_max_items', 50)
        
        # 初始化采集器
        self._init_collectors()
    
    def _init_collectors(self):
        """初始化采集器"""
        if DataSource.NEWS in self.enabled_sources:
            self.collectors[DataSource.NEWS] = NewsCollector(
                self.config.get('news', {})
            )
        
        if DataSource.TWITTER in self.enabled_sources:
            self.collectors[DataSource.TWITTER] = TwitterCollector(
                self.config.get('twitter', {})
            )
        
        if DataSource.REDDIT in self.enabled_sources:
            self.collectors[DataSource.REDDIT] = RedditCollector(
                self.config.get('reddit', {})
            )
    
    def collect_all(self, keywords: List[str], 
                    max_items_per_source: int = None,
                    time_range: Dict[str, datetime] = None,
                    parallel: bool = True) -> AggregatedResult:
        """
        从所有启用的数据源采集数据
        
        Args:
            keywords: 关键词列表
            max_items_per_source: 每个来源最大采集数
            time_range: 时间范围
            parallel: 是否并行采集
        
        Returns:
            AggregatedResult: 聚合结果
        """
        max_items = max_items_per_source or self.default_max_items
        start_time = datetime.now()
        
        all_data = []
        by_source = {}
        errors = []
        
        if parallel:
            # 并行采集
            all_data, by_source, errors = self._collect_parallel(
                keywords, max_items, time_range
            )
        else:
            # 串行采集
            all_data, by_source, errors = self._collect_sequential(
                keywords, max_items, time_range
            )
        
        # 合并后处理
        all_data = self._deduplicate(all_data)
        all_data = self._sort_by_relevance(all_data)
        
        collection_time = (datetime.now() - start_time).total_seconds()
        
        return AggregatedResult(
            total_items=len(all_data),
            by_source=by_source,
            data=all_data,
            collection_time=collection_time,
            errors=errors
        )
    
    def _collect_parallel(self, keywords: List[str], max_items: int,
                          time_range: Dict[str, datetime]) -> tuple:
        """并行采集"""
        all_data = []
        by_source = {}
        errors = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            
            for source_type, collector in self.collectors.items():
                if not collector.is_initialized:
                    continue
                future = executor.submit(
                    collector.collect,
                    keywords,
                    max_items,
                    time_range
                )
                futures[future] = source_type
            
            for future in as_completed(futures):
                source_type = futures[future]
                try:
                    result = future.result()
                    if result.success:
                        all_data.extend(result.data)
                        by_source[source_type.value] = len(result.data)
                    elif result.error:
                        errors.append(f"{source_type.value}: {result.error}")
                except Exception as e:
                    errors.append(f"{source_type.value}: {str(e)}")
        
        return all_data, by_source, errors
    
    def _collect_sequential(self, keywords: List[str], max_items: int,
                            time_range: Dict[str, datetime]) -> tuple:
        """串行采集"""
        all_data = []
        by_source = {}
        errors = []
        
        for source_type, collector in self.collectors.items():
            if not collector.is_initialized:
                continue
            
            try:
                result = collector.collect(keywords, max_items, time_range)
                if result.success:
                    all_data.extend(result.data)
                    by_source[source_type.value] = len(result.data)
                elif result.error:
                    errors.append(f"{source_type.value}: {result.error}")
            except Exception as e:
                errors.append(f"{source_type.value}: {str(e)}")
        
        return all_data, by_source, errors
    
    def collect_from_source(self, source: DataSource, keywords: List[str],
                            max_items: int = 50,
                            time_range: Dict[str, datetime] = None) -> CollectionResult:
        """从指定来源采集"""
        if source not in self.collectors:
            return CollectionResult(
                success=False,
                error=f"数据源 {source.value} 未启用或未配置"
            )
        
        collector = self.collectors[source]
        return collector.collect(keywords, max_items, time_range)
    
    def get_available_sources(self) -> List[DataSource]:
        """获取可用的数据源"""
        return [
            source for source, collector in self.collectors.items()
            if collector.is_initialized
        ]
    
    def health_check_all(self) -> Dict[str, bool]:
        """检查所有采集器健康状态"""
        status = {}
        for source_type, collector in self.collectors.items():
            try:
                status[source_type.value] = collector.health_check()
            except:
                status[source_type.value] = False
        return status
    
    def get_stats(self) -> Dict[str, Any]:
        """获取所有采集器统计信息"""
        stats = {
            'enabled_sources': [s.value for s in self.enabled_sources],
            'available_sources': [s.value for s in self.get_available_sources()],
            'collectors': {}
        }
        
        for source_type, collector in self.collectors.items():
            stats['collectors'][source_type.value] = collector.get_stats()
        
        return stats
    
    def _deduplicate(self, data: List[CollectedData]) -> List[CollectedData]:
        """去重"""
        seen_urls = set()
        unique_data = []
        
        for item in data:
            # 使用 URL 作为唯一标识
            if item.url and item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_data.append(item)
            elif not item.url:
                # 无 URL 的项目使用内容 hash
                content_hash = hash(item.content[:100])
                if content_hash not in seen_urls:
                    seen_urls.add(content_hash)
                    unique_data.append(item)
        
        return unique_data
    
    def _sort_by_relevance(self, data: List[CollectedData]) -> List[CollectedData]:
        """按相关性排序"""
        def relevance_score(item: CollectedData) -> float:
            # 时间新鲜度
            hours_old = (datetime.now() - item.timestamp).total_seconds() / 3600
            time_score = max(0, 1 - hours_old / 48)  # 48小时衰减
            
            # 互动分数
            engagement = item.likes + item.shares * 2 + item.comments * 3
            engagement_score = min(1.0, engagement / 1000)
            
            # 来源优先级
            source_score = item.metadata.get('source_priority', 0.6)
            
            return time_score * 0.4 + engagement_score * 0.3 + source_score * 0.3
        
        return sorted(data, key=relevance_score, reverse=True)


# 便捷函数
def create_collector_manager(enabled_sources: List[str] = None,
                             config: Dict[str, Any] = None) -> DataCollectorManager:
    """
    创建数据采集管理器的便捷函数
    
    Args:
        enabled_sources: 启用的数据源名称列表 ['news', 'twitter', 'reddit']
        config: 配置字典
    
    Returns:
        DataCollectorManager 实例
    """
    if enabled_sources:
        source_map = {
            'news': DataSource.NEWS,
            'twitter': DataSource.TWITTER,
            'reddit': DataSource.REDDIT
        }
        sources = [source_map.get(s) for s in enabled_sources if s in source_map]
        sources = [s for s in sources if s is not None]
    else:
        sources = None
    
    full_config = config or {}
    if sources:
        full_config['enabled_sources'] = sources
    
    return DataCollectorManager(full_config)
