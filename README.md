# Polymarket 信息套利系统

基于新闻情绪分析和预测市场价格差异的自动化套利系统。

## 🎯 系统特性

- **四策略专业模式**: 信息优势、概率套利、跨市场套利、时间套利，统一资金管理
- **Telegram Bot 交互**: 远程查看状态、调整参数、热重启、紧急停止
- **双策略驱动**: 情绪策略 + 价格策略，智能加权组合（自动交易监控版）
- **高级风控**: 仓位管理、止损止盈、熔断机制、实时风险监控
- **实时监控**: Telegram 通知、Bot交互控制、错误告警、健康检查
- **回测框架**: 历史数据回测、性能评估、策略优化
- **健壮架构**: API 重试、异常处理、数据验证
- **智能交易客户端**: 自动API凭证生成、多层token_id获取、增强fallback机制

## 📊 系统架构

```
专业模式(4策略) → 统一策略管理器 → Telegram Bot交互控制
  ↓
自动交易监控 → 双策略(情绪+价格) → Telegram通知
  ↓
新闻监控 → 情绪分析 → 市场数据 → 策略组合 → 风险控制 → 交易执行
```

## 🚀 快速开始

### 1. 安装依赖

```bash
# 克隆项目
git clone <repository_url>
cd polymarket-arbitrage

# 运行部署脚本
./deploy.sh

# 或手动安装
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境

```bash
# 复制配置模板
cp config/.env.template config/.env

# 编辑配置文件
nano config/.env
```

### 3. 运行专业模式（推荐）

```bash
# 模拟模式 - 4策略专业系统
python run_all_strategies.py

# 实盘模式 - 启用Telegram Bot交互控制
python run_all_strategies.py --trade

# 查看系统状态
python run_all_strategies.py --status

# 查看策略信息
python run_all_strategies.py --info
```

### 4. 运行自动交易监控

```bash
# 激活虚拟环境
source venv/bin/activate

# 运行定时监控（模拟模式）
python scheduled_monitor.py

# 运行定时监控（实盘模式）
python scheduled_monitor.py --trade

# 单次扫描
python auto_trade.py

# 运行回测
python src/backtest.py
```

## ⚙️ 配置说明

### 必需配置

```env
# API 凭证
POLYMARKET_API_KEY="your_api_key"
POLYMARKET_API_SECRET="your_api_secret"
POLYGON_PRIVATE_KEY="your_private_key"
TAVILY_API_KEY="your_tavily_key"
```

### 风险控制配置

```env
# 仓位管理
MAX_POSITION_SIZE=0.1          # 单笔最大仓位 10%
MAX_TOTAL_EXPOSURE=0.3         # 总仓位上限 30%

# 损失限制
MAX_DAILY_LOSS_USD=50          # 日损失限制 $50
STOP_LOSS_PERCENTAGE=10        # 止损 10%
TAKE_PROFIT_PERCENTAGE=20      # 止盈 20%
```

### 策略配置

```env
# 策略权重
SENTIMENT_STRATEGY_WEIGHT=0.4  # 情绪策略
PRICE_STRATEGY_WEIGHT=0.6      # 价格策略

# 置信度阈值
MIN_CONFIDENCE=0.3             # 最低置信度
```

### Telegram Bot 交互配置（可选但推荐）

```env
# Telegram Bot Token (从 @BotFather 获取)
TELEGRAM_BOT_TOKEN="your_bot_token"

