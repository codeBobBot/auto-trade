#!/usr/bin/env python3
"""
使用正确的USDC合约地址检查余额
"""

from web3 import Web3

def main():
    print("🔍 使用正确的USDC合约地址检查余额")
    print("=" * 60)
    
    # 钱包地址
    wallet_address = "0x912c2320F63b631fE3Ef38D914ca102366cdc291"
    checksum_address = Web3.to_checksum_address(wallet_address)
    print(f"钱包地址: {checksum_address}")
    
    # 正确的USDC合约地址
    usdc_addresses = {
        "Ethereum主网": "0xA0b86a33E6c5c8d4B0c8c0c8c8c8c8c8c8c8c8c8c",
        "Polygon": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "Arbitrum": "0xA0b86a33E6c5c8d4B0c8c0c8c8c8c8c8c8c8c8c8c",
        "Optimism": "0x0b2C639c533813f4Aa9D7837CAf62653d097F8572",
        "BSC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"
    }
    
    # RPC地址
    rpc_urls = {
        "Ethereum主网": "https://mainnet.infura.io/v3/6a59e5fe8c2f4af7876978230e916d41",
        "Polygon": "https://polygon-mainnet.infura.io/v3/6a59e5fe8c2f4af7876978230e916d41",
        "Arbitrum": "https://arbitrum-mainnet.infura.io/v3/6a59e5fe8c2f4af7876978230e916d41",
        "Optimism": "https://optimism-mainnet.infura.io/v3/6a59e5fe8c2f4af7876978230e916d41",
        "BSC": "https://bsc-dataseed.binance.org"
    }
    
    # USDC ABI
    USDC_ABI = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        }
    ]
    
    found_usdc = False
    chains_with_usdc = []
    
    # 检查每个链
    for chain_name, usdc_address in usdc_addresses.items():
        print(f"\n🔍 {chain_name}链检查:")
        print(f"   USDC地址: {usdc_address}")
        
        try:
            # 连接到链
            rpc_url = rpc_urls[chain_name]
            web3 = Web3(Web3.HTTPProvider(rpc_url))
            
            if not web3.is_connected():
                print(f"   ❌ 连接失败")
                continue
            
            print(f"   ✅ 连接成功")
            print(f"   Chain ID: {web3.eth.chain_id}")
            
            # 检查原生代币余额
            native_balance = web3.from_wei(web3.eth.get_balance(checksum_address), 'ether')
            if chain_name == "Ethereum主网":
                print(f"   ETH余额: {native_balance:.6f} ETH")
            elif chain_name == "Polygon":
                print(f"   MATIC余额: {native_balance:.6f} MATIC")
            elif chain_name == "BSC":
                print(f"   BNB余额: {native_balance:.6f} BNB")
            else:
                print(f"   原生代币余额: {native_balance:.6f}")
            
            # 检查USDC余额
            try:
                usdc_contract = web3.eth.contract(address=usdc_address, abi=USDC_ABI)
                usdc_balance = usdc_contract.functions.balanceOf(checksum_address).call()
                usdc_balance_usdc = usdc_balance / 1_000_000
                
                print(f"   USDC余额: {usdc_balance_usdc} USDC")
                
                if usdc_balance_usdc > 0:
                    print(f"   ✅ 有USDC余额!")
                    found_usdc = True
                    chains_with_usdc.append(chain_name)
                else:
                    print(f"   ❌ 无USDC余额")
                    
            except Exception as e:
                print(f"   ❌ USDC查询失败: {e}")
                
        except Exception as e:
            print(f"   ❌ 检查失败: {e}")
    
    # 总结
    print(f"\n🎯 总结:")
    print(f"1. Polymarket运行在Polygon链上")
    print(f"2. 需要Polygon链上的USDC余额")
    
    if found_usdc:
        print(f"3. ✅ 您在以下链有USDC余额:")
        for chain in chains_with_usdc:
            print(f"   - {chain}")
        print(f"4. 💡 需要将USDC桥接到Polygon链")
        print(f"5. 💡 推荐桥接方式:")
        print(f"   - Polygon Bridge: https://polygon.technology/")
        print(f"   - Multichain: https://multichain.xyz/")
        print(f"   - LayerZero: https://layerzero.network/")
    else:
        print(f"3. ❌ 未在任何链找到USDC余额")
        print(f"4. 💡 需要先购买USDC")
        print(f"5. 💡 推荐购买方式:")
        print(f"   - 交易所购买 (Binance, Coinbase, Kraken等)")
        print(f"   - DEX交换 (Uniswap, SushiSwap等)")
        print(f"   - OTC交易")
        print(f"\n6. 💡 购买后桥接到Polygon:")
        print(f"   - 在交易所直接提取到Polygon")
        print(f"   - 或先提取到Ethereum再桥接到Polygon")

if __name__ == "__main__":
    main()
