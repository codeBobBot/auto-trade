#!/usr/bin/env python3
"""
CLOB API 客户端
Polymarket 交易执行接口
"""

import os
import json
import time
import hmac
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv('/Users/lsl_mac/.openclaw/workspace/projects/polymarket-arbitrage/config/.env')

class ClobClient:
    """CLOB (Central Limit Order Book) API 客户端"""
    
    # CLOB API 端点
    BASE_URL = "https://clob.polymarket.com"
    
    def __init__(self):
        self.api_key = os.getenv('CLOB_API_KEY')
        self.api_secret = os.getenv('CLOB_API_SECRET')
        self.api_passphrase = os.getenv('CLOB_API_PASSPHRASE')
        
        if not all([self.api_key, self.api_secret, self.api_passphrase]):
            raise ValueError("CLOB API 凭证未配置，请检查 .env 文件")
        
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
    
    def get_balance(self) -> Dict:
        """获取账户余额"""
        path = "/balance"
        headers = self._get_headers('GET', path)
        
        response = self.session.get(f"{self.BASE_URL}{path}", headers=headers)
        response.raise_for_status()
        return response.json()
    
    def get_orders(self, status: str = 'open') -> List[Dict]:
        """获取订单列表"""
        path = f"/orders?status={status}"
        headers = self._get_headers('GET', path)
        
        response = self.session.get(f"{self.BASE_URL}{path}", headers=headers)
        response.raise_for_status()
        return response.json()
    
    def create_order(self, market_id: str, side: str, size: float, 
                     price: float, order_type: str = 'limit') -> Dict:
        """
        创建订单
        
        Args:
            market_id: 市场 ID
            side: 'buy' 或 'sell'
            size: 订单数量
            price: 价格 (0-1)
            order_type: 'limit' 或 'market'
        """
        path = "/orders"
        body = json.dumps({
            'marketId': market_id,
            'side': side,
            'size': str(size),
            'price': str(price),
            'type': order_type
        })
        
        headers = self._get_headers('POST', path, body)
        
        response = self.session.post(
            f"{self.BASE_URL}{path}",
            headers=headers,
            data=body
        )
        response.raise_for_status()
        return response.json()
    
    def cancel_order(self, order_id: str) -> Dict:
        """取消订单"""
        path = f"/orders/{order_id}"
        headers = self._get_headers('DELETE', path)
        
        response = self.session.delete(f"{self.BASE_URL}{path}", headers=headers)
        response.raise_for_status()
        return response.json()
    
    def cancel_all_orders(self) -> Dict:
        """取消所有订单"""
        path = "/orders"
        headers = self._get_headers('DELETE', path)
        
        response = self.session.delete(f"{self.BASE_URL}{path}", headers=headers)
        response.raise_for_status()
        return response.json()


class TradingExecutor:
    """交易执行器 - 带风险控制"""
    
    def __init__(self):
        self.client = ClobClient()
        self.max_trade_amount = float(os.getenv('MAX_TRADE_AMOUNT_USD', 2))
        self.max_daily_loss = float(os.getenv('MAX_DAILY_LOSS_USD', 5))
        self.daily_trades = []
        
    def check_risk_limits(self, size: float, price: float) -> bool:
        """检查风险限制"""
        trade_value = size * price
        
        # 检查单笔交易限制
        if trade_value > self.max_trade_amount:
            print(f"❌ 超过单笔交易限制: ${trade_value:.2f} > ${self.max_trade_amount}")
            return False
        
        # 检查日亏损限制
        daily_loss = sum(t.get('loss', 0) for t in self.daily_trades)
        if daily_loss >= self.max_daily_loss:
            print(f"❌ 超过日亏损限制: ${daily_loss:.2f} >= ${self.max_daily_loss}")
            return False
        
        return True
    
    def execute_signal(self, signal: str, market_id: str, market_question: str,
                       confidence: float, max_size: float = 1.0) -> Optional[Dict]:
        """
        执行交易信号
        
        Args:
            signal: 'buy_yes' 或 'buy_no'
            market_id: 市场 ID
            market_question: 市场问题
            confidence: 置信度 (0-1)
            max_size: 最大交易数量
        """
        print(f"\n🎯 执行交易信号")
        print(f"   市场: {market_question[:50]}...")
        print(f"   信号: {signal}")
        print(f"   置信度: {confidence:.2%}")
        
        # 解析信号
        if signal == 'buy_yes':
            side = 'buy'
            target_price = 0.55  # 目标买入价格
        elif signal == 'buy_no':
            side = 'buy'
            target_price = 0.45  # 目标买入价格
        else:
            print(f"   ⚠️  未知信号: {signal}")
            return None
        
        # 计算交易数量 (基于置信度)
        size = min(max_size * confidence, self.max_trade_amount / target_price)
        
        # 风险检查
        if not self.check_risk_limits(size, target_price):
            return None
        
        try:
            # 执行订单
            print(f"   📊 下单: {side} {size:.4f} @ {target_price:.4f}")
            
            order = self.client.create_order(
                market_id=market_id,
                side=side,
                size=size,
                price=target_price,
                order_type='limit'
            )
            
            print(f"   ✅ 订单已创建: {order.get('id', 'N/A')}")
            
            # 记录交易
            self.daily_trades.append({
                'timestamp': datetime.now().isoformat(),
                'market_id': market_id,
                'signal': signal,
                'size': size,
                'price': target_price,
                'confidence': confidence
            })
            
            return order
            
        except Exception as e:
            print(f"   ❌ 下单失败: {e}")
            return None


def test_clob_api():
    """测试 CLOB API"""
    print("\n" + "=" * 70)
    print("🔍 CLOB API 测试")
    print("=" * 70)
    
    try:
        client = ClobClient()
        print("✅ CLOB 客户端初始化成功")
        
        # 测试获取余额
        print("\n  💰 获取账户余额...")
        balance = client.get_balance()
        print(f"  ✅ 余额: ${balance.get('balance', 0):,.2f}")
        print(f"  ✅ 可用: ${balance.get('available', 0):,.2f}")
        
        # 测试获取订单
        print("\n  📋 获取活跃订单...")
        orders = client.get_orders(status='open')
        print(f"  ✅ 活跃订单: {len(orders)} 个")
        
        return True
        
    except ValueError as e:
        print(f"\n⚠️  CLOB API 未配置: {e}")
        print("\n  请访问 https://polymarket.com/account/api 申请 CLOB API")
        return False
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    test_clob_api()
