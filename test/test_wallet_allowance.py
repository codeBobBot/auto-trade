from web3 import Web3

rpc = "https://polygon-mainnet.infura.io/v3/6a59e5fe8c2f4af7876978230e916d41"
web3 = Web3(Web3.HTTPProvider(rpc))

USDC = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")
SPENDER = Web3.to_checksum_address("0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e")
OWNER = Web3.to_checksum_address("0x912c2320F63b631fE3Ef38D914ca102366cdc291")

ERC20_ABI = [{
    "constant": True,
    "inputs": [
        {"name": "_owner","type": "address"},
        {"name": "_spender","type": "address"}
    ],
    "name": "allowance",
    "outputs": [{"name": "","type": "uint256"}],
    "type": "function"
}]

contract = web3.eth.contract(address=USDC, abi=ERC20_ABI)

allowance = contract.functions.allowance(OWNER, SPENDER).call()

print("allowance:", allowance)