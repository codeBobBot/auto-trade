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

        self.client = None
        self.wallet_address = None

        self.logger = logging.getLogger(__name__)

        self._init_client()

    # ✅ 核心修复1：不再强制 signature_type
    def _init_client(self):
        try:
            if self.api_key and self.api_secret and self.api_passphrase:
                self.logger.info("✅ 使用已有 API 凭证")

                creds = ApiCreds(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    api_passphrase=self.api_passphrase
                )

                self.client = ClobClient(
                    host=self.host,
                    chain_id=self.chain_id,
                    key=self.private_key,
                    creds=creds
                )

            else:
                self.logger.info("🔧 首次生成 API 凭证")

                temp_client = ClobClient(
                    host=self.host,
                    chain_id=self.chain_id,
                    key=self.private_key
                )

                creds = temp_client.create_or_derive_api_creds()

                self._save_creds(creds)

                self.client = ClobClient(
                    host=self.host,
                    chain_id=self.chain_id,
                    key=self.private_key,
                    creds=creds
                )

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
            return {
                'success': False,
                'error': str(e)
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