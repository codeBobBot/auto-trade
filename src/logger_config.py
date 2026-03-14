#!/usr/bin/env python3
"""
统一日志配置模块
提供结构化的日志记录功能，替代print语句
"""

import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# 创建logs目录
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m',  # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # 添加颜色
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        
        # 格式化消息
        formatted = super().format(record)
        
        # 添加模块名和行号（如果有）
        if hasattr(record, 'module_name'):
            module_info = f" [{record.module_name}:{record.line_number}]"
            formatted = formatted.replace(record.getMessage(), f"{record.getMessage()}{module_info}")
        
        return formatted

def setup_logger(
    name: str,
    level: str = "INFO",
    log_to_file: bool = True,
    log_to_console: bool = True,
    module_name: Optional[str] = None
) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: 是否记录到文件
        log_to_console: 是否输出到控制台
        module_name: 模块名称（用于标识）
    
    Returns:
        配置好的日志记录器
    """
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 创建格式化器
    console_formatter = ColoredFormatter(
        fmt='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # 文件处理器
    if log_to_file:
        # 主日志文件
        log_file = LOG_DIR / f"{name.lower()}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # 错误日志文件
        error_file = LOG_DIR / f"{name.lower()}_errors.log"
        error_handler = logging.FileHandler(error_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        logger.addHandler(error_handler)
    
    # 存储模块信息
    if module_name:
        logger.module_name = module_name
    
    return logger

def get_logger(name: str, module_name: Optional[str] = None) -> logging.Logger:
    """
    获取日志记录器的便捷函数
    
    Args:
        name: 日志记录器名称
        module_name: 模块名称
    
    Returns:
        日志记录器
    """
    return setup_logger(name, module_name=module_name)

# 预定义的日志记录器
def get_strategy_logger(strategy_name: str) -> logging.Logger:
    """获取策略日志记录器"""
    return get_logger(f"strategy_{strategy_name}", f"Strategy:{strategy_name}")

def get_system_logger() -> logging.Logger:
    """获取系统日志记录器"""
    return get_logger("system", "System")

def get_trading_logger() -> logging.Logger:
    """获取交易日志记录器"""
    return get_logger("trading", "Trading")

def get_notification_logger() -> logging.Logger:
    """获取通知日志记录器"""
    return get_logger("notification", "Notification")

def get_telegram_logger() -> logging.Logger:
    """获取Telegram Bot日志记录器"""
    return get_logger("telegram_bot", "TelegramBot")

# 日志装饰器
def log_function_call(logger: logging.Logger):
    """
    装饰器：记录函数调用
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(f"调用函数 {func.__name__}({args}, {kwargs})")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"函数 {func.__name__} 执行成功")
                return result
            except Exception as e:
                logger.error(f"函数 {func.__name__} 执行失败: {e}")
                raise
        return wrapper
    return decorator

# 日志上下文管理器
class LogContext:
    """日志上下文管理器，用于临时更改日志级别"""
    
    def __init__(self, logger: logging.Logger, level: str):
        self.logger = logger
        self.level = getattr(logging, level.upper())
        self.original_level = None
    
    def __enter__(self):
        self.original_level = self.logger.level
        self.logger.setLevel(self.level)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.original_level)

# 示例用法
if __name__ == "__main__":
    # 测试日志配置
    logger = get_logger("test", "TestModule")
    
    logger.debug("这是调试信息")
    logger.info("这是普通信息")
    logger.warning("这是警告信息")
    logger.error("这是错误信息")
    logger.critical("这是严重错误信息")
    
    # 测试策略日志
    strategy_logger = get_strategy_logger("information_advantage")
    strategy_logger.info("策略启动成功")
    
    # 测试日志上下文
    with LogContext(logger, "DEBUG"):
        logger.debug("临时调试信息")
