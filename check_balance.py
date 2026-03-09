#!/usr/bin/env python3
"""
查询 Polygon 链上 USDC 余额
"""

from web3 import Web3

# 使用 Ankr 公共节点（无需 API Key）
RPC_URL = "https://rpc.ankr.com/polygon"
USDC_CONTRACT = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

# 简化 ABI - 只需要 balanceOf
ABI = [{
    "constant": True,
    "inputs": [{"name": "account", "type": "address"}],
    "name": "balanceOf",
    "outputs": [{"name": "", "type": "uint256"}],
    "payable": False,
    "stateMutability": "view",
    "type": "function"
}]

def get_usdc_balance(address: str) -> float:
    """获取 USDC 余额"""
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    if not w3.is_connected():
        raise Exception("无法连接到 Polygon 网络")
    
    contract = w3.eth.contract(address=USDC_CONTRACT, abi=ABI)
    balance = contract.functions.balanceOf(address).call()
    
    return balance / 1e6  # USDC 有 6 位小数


if __name__ == "__main__":
    # 查询代理地址余额
    proxy_address = "0x13e01f7B26D9227Cd9d306C20985B2FE1FC53a60"
    
    try:
        balance = get_usdc_balance(proxy_address)
        print(f"地址: {proxy_address}")
        print(f"USDC 余额: {balance:.2f} USDC")
    except Exception as e:
        print(f"查询失败: {e}")
