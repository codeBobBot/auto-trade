# Polymarket 信息套利系统

基于新闻情绪分析和预测市场价格差异的自动化套利系统。

## 架构

```
新闻监控 → 情绪分析 → 套利检测 → 自动下单 → 风险控制
```

## 安装

```bash
# 1. 克隆项目
cd /Users/lsl_mac/.openclaw/workspace/projects/polymarket-arbitrage

# 2. 配置环境
cp config/.env.template config/.env
# 编辑 config/.env 填入您的 API 凭证

# 3. 运行测试
python3 run.py
```

## 配置

编辑 `config/.env`:

```env
POLYMARKET_API_KEY="your_api_key"
POLYMARKET_API_SECRET="your_api_secret"
POLYMARKET_API_PASSPHRASE="your_passphrase"

# 风险控制
MAX_TRADE_AMOUNT_USD=10
MAX_DAILY_LOSS_USD=50
```

## 模块

- `polymarket_client.py` - API 客户端
- `news_monitor.py` - 新闻监控
- `arbitrage_strategy.py` - 套利策略

## 风险警告

⚠️ 交易有风险，请只用可承受损失的资金进行交易。
