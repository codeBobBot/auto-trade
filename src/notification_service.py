#!/usr/bin/env python3
"""
通用通知服务
支持Telegram等多种通知渠道，为自动交易系统提供实时通知功能
"""

import os
import json
import subprocess
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging
import requests

class NotificationLevel(Enum):
    """通知级别"""
    INFO = "info"
    SUCCESS = "success" 
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class NotificationChannel(Enum):
    """通知渠道"""
    TELEGRAM = "telegram"
    CONSOLE = "console"
    LOG = "log"

@dataclass
class NotificationMessage:
    """通知消息"""
    title: str
    content: str
    level: NotificationLevel = NotificationLevel.INFO
    channel: NotificationChannel = NotificationChannel.TELEGRAM
    timestamp: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}

class NotificationService:
    """通用通知服务"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.enabled_channels = self.config.get('enabled_channels', ['telegram', 'console'])
        self.telegram_config = self.config.get('telegram', {})
        
        # 从环境变量加载Telegram配置
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # 如果配置中有提供，则优先使用配置中的值
        self.bot_token = self.telegram_config.get('bot_token', self.bot_token)
        self.chat_id = self.telegram_config.get('chat_id', self.chat_id)
        
        self.telegram_enabled = 'telegram' in self.enabled_channels and self.bot_token and self.chat_id
        
        # 日志配置
        self.setup_logging()
        
        # 通知历史
        self.notification_history: List[NotificationMessage] = []
        self.max_history = self.config.get('max_history', 100)
        
        print(f"📱 通知服务已初始化")
        print(f"   启用渠道: {', '.join(self.enabled_channels)}")
        print(f"   Telegram: {'✅' if self.telegram_enabled else '❌'}")
        if self.telegram_enabled:
            print(f"   Bot Token: {self.bot_token[:10]}...")
            print(f"   Chat ID: {self.chat_id}")
    
    def setup_logging(self):
        """设置日志"""
        log_level = self.config.get('log_level', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/notifications.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('NotificationService')
        
        # 确保日志目录存在
        os.makedirs('logs', exist_ok=True)
    
    def send_notification(self, message: NotificationMessage) -> bool:
        """
        发送通知
        
        Args:
            message: 通知消息
            
        Returns:
            是否发送成功
        """
        success = True
        
        # 添加到历史
        self.notification_history.append(message)
        if len(self.notification_history) > self.max_history:
            self.notification_history = self.notification_history[-self.max_history:]
        
        # 根据渠道发送
        for channel in self.enabled_channels:
            try:
                if channel == 'telegram':
                    success &= self._send_telegram(message)
                elif channel == 'console':
                    success &= self._send_console(message)
                elif channel == 'log':
                    success &= self._send_log(message)
            except Exception as e:
                self.logger.error(f"发送{channel}通知失败: {e}")
                success = False
        
        return success
    
    def _send_telegram(self, message: NotificationMessage) -> bool:
        """发送Telegram通知"""
        if not self.telegram_enabled:
            self.logger.warning("Telegram未配置，跳过发送")
            return True
        
        try:
            # 格式化消息
            formatted_message = self._format_telegram_message(message)
            
            # 使用Telegram Bot API发送消息
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            payload = {
                'chat_id': self.chat_id,
                'text': formatted_message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if result.get('ok'):
                self.logger.info(f"Telegram通知发送成功: {message.title}")
                return True
            else:
                error_msg = result.get('description', 'Unknown error')
                self.logger.error(f"Telegram通知发送失败: {error_msg}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Telegram网络请求失败: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Telegram通知发送异常: {e}")
            return False
    
    def _send_console(self, message: NotificationMessage) -> bool:
        """发送控制台通知"""
        try:
            icon = self._get_level_icon(message.level)
            timestamp = message.timestamp.strftime('%H:%M:%S')
            
            print(f"\n{icon} [{timestamp}] {message.title}")
            print(f"   {message.content}")
            
            return True
        except Exception as e:
            self.logger.error(f"控制台通知发送失败: {e}")
            return False
    
    def _send_log(self, message: NotificationMessage) -> bool:
        """发送日志通知"""
        try:
            log_level = self._get_log_level(message.level)
            self.logger.log(log_level, f"{message.title}: {message.content}")
            return True
        except Exception as e:
            print(f"日志通知发送失败: {e}")
            return False
    
    def _format_telegram_message(self, message: NotificationMessage) -> str:
        """格式化Telegram消息"""
        level_emoji = self._get_level_emoji(message.level)
        timestamp = message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        formatted = f"""
{level_emoji} <b>{message.title}</b>

{message.content}

