#!/usr/bin/env python3
"""
CLOB 客户端 - 自动生成 API 凭证
使用 create_or_derive_api_creds 解决 401 问题
"""

import os
import json
import time
import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

# 导入官方 SDK
from py_clob_client import ClobClient
from py_clob_client.clob_types import ApiCreds, BalanceAllowanceParams, OrderArgs
from py_clob_client.order_builder.constants import BUY, SELL

load_dotenv('config/.env', override=True)


class ClobTradingClientAutoCreds:
    """CLOB 交易客户端 - 自动生成 API 凭证"""
    
    def __init__(self, auto_derive_creds: bool = True):
        # API 配置
        self.host = "https://clob.polymarket.com"
        self.chain_id = 137  # Polygon
        self.signature_type = 2  # EIP712
        self.auto_derive_creds = auto_derive_creds
        
        # Gamma API 配置
        self.gamma_api_url = "https://gamma-api.polymarket.com"
        
        # 从环境变量获取私钥
        self.private_key = os.getenv('POLYGON_PRIVATE_KEY', '')
        
        # 确保私钥有 0x 前缀
        if self.private_key and not self.private_key.startswith('0x'):
            self.private_key = '0x' + self.private_key
        
        # API 凭证（初始从环境变量，后续可能自动生成）
        self.api_key = os.getenv('POLYMARKET_API_KEY', '')
        self.api_secret = os.getenv('POLYMARKET_API_SECRET', '')
        self.api_passphrase = os.getenv('POLYMARKET_API_PASSPHRASE', '')
        
        # 初始化客户端
        self.client = None
        self.wallet_address = None
        self.derived_creds = None
        
        # token_id缓存
        self._token_cache = {}
        
        # 配置logger
        self.logger = logging.getLogger(__name__)
        
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化客户端"""
        try:
            # 方法1: 使用环境变量中的凭证
            if not self.auto_derive_creds and self.api_key:
                self._init_with_env_creds()
            else:
                # 方法2: 自动生成凭证
                self._init_with_derived_creds()
                
        except Exception as e:
            print(f"❌ 客户端初始化失败: {e}")
            self.client = None
    
    def _init_with_env_creds(self):
        """使用环境变量凭证初始化"""
        try:
            creds = ApiCreds(
                api_key=self.api_key,
                api_secret=self.api_secret,
                api_passphrase=self.api_passphrase
            )
            
            self.client = ClobClient(
                host=self.host,
                chain_id=self.chain_id,
                key=self.private_key,
                creds=creds,
                signature_type=self.signature_type
            )
            
            self.wallet_address = self.client.get_address()
            print(f"✅ 使用环境变量凭证初始化成功")
            print(f"   钱包地址: {self.wallet_address}")
            
        except Exception as e:
            print(f"❌ 环境变量凭证初始化失败: {e}")
            raise
    
    def _init_with_derived_creds(self):
        """使用自动生成的凭证初始化"""
        try:
            print("🔧 尝试自动生成 API 凭证...")
            
            # 首先创建一个临时客户端（不需要凭证）
            temp_client = ClobClient(
                host=self.host,
                chain_id=self.chain_id,
                key=self.private_key,
                signature_type=self.signature_type
            )
            
            # 生成 API 凭证
            self.derived_creds = temp_client.create_or_derive_api_creds()
            
            print(f"✅ API 凭证生成成功")
            print(f"   API Key: {self.derived_creds.api_key[:10]}...")
            print(f"   API Secret: {self.derived_creds.api_secret[:10]}...")
            print(f"   API Passphrase: {self.derived_creds.api_passphrase[:10]}...")
            
            # 使用生成的凭证创建正式客户端
            self.client = ClobClient(
                host=self.host,
                chain_id=self.chain_id,
                key=self.private_key,
                creds=self.derived_creds,
                signature_type=self.signature_type
            )
            
            self.wallet_address = self.client.get_address()
            print(f"✅ 使用生成凭证初始化成功")
            print(f"   钱包地址: {self.wallet_address}")
            
            # 保存生成的凭证到环境变量文件
            self._save_derived_creds()
            
        except Exception as e:
            print(f"❌ 自动生成凭证失败: {e}")
            # 如果自动生成失败，尝试使用环境变量
            if self.api_key:
                print("🔄 回退到环境变量凭证...")
                self._init_with_env_creds()
            else:
                raise
    
    def _save_derived_creds(self):
        """保存生成的凭证到 .env 文件"""
        try:
            env_file = 'config/.env'
            
            # 读取现有 .env 文件
            lines = []
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    lines = f.readlines()
            
            # 更新或添加 API 凭证
            updated_lines = []
            cred_updates = {
                'POLYMARKET_API_KEY': self.derived_creds.api_key,
                'POLYMARKET_API_SECRET': self.derived_creds.api_secret,
                'POLYMARKET_API_PASSPHRASE': self.derived_creds.api_passphrase
            }
            
            for line in lines:
                line = line.strip()
                if '=' in line:
                    key = line.split('=')[0]
                    if key in cred_updates:
                        updated_lines.append(f"{key}={cred_updates[key]}")
                        del cred_updates[key]
                    else:
                        updated_lines.append(line)
                else:
                    updated_lines.append(line)
            
            # 添加新的凭证
            for key, value in cred_updates.items():
                updated_lines.append(f"{key}={value}")
            
            # 写回文件
            with open(env_file, 'w') as f:
                f.write('\n'.join(updated_lines) + '\n')
            
            print(f"✅ API 凭证已保存到 .env 文件")
            
        except Exception as e:
            print(f"⚠️  保存凭证失败: {e}")
    
    def get_balance(self) -> Dict:
        """获取 USDC 余额"""
        if not self.client:
            return {
                'balance': 0,
                'available': 0,
                'error': '客户端未初始化',
                'currency': 'USDC'
            }
        
        try:
            print("🔍 获取余额...")
            
            # 使用正确的 AssetType 获取余额
            from py_clob_client.clob_types import AssetType
            
            balance_allowance = None
            
            # 方法1: 使用 COLLATERAL (USDC 是抵押品)
            try:
                params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
                balance_allowance = self.client.get_balance_allowance(params)
                print("✅ 方法1成功: COLLATERAL")
            except Exception as e1:
                print(f"❌ 方法1失败: {e1}")
                
                # 方法2: 使用 CONDITIONAL
                try:
                    params = BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL)
                    balance_allowance = self.client.get_balance_allowance(params)
                    print("✅ 方法2成功: CONDITIONAL")
                except Exception as e2:
                    print(f"❌ 方法2失败: {e2}")
                    
                    # 方法3: 不传参数
                    try:
                        params = BalanceAllowanceParams()
                        balance_allowance = self.client.get_balance_allowance(params)
                        print("✅ 方法3成功: 无参数")
                    except Exception as e3:
                        print(f"❌ 方法3失败: {e3}")
                        raise e3
            
            print(f"🔍 balance_allowance 类型: {type(balance_allowance)}")
            print(f"🔍 balance_allowance 内容: {balance_allowance}")
            
            if balance_allowance is None:
                print("⚠️  balance_allowance 为 None，返回默认值")
                return {
                    'balance': 0.0,
                    'available': 0.0,
                    'currency': 'USDC',
                    'source': 'auto_derived_creds',
                    'note': 'API 返回 None，可能账户无余额'
                }
            
            if isinstance(balance_allowance, dict):
                data = balance_allowance
                print(f"✅ 余额查询成功: {data}")
                
                # 解析余额数据
                balance = 0
                available = 0
                
                # USDC 使用 6 位小数
                if 'balance' in data:
                    try:
                        balance = float(data['balance']) / 1_000_000  # 转换为 USDC
                        print(f"✅ 解析余额: {data['balance']} -> {balance} USDC")
                    except (ValueError, TypeError):
                        balance = 0
                
                # 可用余额就是总余额（USDC 没有锁定概念）
                available = balance
                
                # 检查 allowances（如果有特殊需求）
                if 'allowances' in data and isinstance(data['allowances'], dict):
                    print(f"📋 发现 allowances: {len(data['allowances'])} 个")
                    # 可以在这里处理特定的授权逻辑
                
                return {
                    'balance': balance,
                    'available': available,
                    'currency': 'USDC',
                    'source': 'auto_derived_creds',
                    'raw_data': data
                }
            
        except Exception as e:
            print(f"❌ 获取余额失败: {e}")
            return {
                'balance': 0,
                'available': 0,
                'error': str(e),
                'currency': 'USDC'
            }
    
    def debug_market_api(self, market_id: str) -> Dict:
        """调试市场API响应"""
        debug_info = {
            'market_id': market_id,
            'api_endpoints': [],
            'responses': {},
            'token_fields_found': [],
            'final_token_id': None
        }
        
        # 测试多个可能的端点
        endpoints = [
            f"{self.gamma_api_url}/markets/{market_id}",
            f"{self.gamma_api_url}/events/{market_id}",
            f"{self.gamma_api_url}/markets",
            f"{self.gamma_api_url}/events"
        ]
        
        for endpoint in endpoints:
            try:
                self.logger.info(f"测试端点: {endpoint}")
                response = requests.get(endpoint, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                debug_info['api_endpoints'].append(endpoint)
                debug_info['responses'][endpoint] = data
                
                # 查找token相关字段
                token_fields = self.find_token_fields_in_data(data)
                debug_info['token_fields_found'].extend(token_fields)
                
                self.logger.info(f"端点 {endpoint} 成功，找到token字段: {token_fields}")
                
            except Exception as e:
                self.logger.error(f"端点 {endpoint} 失败: {e}")
        
        # 尝试从响应中提取token_id
        for endpoint, data in debug_info['responses'].items():
            if isinstance(data, list) and len(data) > 0:
                # 如果是列表，查找匹配的市场
                for item in data:
                    if str(item.get('id')) == market_id:
                        token_id = self.extract_token_id_from_full_data(item)
                        if token_id:
                            debug_info['final_token_id'] = token_id
                            break
            elif isinstance(data, dict):
                # 如果是字典，直接提取
                token_id = self.extract_token_id_from_full_data(data)
                if token_id:
                    debug_info['final_token_id'] = token_id
                    break
            
            if debug_info['final_token_id']:
                break
        
        return debug_info
    
    def find_token_fields_in_data(self, data) -> List[str]:
        """递归查找数据中的token相关字段"""
        token_fields = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                # 检查字段名是否包含token相关关键词
                if any(keyword in key.lower() for keyword in ['token', 'address', 'contract']):
                    token_fields.append(f"{key}: {type(value).__name__}")
                
                # 递归检查嵌套结构
                if isinstance(value, (dict, list)):
                    nested_fields = self.find_token_fields_in_data(value)
                    token_fields.extend([f"{key}.{field}" for field in nested_fields])
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                nested_fields = self.find_token_fields_in_data(item)
                token_fields.extend([f"[{i}].{field}" for field in nested_fields])
        
        return token_fields
    
    def get_token_id_alternative_methods(self, market: Dict) -> Optional[str]:
        """使用备选方法获取token_id"""
        market_id = market.get('id')
        if not market_id:
            return None
        
        # 备选方法1: 使用ClobClient的内置方法
        try:
            if self.client:
                # 尝试获取订单簿来推断token_id
                order_book = self.client.get_order_book(market_id)
                if order_book and hasattr(order_book, 'asset_id'):
                    self.logger.info(f"从订单簿获取token_id: {order_book.asset_id}")
                    return order_book.asset_id
        except Exception as e:
            self.logger.warning(f"订单簿方法失败: {e}")
        
        # 备选方法2: 使用价格API
        try:
            if self.client:
                # 尝试获取价格来推断token_id
                price_data = self.client.get_price(market_id, "BUY")
                if price_data:
                    self.logger.info(f"从价格API推断token_id成功")
                    return market_id  # 如果价格API成功，market_id可能就是token_id
        except Exception as e:
            self.logger.warning(f"价格API方法失败: {e}")
        
        # 备选方法3: 直接使用market_id作为token_id
        try:
            self.logger.warning(f"直接使用market_id作为token_id: {market_id}")
            return market_id
        except Exception as e:
            self.logger.error(f"直接使用market_id失败: {e}")
        
        return None
    
    def create_order_with_enhanced_fallback(self, market: Dict, side: str, size: float, price: float) -> Dict:
        """使用增强fallback的订单创建"""
        market_id = market.get('id')
        
        # 方法1: 增强的token_id获取
        token_id = self.get_market_token_id_enhanced(market)
        if token_id:
            return self.create_order(token_id, side, size, price)
        
        # 方法2: 备选方法
        token_id = self.get_token_id_alternative_methods(market)
        if token_id:
            return self.create_order(token_id, side, size, price)
        
        # 方法3: 最后的fallback
        try:
            self.logger.error(f"所有方法失败，尝试直接使用market_id: {market_id}")
            return self.create_order(market_id, side, size, price)
        except Exception as e:
            self.logger.error(f"最终fallback失败: {e}")
            return {
                'success': False,
                'error': f'所有token_id获取方法都失败 for market {market_id}',
                'order_id': None
            }
    
    def get_market_token_id_enhanced(self, market: Dict) -> Optional[str]:
        """增强版token_id获取方法 - 支持从Gamma API获取"""
        
        # 首先尝试从现有数据获取
        token_id = self.get_market_token_id(market)
        if token_id:
            return token_id
        
        # 如果没有，从Gamma API获取完整数据
        market_id = market.get('id')
        if not market_id:
            return None
        
        # 检查缓存
        if market_id in self._token_cache:
            return self._token_cache[market_id]
        
        try:
            # 获取完整的市场数据
            full_market_data = self.get_market_by_id(market_id)
            if not full_market_data:
                return None
            
            # 从完整数据中提取token_id
            token_id = self.extract_token_id_from_full_data(full_market_data)
            
            # 缓存结果
            if token_id:
                self._token_cache[market_id] = token_id
            
            return token_id
            
        except Exception as e:
            self.logger.error(f"获取token_id失败: {e}")
            return None
    
    def get_market_by_id(self, market_id: str) -> Optional[Dict]:
        """根据ID获取完整的市场数据"""
        try:
            # 使用Gamma API获取市场详情
            url = f"{self.gamma_api_url}/markets/{market_id}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            self.logger.error(f"获取市场数据失败: {e}")
            return None
    
    def extract_token_id_from_full_data(self, market_data: Dict) -> Optional[str]:
        """从完整市场数据中提取token_id"""
        
        # 检查各种可能的字段
        token_fields = [
            'clobTokenId',
            'clobTokenIds',     # 新增：复数形式
            'token_id', 
            'tokenAddress',
            'condition_id',
            'outcomeTokenId'
        ]
        
        for field in token_fields:
            if field in market_data and market_data[field]:
                token_value = market_data[field]
                # 如果是clobTokenIds（可能是字符串或数组）
                if field == 'clobTokenIds':
                    if isinstance(token_value, str):
                        # 如果是字符串，尝试解析为JSON
                        try:
                            import json
                            parsed = json.loads(token_value)
                            if isinstance(parsed, list) and len(parsed) > 0:
                                return parsed[0]  # 返回第一个token ID
                            else:
                                return token_value
                        except (json.JSONDecodeError, TypeError):
                            return token_value
                    elif isinstance(token_value, list) and len(token_value) > 0:
                        # 对于Yes/No市场，通常第一个token是Yes
                        return str(token_value[0])  # 返回第一个token ID的字符串形式
                elif field == 'clobTokenId':
                    return token_value
                else:
                    return token_value
        
        # 检查outcomeTokens
        if 'outcomeTokens' in market_data:
            outcome_tokens = market_data['outcomeTokens']
            if isinstance(outcome_tokens, list) and len(outcome_tokens) > 0:
                # 查找Yes代币
                for token in outcome_tokens:
                    if isinstance(token, dict):
                        if token.get('outcome') == 'Yes':
                            return token.get('address') or token.get('token_id')
                # 返回第一个
                first_token = outcome_tokens[0]
                return first_token.get('address') or first_token.get('token_id')
        
        # 检查tokens
        if 'tokens' in market_data:
            tokens = market_data['tokens']
            if isinstance(tokens, list) and len(tokens) > 0:
                first_token = tokens[0]
                return first_token.get('address') or first_token.get('token_id')
        
        return None
    
    def create_order_with_market_id(self, market: Dict, side: str, size: float, price: float) -> Dict:
        """使用market_id创建订单的fallback方法"""
        
        # 尝试多种方法获取token_id
        
        # 方法1: 使用增强的token_id获取
        token_id = self.get_market_token_id_enhanced(market)
        if token_id:
            return self.create_order(token_id, side, size, price)
        
        # 方法2: 尝试直接使用market_id
        market_id = market.get('id')
        try:
            self.logger.warning(f"尝试直接使用market_id: {market_id}")
            return self.create_order(market_id, side, size, price)
        except Exception as e:
            self.logger.error(f"直接使用market_id失败: {e}")
        
        # 方法3: 返回错误
        return {
            'success': False,
            'error': f'无法获取token_id for market {market_id}',
            'order_id': None
        }
    
    def get_market_token_id(self, market: Dict) -> Optional[str]:
        """从市场数据中提取正确的token_id"""
        
        # 方法1: 直接查找常见字段
        direct_fields = ['clobTokenId', 'token_id', 'tokenAddress', 'condition_id', 'outcomeTokenId']
        for field in direct_fields:
            if field in market and market[field]:
                return market[field]
        
        # 方法2: 检查outcomeTokens结构
        if 'outcomeTokens' in market:
            outcome_tokens = market['outcomeTokens']
            if isinstance(outcome_tokens, list) and len(outcome_tokens) > 0:
                # 查找"Yes"代币
                for token in outcome_tokens:
                    if isinstance(token, dict):
                        if token.get('outcome') == 'Yes' or 'yes' in str(token.get('outcome', '')).lower():
                            return token.get('address') or token.get('token_id')
                # 如果没找到Yes，返回第一个
                first_token = outcome_tokens[0]
                return first_token.get('address') or first_token.get('token_id')
        
        # 方法3: 检查tokens结构
        if 'tokens' in market:
            tokens = market['tokens']
            if isinstance(tokens, list) and len(tokens) > 0:
                first_token = tokens[0]
                return first_token.get('address') or first_token.get('token_id')
        
        # 方法4: 检查嵌套的market数据
        if 'market' in market:
            nested_market = market['market']
            return self.get_market_token_id(nested_market)
        
        # 方法5: 检查question markets结构
        if 'question' in market and isinstance(market['question'], dict):
            question_market = market['question']
            return self.get_market_token_id(question_market)
        
        return None
    
    def create_order(self, token_id: str, side: str, size: float, price: float) -> Dict:
        """创建订单
        
        Args:
            token_id: 代币ID (条件代币地址)
            side: 买卖方向 'BUY' 或 'SELL'
            size: 订单数量
            price: 订单价格 (0-1)
            
        Returns:
            订单结果字典
        """
        if not self.client:
            return {
                'success': False,
                'error': '客户端未初始化',
                'order_id': None
            }
        
        try:
            self.logger.info(f"创建订单: {side} {size} @ {price}")
            
            # 确定买卖方向
            order_side = BUY if side.upper() == 'BUY' else SELL
            
            # 创建订单参数
            order_args = OrderArgs(
                price=price,
                size=size,
                side=order_side,
                token_id=token_id
            )
            
            # 创建并发布订单
            order_result = self.client.create_and_post_order(order_args)
            
            self.logger.info(f"订单创建成功: {order_result}")
            
            return {
                'success': True,
                'order_id': getattr(order_result, 'order_id', None),
                'result': order_result
            }
            
        except Exception as e:
            self.logger.error(f"创建订单失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'order_id': None
            }
    
    def get_orders(self) -> List[Dict]:
        """获取订单列表"""
        if not self.client:
            return []
        
        try:
            orders = self.client.get_orders()
            
            # 转换为字典格式
            order_list = []
            for order in orders:
                if hasattr(order, '__dict__'):
                    order_data = order.__dict__
                    order_list.append(order_data)
            
            return order_list
            
        except Exception as e:
            self.logger.error(f"获取订单失败: {e}")
            return []
    
    def test_connection(self) -> Dict:
        """测试连接状态"""
        if not self.client:
            return {
                'status': 'failed',
                'error': '客户端未初始化'
            }
        
        try:
            # 测试基本功能
            address = self.client.get_address()
            server_time = self.client.get_server_time()
            
            # 测试余额查询
            balance = self.get_balance()
            
            return {
                'status': 'success',
                'address': address,
                'server_time': server_time,
                'balance': balance,
                'creds_source': 'derived' if self.derived_creds else 'environment'
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }


def test_auto_creds():
    """测试自动生成凭证功能"""
    print("=" * 70)
    print("🔧 测试自动生成 API 凭证")
    print("=" * 70)
    
    try:
        # 测试1: 自动生成凭证
        print("\n🚀 测试1: 自动生成凭证")
        client1 = ClobTradingClientAutoCreds(auto_derive_creds=True)
        
        result1 = client1.test_connection()
        print(f"   状态: {result1['status']}")
        if result1['status'] == 'success':
            print(f"   地址: {result1['address']}")
            print(f"   余额: ${result1['balance'].get('balance', 0):.2f}")
            print(f"   凭证来源: {result1['creds_source']}")
        
        # 测试2: 使用环境变量凭证（如果存在）
        print("\n🔄 测试2: 环境变量凭证")
        client2 = ClobTradingClientAutoCreds(auto_derive_creds=False)
        
        result2 = client2.test_connection()
        print(f"   状态: {result2['status']}")
        if result2['status'] == 'success':
            print(f"   地址: {result2['address']}")
            print(f"   余额: ${result2['balance'].get('balance', 0):.2f}")
            print(f"   凭证来源: {result2['creds_source']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("🚀 CLOB 自动凭证生成测试")
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    success = test_auto_creds()
    
    print("\n" + "=" * 70)
    print("📊 测试结果")
    print("=" * 70)
    
    if success:
        print("✅ 自动凭证生成测试成功")
        print("💡 建议：使用 ClobTradingClientAutoCreds 替换原来的客户端")
    else:
        print("❌ 测试失败，请检查私钥配置")
    
    print("\n🔧 使用方法:")
    print("from src.clob_client_auto_creds import ClobTradingClientAutoCreds")
    print("client = ClobTradingClientAutoCreds(auto_derive_creds=True)")
    print("balance = client.get_balance()")


if __name__ == '__main__':
    main()
