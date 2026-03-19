#!/usr/bin/env python3
"""
CLOB 客户端 - 修复签名问题版本（稳定版）
"""

import os
import json
import time
import logging
from decimal import Decimal
from typing import Dict, List, Optional
from dotenv import load_dotenv

from py_clob_client import ClobClient
from py_clob_client.clob_types import ApiCreds, BalanceAllowanceParams, OrderArgs
from py_clob_client.order_builder.constants import BUY, SELL

load_dotenv('config/.env', override=True)

MAX_TRADE_AMOUNT_USD = float(os.getenv('MAX_TRADE_AMOUNT_USD', 10))


class ClobTradingClientAutoCreds:

    def __init__(self):
        self.host = "https://clob.polymarket.com"
        self.chain_id = 137

        self.private_key = os.getenv('POLYGON_PRIVATE_KEY', '')
        if self.private_key and not self.private_key.startswith('0x'):
            self.private_key = '0x' + self.private_key

        self.api_key = os.getenv('POLYMARKET_API_KEY', '')
        self.api_secret = os.getenv('POLYMARKET_API_SECRET', '')
        self.api_passphrase = os.getenv('POLYMARKET_API_PASSPHRASE', '')
        
        # 新增：代理钱包地址（funder address）
        self.funder_address = os.getenv('POLYMARKET_FUNDER_ADDRESS', '')

        self.client = None
        self.wallet_address = None

        self.logger = logging.getLogger(__name__)

        self._init_client()

    # ✅ 核心修复1：使用官方推荐的参数
    def _init_client(self):
        try:
            if self.api_key and self.api_secret and self.api_passphrase:
                self.logger.info("✅ 使用已有 API 凭证")

                creds = ApiCreds(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    api_passphrase=self.api_passphrase
                )

                # 官方推荐：使用 signature_type=2 (GNOSIS_SAFE) 和 funder 参数
                client_params = {
                    'host': self.host,
                    'chain_id': self.chain_id,
                    'key': self.private_key,
                    'creds': creds,
                    'signature_type': 2  # GNOSIS_SAFE（浏览器钱包登录）
                }
                
                # 如果提供了代理钱包地址，添加 funder 参数
                if self.funder_address:
                    client_params['funder'] = self.funder_address
                    self.logger.info(f"✅ 使用代理钱包: {self.funder_address}")
                else:
                    self.logger.warning("⚠️  未设置代理钱包地址，可能影响交易")

                self.client = ClobClient(**client_params)

            else:
                self.logger.info("🔧 首次生成 API 凭证")

                temp_client = ClobClient(
                    host=self.host,
                    chain_id=self.chain_id,
                    key=self.private_key
                )

                creds = temp_client.create_or_derive_api_creds()

                self._save_creds(creds)

                # 官方推荐：使用 signature_type=2 (GNOSIS_SAFE) 和 funder 参数
                client_params = {
                    'host': self.host,
                    'chain_id': self.chain_id,
                    'key': self.private_key,
                    'creds': creds,
                    'signature_type': 2  # GNOSIS_SAFE（浏览器钱包登录）
                }
                
                # 如果提供了代理钱包地址，添加 funder 参数
                if self.funder_address:
                    client_params['funder'] = self.funder_address
                    self.logger.info(f"✅ 使用代理钱包: {self.funder_address}")
                else:
                    self.logger.warning("⚠️  未设置代理钱包地址，可能影响交易")

                self.client = ClobClient(**client_params)

            self.wallet_address = self.client.get_address()
            self.logger.info(f"钱包地址: {self.wallet_address}")

        except Exception as e:
            raise Exception(f"初始化失败: {e}")

    def _save_creds(self, creds: ApiCreds):
        env_file = 'config/.env'
        with open(env_file, 'a') as f:
            f.write(f"\nPOLYMARKET_API_KEY={creds.api_key}")
            f.write(f"\nPOLYMARKET_API_SECRET={creds.api_secret}")
            f.write(f"\nPOLYMARKET_API_PASSPHRASE={creds.api_passphrase}\n")

    # ✅ 核心修复2：Decimal 精度
    def create_order(self, token_id: str, side: str, size: float, price: float):

        if not self.client:
            return {'success': False, 'error': 'client not ready'}

        try:
            # 预检查余额和授权
            balance_check = self._check_balance_and_allowance()
            if not balance_check['sufficient']:
                return {
                    'success': False,
                    'error': balance_check['error'],
                    'balance_info': balance_check['info']
                }

            price = Decimal(str(price))
            size = Decimal(str(size))

            trade_amount = price * size
            if trade_amount > Decimal(str(MAX_TRADE_AMOUNT_USD)):
                size = Decimal(str(MAX_TRADE_AMOUNT_USD)) / price

            order_args = OrderArgs(
                price=float(price),
                size=float(size),
                side=BUY if side.upper() == 'BUY' else SELL,
                token_id=str(token_id)
            )

            result = self.client.create_and_post_order(order_args)

            return {
                'success': True,
                'order_id': getattr(result, 'order_id', None),
                'result': result
            }

        except Exception as e:
            error_msg = str(e)
            
            # 分析具体错误类型
            if "not enough balance" in error_msg.lower():
                return {
                    'success': False,
                    'error': '余额不足',
                    'error_type': 'insufficient_balance',
                    'suggestion': '请充值USDC到钱包地址: ' + self.wallet_address
                }
            elif "allowance" in error_msg.lower():
                return {
                    'success': False,
                    'error': 'CLOB合约授权不足',
                    'error_type': 'insufficient_allowance',
                    'suggestion': '请在Polymarket网站授权CLOB合约进行USDC交易'
                }
            else:
                return {
                    'success': False,
                    'error': error_msg,
                    'error_type': 'unknown'
                }

    def _check_balance_and_allowance(self) -> Dict:
        """检查余额和授权状态"""
        try:
            from py_clob_client.clob_types import AssetType, BalanceAllowanceParams
            params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            balance_info = self.client.get_balance_allowance(params)
            
            if not isinstance(balance_info, dict):
                return {
                    'sufficient': False,
                    'error': '无法获取余额信息',
                    'info': balance_info
                }
            
            # 检查余额
            raw_balance = balance_info.get('balance', '0')
            try:
                balance_int = int(raw_balance)
                balance_usdc = balance_int / 1_000_000
            except (ValueError, TypeError):
                balance_usdc = 0.0
            
            # 检查授权
            allowances = balance_info.get('allowances', {})
            clob_address = '0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E'
            clob_allowance = allowances.get(clob_address, '0')
            
            try:
                allowance_int = int(clob_allowance)
                max_allowance = 115792089237316195423570985008687907853269984665640564039457584007913129639935
            except (ValueError, TypeError):
                allowance_int = 0
            
            # 判断是否充足
            min_required_balance = 5.0  # 最小需要5 USDC
            
            if balance_usdc < min_required_balance:
                return {
                    'sufficient': False,
                    'error': f'余额不足，当前余额: {balance_usdc} USDC，最小需要: {min_required_balance} USDC',
                    'info': {
                        'balance_usdc': balance_usdc,
                        'min_required': min_required_balance,
                        'wallet_address': self.wallet_address
                    }
                }
            
            if allowance_int < max_allowance:
                return {
                    'sufficient': False,
                    'error': 'CLOB合约授权不足',
                    'info': {
                        'allowance': clob_allowance,
                        'max_allowance': max_allowance,
                        'clob_address': clob_address
                    }
                }
            
            return {
                'sufficient': True,
                'info': {
                    'balance_usdc': balance_usdc,
                    'allowance': clob_allowance,
                    'wallet_address': self.wallet_address
                }
            }
            
        except Exception as e:
            return {
                'sufficient': False,
                'error': f'余额检查失败: {str(e)}',
                'info': {'error': str(e)}
            }

    def get_balance(self):

        try:
            from py_clob_client.clob_types import AssetType

            params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            data = self.client.get_balance_allowance(params)

            if isinstance(data, dict) and 'balance' in data:
                balance = float(data['balance']) / 1_000_000
            else:
                balance = 0

            return {'balance': balance}

        except Exception as e:
            return {'error': str(e)}

    def test(self):
        return {
            'address': self.wallet_address,
            'balance': self.get_balance()
        }


if __name__ == "__main__":
    client = ClobTradingClientAutoCreds()
    print(client.test())