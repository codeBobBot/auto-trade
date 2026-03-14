#!/usr/bin/env python3
"""
Reddit 数据采集器
支持 Reddit API 和 Pushshift 备用方案
"""

import os
import re
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

from .base_collector import BaseCollector, CollectedData, CollectionResult, DataSource

load_dotenv('/Users/lsl_mac/.openclaw/workspace/projects/polymarket-arbitrage/config/.env')


class RedditCollector(BaseCollector):
    """Reddit 数据采集器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.source_type = DataSource.REDDIT
        
        # API 凭证
        self.client_id = os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        self.user_agent = os.getenv('REDDIT_USER_AGENT', 'PolymarketSentimentBot/1.0')
        
        # 关注的子版块
        self.target_subreddits = self.config.get('subreddits', [
            'politics', 'worldnews', 'CryptoCurrency', 'Bitcoin', 'stocks',
            'wallstreetbets', 'economics', 'technology', 'news'
        ])
        
        # OAuth token
        self.access_token = None
        self.token_expires = None
        
        self.is_initialized = bool(self.client_id and self.client_secret)
    
    def collect(self, keywords: List[str], max_items: int = 50,
                time_range: Dict[str, datetime] = None) -> CollectionResult:
        """采集 Reddit 数据"""
        all_data = []
        errors = []
        
        # 获取访问令牌
        if not self._ensure_access_token():
            # 尝试使用公开 API
            result = self._collect_public_api(keywords, max_items, time_range)
            if result.success:
                all_data.extend(result.data)
            else:
                errors.append(result.error or "公开 API 采集失败")
        else:
            # 使用官方 API
            result = self._collect_official_api(keywords, max_items, time_range)
            if result.success:
                all_data.extend(result.data)
            elif result.error:
                errors.append(f"Reddit API: {result.error}")
        
        # 使用 Pushshift 备用（历史数据）
        if len(all_data) < max_items // 2:
            result = self._collect_pushshift(keywords, max_items - len(all_data), time_range)
            if result.success:
                all_data.extend(result.data)
            elif result.error:
                errors.append(f"Pushshift: {result.error}")
        
        # 去重和过滤
        all_data = self._deduplicate(all_data)
        if time_range:
            all_data = self._filter_by_time_range(all_data, time_range)
        
        # 按互动分数排序
        all_data.sort(key=lambda x: self._calculate_engagement_score(x), reverse=True)
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
    
    def collect_from_subreddits(self, subreddits: List[str] = None,
                                 max_items_per_subreddit: int = 20,
                                 sort: str = 'hot') -> CollectionResult:
        """
        从指定子版块采集热门帖子
        
        Args:
            subreddits: 子版块列表
            max_items_per_subreddit: 每个子版块最大采集数
            sort: 排序方式 ('hot', 'new', 'top', 'rising')
        """
        subreddits = subreddits or self.target_subreddits
        all_data = []
        
        for subreddit in subreddits:
            result = self._collect_subreddit_posts(subreddit, max_items_per_subreddit, sort)
            if result.success:
                all_data.extend(result.data)
        
        return CollectionResult(
            success=len(all_data) > 0,
            data=all_data,
            total_count=len(all_data)
        )
    
    def _ensure_access_token(self) -> bool:
        """确保有有效的访问令牌"""
        if not self.client_id or not self.client_secret:
            return False
        
        # 检查令牌是否有效
        if self.access_token and self.token_expires:
            if datetime.now() < self.token_expires:
                return True
        
        # 获取新令牌
        try:
            auth = (self.client_id, self.client_secret)
            data = {
                'grant_type': 'client_credentials',
                'duration': 'temporary'
            }
            headers = {'User-Agent': self.user_agent}
            
            response = requests.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=auth,
                data=data,
                headers=headers,
                timeout=15
            )
            
            response.raise_for_status()
            token_data = response.json()
            
            self.access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires = datetime.now() + timedelta(seconds=expires_in - 60)
            
            return True
            
        except Exception:
            return False
    
    def _collect_official_api(self, keywords: List[str], max_items: int,
                              time_range: Dict[str, datetime] = None) -> CollectionResult:
        """使用 Reddit 官方 API 采集"""
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'User-Agent': self.user_agent
            }
            
            query = " OR ".join(keywords)
            posts = []
            
            # 搜索多个子版块
            for subreddit in self.target_subreddits[:5]:  # 限制子版块数量
                params = {
                    'q': query,
                    'limit': min(100, max_items // len(self.target_subreddits[:5]) + 1),
                    'sort': 'relevance',
                    't': 'week'  # 时间范围：周
                }
                
                if time_range:
                    start = time_range.get('start')
                    if start:
                        days_ago = (datetime.now() - start).days
                        if days_ago <= 1:
                            params['t'] = 'day'
                        elif days_ago <= 7:
                            params['t'] = 'week'
                        elif days_ago <= 30:
                            params['t'] = 'month'
                        else:
                            params['t'] = 'year'
                
                response = requests.get(
                    f"https://oauth.reddit.com/r/{subreddit}/search",
                    headers=headers,
                    params=params,
                    timeout=30
                )
                
                if response.status_code != 200:
                    continue
                
                data = response.json()
                
                for child in data.get('data', {}).get('children', []):
                    post = child.get('data', {})
                    
                    timestamp = datetime.fromtimestamp(
                        post.get('created_utc', datetime.now().timestamp())
                    )
                    
                    rd = CollectedData(
                        source=DataSource.REDDIT,
                        title=post.get('title', ''),
                        content=post.get('selftext', ''),
                        url=f"https://reddit.com{post.get('permalink', '')}",
                        timestamp=timestamp,
                        author=post.get('author', ''),
                        language='en',
                        likes=post.get('ups', 0),
                        shares=0,
                        comments=post.get('num_comments', 0),
                        metadata={
                            'subreddit': post.get('subreddit', ''),
                            'upvote_ratio': post.get('upvote_ratio', 0.5),
                            'post_id': post.get('id', ''),
                            'link_flair_text': post.get('link_flair_text', '')
                        }
                    )
                    posts.append(rd)
            
            return CollectionResult(success=True, data=posts, total_count=len(posts))
            
        except Exception as e:
            return CollectionResult(success=False, error=str(e))
    
    def _collect_public_api(self, keywords: List[str], max_items: int,
                            time_range: Dict[str, datetime] = None) -> CollectionResult:
        """使用 Reddit 公开 API（无需认证）"""
        try:
            headers = {'User-Agent': self.user_agent}
            query = " OR ".join(keywords)
            posts = []
            
            for subreddit in self.target_subreddits[:3]:
                # 使用公开搜索端点
                url = f"https://www.reddit.com/r/{subreddit}/search.json"
                params = {
                    'q': query,
                    'restrict_sr': 'on',
                    'limit': max_items // 3,
                    'sort': 'relevance'
                }
                
                response = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=30
                )
                
                if response.status_code != 200:
                    continue
                
                data = response.json()
                
                for child in data.get('data', {}).get('children', []):
                    post = child.get('data', {})
                    
                    timestamp = datetime.fromtimestamp(
                        post.get('created_utc', datetime.now().timestamp())
                    )
                    
                    rd = CollectedData(
                        source=DataSource.REDDIT,
                        title=post.get('title', ''),
                        content=post.get('selftext', ''),
                        url=f"https://reddit.com{post.get('permalink', '')}",
                        timestamp=timestamp,
                        author=post.get('author', ''),
                        language='en',
                        likes=post.get('ups', 0),
                        shares=0,
                        comments=post.get('num_comments', 0),
                        metadata={
                            'subreddit': post.get('subreddit', ''),
                            'upvote_ratio': post.get('upvote_ratio', 0.5)
                        }
                    )
                    posts.append(rd)
            
            return CollectionResult(success=True, data=posts, total_count=len(posts))
            
        except Exception as e:
            return CollectionResult(success=False, error=str(e))
    
    def _collect_pushshift(self, keywords: List[str], max_items: int,
                           time_range: Dict[str, datetime] = None) -> CollectionResult:
        """使用 Pushshift API 采集历史数据"""
        try:
            query = " OR ".join(keywords)
            posts = []
            
            params = {
                'q': query,
                'size': max_items,
                'sort_type': 'score',
                'sort': 'desc'
            }
            
            if time_range:
                start = time_range.get('start')
                end = time_range.get('end')
                if start:
                    params['after'] = int(start.timestamp())
                if end:
                    params['before'] = int(end.timestamp())
            
            # Pushshift API 端点（可能有多个镜像）
            endpoints = [
                'https://api.pushshift.io/reddit/search/submission',
                'https://elastic.pushshift.io/rs/submissions'
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.get(
                        endpoint,
                        params=params,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        for post in data.get('data', []):
                            timestamp = datetime.fromtimestamp(
                                post.get('created_utc', datetime.now().timestamp())
                            )
                            
                            rd = CollectedData(
                                source=DataSource.REDDIT,
                                title=post.get('title', ''),
                                content=post.get('selftext', ''),
                                url=f"https://reddit.com/r/{post.get('subreddit', '')}/comments/{post.get('id', '')}",
                                timestamp=timestamp,
                                author=post.get('author', ''),
                                language='en',
                                likes=post.get('score', 0),
                                shares=0,
                                comments=post.get('num_comments', 0),
                                metadata={
                                    'subreddit': post.get('subreddit', ''),
                                    'upvote_ratio': post.get('upvote_ratio', 0.5)
                                }
                            )
                            posts.append(rd)
                        
                        break
                        
                except Exception:
                    continue
            
            return CollectionResult(success=True, data=posts, total_count=len(posts))
            
        except Exception as e:
            return CollectionResult(success=False, error=str(e))
    
    def _collect_subreddit_posts(self, subreddit: str, max_items: int,
                                  sort: str = 'hot') -> CollectionResult:
        """采集指定子版块的帖子"""
        try:
            headers = {'User-Agent': self.user_agent}
            
            url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
            params = {'limit': max_items}
            
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            posts = []
            for child in data.get('data', {}).get('children', []):
                post = child.get('data', {})
                
                timestamp = datetime.fromtimestamp(
                    post.get('created_utc', datetime.now().timestamp())
                )
                
                rd = CollectedData(
                    source=DataSource.REDDIT,
                    title=post.get('title', ''),
                    content=post.get('selftext', ''),
                    url=f"https://reddit.com{post.get('permalink', '')}",
                    timestamp=timestamp,
                    author=post.get('author', ''),
                    language='en',
                    likes=post.get('ups', 0),
                    shares=0,
                    comments=post.get('num_comments', 0),
                    metadata={
                        'subreddit': subreddit,
                        'upvote_ratio': post.get('upvote_ratio', 0.5),
                        'link_flair_text': post.get('link_flair_text', '')
                    }
                )
                posts.append(rd)
            
            return CollectionResult(success=True, data=posts, total_count=len(posts))
            
        except Exception as e:
            return CollectionResult(success=False, error=str(e))
    
    def health_check(self) -> bool:
        """检查采集器健康状态"""
        try:
            headers = {'User-Agent': self.user_agent}
            response = requests.get(
                "https://www.reddit.com/r/news/hot.json?limit=1",
                headers=headers,
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
    
    def _deduplicate(self, data: List[CollectedData]) -> List[CollectedData]:
        """去重"""
        seen_urls = set()
        unique_data = []
        
        for item in data:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_data.append(item)
        
        return unique_data
