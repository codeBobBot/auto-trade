#!/usr/bin/env python3
"""
CLOB API 客户端 - 直接使用 REST API
绕过 SDK 问题，直接调用 CLOB API
"""

import os
import json
import time
import hmac
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_defunct
import requests

load_dotenv('/Users/lsl_mac/.openclaw/workspace/projects/polymarket-arbitrage/config/.env', override=True)


class ClobTradingClient:
    """CLOB 交易客户端 - REST API 版本"""
    
    BASE_URL = "https://clob.polymarket.com"
    DATA_API_URL = "https://data-api.polymarket.com"
    GAMMA_API_URL = "https://gamma-api.polymarket.com"
    
    def __init__(self):
        self.private_key = os.getenv('POLYGON_PRIVATE_KEY', '')
        self.api_key = os.getenv('CLOB_API_KEY', '')
        self.api_secret = os.getenv('CLOB_API_SECRET', '')
        self.api_passphrase = os.getenv('CLOB_API_PASSPHRASE', '')
        
        # 确保私钥有 0x 前缀
        if self.private_key and not self.private_key.startswith('0x'):
            self.private_key = '0x' + self.private_key
        
        # 初始化钱包
        self.account = Account.from_key(self.private_key) if self.private_key else None
        self.signer_address = self.account.address if self.account else None
        
        # 使用代理地址作为实际交易地址
        self.proxy_address = os.getenv('POLYMARKET_PROXY_ADDRESS', self.signer_address)
        self.wallet_address = self.proxy_address if self.proxy_address else self.signer_address
        
        self.session = requests.Session()
        
        if self.wallet_address:
            print(f"✅ CLOB 客户端初始化成功")
            print(f"   签名地址: {self.signer_address}")
            print(f"   代理地址 (资金): {self.wallet_address}")
        else:
            raise ValueError("私钥无效或未配置")
    
    def _generate_signature(self, timestamp: str, method: str, path: str, body: str = '') -> str:
        """生成 HMAC 签名"""
        message = timestamp + method.upper() + path + body
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _get_headers(self, method: str, path: str, body: str = '') -> Dict:
        """获取认证请求头"""
        timestamp = str(int(time.time()))
        signature = self._generate_signature(timestamp, method, path, body)
        
        return {
            'POLY_ADDRESS': self.wallet_address,
            'POLY_SIGNATURE': signature,
            'POLY_TIMESTAMP': timestamp,
            'POLY_API_KEY': self.api_key,
            'POLY_PASSPHRASE': self.api_passphrase,
            'Content-Type': 'application/json'
        }
    
    def get_balance(self) -> Dict:
        """获取 USDC 余额 - 通过 Data API"""
        try:
            # 使用 Data API 获取用户 portfolio
            url = f"{self.DATA_API_URL}/portfolio/balance/{self.wallet_address}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # 提取 USDC 余额
                usdc_balance = 0
                available = 0
                
                if isinstance(data, dict):
                    usdc_balance = float(data.get('balance', 0))
                    available = float(data.get('available', usdc_balance))
                
                return {
                    'balance': usdc_balance,
                    'available': available,
                    'currency': 'USDC'
                }
            else:
                # 如果 API 失败，尝试备用方案
                return self._get_balance_from_clob()
                
        except Exception as e:
            print(f"⚠️  Data API 获取余额失败: {e}")
            return self._get_balance_from_clob()
    
    def _get_balance_from_clob(self) -> Dict:
        """通过 CLOB API 获取余额"""
        try:
            path = "/balance"
            headers = self._get_headers('GET', path)
            
            response = self.session.get(
                f"{self.BASE_URL}{path}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'balance': float(data.get('balance', 0)),
                    'available': float(data.get('available', 0)),
                    'currency': 'USDC'
                }
            else:
                return {'balance': 0, 'available': 0, 'error': f'CLOB API {response.status_code}'}
                
        except Exception as e:
            return {'balance': 0, 'available': 0, 'error': str(e)}
    
    def get_orders(self) -> List[Dict]:
        """获取订单列表"""
        try:
            path = "/orders"
            headers = self._get_headers('GET', path)
            
            response = self.session.get(
                f"{self.BASE_URL}{path}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                # 返回订单列表
                if isinstance(data, dict) and 'data' in data:
                    return data['data']
                return data if isinstance(data, list) else []
            elif response.status_code == 405:
                print(f"⚠️  API 方法不允许 (405)，尝试备用端点...")
                return self._get_orders_backup()
            else:
                print(f"⚠️  获取订单失败: {response.status_code} - {response.text[:100]}")
                return []
                
        except Exception as e:
            print(f"⚠️  获取订单失败: {e}")
            return []
    
    def _get_orders_backup(self) -> List[Dict]:
        """备用订单查询方法"""
        try:
            # 尝试使用 Data API
            url = f"{self.DATA_API_URL}/orders/{self.wallet_address}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            return []
        except:
            return []
    
    def _sign_order(self, order_data: Dict) -> str:
        """使用 EIP-712 签名订单"""
        # 创建订单消息
        message = json.dumps(order_data, sort_keys=True)
        message_hash = encode_defunct(text=message)
        signed = self.account.sign_message(message_hash)
        return signed.signature.hex()
    
    def create_order(self, token_id: str, side: str, size: float,
                     price: float, order_type: str = 'limit') -> Optional[Dict]:
        """
        创建订单
        
        Args:
            token_id: 市场 token ID (从 Gamma API 获取)
            side: 'BUY' 或 'SELL'
            size: 订单数量
            price: 价格 (0-1)
            order_type: 'limit' 或 'market'
        """
        try:
            # 构建订单数据
            order_data = {
                'token_id': token_id,
                'side': side.upper(),
                'size': str(size),
                'price': str(price),
                'type': order_type.upper(),
                'timestamp': str(int(time.time() * 1000)),
            }
            
            # 签名订单
            signature = self._sign_order(order_data)
            order_data['signature'] = signature
            
            # 提交订单
            path = "/orders"
            body = json.dumps(order_data)
            headers = self._get_headers('POST', path, body)
            
            response = self.session.post(
                f"{self.BASE_URL}{path}",
                headers=headers,
                data=body,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 订单创建成功: {result.get('id', 'N/A')}")
                return result
            else:
                print(f"❌ 创建订单失败: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ 创建订单失败: {e}")
            return None
    
    def cancel_all_orders(self) -> bool:
        """取消所有订单"""
        try:
            path = "/orders"
            headers = self._get_headers('DELETE', path)
            
            response = self.session.delete(
                f"{self.BASE_URL}{path}",
                headers=headers,
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"❌ 取消订单失败: {e}")
            return False


class TradingExecutor:
    """交易执行器 - 带风险控制"""
    
    def __init__(self):
        self.client = ClobTradingClient()
        self.max_trade_amount = float(os.getenv('MAX_TRADE_AMOUNT_USD', 2))
        self.max_daily_loss = float(os.getenv('MAX_DAILY_LOSS_USD', 5))
        self.daily_trades = []
        
    def check_risk_limits(self, size: float, price: float) -> bool:
        """检查风险限制"""
        trade_value = size * price
        
        if trade_value > self.max_trade_amount:
            print(f"❌ 超过单笔交易限制: ${trade_value:.2f} > ${self.max_trade_amount}")
            return False
        
        daily_loss = sum(t.get('loss', 0) for t in self.daily_trades)
        if daily_loss >= self.max_daily_loss:
            print(f"❌ 超过日亏损限制: ${daily_loss:.2f} >= ${self.max_daily_loss}")
            return False
        
        return True
    
    def execute_signal(self, signal: str, market_id: str, market_question: str,
                       confidence: float, max_size: float = 1.0) -> Optional[Dict]:
        """执行交易信号"""
        print(f"\n🎯 执行交易信号")
        print(f"   市场: {market_question[:50]}...")
        print(f"   信号: {signal}")
        print(f"   置信度: {confidence:.2%}")
        
        # 解析信号
        if signal == 'buy_yes':
            side = 'BUY'
            target_price = 0.55
        elif signal == 'buy_no':
            side = 'BUY'
            target_price = 0.45
        else:
            print(f"   ⚠️  未知信号: {signal}")
            return None
        
        # 计算交易数量
        size = min(max_size * confidence, self.max_trade_amount / target_price)
        
        # 风险检查
        if not self.check_risk_limits(size, target_price):
            return None
        
        try:
            print(f"   📊 下单: {side} {size:.4f} @ {target_price:.4f}")
            
            # 注意: market_id 需要是 token_id 而非 condition_id
            # 这里简化处理，实际应从 Gamma API 获取正确的 token_id
            order = self.client.create_order(
                token_id=market_id,  # 这应该是 token_id
                side=side,
                size=size,
                price=target_price,
                order_type='limit'
            )
            
            if order:
                print(f"   ✅ 订单已创建: {order.get('id', 'N/A')}")
                
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
    print("🔍 CLOB API 测试 (REST API 版本)")
    print("=" * 70)
    
    try:
        client = ClobTradingClient()
        
        # 测试获取余额
        print("\n💰 获取账户余额...")
        balance = client.get_balance()
        print(f"   USDC 余额: ${balance.get('balance', 0):,.2f}")
        print(f"   可用: ${balance.get('available', 0):,.2f}")
        
        # 测试获取订单
        print("\n📋 获取活跃订单...")
        orders = client.get_orders()
        print(f"   订单数量: {len(orders)}")
        for order in orders[:3]:
            print(f"   - {order.get('id', 'N/A')}: {order.get('status', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    test_clob_api()
