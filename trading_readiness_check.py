#!/usr/bin/env python3
"""
实盘交易准备检查
验证系统是否准备好进行真实交易
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv('config/.env')

def check_api_configuration():
    """检查 API 配置"""
    print("\n" + "="*70)
    print("🔑 API 配置检查")
    print("="*70)
    
    required_apis = {
        'POLYMARKET_API_KEY': 'Polymarket API Key',
        'POLYMARKET_API_SECRET': 'Polymarket API Secret', 
        'POLYMARKET_API_PASSPHRASE': 'Polymarket API Passphrase',
        'POLYGON_PRIVATE_KEY': 'Polygon 私钥（交易签名）',
        'TAVILY_API_KEY': 'Tavily API Key（新闻搜索）'
    }
    
    optional_apis = {
        'NEWSAPI_KEY': 'NewsAPI Key（可选新闻源）',
        'TWITTER_BEARER_TOKEN': 'Twitter Bearer Token（可选）',
        'REDDIT_CLIENT_ID': 'Reddit Client ID（可选）',
        'GOOGLE_TRANSLATE_API_KEY': 'Google Translate API Key（多语言）'
    }
    
    missing_required = []
    missing_optional = []
    
    print("\n必需 API:")
    for key, desc in required_apis.items():
        value = os.getenv(key)
        if value and value != 'your_api_key_here':
            print(f"✅ {desc}: 已配置")
        else:
            print(f"❌ {desc}: 未配置")
            missing_required.append(key)
    
    print("\n可选 API:")
    for key, desc in optional_apis.items():
        value = os.getenv(key)
        if value and value != 'your_api_key_here':
            print(f"✅ {desc}: 已配置")
        else:
            print(f"⚠️  {desc}: 未配置（可选）")
            missing_optional.append(key)
    
    return len(missing_required) == 0, missing_required, missing_optional

def check_risk_configuration():
    """检查风险控制配置"""
    print("\n" + "="*70)
    print("⚠️ 风险控制配置")
    print("="*70)
    
    risk_configs = {
        'MAX_POSITION_SIZE': float(os.getenv('MAX_POSITION_SIZE', 0.1)),
        'MAX_TOTAL_EXPOSURE': float(os.getenv('MAX_TOTAL_EXPOSURE', 0.3)),
        'MAX_DAILY_LOSS_USD': float(os.getenv('MAX_DAILY_LOSS_USD', 50)),
        'STOP_LOSS_PERCENTAGE': float(os.getenv('STOP_LOSS_PERCENTAGE', 10)),
        'TAKE_PROFIT_PERCENTAGE': float(os.getenv('TAKE_PROFIT_PERCENTAGE', 20))
    }
    
    print("\n当前风险设置:")
    print(f"📊 单笔最大仓位: {risk_configs['MAX_POSITION_SIZE']:.1%}")
    print(f"📊 总仓位上限: {risk_configs['MAX_TOTAL_EXPOSURE']:.1%}")
    print(f"💰 日损失限制: ${risk_configs['MAX_DAILY_LOSS_USD']}")
    print(f"📉 止损百分比: {risk_configs['STOP_LOSS_PERCENTAGE']:.1%}")
    print(f"📈 止盈百分比: {risk_configs['TAKE_PROFIT_PERCENTAGE']:.1%}")
    
    # 风险检查
    warnings = []
    if risk_configs['MAX_POSITION_SIZE'] > 0.2:
        warnings.append("单笔仓位过高，建议不超过 20%")
    if risk_configs['MAX_TOTAL_EXPOSURE'] > 0.5:
        warnings.append("总仓位过高，建议不超过 50%")
    if risk_configs['MAX_DAILY_LOSS_USD'] > 100:
        warnings.append("日损失限制过高，建议设置更严格的限制")
    
    if warnings:
        print("\n⚠️ 风险警告:")
        for warning in warnings:
            print(f"   - {warning}")
    else:
        print("\n✅ 风险配置合理")
    
    return len(warnings) == 0

def test_system_components():
    """测试系统组件"""
    print("\n" + "="*70)
    print("🔧 系统组件测试")
    print("="*70)
    
    components = {}
    
    # 测试基础模块
    try:
        from src.sentiment_service import GlobalSentimentService
        service = GlobalSentimentService()
        health = service.health_check()
        components['舆情模块'] = all(health.values())
        print(f"✅ 舆情模块: {'正常' if all(health.values()) else '部分异常'}")
    except Exception as e:
        components['舆情模块'] = False
        print(f"❌ 舆情模块: 加载失败 ({e})")
    
    # 测试交易模块
    try:
        from src.clob_client_auto_creds import ClobTradingClientAutoCreds
        executor = ClobTradingClientAutoCreds()
        components['交易执行器'] = True
        print("✅ 交易执行器: 正常")
    except Exception as e:
        components['交易执行器'] = False
        print(f"❌ 交易执行器: {e}")
    
    # 测试风险管理
    try:
        from src.risk_manager import RiskManager
        risk_manager = RiskManager()
        components['风险管理'] = True
        print("✅ 风险管理: 正常")
    except Exception as e:
        components['风险管理'] = False
        print(f"❌ 风险管理: {e}")
    
    return components

def generate_trading_plan():
    """生成交易计划"""
    print("\n" + "="*70)
    print("📋 推荐交易计划")
    print("="*70)
    
    print("""
