#!/usr/bin/env python3
"""
舆情预警管理器
监控舆情变化，触发预警通知
"""

import os
import json
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
from dotenv import load_dotenv

from .analyzers.sentiment_engine import SentimentLabel
from .trend_tracker import TrendSignal, TrendDirection
from ..notification_service import NotificationService, get_notification_service, NotificationLevel

load_dotenv('/Users/lsl_mac/.openclaw/workspace/projects/polymarket-arbitrage/config/.env')


class AlertLevel(Enum):
    """预警级别"""
    INFO = "info"           # 信息
    WARNING = "warning"     # 警告
    CRITICAL = "critical"   # 严重
    EMERGENCY = "emergency" # 紧急


class AlertType(Enum):
    """预警类型"""
    SENTIMENT_EXTREME = "sentiment_extreme"       # 情绪极端
    TREND_REVERSAL = "trend_reversal"             # 趋势反转
    TREND_BREAKOUT = "trend_breakout"             # 趋势突破
    ANOMALY_DETECTED = "anomaly_detected"         # 异常检测
    VOLATILITY_HIGH = "volatility_high"           # 高波动
    SENTIMENT_DIVERGENCE = "sentiment_divergence" # 情绪分歧
    VOLUME_SPIKE = "volume_spike"                 # 流量激增
    THRESHOLD_CROSS = "threshold_cross"           # 阈值穿越


@dataclass
class AlertRule:
    """预警规则"""
    name: str
    alert_type: AlertType
    condition: Callable[[Dict], bool]  # 条件函数
    level: AlertLevel = AlertLevel.WARNING
    enabled: bool = True
    cooldown_minutes: int = 30  # 冷却时间
    last_triggered: datetime = None
    
    def should_trigger(self, data: Dict) -> bool:
        """检查是否应触发"""
        if not self.enabled:
            return False
        
        # 检查冷却时间
        if self.last_triggered:
            elapsed = (datetime.now() - self.last_triggered).total_seconds() / 60
            if elapsed < self.cooldown_minutes:
                return False
        
        return self.condition(data)


@dataclass
class Alert:
    """预警"""
    alert_id: str
    alert_type: AlertType
    level: AlertLevel
    keyword: str
    title: str
    message: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'alert_type': self.alert_type.value,
            'level': self.level.value,
            'keyword': self.keyword,
            'title': self.title,
            'message': self.message,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'acknowledged': self.acknowledged
        }


