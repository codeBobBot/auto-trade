#!/usr/bin/env python3
"""
CLOB 客户端 - 自动生成 API 凭证
使用 create_or_derive_api_creds 解决 401 问题
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

# 导入官方 SDK
from py_clob_client import ClobClient
from py_clob_client.clob_types import ApiCreds, BalanceAllowanceParams

load_dotenv('/Users/lsl_mac/.openclaw/workspace/projects/polymarket-arbitrage/config/.env', override=True)


class ClobTradingClientAutoCreds:
    """CLOB 交易客户端 - 自动生成 API 凭证"""
    
    def __init__(self, auto_derive_creds: bool = True):
        # API 配置
        self.host = "https://clob.polymarket.com"
        self.chain_id = 137  # Polygon
        self.signature_type = 2  # EIP712
        self.auto_derive_creds = auto_derive_creds
        
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
            env_file = '/Users/lsl_mac/.openclaw/workspace/projects/polymarket-arbitrage/config/.env'
            
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
            print(f"❌ 获取订单失败: {e}")
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