1. 🚀 启动阶段（第1周）
   - 模拟模式运行，验证策略表现
   - 监控系统稳定性
   - 调整参数优化策略

2. 📊 小资金测试（第2周）
   - 启用实盘模式，但限制单笔金额 $5
   - 严格风险控制，日损失限制 $20
   - 记录每笔交易，分析表现

3. 🔄 逐步扩大（第3-4周）
   - 根据表现调整仓位大小
   - 优化置信度阈值
   - 完善预警机制

4. 🚀 正常运行（第5周起）
   - 根据回测结果设置最终参数
   - 启用完整风险管理
   - 定期评估和调整
    """)

def main():
    """主检查函数"""
    print("🔍 Polymarket 实盘交易准备检查")
    print(f"⏰ 检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. API 配置检查
    api_ready, missing_required, missing_optional = check_api_configuration()
    
    # 2. 风险配置检查
    risk_ready = check_risk_configuration()
    
    # 3. 系统组件测试
    components = test_system_components()
    
    # 4. 总体评估
    print("\n" + "="*70)
    print("📊 总体评估")
    print("="*70)
    
    ready_score = 0
    total_checks = 4
    
    if api_ready:
        ready_score += 1
        print("✅ API 配置: 完整")
    else:
        print(f"❌ API 配置: 缺少 {len(missing_required)} 个必需配置")
        print(f"   缺失: {', '.join(missing_required)}")
    
    if risk_ready:
        ready_score += 1
        print("✅ 风险配置: 合理")
    else:
        print("⚠️ 风险配置: 需要调整")
    
    if components.get('舆情模块', False):
        ready_score += 1
        print("✅ 舆情模块: 正常")
    else:
        print("❌ 舆情模块: 异常")
    
    if components.get('交易执行器', False):
        ready_score += 1
        print("✅ 交易执行器: 正常")
    else:
        print("❌ 交易执行器: 异常")
    
    # 5. 准备度评估
    print(f"\n📈 准备度: {ready_score}/{total_checks} ({ready_score/total_checks:.0%})")
    
    if ready_score == total_checks:
        print("\n🎉 恭喜！系统已准备好进行实盘交易")
        print("\n📋 执行流程:")
        print_execution_flow()
        generate_trading_plan()
        
    elif ready_score >= 3:
        print("\n⚠️ 系统基本准备就绪，但建议先完善配置")
        print("\n📋 建议执行流程:")
        print_execution_flow(simulation_only=True)
        
    else:
        print("\n❌ 系统尚未准备好实盘交易")
        print("\n🔧 请完成以下配置后再试:")
        if not api_ready:
            print("   - 配置必需的 API 密钥")
        if not risk_ready:
            print("   - 调整风险控制参数")
        if not components.get('舆情模块', False):
            print("   - 修复舆情模块")
        if not components.get('交易执行器', False):
            print("   - 配置交易执行器")

def print_execution_flow(simulation_only=False):
    """打印执行流程"""
    mode = "模拟" if simulation_only else "实盘"
    
    print(f"""
{mode}交易执行流程:

1. 📡 数据采集
   ├── 新闻数据 (Tavily API)
   ├── 市场数据 (Polymarket API)
   └── 社交媒体 (Twitter/Reddit)

2. 🧠 情绪分析
   ├── 多源数据融合
   ├── 多语言处理
   └── 情绪分数计算

3. 📊 策略决策
   ├── 情绪策略 (权重 40%)
   ├── 价格策略 (权重 60%)
   └── 综合信号生成

4. ⚖️ 风险控制
   ├── 仓位大小计算
   ├── 止损止盈设置
   └── 相关性检查

5. 💰 交易执行
   ├── 信号验证
   ├── 订单提交
   └── 执行确认

6. 📈 监控告警
   ├── 实时监控
   ├── 异常预警
   └── 性能追踪

启动命令:
python scheduled_monitor.py {"--trade" if not simulation_only else ""} --confidence 0.5
    """)

if __name__ == '__main__':
    main()