# Telegram Chat ID (你的用户ID)
TELEGRAM_CHAT_ID="your_chat_id"
```

配置后启动 `run_all_strategies.py` 即可通过 Telegram 远程控制：
- `/status` - 查看实时状态
- `/strategies` - 查看策略信息
- `/set 参数=值` - 动态调整参数
- `/restart` - 热重启策略
- `/emergency` - 紧急停止

## 📁 项目结构

```
polymarket-arbitrage/
├── src/                            # 核心模块
│   ├── unified_strategy_manager.py # 统一策略管理器(4策略)
│   ├── telegram_bot_service.py     # Telegram Bot交互服务
│   ├── notification_service.py     # 通知服务
│   ├── information_advantage_strategy.py  # 信息优势策略
│   ├── probability_arbitrage_strategy.py  # 概率套利策略
│   ├── cross_market_arbitrage_strategy.py # 跨市场套利策略
│   ├── time_arbitrage_strategy.py  # 时间套利策略
│   ├── risk_manager.py             # 风险管理
│   ├── enhanced_sentiment.py      # 增强情绪分析
│   ├── error_handler.py           # 错误处理
│   ├── alert_system.py            # 监控告警
│   ├── backtest.py                # 回测框架
│   ├── gamma_client.py            # Gamma API 客户端
│   ├── clob_client_auto_creds.py  # 智能CLOB交易客户端(自动凭证+增强fallback)
│   ├── tavily_monitor.py          # 新闻监控
│   ├── arbitrage_strategy.py      # 情绪套利策略(简化版)
│   ├── price_strategy.py          # 价格策略(简化版)
│   └── sentiment/                 # 全球舆情模块
├── config/                        # 配置文件
│   ├── .env.template              # 配置模板
│   └── .env                       # 实际配置
├── run_all_strategies.py          # 全策略专业模式(推荐)
├── auto_trade.py                  # 自动交易主程序(简化版)
├── scheduled_monitor.py           # 定时监控
├── test_telegram_notifications.py # Telegram通知测试
├── test_telegram_bot.py           # Telegram Bot测试
├── run.py                         # 测试运行
├── deploy.sh                      # 部署脚本
├── requirements.txt               # 依赖列表
└── README.md                      # 本文档
```

## 🔧 核心模块说明

### 1. 统一策略管理器 (`unified_strategy_manager.py`)

专业模式核心，同时运行4个策略：

- **策略组合**: 
  - 信息优势策略 (35%权重): 利用新闻速度优势，30秒扫描
  - 概率套利策略 (25%权重): 发现市场定价错误，60秒扫描
  - 跨市场套利策略 (20%权重): 利用相关市场价格差异，90秒扫描
  - 时间套利策略 (20%权重): 临近结算时价格偏差，120秒扫描
  
- **智能调度**: 基于优先级和扫描间隔的并行执行
- **资金分配**: 按权重自动分配仓位
- **风险整合**: 统一的风险敞口管理
- **Telegram Bot集成**: 远程控制和监控

### 2. Telegram Bot 服务 (`telegram_bot_service.py`)

交互式远程控制系统：

**基础命令** (所有用户):
- `/start` - 启动Bot并显示帮助
- `/help` - 显示所有命令
- `/status` - 查看实时系统状态(运行时间、资金、收益)
- `/strategies` - 查看4个策略的详细信息
- `/performance` - 查看策略表现统计
- `/positions` - 查看当前持仓
- `/trades` - 查看最近10笔交易历史
- `/risk` - 查看风险状态和指标
- `/config` - 查看系统配置

**管理员命令** (需要权限):
- `/set 参数=值` - 动态调整参数
  - `/set capital=15000` - 修改总资金
  - `/set max_trade=500` - 修改最大单笔交易
  - `/set information_advantage.weight=0.4` - 修改策略权重
  - `/set probability_arbitrage.confidence=0.7` - 修改置信度
- `/restart` - 热重启所有策略
- `/stop` - 停止所有策略
- `/emergency` - 紧急停止所有交易

### 3. 通知服务 (`notification_service.py`)

多级别通知系统：

- **通知级别**: INFO, SUCCESS, WARNING, ERROR, CRITICAL
- **通知渠道**: Telegram Bot、控制台、日志文件
- **交易通知**: 信号发现、交易执行、风险预警
- **系统通知**: 启动、停止、每日总结
- **风险预警**: 情绪极端、异常波动、损失超限

### 4. 风险管理 (`risk_manager.py`)

- **仓位管理**: 凯利公式、固定比例、波动率调整
- **组合优化**: 相关性控制、风险分散
- **止损止盈**: 自动触发、动态调整
- **实时监控**: 日损失限制、最大回撤监控

### 5. 监控告警 (`alert_system.py`)

- **Telegram 通知**: 交易信号、错误告警、每日报告
- **系统监控**: 健康检查、性能追踪
- **告警规则**: 日损失、仓位、错误率

### 6. 回测框架 (`backtest.py`)

- **历史回测**: 时间序列模拟
- **性能指标**: 夏普比率、最大回撤、胜率
- **报告生成**: 文本报告、JSON 数据

### 8. 智能CLOB交易客户端 (`clob_client_auto_creds.py`)

新一代交易客户端，解决所有API调用问题：

- **自动API凭证生成**: 使用`create_or_derive_api_creds`解决401错误
- **增强token_id获取**: 多层fallback机制，从Gamma API智能提取token地址
- **多层fallback保护**: 
  1. 增强的token_id获取（本地数据→缓存→Gamma API）
  2. 备选方法（订单簿→价格API→直接使用market_id）
  3. 最终fallback（直接使用market_id创建订单）
- **智能调试功能**: `debug_market_api()`测试多个端点，`find_token_fields_in_data()`递归查找token字段
- **标准Logger**: 替换所有print语句，支持日志级别和文件输出
- **健壮错误处理**: 详细的错误信息和恢复机制

**核心方法**:
```python
# 自动凭证生成
client = ClobTradingClientAutoCreds(auto_derive_creds=True)

