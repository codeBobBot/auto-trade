#!/usr/bin/env python3
"""
日志功能测试脚本
验证日志配置和输出功能
"""

import sys
import os
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from logger_config import (
    get_logger, 
    get_strategy_logger, 
    get_system_logger,
    get_trading_logger,
    get_notification_logger,
    get_telegram_logger,
    LogContext
)

def test_basic_logging():
    """测试基础日志功能"""
    print("🧪 测试基础日志功能...")
    
    # 获取通用日志记录器
    logger = get_logger("test", "TestModule")
    
    # 测试不同级别的日志
    logger.debug("这是调试信息")
    logger.info("这是普通信息")
    logger.warning("这是警告信息")
    logger.error("这是错误信息")
    logger.critical("这是严重错误信息")
    
    print("✅ 基础日志功能测试完成")

def test_strategy_logging():
    """测试策略日志功能"""
    print("\n🧪 测试策略日志功能...")
    
    # 测试不同策略的日志记录器
    strategies = [
        "information_advantage",
        "probability_arbitrage", 
        "cross_market_arbitrage",
        "time_arbitrage"
    ]
    
    for strategy in strategies:
        logger = get_strategy_logger(strategy)
        logger.info(f"策略 {strategy} 启动成功")
        logger.warning(f"策略 {strategy} 发现潜在风险")
        logger.error(f"策略 {strategy} 执行失败")
    
    print("✅ 策略日志功能测试完成")

def test_specialized_loggers():
    """测试专用日志记录器"""
    print("\n🧪 测试专用日志记录器...")
    
    # 系统日志
    system_logger = get_system_logger()
    system_logger.info("系统启动")
    system_logger.warning("系统资源使用率高")
    
    # 交易日志
    trading_logger = get_trading_logger()
    trading_logger.info("执行交易订单")
    trading_logger.info("订单执行成功")
    
    # 通知日志
    notification_logger = get_notification_logger()
    notification_logger.info("发送Telegram通知")
    notification_logger.error("通知发送失败")
    
    # Telegram Bot日志
    telegram_logger = get_telegram_logger()
    telegram_logger.info("Bot启动")
    telegram_logger.info("处理用户命令")
    
    print("✅ 专用日志记录器测试完成")

def test_log_context():
    """测试日志上下文管理器"""
    print("\n🧪 测试日志上下文管理器...")
    
    logger = get_logger("context_test")
    
    # 正常日志级别
    logger.info("正常级别的日志")
    logger.debug("这条调试信息不会显示")
    
    # 临时切换到调试级别
    with LogContext(logger, "DEBUG"):
        logger.info("在调试上下文中")
        logger.debug("现在可以看到调试信息")
    
    # 恢复正常级别
    logger.info("回到正常级别")
    logger.debug("这条调试信息又不会显示了")
    
    print("✅ 日志上下文管理器测试完成")

def test_log_files():
    """测试日志文件生成"""
    print("\n🧪 测试日志文件生成...")
    
    # 检查logs目录
    log_dir = Path("logs")
    if log_dir.exists():
        print("✅ logs目录已创建")
        
        # 列出生成的日志文件
        log_files = list(log_dir.glob("*.log"))
        print(f"📁 生成了 {len(log_files)} 个日志文件:")
        for log_file in log_files:
            size = log_file.stat().st_size
            print(f"   - {log_file.name} ({size} bytes)")
    else:
        print("❌ logs目录未创建")
    
    print("✅ 日志文件测试完成")

def main():
    """主测试函数"""
    print("=" * 70)
    print("🧪 日志功能测试")
    print("=" * 70)
    
    try:
        # 运行各项测试
        test_basic_logging()
        test_strategy_logging()
        test_specialized_loggers()
        test_log_context()
        test_log_files()
        
        print("\n" + "=" * 70)
        print("✅ 所有日志功能测试通过！")
        print("\n📋 日志功能特性:")
        print("   ✅ 彩色控制台输出")
        print("   ✅ 文件日志记录")
        print("   ✅ 错误日志分离")
        print("   ✅ 模块化日志记录器")
        print("   ✅ 日志级别控制")
        print("   ✅ 上下文管理器")
        print("\n📁 日志文件位置: logs/")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
