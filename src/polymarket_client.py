#!/usr/bin/env python3
"""
Polymarket API 客户端
用于获取市场数据、下单、查询账户信息
"""

import os
import json
import hmac
import hashlib
import time
from datetime import datetime
from typing import Dict, List, Optional
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv('/Users/lsl_mac/.openclaw/workspace/projects/polymarket-arbitrage/config/.env')

class PolymarketClient:
    """Polymarket API 客户端"""
    
    BASE_URL = "https://api.polymarket.com"
    
    def __init__(self):
        self.api_key = os.getenv('POLYMARKET_API_KEY')
        self.api_secret = os.getenv('POLYMARKET_API_SECRET')
        self.api_passphrase = os.getenv('POLYMARKET_API_PASSPHRASE')
        
        if not all([self.api_key, self.api_secret, self.api_passphrase]):
            raise ValueError("API 凭证未配置，请检查 .env 文件")
        
        self.session = requests.Session()
        
    def _generate_signature(self, timestamp: str, method: str, path: str, body: str = '') -> str:
        """生成 API 签名"""
        message = timestamp + method.upper() + path + body
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _get_headers(self, method: str, path: str, body: str = '') -> Dict:
        """获取请求头"""
        timestamp = str(int(time.time()))
        signature = self._generate_signature(timestamp, method, path, body)
        
        return {
            'POLYMARKET-API-KEY': self.api_key,
            'POLYMARKET-API-SIGNATURE': signature,
            'POLYMARKET-API-TIMESTAMP': timestamp,
            'POLYMARKET-API-PASSPHRASE': self.api_passphrase,
            'Content-Type': 'application/json'
        }
    
    def get_markets(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """获取活跃市场列表"""
        path = f"/markets?limit={limit}&offset={offset}&active=true"
        headers = self._get_headers('GET', path)
        
        response = self.session.get(f"{self.BASE_URL}{path}", headers=headers)
        response.raise_for_status()
        return response.json()
    
    def get_market(self, market_id: str) -> Dict:
        """获取特定市场详情"""
        path = f"/markets/{market_id}"
        headers = self._get_headers('GET', path)
        
        response = self.session.get(f"{self.BASE_URL}{path}", headers=headers)
        response.raise_for_status()
        return response.json()
    
    def get_order_book(self, market_id: str) -> Dict:
        """获取订单簿"""
        path = f"/markets/{market_id}/orderbook"
        headers = self._get_headers('GET', path)
        
        response = self.session.get(f"{self.BASE_URL}{path}", headers=headers)
        response.raise_for_status()
        return response.json()
    
    def get_balance(self) -> Dict:
        """获取账户余额"""
        path = "/balance"
        headers = self._get_headers('GET', path)
        
        response = self.session.get(f"{self.BASE_URL}{path}", headers=headers)
        response.raise_for_status()
        return response.json()
    
    def place_order(self, market_id: str, side: str, size: float, price: float) -> Dict:
        """下单"""
        path = "/orders"
        body = json.dumps({
            'marketId': market_id,
            'side': side,  # 'buy' or 'sell'
            'size': size,
            'price': price
        })
        
        headers = self._get_headers('POST', path, body)
        
        response = self.session.post(
            f"{self.BASE_URL}{path}",
            headers=headers,
            data=body
        )
        response.raise_for_status()
        return response.json()


def test_connection():
    """测试 API 连接"""
    print("\n🔍 测试 Polymarket API 连接...")
    
    try:
        client = PolymarketClient()
        
        # 测试获取市场列表
        print("  📊 获取市场列表...")
        markets = client.get_markets(limit=5)
        print(f"  ✅ 成功获取 {len(markets)} 个市场")
        
        # 显示第一个市场
        if markets:
            market = markets[0]
            print(f"\n  📈 示例市场:")
            print(f"     标题: {market.get('question', 'N/A')}")
            print(f"     交易量: ${market.get('volume', 0):,.2f}")
            print(f"     流动性: ${market.get('liquidity', 0):,.2f}")
        
        # 测试获取余额
        print("\n  💰 获取账户余额...")
        balance = client.get_balance()
        print(f"  ✅ 余额: ${balance.get('balance', 0):,.2f}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 连接失败: {e}")
        return False


if __name__ == '__main__':
    test_connection()