# 增强的token_id获取
token_id = client.get_market_token_id_enhanced(market)

# 多层fallback订单创建
result = client.create_order_with_enhanced_fallback(market, 'BUY', size, price)

# 调试API响应
debug_info = client.debug_market_api(market_id)
```

### 9. 全球舆情模块 (`src/sentiment/`)

- **多源数据采集**: 新闻(Tavily/NewsAPI/GNews)、Twitter/X、Reddit
- **多语言分析**: 支持中英日韩等10+语言，自动翻译
- **趋势追踪**: 趋势方向、速度、加速度、异常检测
- **舆情预警**: 极端情绪、趋势反转、异常波动等预警
- **数据缓存**: 内存缓存 + 持久化存储

## 📈 使用示例

### 智能交易客户端使用

```python
from src.clob_client_auto_creds import ClobTradingClientAutoCreds
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)

# 创建智能客户端（自动生成凭证）
client = ClobTradingClientAutoCreds(auto_derive_creds=True)

# 测试市场数据
market = {
    'id': '1162940',
    'question': 'Will Bitcoin reach $100,000 by end of 2024?'
}

# 方法1: 增强的token_id获取
token_id = client.get_market_token_id_enhanced(market)
if token_id:
    print(f"成功获取token_id: {token_id}")

# 方法2: 多层fallback订单创建
result = client.create_order_with_enhanced_fallback(
    market, 'BUY', 10.0, 0.65
)
if result['success']:
    print(f"订单创建成功: {result['order_id']}")
else:
    print(f"订单失败: {result['error']}")

# 方法3: 调试API响应
debug_info = client.debug_market_api('1162940')
print(f"测试的端点: {debug_info['api_endpoints']}")
print(f"找到的token字段: {debug_info['token_fields_found']}")
```

### 运行定时监控

```bash
# 模拟模式，每小时扫描一次
python scheduled_monitor.py --interval 1

# 实盘模式，最低置信度 0.5
python scheduled_monitor.py --trade --confidence 0.5
```

### 运行回测

```python
from src.backtest import BacktestEngine, simple_strategy
from datetime import datetime

engine = BacktestEngine(initial_capital=1000.0)