<i>🕐 {timestamp}</i>
<i>🤖 Polymarket自动交易系统</i>"""
        
        # 添加元数据
        if message.metadata:
            if 'strategy' in message.metadata:
                formatted += f"\n<i>📊 策略: {message.metadata['strategy']}</i>"
            if 'confidence' in message.metadata:
                formatted += f"\n<i>🎯 置信度: {message.metadata['confidence']:.1%}</i>"
            if 'market' in message.metadata:
                formatted += f"\n<i>📈 市场: {message.metadata['market'][:50]}...</i>"
        
        return formatted.strip()
    
    def _get_level_icon(self, level: NotificationLevel) -> str:
        """获取级别图标"""
        icons = {
            NotificationLevel.INFO: "ℹ️",
            NotificationLevel.SUCCESS: "✅",
            NotificationLevel.WARNING: "⚠️",
            NotificationLevel.ERROR: "❌",
            NotificationLevel.CRITICAL: "🚨"
        }
        return icons.get(level, "📢")
    
    def _get_level_emoji(self, level: NotificationLevel) -> str:
        """获取级别emoji"""
        emojis = {
            NotificationLevel.INFO: "ℹ️",
            NotificationLevel.SUCCESS: "🎉",
            NotificationLevel.WARNING: "⚠️",
            NotificationLevel.ERROR: "❌",
            NotificationLevel.CRITICAL: "🚨"
        }
        return emojis.get(level, "📢")
    
    def _get_log_level(self, level: NotificationLevel) -> int:
        """获取日志级别"""
        levels = {
            NotificationLevel.INFO: logging.INFO,
            NotificationLevel.SUCCESS: logging.INFO,
            NotificationLevel.WARNING: logging.WARNING,
            NotificationLevel.ERROR: logging.ERROR,
            NotificationLevel.CRITICAL: logging.CRITICAL
        }
        return levels.get(level, logging.INFO)
    
    # 便捷方法
    def info(self, title: str, content: str, **kwargs) -> bool:
        """发送信息通知"""
        message = NotificationMessage(title, content, NotificationLevel.INFO, **kwargs)
        return self.send_notification(message)
    
    def success(self, title: str, content: str, **kwargs) -> bool:
        """发送成功通知"""
        message = NotificationMessage(title, content, NotificationLevel.SUCCESS, **kwargs)
        return self.send_notification(message)
    
    def warning(self, title: str, content: str, **kwargs) -> bool:
        """发送警告通知"""
        message = NotificationMessage(title, content, NotificationLevel.WARNING, **kwargs)
        return self.send_notification(message)
    
    def error(self, title: str, content: str, **kwargs) -> bool:
        """发送错误通知"""
        message = NotificationMessage(title, content, NotificationLevel.ERROR, **kwargs)
        return self.send_notification(message)
    
    def critical(self, title: str, content: str, **kwargs) -> bool:
        """发送严重错误通知"""
        message = NotificationMessage(title, content, NotificationLevel.CRITICAL, **kwargs)
        return self.send_notification(message)
    
    # 交易相关通知
    def trade_executed(self, strategy: str, market: str, signal: str, confidence: float, order_id: str = None) -> bool:
        """交易执行通知"""
        title = f"🤖 交易执行 - {strategy}"
        content = f"""信号: {signal}
市场: {market}
置信度: {confidence:.1%}
{f'订单ID: {order_id}' if order_id else ''}"""
        
        return self.success(
            title, content,
            metadata={
                'strategy': strategy,
                'market': market,
                'signal': signal,
                'confidence': confidence,
                'order_id': order_id
            }
        )
    
    def signal_detected(self, strategy: str, market: str, signal: str, confidence: float, market_details: List[Dict] = None) -> bool:
        """信号发现通知"""
        title = f"🎯 信号发现 - {strategy}"
        content = f"""检测到交易信号
信号: {signal}
市场: {market}
置信度: {confidence:.1%}"""
        
        # 添加具体市场详情
        if market_details:
            content += "\n\n📊 相关市场详情:"
            for i, mkt in enumerate(market_details[:5], 1):  # 最多显示5个市场
                content += f"\n{i}. <b>{mkt.get('question', 'N/A')[:40]}...</b>"
                content += f"\n   🆔 ID: {mkt.get('id', 'N/A')[:12]}..."
                content += f"\n   💰 价格: {mkt.get('yes_price', mkt.get('price', 'N/A'))}"
                content += f"\n   💧 流动性: {mkt.get('liquidity', 'N/A'):,} USDC"
                content += f"\n   📈 24h交易量: {mkt.get('volume24hr', 'N/A'):,} USDC"
                if i < len(market_details[:5]):
                    content += "\n"
        
        return self.info(
            title, content,
            metadata={
                'strategy': strategy,
                'market': market,
                'signal': signal,
                'confidence': confidence,
                'markets_count': len(market_details) if market_details else 0
            }
        )
    
    def risk_alert(self, alert_type: str, description: str, level: NotificationLevel = NotificationLevel.WARNING) -> bool:
        """风险预警通知"""
        title = f"⚠️ 风险预警 - {alert_type}"
        return self.send_notification(
            NotificationMessage(title, description, level)
        )
    
    def system_status(self, status: str, details: str = "") -> bool:
        """系统状态通知"""
        title = f"📊 系统状态 - {status}"
        return self.info(title, details)
    
    def daily_summary(self, date: str, stats: Dict[str, Any]) -> bool:
        """每日总结通知"""
        title = f"📈 每日交易总结 - {date}"
        
        content = f"""总交易数: {stats.get('total_trades', 0)}
成功交易: {stats.get('successful_trades', 0)}
总收益: {stats.get('total_return', 0):.2%}
当前仓位: {len(stats.get('current_positions', []))}"""
        
        return self.info(title, content)
    
    def get_notification_stats(self) -> Dict[str, Any]:
        """获取通知统计"""
        total = len(self.notification_history)
        by_level = {}
        by_channel = {}
        
        for notification in self.notification_history:
            level = notification.level.value
            by_level[level] = by_level.get(level, 0) + 1
        
        return {
            'total_notifications': total,
            'by_level': by_level,
            'enabled_channels': self.enabled_channels,
            'telegram_enabled': self.telegram_enabled
        }

# 全局通知服务实例
_notification_service: Optional[NotificationService] = None

def get_notification_service(config: Dict[str, Any] = None) -> NotificationService:
    """获取全局通知服务实例"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService(config)
    return _notification_service

def init_notification_service(config: Dict[str, Any] = None) -> NotificationService:
    """初始化通知服务"""
    global _notification_service
    _notification_service = NotificationService(config)
    return _notification_service
