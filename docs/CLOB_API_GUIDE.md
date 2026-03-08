# CLOB API 申请指南

## 什么是 CLOB API?

CLOB (Central Limit Order Book) API 是 Polymarket 的交易执行接口，允许程序化下单、查询账户、管理订单等操作。

## 申请步骤

### 1. 注册 Polymarket 账号

1. 访问 https://polymarket.com/
2. 点击 "Sign Up" 注册账号
3. 完成邮箱验证
4. 完成身份验证 (KYC)

### 2. 充值账户

1. 进入 Account → Deposit
2. 选择充值方式 (USDC on Polygon/Ethereum)
3. 建议初始充值: $50-100 (用于测试)

### 3. 申请 API Key

1. 登录后访问: https://polymarket.com/account/api
2. 点击 "Create API Key"
3. 选择权限:
   - ✅ Read (读取市场数据)
   - ✅ Trade (执行交易)
   - ❌ Withdraw (建议不开启，安全考虑)
4. 复制生成的:
   - API Key
   - API Secret
   - Passphrase

### 4. 配置到系统

编辑 `config/.env` 文件:

```bash
# CLOB API 配置 (交易执行)
CLOB_API_KEY="your_clob_api_key"
CLOB_API_SECRET="your_clob_api_secret"
CLOB_API_PASSPHRASE="your_clob_passphrase"

# 风险控制 (非常重要!)
MAX_TRADE_AMOUNT_USD=2        # 单笔交易上限 $2
MAX_DAILY_LOSS_USD=5          # 日亏损上限 $5
STOP_LOSS_PERCENTAGE=50       # 止损比例 50%
```

## 权限说明

| 权限 | 说明 | 建议 |
|------|------|------|
| Read | 读取市场数据、账户信息 | ✅ 必须开启 |
| Trade | 创建/取消订单 | ✅ 必须开启 |
| Withdraw | 提取资金 | ❌ 建议关闭 |

## 安全建议

1. **不要分享 API Secret** - 相当于密码
2. **限制 IP 地址** - 在 API 设置中绑定服务器 IP
3. **设置交易限额** - 使用 config/.env 中的风险控制参数
4. **定期轮换 API Key** - 每 3 个月更换一次
5. **监控账户活动** - 定期检查交易记录

## 测试交易

配置完成后，运行测试:

```bash
cd /Users/lsl_mac/.openclaw/workspace/projects/polymarket-arbitrage
source venv/bin/activate
python3 src/clob_client.py
```

## 常见问题

### Q: 为什么需要 KYC?
A: Polymarket 需要遵守美国法规，所有交易者必须完成身份验证。

### Q: 最低充值多少?
A: 建议 $50-100 用于测试，正式运行建议 $500+。

### Q: API 有速率限制吗?
A: 有，默认 100 请求/分钟。如需更高限制，可联系 Polymarket 客服。

### Q: 可以提现吗?
A: 可以，但需要完成 KYC 并绑定银行账户。

## 相关链接

- Polymarket: https://polymarket.com/
- API 文档: https://docs.polymarket.com/
- CLOB API 参考: https://github.com/Polymarket/py-clob-client

---

**⚠️ 风险提示**: 交易有风险，请只用可承受损失的资金进行交易。
