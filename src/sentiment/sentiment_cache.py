#!/usr/bin/env python3
"""
舆情数据缓存模块
提供内存缓存和持久化存储
"""

import os
import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict
from dotenv import load_dotenv

from .data_collectors.base_collector import CollectedData
from .analyzers.sentiment_engine import AnalysisResult

load_dotenv('/Users/lsl_mac/.openclaw/workspace/projects/polymarket-arbitrage/config/.env')


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    data: Any
    timestamp: datetime
    ttl: timedelta  # 生存时间
    access_count: int = 0
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return datetime.now() > self.timestamp + self.ttl
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典"""
        return {
            'key': self.key,
            'data': self._serialize_data(self.data),
            'timestamp': self.timestamp.isoformat(),
            'ttl_seconds': self.ttl.total_seconds(),
            'access_count': self.access_count
        }
    
    def _serialize_data(self, data: Any) -> Any:
        """序列化数据"""
        if hasattr(data, 'to_dict'):
            return data.to_dict()
        elif isinstance(data, list):
            return [self._serialize_data(item) for item in data]
        elif isinstance(data, dict):
            return {k: self._serialize_data(v) for k, v in data.items()}
        else:
            return data


class SentimentDataCache:
    """舆情数据缓存"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # 内存缓存
        self.memory_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        
        # 缓存配置
        self.max_memory_items = self.config.get('max_memory_items', 500)
        self.default_ttl = timedelta(
            seconds=self.config.get('default_ttl_seconds', 3600)  # 默认1小时
        )
        
        # 不同类型数据的 TTL
        self.ttl_by_type = {
            'collected_data': timedelta(hours=2),
            'analysis_result': timedelta(hours=1),
            'trend_data': timedelta(minutes=30),
            'alert': timedelta(hours=24),
            'translation': timedelta(hours=6)
        }
        
        # 持久化存储路径
        self.cache_dir = self.config.get('cache_dir', './data/cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 统计信息
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'saves': 0,
            'loads': 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存数据
        
        Args:
            key: 缓存键
        
        Returns:
            缓存的数据，不存在或过期返回 None
        """
        # 检查内存缓存
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            
            if entry.is_expired():
                del self.memory_cache[key]
                self.stats['misses'] += 1
                return None
            
            # 更新访问计数和顺序
            entry.access_count += 1
            self.memory_cache.move_to_end(key)
            
            self.stats['hits'] += 1
            return entry.data
        
        # 尝试从持久化存储加载
        data = self._load_from_disk(key)
        if data is not None:
            self.stats['hits'] += 1
            return data
        
        self.stats['misses'] += 1
        return None
    
    def set(self, key: str, data: Any, ttl: timedelta = None, 
            data_type: str = None, persist: bool = False):
        """
        设置缓存数据
        
        Args:
            key: 缓存键
            data: 要缓存的数据
            ttl: 生存时间
            data_type: 数据类型（用于确定 TTL）
            persist: 是否持久化到磁盘
        """
        # 确定 TTL
        if ttl is None:
            if data_type and data_type in self.ttl_by_type:
                ttl = self.ttl_by_type[data_type]
            else:
                ttl = self.default_ttl
        
        # 创建缓存条目
        entry = CacheEntry(
            key=key,
            data=data,
            timestamp=datetime.now(),
            ttl=ttl
        )
        
        # 检查容量
        while len(self.memory_cache) >= self.max_memory_items:
            self._evict_oldest()
        
        # 存入内存缓存
        self.memory_cache[key] = entry
        
        # 持久化
        if persist:
            self._save_to_disk(key, entry)
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        if key in self.memory_cache:
            del self.memory_cache[key]
            return True
        
        # 删除持久化文件
        filepath = self._get_cache_filepath(key)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        
        return False
    
    def clear(self, clear_disk: bool = False):
        """清空缓存"""
        self.memory_cache.clear()
        
        if clear_disk:
            for filename in os.listdir(self.cache_dir):
                filepath = os.path.join(self.cache_dir, filename)
                if os.path.isfile(filepath):
                    os.remove(filepath)
    
    def cleanup_expired(self):
        """清理过期缓存"""
        expired_keys = [
            key for key, entry in self.memory_cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            del self.memory_cache[key]
    
    def get_or_compute(self, key: str, compute_func: callable,
                       ttl: timedelta = None, **kwargs) -> Any:
        """
        获取缓存或计算结果
        
        Args:
            key: 缓存键
            compute_func: 计算函数
            ttl: 生存时间
            **kwargs: 传递给计算函数的参数
        
        Returns:
            缓存或计算的数据
        """
        cached = self.get(key)
        if cached is not None:
            return cached
        
        # 计算
        data = compute_func(**kwargs)
        
        # 缓存
        self.set(key, data, ttl)
        
        return data
    
    def generate_key(self, *args, **kwargs) -> str:
        """生成缓存键"""
        # 组合参数
        key_parts = [str(arg) for arg in args]
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        
        key_string = ":".join(key_parts)
        
        # 使用 hash 缩短键长度
        if len(key_string) > 100:
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            return f"hash:{key_hash}"
        
        return key_string
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            'memory_items': len(self.memory_cache),
            'max_items': self.max_memory_items,
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': hit_rate,
            'evictions': self.stats['evictions'],
            'saves': self.stats['saves'],
            'loads': self.stats['loads']
        }
    
    def _evict_oldest(self):
        """驱逐最旧的条目"""
        if self.memory_cache:
            self.memory_cache.popitem(last=False)
            self.stats['evictions'] += 1
    
    def _get_cache_filepath(self, key: str) -> str:
        """获取缓存文件路径"""
        # 使用 hash 作为文件名
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{key_hash}.json")
    
    def _save_to_disk(self, key: str, entry: CacheEntry):
        """保存到磁盘"""
        try:
            filepath = self._get_cache_filepath(key)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(entry.to_dict(), f, indent=2, ensure_ascii=False)
            
            self.stats['saves'] += 1
            
        except Exception as e:
            print(f"缓存持久化失败: {e}")
    
    def _load_from_disk(self, key: str) -> Optional[Any]:
        """从磁盘加载"""
        try:
            filepath = self._get_cache_filepath(key)
            
            if not os.path.exists(filepath):
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查是否过期
            timestamp = datetime.fromisoformat(data['timestamp'])
            ttl = timedelta(seconds=data['ttl_seconds'])
            
            if datetime.now() > timestamp + ttl:
                os.remove(filepath)
                return None
            
            self.stats['loads'] += 1
            
            # 放入内存缓存
            entry = CacheEntry(
                key=key,
                data=data['data'],
                timestamp=timestamp,
                ttl=ttl,
                access_count=data.get('access_count', 0)
            )
            
            self.memory_cache[key] = entry
            
            return entry.data
            
        except Exception as e:
            print(f"缓存加载失败: {e}")
            return None


class SentimentDataStore:
    """舆情数据存储（长期存储）"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # 存储路径
        self.data_dir = self.config.get('data_dir', './data/sentiment')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 子目录
        self.collections_dir = os.path.join(self.data_dir, 'collections')
        self.analyses_dir = os.path.join(self.data_dir, 'analyses')
        self.trends_dir = os.path.join(self.data_dir, 'trends')
        
        for d in [self.collections_dir, self.analyses_dir, self.trends_dir]:
            os.makedirs(d, exist_ok=True)
    
    def save_collection(self, keyword: str, data: List[CollectedData],
                        metadata: Dict[str, Any] = None):
        """保存采集数据"""
        timestamp = datetime.now()
        filename = f"{keyword.replace(' ', '_')}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.collections_dir, filename)
        
        record = {
            'keyword': keyword,
            'timestamp': timestamp.isoformat(),
            'count': len(data),
            'metadata': metadata or {},
            'items': [d.to_dict() for d in data]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def save_analysis(self, keyword: str, result: AnalysisResult):
        """保存分析结果"""
        timestamp = datetime.now()
        filename = f"{keyword.replace(' ', '_')}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.analyses_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def load_recent_collections(self, keyword: str = None, 
                                hours: int = 24) -> List[Dict]:
        """加载最近的采集数据"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        collections = []
        for filename in os.listdir(self.collections_dir):
            if keyword and keyword.replace(' ', '_') not in filename:
                continue
            
            filepath = os.path.join(self.collections_dir, filename)
            
            # 检查文件时间
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            if file_time < cutoff:
                continue
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    collections.append(json.load(f))
            except:
                continue
        
        return collections
    
    def get_data_summary(self) -> Dict[str, Any]:
        """获取数据摘要"""
        collections_count = len([f for f in os.listdir(self.collections_dir) if f.endswith('.json')])
        analyses_count = len([f for f in os.listdir(self.analyses_dir) if f.endswith('.json')])
        trends_count = len([f for f in os.listdir(self.trends_dir) if f.endswith('.json')])
        
        # 计算存储大小
        total_size = 0
        for directory in [self.collections_dir, self.analyses_dir, self.trends_dir]:
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                total_size += os.path.getsize(filepath)
        
        return {
            'collections_count': collections_count,
            'analyses_count': analyses_count,
            'trends_count': trends_count,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2)
        }
    
    def cleanup_old_data(self, days: int = 30):
        """清理旧数据"""
        cutoff = datetime.now() - timedelta(days=days)
        
        cleaned = 0
        for directory in [self.collections_dir, self.analyses_dir, self.trends_dir]:
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                
                if file_time < cutoff:
                    os.remove(filepath)
                    cleaned += 1
        
        return cleaned
