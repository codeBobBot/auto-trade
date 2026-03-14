#!/usr/bin/env python3
"""
新闻数据采集器
支持多源新闻采集：Tavily、NewsAPI、Google News
"""

import os
import re
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

from .base_collector import BaseCollector, CollectedData, CollectionResult, DataSource

load_dotenv('config/.env')


class NewsCollector(BaseCollector):
    """新闻数据采集器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.source_type = DataSource.NEWS
        self.tavily_api_key = os.getenv('TAVILY_API_KEY')
        self.newsapi_key = os.getenv('NEWSAPI_KEY')
        self.gnews_key = os.getenv('GNEWS_KEY')
        
        # 新闻源优先级
        self.source_priority = {
            'reuters': 1.0,
            'ap': 1.0,
            'bbc': 0.95,
            'bloomberg': 0.95,
            'cnn': 0.85,
            'cnbc': 0.85,
            'guardian': 0.85,
            'wsj': 0.90,
            'ft': 0.90,
            'default': 0.6
        }
        
        self.is_initialized = bool(self.tavily_api_key or self.newsapi_key)
    
    def collect(self, keywords: List[str], max_items: int = 50,
                time_range: Dict[str, datetime] = None) -> CollectionResult:
        """采集新闻数据"""
        all_data = []
        errors = []
        
        # 使用 Tavily 采集
        if self.tavily_api_key:
            result = self._collect_from_tavily(keywords, max_items, time_range)
            if result.success:
                all_data.extend(result.data)
            elif result.error:
                errors.append(f"Tavily: {result.error}")
        
        # 使用 NewsAPI 采集（补充）
        if self.newsapi_key and len(all_data) < max_items:
            result = self._collect_from_newsapi(keywords, max_items - len(all_data), time_range)
            if result.success:
                all_data.extend(result.data)
            elif result.error:
                errors.append(f"NewsAPI: {result.error}")
        
        # 使用 GNews 采集（补充）
        if self.gnews_key and len(all_data) < max_items:
            result = self._collect_from_gnews(keywords, max_items - len(all_data), time_range)
            if result.success:
                all_data.extend(result.data)
            elif result.error:
                errors.append(f"GNews: {result.error}")
        
        # 去重
        all_data = self._deduplicate(all_data)
        
        # 按时间过滤
        if time_range:
            all_data = self._filter_by_time_range(all_data, time_range)
        
        # 按时间排序
        all_data.sort(key=lambda x: x.timestamp, reverse=True)
        
        # 限制数量
        all_data = all_data[:max_items]
        
        self.last_collection_time = datetime.now()
        self.collection_count += 1
        
        if not all_data and errors:
            self.error_count += 1
            return CollectionResult(
                success=False,
                error="; ".join(errors)
            )
        
        return CollectionResult(
            success=True,
            data=all_data,
            total_count=len(all_data)
        )
    
    def _collect_from_tavily(self, keywords: List[str], max_items: int,
                             time_range: Dict[str, datetime] = None) -> CollectionResult:
        """从 Tavily 采集新闻"""
        try:
            query = " ".join(keywords)
            
            payload = {
                'api_key': self.tavily_api_key,
                'query': query,
                'search_depth': 'advanced',
                'max_results': max_items,
                'include_answer': True,
                'include_raw_content': False,
                'include_domains': [],  # 不限制域名
                'exclude_domains': [],
                'topic': 'news'  # 专注于新闻
            }
            
            # 添加时间范围
            if time_range:
                start = time_range.get('start')
                if start:
                    days_ago = (datetime.now() - start).days
                    payload['days'] = max(1, days_ago)
            
            response = requests.post(
                "https://api.tavily.com/search",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            news_items = []
            for result in data.get('results', []):
                timestamp = self._parse_timestamp(result.get('published_date', ''))
                
                news = CollectedData(
                    source=DataSource.NEWS,
                    title=result.get('title', ''),
                    content=result.get('content', ''),
                    url=result.get('url', ''),
                    timestamp=timestamp,
                    author=self._extract_source_name(result.get('url', '')),
                    language=self._detect_language(result.get('content', '')),
                    metadata={
                        'score': result.get('score', 0.5),
                        'source_priority': self._get_source_priority(result.get('url', ''))
                    }
                )
                news_items.append(news)
            
            return CollectionResult(success=True, data=news_items, total_count=len(news_items))
            
        except Exception as e:
            return CollectionResult(success=False, error=str(e))
    
    def _collect_from_newsapi(self, keywords: List[str], max_items: int,
                              time_range: Dict[str, datetime] = None) -> CollectionResult:
        """从 NewsAPI 采集新闻"""
        try:
            query = " OR ".join(keywords)
            
            params = {
                'apiKey': self.newsapi_key,
                'q': query,
                'pageSize': max_items,
                'sortBy': 'publishedAt',
                'language': 'en'
            }
            
            # 添加时间范围
            if time_range:
                start = time_range.get('start')
                end = time_range.get('end')
                if start:
                    params['from'] = start.isoformat()
                if end:
                    params['to'] = end.isoformat()
            
            response = requests.get(
                "https://newsapi.org/v2/everything",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') != 'ok':
                return CollectionResult(success=False, error=data.get('message', 'Unknown error'))
            
            news_items = []
            for article in data.get('articles', []):
                timestamp = self._parse_timestamp(article.get('publishedAt', ''))
                
                news = CollectedData(
                    source=DataSource.NEWS,
                    title=article.get('title', ''),
                    content=article.get('description', '') or article.get('content', ''),
                    url=article.get('url', ''),
                    timestamp=timestamp,
                    author=article.get('source', {}).get('name', ''),
                    language='en',
                    metadata={
                        'source_priority': self._get_source_priority(article.get('url', ''))
                    }
                )
                news_items.append(news)
            
            return CollectionResult(success=True, data=news_items, total_count=len(news_items))
            
        except Exception as e:
            return CollectionResult(success=False, error=str(e))
    
    def _collect_from_gnews(self, keywords: List[str], max_items: int,
                            time_range: Dict[str, datetime] = None) -> CollectionResult:
        """从 GNews 采集新闻"""
        try:
            query = " OR ".join(keywords)
            
            params = {
                'token': self.gnews_key,
                'q': query,
                'max': max_items,
                'lang': 'en',
                'country': 'us',
                'sortby': 'publishedAt'
            }
            
            # 添加时间范围
            if time_range:
                start = time_range.get('start')
                end = time_range.get('end')
                if start:
                    params['from'] = start.strftime('%Y-%m-%dT%H:%M:%SZ')
                if end:
                    params['to'] = end.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            response = requests.get(
                "https://gnews.io/api/v4/search",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            news_items = []
            for article in data.get('articles', []):
                timestamp = self._parse_timestamp(article.get('publishedAt', ''))
                
                news = CollectedData(
                    source=DataSource.NEWS,
                    title=article.get('title', ''),
                    content=article.get('description', ''),
                    url=article.get('url', ''),
                    timestamp=timestamp,
                    author=article.get('source', {}).get('name', ''),
                    language=article.get('language', 'en'),
                    metadata={
                        'source_priority': self._get_source_priority(article.get('url', ''))
                    }
                )
                news_items.append(news)
            
            return CollectionResult(success=True, data=news_items, total_count=len(news_items))
            
        except Exception as e:
            return CollectionResult(success=False, error=str(e))
    
    def health_check(self) -> bool:
        """检查采集器健康状态"""
        if not (self.tavily_api_key or self.newsapi_key or self.gnews_key):
            return False
        
        # 尝试简单搜索
        try:
            result = self.collect(['test'], max_items=1)
            return result.success or len(result.data) > 0
        except:
            return False
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """解析时间戳"""
        if not timestamp_str:
            return datetime.now()
        
        formats = [
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%S.%f%z',
            '%Y-%m-%d %H:%M:%S',
            '%a, %d %b %Y %H:%M:%S %Z'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str.replace('+00:00', 'Z').rstrip('Z'), 
                                        fmt.replace('%z', '').replace('Z', ''))
            except:
                continue
        
        # 尝试 ISO 格式
        try:
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            return datetime.now()
    
    def _extract_source_name(self, url: str) -> str:
        """从 URL 提取来源名称"""
        try:
            match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            if match:
                domain = match.group(1)
                parts = domain.split('.')
                if len(parts) >= 2:
                    return parts[-2]
            return 'unknown'
        except:
            return 'unknown'
    
    def _get_source_priority(self, url: str) -> float:
        """获取来源优先级"""
        source = self._extract_source_name(url).lower()
        return self.source_priority.get(source, self.source_priority['default'])
    
    def _detect_language(self, text: str) -> str:
        """简单语言检测"""
        # 基于字符特征简单判断
        if not text:
            return 'en'
        
        # 中文
        if re.search(r'[\u4e00-\u9fff]', text):
            return 'zh'
        # 日文
        if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text):
            return 'ja'
        # 韩文
        if re.search(r'[\uac00-\ud7af]', text):
            return 'ko'
        # 西班牙语/葡萄牙语等拉丁语系
        if re.search(r'[áéíóúñüç]', text.lower()):
            return 'es'  # 简化处理
        
        return 'en'
    
    def _deduplicate(self, data: List[CollectedData]) -> List[CollectedData]:
        """去重"""
        seen_urls = set()
        unique_data = []
        
        for item in data:
            # 基于 URL 去重
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_data.append(item)
        
        return unique_data