result = engine.run_backtest(
    strategy=simple_strategy,
    market_ids=['market_1', 'market_2'],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

print(f"总收益率: {result.total_return:.2%}")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
print(f"最大回撤: {result.max_drawdown:.2%}")
```

### 自定义策略

```python
from src.strategy_manager import StrategyEnsemble

ensemble = StrategyEnsemble()

# 组合多个策略信号
combined_signal = ensemble.ensemble_signals(
    signals=[('sentiment', sentiment_signal), ('price', price_signal)],
    market_data=market_data,
    method='weighted_average'  # 或 'majority_vote', 'unanimous', 'best_signal'
)
```

## 🛡️ 风险警告

⚠️ **重要提示**:

1. 本系统涉及真实资金交易，存在亏损风险
2. 请仅使用可承受损失的资金进行交易
3. 建议先在模拟模式下充分测试
4. 定期检查系统运行状态和风险指标
5. 合理设置止损止盈和仓位限制

## 📊 性能监控

系统提供多种监控方式：

1. **实时日志**: 控制台输出和日志文件
2. **Telegram 通知**: 交易信号和告警推送
3. **Telegram Bot 交互**: 远程查看状态和控制
4. **风险报告**: `risk_manager.get_risk_report()`
5. **策略统计**: `strategy_manager.get_strategy_stats()`
6. **错误统计**: `error_handler.get_error_stats()`

### Telegram 命令示例

```bash
# 查看实时状态
/status

# 输出:
📊 系统状态
运行状态: 🟢 运行中
运行时间: 02:34:12
💰 总资金: $10,000.00
📋 今日交易: 15笔
   • 成功: 12笔 (80%)
   • 总盈亏: +$125.50
🎯 活跃策略: 4/4
```

```bash
# 调整参数示例
/set capital=15000
/set information_advantage.weight=0.4
/set max_trade=500
```

## 🔨 开发路线

### 已完成 ✅

- [x] 四策略专业模式（信息优势、概率套利、跨市场套利、时间套利）
- [x] Telegram Bot 交互式远程控制（13个命令）
- [x] 统一策略管理器（智能调度、资金分配）
- [x] 通用通知服务（Telegram Bot API）
- [x] 双策略系统（情绪 + 价格）
- [x] 高级风险管理
- [x] 策略权重管理
- [x] 增强情绪分析
- [x] 错误处理和重试
- [x] 监控告警系统
- [x] 回测框架
- [x] 全球舆情模块（多源采集、多语言分析、趋势追踪、预警系统）
- [x] 智能CLOB交易客户端（自动凭证生成、多层token_id获取、增强fallback）
- [x] API调用问题修复（401/404/400错误解决）
- [x] Logger标准化（替换print语句）
- [x] Gamma API集成（智能token地址提取）

### 进行中 🚧

- [ ] 机器学习模型集成
- [ ] Web 管理界面
- [ ] 策略参数自动优化

### 计划中 📋

- [ ] 实时数据管道优化
- [ ] 微服务架构重构
- [ ] 高级技术指标集成
- [ ] 多交易所套利扩展
- [ ] 策略回测可视化
- [ ] 移动端APP

### 未来优化 🚀

- **性能优化**: 异步API调用、连接池、缓存策略
- **可观测性**: Prometheus指标、Grafana仪表盘、分布式追踪
- **安全增强**: 密钥管理、API限流、访问审计
- **智能运维**: 异常检测、自动恢复、智能告警降噪

## 📝 更新日志

### v2.2.0 (2026-03-17)

- ✨ 新增智能CLOB交易客户端 (`clob_client_auto_creds.py`)
  - 自动API凭证生成，解决401错误
  - 多层token_id获取机制，解决"无法获取token_id"错误
  - 增强fallback机制，确保交易执行成功率
  - 智能调试功能，自动测试Gamma API端点
  - 标准Logger替换，支持日志级别和文件输出
- 🔧 API调用问题修复
  - 修复401错误：使用`create_or_derive_api_creds`自动生成凭证
  - 修复404错误：正确的token_id提取和API方法调用
  - 修复400错误：clobTokenIds字段解析和token_id格式处理
- 🔍 Gamma API集成
  - 智能token地址提取（支持clobTokenIds、clobTokenId等多种字段）
  - 递归查找token相关字段
  - 多端点测试和fallback机制
- 📝 完善错误处理和日志系统
  - 所有新方法使用标准logger
  - 详细的错误信息和调试数据
  - 多层fallback保护机制

### v2.1.0 (2026-03-14)

- ✨ 新增四策略专业模式 (`run_all_strategies.py`)
  - 信息优势策略、概率套利策略、跨市场套利策略、时间套利策略
  - 统一策略管理器，智能资金分配
  - 支持热重启和动态参数调整
- ✨ 新增 Telegram Bot 交互式远程控制
  - 13个交互命令（状态查询、策略管理、参数调整）
  - 管理员权限控制
  - 紧急停止功能
- ✨ 重构通知服务
  - 支持 Telegram Bot API
  - 多级别通知（INFO/SUCCESS/WARNING/ERROR/CRITICAL）
  - 交易通知、风险预警、系统状态
- 📝 完善文档和测试脚本

### v2.0.0 (2026-03-13)

- ✨ 新增高级风险管理模块
- ✨ 实现策略权重系统
- ✨ 增强情绪分析（时效性、强度）
- ✨ 添加错误处理和熔断机制
- ✨ 集成 Telegram 监控告警
- ✨ 实现回测框架
- 📝 完善配置和文档

## 🔧 故障排除

### 常见问题解决

#### 1. "无法获取token_id"错误

**问题**: 程序报错"无法获取token_id: {'id': '1162940', 'question': ...}"

**解决方案**: 使用新的智能交易客户端
```python
from src.clob_client_auto_creds import ClobTradingClientAutoCreds

# 替换原来的客户端
client = ClobTradingClientAutoCreds(auto_derive_creds=True)

# 使用增强的token_id获取
token_id = client.get_market_token_id_enhanced(market)
```

#### 2. 401 API错误

**问题**: "PolyApiException[status_code=401]"

**解决方案**: 启用自动凭证生成
```python
# 自动生成API凭证
client = ClobTradingClientAutoCreds(auto_derive_creds=True)
```

#### 3. 404 Market Not Found错误

**问题**: "PolyApiException[status_code=404, error_message={'error': 'market not found'}]"

**解决方案**: 使用正确的token地址而不是市场ID
```python
# 使用增强方法获取正确的token_id
token_id = client.get_market_token_id_enhanced(market)
result = client.create_order(token_id, 'BUY', size, price)
```

#### 4. 400 Invalid Token ID错误

**问题**: "PolyApiException[status_code=400, error_message={'error': 'Invalid token id'}]"

**解决方案**: 使用多层fallback机制
```python
# 使用增强fallback自动处理token_id格式
result = client.create_order_with_enhanced_fallback(market, 'BUY', size, price)
```

#### 5. 403 地区限制错误

**问题**: "Trading restricted in your region"

**解决方案**: 这是正常的地区限制，不是代码问题
- 检查Polymarket支持的地区
- 使用VPN或代理服务器
- 仅在支持的地区进行交易

### 调试工具

#### 调试Gamma API响应
```python
# 测试多个API端点并查找token字段
debug_info = client.debug_market_api('1162940')
print(f"找到的token字段: {debug_info['token_fields_found']}")
print(f"最终token_id: {debug_info['final_token_id']}")
```

#### 测试交易连接
```python
# 测试客户端连接和凭证
result = client.test_connection()
print(f"连接状态: {result['status']}")
if result['status'] == 'success':
    print(f"钱包地址: {result['address']}")
    print(f"余额: ${result['balance']:.2f}")
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License
