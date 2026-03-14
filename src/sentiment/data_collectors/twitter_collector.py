#!/usr/bin/env python3
"""
Twitter/X 数据采集器
支持 Twitter API v2 和 Nitter 备用方案
"""

import os
import re
import json
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

from .base_collector import BaseCollector, CollectedData, CollectionResult, DataSource

load_dotenv('/Users/lsl_mac/.openclaw/workspace/projects/polymarket-arbitrage/config/.env')


class TwitterCollector(BaseCollector):
    """Twitter/X 数据采集器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.source_type = DataSource.TWITTER
        
        # API 凭证
        self.bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        self.api_key = os.getenv('TWITTER_API_KEY')
        self.api_secret = os.getenv('TWITTER_API_SECRET')
        
        # 备用 Nitter 实例
        self.nitter_instances = [
            'https://nitter.net',
            'https://nitter.poast.org',
            'https://nitter.privacydev.net'
        ]
        
        # 影响力账户列表（可配置）
        self.influential_accounts = self.config.get('influential_accounts', [
            'elonmusk', 'POTUS', 'WhiteHouse', 'SecYellen',
            'federalreserve', 'SEC_News', 'CoinDesk', 'CryptoWhale'
        ])
        
        self.is_initialized = bool(self.bearer_token)
        
        # 请求头
        self.headers = {
            'Authorization': f'Bearer {self.bearer_token}',
            'Content-Type': 'application/json'
        } if self.bearer_token else {}
    
    def collect(self, keywords: List[str], max_items: int = 50,
                time_range: Dict[str, datetime] = None) -> CollectionResult:
        """采集 Twitter 数据"""
        all_data = []
        errors = []
        
        # 方法1: 使用 Twitter API v2
        if self.bearer_token:
            result = self._collect_from_api(keywords, max_items, time_range)
            if result.success:
                all_data.extend(result.data)
            elif result.error:
                errors.append(f"Twitter API: {result.error}")
        
        # 方法2: 使用 Nitter 备用（如果 API 不可用或数据不足）
        if len(all_data) < max_items:
            result = self._collect_from_nitter(keywords, max_items - len(all_data), time_range)
            if result.success:
                all_data.extend(result.data)
            elif result.error:
                errors.append(f"Nitter: {result.error}")
        
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
    
    def collect_from_accounts(self, accounts: List[str] = None, 
                              max_items_per_account: int = 10) -> CollectionResult:
        """
        从指定账户采集推文
        
        用于追踪影响力人物的发言
        """
        accounts = accounts or self.influential_accounts
        all_data = []
        
        for account in accounts:
            result = self._collect_user_tweets(account, max_items_per_account)
            if result.success:
                all_data.extend(result.data)
        
        return CollectionResult(
            success=len(all_data) > 0,
            data=all_data,
            total_count=len(all_data)
        )
    
    def _collect_from_api(self, keywords: List[str], max_items: int,
                          time_range: Dict[str, datetime] = None) -> CollectionResult:
        """使用 Twitter API v2 采集"""
        try:
            query = " OR ".join(keywords)
            query = f"({query}) -is:retweet lang:en"
            
            params = {
                'query': query,
                'max_results': min(100, max_items),
                'tweet.fields': 'created_at,public_metrics,author_id,lang',
                'expansions': 'author_id',
                'user.fields': 'username,public_metrics',
                'sort_order': 'relevancy'
            }
            
            # 添加时间范围
            if time_range:
                start = time_range.get('start')
                if start:
                    params['start_time'] = start.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            response = requests.get(
                "https://api.twitter.com/2/tweets/search/recent",
                headers=self.headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 401:
                return CollectionResult(success=False, error="认证失败，请检查 API 凭证")
            
            response.raise_for_status()
            data = response.json()
            
            # 构建用户 ID 到用户名的映射
            users_map = {}
            for user in data.get('includes', {}).get('users', []):
                users_map[user['id']] = user
            
            tweets = []
            for tweet in data.get('data', []):
                author_id = tweet.get('author_id', '')
                user = users_map.get(author_id, {})
                metrics = tweet.get('public_metrics', {})
                
                timestamp = datetime.fromisoformat(
                    tweet['created_at'].replace('Z', '+00:00')
                )
                
                tw = CollectedData(
                    source=DataSource.TWITTER,
                    title='',  # Twitter 没有标题
                    content=tweet.get('text', ''),
                    url=f"https://twitter.com/{user.get('username', 'i')}/status/{tweet['id']}",
                    timestamp=timestamp,
                    author=user.get('username', ''),
                    language=tweet.get('lang', 'en'),
                    likes=metrics.get('like_count', 0),
                    shares=metrics.get('retweet_count', 0),
                    comments=metrics.get('reply_count', 0),
                    followers=user.get('public_metrics', {}).get('followers_count', 0),
                    metadata={
                        'tweet_id': tweet['id'],
                        'impression_count': metrics.get('impression_count', 0)
                    }
                )
                tweets.append(tw)
            
            return CollectionResult(success=True, data=tweets, total_count=len(tweets))
            
        except Exception as e:
            return CollectionResult(success=False, error=str(e))
    
    def _collect_from_nitter(self, keywords: List[str], max_items: int,
                             time_range: Dict[str, datetime] = None) -> CollectionResult:
        """使用 Nitter 实例采集（备用方案）"""
        tweets = []
        
        for instance in self.nitter_instances:
            try:
                for keyword in keywords[:3]:  # 限制关键词数量
                    search_url = f"{instance}/search"
                    params = {
                        'q': keyword,
                        'f': 'tweets'  # 只搜索推文
                    }
                    
                    response = requests.get(
                        search_url,
                        params=params,
                        timeout=15,
                        headers={'User-Agent': 'Mozilla/5.0'}
                    )
                    
                    if response.status_code != 200:
                        continue
                    
                    # 解析 HTML（简化版本）
                    parsed = self._parse_nitter_html(response.text, instance)
                    tweets.extend(parsed)
                    
                    if len(tweets) >= max_items:
                        break
                
                if tweets:
                    break  # 成功获取数据，跳出实例循环
                    
            except Exception:
                continue
        
        return CollectionResult(
            success=len(tweets) > 0,
            data=tweets[:max_items],
            total_count=min(len(tweets), max_items)
        )
    
    def _collect_user_tweets(self, username: str, max_items: int) -> CollectionResult:
        """采集指定用户的推文"""
        try:
            if self.bearer_token:
                # 使用 API
                params = {
                    'max_results': max_items,
                    'tweet.fields': 'created_at,public_metrics',
                    'exclude': 'retweets,replies'
                }
                
                # 先获取用户 ID
                user_response = requests.get(
                    f"https://api.twitter.com/2/users/by/username/{username}",
                    headers=self.headers,
                    timeout=30
                )
                
                if user_response.status_code != 200:
                    return CollectionResult(success=False, error=f"用户 {username} 不存在")
                
                user_id = user_response.json()['data']['id']
                
                # 获取推文
                response = requests.get(
                    f"https://api.twitter.com/2/users/{user_id}/tweets",
                    headers=self.headers,
                    params=params,
                    timeout=30
                )
                
                response.raise_for_status()
                data = response.json()
                
                tweets = []
                for tweet in data.get('data', []):
                    metrics = tweet.get('public_metrics', {})
                    timestamp = datetime.fromisoformat(
                        tweet['created_at'].replace('Z', '+00:00')
                    )
                    
                    tw = CollectedData(
                        source=DataSource.TWITTER,
                        title='',
                        content=tweet.get('text', ''),
                        url=f"https://twitter.com/{username}/status/{tweet['id']}",
                        timestamp=timestamp,
                        author=username,
                        likes=metrics.get('like_count', 0),
                        shares=metrics.get('retweet_count', 0),
                        comments=metrics.get('reply_count', 0),
                        metadata={'tweet_id': tweet['id']}
                    )
                    tweets.append(tw)
                
                return CollectionResult(success=True, data=tweets, total_count=len(tweets))
            else:
                return CollectionResult(success=False, error="无 API 凭证")
                
        except Exception as e:
            return CollectionResult(success=False, error=str(e))
    
    def _parse_nitter_html(self, html: str, instance: str) -> List[CollectedData]:
        """解析 Nitter HTML 页面"""
        tweets = []
        
        # 简化的 HTML 解析（实际应用中应使用 BeautifulSoup）
        # 这里使用正则表达式作为示例
        tweet_pattern = r'<div class="tweet-content[^"]*"[^>]*>(.*?)</div>'
        time_pattern = r'<span class="tweet-date[^"]*"[^>]*><a href="([^"]+)"[^>]*>(.*?)</a></span>'
        author_pattern = r'<a class="fullname[^"]*"[^>]*>(.*?)</a>'
        stats_pattern = r'<span class="icon-heart[^"]*"[^>]*></span>\s*(\d+)'
        
        # 注意：这是简化实现，实际需要更完善的解析
        # 建议使用 BeautifulSoup: from bs4 import BeautifulSoup
        
        return tweets
    
    def health_check(self) -> bool:
        """检查采集器健康状态"""
        if self.bearer_token:
            try:
                response = requests.get(
                    "https://api.twitter.com/2/users/by/username/twitter",
                    headers=self.headers,
                    timeout=10
                )
                return response.status_code == 200
            except:
                pass
        
        # 检查 Nitter 备用
        for instance in self.nitter_instances:
            try:
                response = requests.get(instance, timeout=5)
                if response.status_code == 200:
                    return True
            except:
                continue
        
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