class SentimentAlertManager:
    """舆情预警管理器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # 初始化通知服务
        self.notification_service = get_notification_service({
            'enabled_channels': ['telegram', 'console'],
            'telegram': {
                'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
                'chat_id': os.getenv('TELEGRAM_CHAT_ID')
            }
        })
        
        # 预警规则
        self.rules: Dict[str, AlertRule] = {}
        
        # 预警历史
        self.alert_history: List[Alert] = []
        self.max_history = self.config.get('max_history', 100)
        
        # 回调函数
        self.callbacks: List[Callable[[Alert], None]] = []
        
        # 预警阈值配置
        self.thresholds = {
            'extreme_sentiment': 0.7,      # 极端情绪阈值
            'high_volatility': 0.3,        # 高波动阈值
            'anomaly_zscore': 2.0,         # 异常 Z-score 阈值
            'volume_spike_ratio': 3.0,     # 流量激增比例
            'trend_change': 0.2            # 趋势变化阈值
        }
        
        # 初始化默认规则
        self._init_default_rules()
        
        # 数据存储
        self.data_dir = self.config.get('data_dir', './data/alerts')
        os.makedirs(self.data_dir, exist_ok=True)
    
    def _init_default_rules(self):
        """初始化默认预警规则"""
        # 极端情绪预警
        self.add_rule(AlertRule(
            name="extreme_bullish",
            alert_type=AlertType.SENTIMENT_EXTREME,
            condition=lambda d: d.get('sentiment_score', 0) > self.thresholds['extreme_sentiment'],
            level=AlertLevel.WARNING,
            cooldown_minutes=60
        ))
        
        self.add_rule(AlertRule(
            name="extreme_bearish",
            alert_type=AlertType.SENTIMENT_EXTREME,
            condition=lambda d: d.get('sentiment_score', 0) < -self.thresholds['extreme_sentiment'],
            level=AlertLevel.WARNING,
            cooldown_minutes=60
        ))
        
        # 趋势反转预警
        self.add_rule(AlertRule(
            name="trend_reversal_up",
            alert_type=AlertType.TREND_REVERSAL,
            condition=lambda d: d.get('signal') == TrendSignal.REVERSAL_UP.value,
            level=AlertLevel.INFO,
            cooldown_minutes=30
        ))
        
        self.add_rule(AlertRule(
            name="trend_reversal_down",
            alert_type=AlertType.TREND_REVERSAL,
            condition=lambda d: d.get('signal') == TrendSignal.REVERSAL_DOWN.value,
            level=AlertLevel.WARNING,
            cooldown_minutes=30
        ))
        
        # 趋势突破预警
        self.add_rule(AlertRule(
            name="breakout_up",
            alert_type=AlertType.TREND_BREAKOUT,
            condition=lambda d: d.get('signal') == TrendSignal.BREAKOUT_UP.value,
            level=AlertLevel.INFO,
            cooldown_minutes=15
        ))
        
        self.add_rule(AlertRule(
            name="breakout_down",
            alert_type=AlertType.TREND_BREAKOUT,
            condition=lambda d: d.get('signal') == TrendSignal.BREAKOUT_DOWN.value,
            level=AlertLevel.WARNING,
            cooldown_minutes=15
        ))
        
        # 异常检测预警
        self.add_rule(AlertRule(
            name="anomaly_detected",
            alert_type=AlertType.ANOMALY_DETECTED,
            condition=lambda d: d.get('is_anomaly', False) and d.get('anomaly_score', 0) > self.thresholds['anomaly_zscore'],
            level=AlertLevel.CRITICAL,
            cooldown_minutes=10
        ))
        
        # 高波动预警
        self.add_rule(AlertRule(
            name="high_volatility",
            alert_type=AlertType.VOLATILITY_HIGH,
            condition=lambda d: d.get('volatility', 0) > self.thresholds['high_volatility'],
            level=AlertLevel.WARNING,
            cooldown_minutes=60
        ))
    
    def add_rule(self, rule: AlertRule):
        """添加预警规则"""
        self.rules[rule.name] = rule
    
    def remove_rule(self, rule_name: str):
        """移除预警规则"""
        if rule_name in self.rules:
            del self.rules[rule_name]
    
    def enable_rule(self, rule_name: str, enabled: bool = True):
        """启用/禁用规则"""
        if rule_name in self.rules:
            self.rules[rule_name].enabled = enabled
    
    def register_callback(self, callback: Callable[[Alert], None]):
        """注册预警回调函数"""
        self.callbacks.append(callback)
    
    def check(self, keyword: str, data: Dict[str, Any]) -> List[Alert]:
        """
        检查预警条件
        
        Args:
            keyword: 关键词
            data: 检查数据，包含 sentiment_score, signal, volatility 等
        
        Returns:
            触发的预警列表
        """
        triggered_alerts = []
        
        for rule_name, rule in self.rules.items():
            if rule.should_trigger(data):
                alert = self._create_alert(keyword, rule, data)
                triggered_alerts.append(alert)
                
                # 更新规则触发时间
                rule.last_triggered = datetime.now()
                
                # 执行回调
                for callback in self.callbacks:
                    try:
                        callback(alert)
                    except Exception as e:
                        print(f"预警回调执行失败: {e}")
        
        # 添加到历史
        self.alert_history.extend(triggered_alerts)
        
        # 限制历史大小
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]
        
        # 发送通知
        for alert in triggered_alerts:
            self._send_alert_notification(alert)
        
        # 保存预警
        for alert in triggered_alerts:
            self._save_alert(alert)
        
        return triggered_alerts
    
    def _create_alert(self, keyword: str, rule: AlertRule, data: Dict) -> Alert:
        """创建预警"""
        alert_id = f"{rule.name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        title, message = self._generate_alert_content(rule, keyword, data)
        
        return Alert(
            alert_id=alert_id,
            alert_type=rule.alert_type,
            level=rule.level,
            keyword=keyword,
            title=title,
            message=message,
            data=data
        )
    
    def _generate_alert_content(self, rule: AlertRule, keyword: str, data: Dict) -> tuple:
        """生成预警标题和消息"""
        score = data.get('sentiment_score', 0)
        signal = data.get('signal', 'stable')
        volatility = data.get('volatility', 0)
        
        templates = {
            AlertType.SENTIMENT_EXTREME: {
                'title': f"⚠️ 情绪极端预警: {keyword}",
                'message': f"关键词 '{keyword}' 情绪达到极端水平（分数: {score:+.2f}），请关注潜在风险。"
            },
            AlertType.TREND_REVERSAL: {
                'title': f"🔄 趋势反转预警: {keyword}",
                'message': f"关键词 '{keyword}' 检测到趋势反转信号（{signal}），当前分数: {score:+.2f}。"
            },
            AlertType.TREND_BREAKOUT: {
                'title': f"🚀 趋势突破预警: {keyword}",
                'message': f"关键词 '{keyword}' 检测到趋势突破（{signal}），当前分数: {score:+.2f}。"
            },
            AlertType.ANOMALY_DETECTED: {
                'title': f"🚨 异常波动预警: {keyword}",
                'message': f"关键词 '{keyword}' 检测到异常波动（Z-score: {data.get('anomaly_score', 0):.2f}），请立即关注！"
            },
            AlertType.VOLATILITY_HIGH: {
                'title': f"📊 高波动预警: {keyword}",
                'message': f"关键词 '{keyword}' 波动率异常升高（{volatility:.2f}），市场可能存在不确定性。"
            }
        }
        
        template = templates.get(rule.alert_type, {
            'title': f"📢 预警: {keyword}",
            'message': f"关键词 '{keyword}' 触发预警规则 '{rule.name}'。"
        })
        
        return template['title'], template['message']
    
    def get_active_alerts(self, level: AlertLevel = None) -> List[Alert]:
        """获取未确认的预警"""
        alerts = [a for a in self.alert_history if not a.acknowledged]
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        return alerts
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认预警"""
        for alert in self.alert_history:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False
    
    def _send_alert_notification(self, alert: Alert):
        """发送预警通知"""
        try:
            # 映射预警级别到通知级别
            level_mapping = {
                AlertLevel.INFO: NotificationLevel.INFO,
                AlertLevel.WARNING: NotificationLevel.WARNING,
                AlertLevel.CRITICAL: NotificationLevel.ERROR,
                AlertLevel.EMERGENCY: NotificationLevel.CRITICAL
            }
            
            notification_level = level_mapping.get(alert.level, NotificationLevel.WARNING)
            
            # 发送风险预警通知
            self.notification_service.risk_alert(
                alert_type=alert.alert_type.value,
                description=alert.message,
                level=notification_level
            )
            
        except Exception as e:
            print(f"发送预警通知失败: {e}")
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """获取预警统计"""
        total = len(self.alert_history)
        by_level = defaultdict(int)
        by_type = defaultdict(int)
        by_keyword = defaultdict(int)
        
        for alert in self.alert_history:
            by_level[alert.level.value] += 1
            by_type[alert.alert_type.value] += 1
            by_keyword[alert.keyword] += 1
        
        return {
            'total_alerts': total,
            'unacknowledged': len([a for a in self.alert_history if not a.acknowledged]),
            'by_level': dict(by_level),
            'by_type': dict(by_type),
            'by_keyword': dict(by_keyword),
            'active_rules': len([r for r in self.rules.values() if r.enabled])
        }
    
    def _save_alert(self, alert: Alert):
        """保存预警到文件"""
        try:
            filename = f"alerts_{datetime.now().strftime('%Y%m%d')}.json"
            filepath = os.path.join(self.data_dir, filename)
            
            # 读取现有数据
            alerts_data = []
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    alerts_data = json.load(f)
            
            # 添加新预警
            alerts_data.append(alert.to_dict())
            
            # 保存
            with open(filepath, 'w') as f:
                json.dump(alerts_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"保存预警失败: {e}")
    
    def load_alerts(self, date: datetime = None) -> List[Alert]:
        """加载指定日期的预警"""
        date = date or datetime.now()
        filename = f"alerts_{date.strftime('%Y%m%d')}.json"
        filepath = os.path.join(self.data_dir, filename)
        
        if not os.path.exists(filepath):
            return []
        
        try:
            with open(filepath, 'r') as f:
                alerts_data = json.load(f)
            
            alerts = []
            for item in alerts_data:
                alert = Alert(
                    alert_id=item['alert_id'],
                    alert_type=AlertType(item['alert_type']),
                    level=AlertLevel(item['level']),
                    keyword=item['keyword'],
                    title=item['title'],
                    message=item['message'],
                    data=item['data'],
                    timestamp=datetime.fromisoformat(item['timestamp']),
                    acknowledged=item['acknowledged']
                )
                alerts.append(alert)
            
            return alerts
            
        except Exception as e:
            print(f"加载预警失败: {e}")
            return []
    
    def clear_history(self, before: datetime = None):
        """清理历史预警"""
        if before:
            self.alert_history = [a for a in self.alert_history if a.timestamp >= before]
        else:
            self.alert_history.clear()
    
    def update_thresholds(self, thresholds: Dict[str, float]):
        """更新预警阈值"""
        self.thresholds.update(thresholds)
    
    def get_thresholds(self) -> Dict[str, float]:
        """获取当前阈值"""
        return self.thresholds.copy()
