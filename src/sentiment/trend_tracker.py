#!/usr/bin/env python3
"""
舆情趋势追踪器
追踪舆情变化趋势，检测异常波动
"""

import os
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
from enum import Enum
import math
from dotenv import load_dotenv

from .analyzers.sentiment_engine import SentimentScore, SentimentLabel

load_dotenv('config/.env')


class TrendDirection(Enum):
    """趋势方向"""
    STRONG_UP = "strong_up"      # 强势上涨
    UP = "up"                     # 上涨
    STABLE = "stable"             # 稳定
    DOWN = "down"                 # 下跌
    STRONG_DOWN = "strong_down"   # 强势下跌


class TrendSignal(Enum):
    """趋势信号"""
    BREAKOUT_UP = "breakout_up"       # 向上突破
    BREAKOUT_DOWN = "breakout_down"   # 向下突破
    REVERSAL_UP = "reversal_up"       # 向上反转
    REVERSAL_DOWN = "reversal_down"   # 向下反转
    ACCELERATION = "acceleration"     # 加速
    DECELERATION = "deceleration"     # 减速
    STABLE = "stable"                 # 稳定
    EXTREME_HIGH = "extreme_high"     # 极端高位
    EXTREME_LOW = "extreme_low"       # 极端低位


@dataclass
class TrendPoint:
    """趋势数据点"""
    timestamp: datetime
    sentiment_score: float
    confidence: float
    volume: int  # 数据量
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'sentiment_score': self.sentiment_score,
            'confidence': self.confidence,
            'volume': self.volume
        }


@dataclass
class TrendAnalysis:
    """趋势分析结果"""
    keyword: str
    current_score: float
    previous_score: float
    change: float
    change_percent: float
    direction: TrendDirection
    signal: TrendSignal
    velocity: float  # 变化速度
    acceleration: float  # 变化加速度
    volatility: float  # 波动率
    history: List[TrendPoint]
    is_anomaly: bool
    anomaly_score: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'keyword': self.keyword,
            'current_score': self.current_score,
            'previous_score': self.previous_score,
            'change': self.change,
            'change_percent': self.change_percent,
            'direction': self.direction.value,
            'signal': self.signal.value,
            'velocity': self.velocity,
            'acceleration': self.acceleration,
            'volatility': self.volatility,
            'is_anomaly': self.is_anomaly,
            'anomaly_score': self.anomaly_score,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class TrendSummary:
    """趋势摘要"""
    keyword: str
    trend: TrendAnalysis
    description: str
    trading_implication: str
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'keyword': self.keyword,
            'trend': self.trend.to_dict(),
            'description': self.description,
            'trading_implication': self.trading_implication,
            'confidence': self.confidence
        }


class TrendTracker:
    """舆情趋势追踪器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # 历史数据存储
        self.history: Dict[str, deque] = {}  # keyword -> deque of TrendPoint
        
        # 配置参数
        self.history_size = self.config.get('history_size', 100)  # 保留历史点数
        self.anomaly_threshold = self.config.get('anomaly_threshold', 2.0)  # 异常检测阈值（标准差）
        self.trend_window = self.config.get('trend_window', 5)  # 趋势计算窗口
        
        # 趋势阈值
        self.direction_thresholds = {
            'strong': 0.3,   # 强趋势阈值
            'normal': 0.1    # 普通趋势阈值
        }
        
        # 数据存储路径
        self.data_dir = self.config.get('data_dir', './data/trends')
        os.makedirs(self.data_dir, exist_ok=True)
    
    def update(self, keyword: str, sentiment_score: float, 
               confidence: float, volume: int = 1) -> TrendAnalysis:
        """
        更新趋势数据
        
        Args:
            keyword: 关键词
            sentiment_score: 情绪分数
            confidence: 置信度
            volume: 数据量
        
        Returns:
            TrendAnalysis: 趋势分析结果
        """
        # 创建新数据点
        point = TrendPoint(
            timestamp=datetime.now(),
            sentiment_score=sentiment_score,
            confidence=confidence,
            volume=volume
        )
        
        # 初始化或更新历史
        if keyword not in self.history:
            self.history[keyword] = deque(maxlen=self.history_size)
        
        history = self.history[keyword]
        previous_score = history[-1].sentiment_score if history else sentiment_score
        
        # 添加新点
        history.append(point)
        
        # 分析趋势
        analysis = self._analyze_trend(keyword, history, previous_score)
        
        # 保存到文件
        self._save_trend_point(keyword, point)
        
        return analysis
    
    def get_trend(self, keyword: str) -> Optional[TrendAnalysis]:
        """获取当前趋势"""
        if keyword not in self.history or not self.history[keyword]:
            return None
        
        history = self.history[keyword]
        previous_score = history[-2].sentiment_score if len(history) > 1 else history[-1].sentiment_score
        
        return self._analyze_trend(keyword, history, previous_score)
    
    def get_history(self, keyword: str, 
                    time_range: Tuple[datetime, datetime] = None) -> List[TrendPoint]:
        """获取历史数据"""
        if keyword not in self.history:
            return []
        
        history = list(self.history[keyword])
        
        if time_range:
            start, end = time_range
            history = [p for p in history if start <= p.timestamp <= end]
        
        return history
    
    def get_summary(self, keyword: str) -> Optional[TrendSummary]:
        """获取趋势摘要"""
        trend = self.get_trend(keyword)
        if not trend:
            return None
        
        # 生成描述
        description = self._generate_description(trend)
        
        # 生成交易建议
        trading_implication = self._generate_trading_implication(trend)
        
        # 计算综合置信度
        confidence = self._calculate_trend_confidence(trend)
        
        return TrendSummary(
            keyword=keyword,
            trend=trend,
            description=description,
            trading_implication=trading_implication,
            confidence=confidence
        )
    
    def detect_anomalies(self, keyword: str) -> List[Dict[str, Any]]:
        """检测异常点"""
        if keyword not in self.history or len(self.history[keyword]) < 5:
            return []
        
        history = list(self.history[keyword])
        scores = [p.sentiment_score for p in history]
        
        # 计算统计量
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std = math.sqrt(variance) if variance > 0 else 0.01
        
        anomalies = []
        for i, point in enumerate(history):
            z_score = abs(point.sentiment_score - mean) / std if std > 0 else 0
            
            if z_score > self.anomaly_threshold:
                anomalies.append({
                    'timestamp': point.timestamp.isoformat(),
                    'score': point.sentiment_score,
                    'z_score': z_score,
                    'type': 'high' if point.sentiment_score > mean else 'low'
                })
        
        return anomalies
    
    def compare_keywords(self, keywords: List[str]) -> Dict[str, Any]:
        """比较多个关键词的趋势"""
        comparisons = {}
        
        for keyword in keywords:
            trend = self.get_trend(keyword)
            if trend:
                comparisons[keyword] = {
                    'current_score': trend.current_score,
                    'change': trend.change,
                    'direction': trend.direction.value,
                    'signal': trend.signal.value
                }
        
        # 排序
        sorted_keywords = sorted(
            comparisons.items(),
            key=lambda x: x[1]['current_score'],
            reverse=True
        )
        
        return {
            'rankings': [{'keyword': k, **v} for k, v in sorted_keywords],
            'timestamp': datetime.now().isoformat()
        }
    
    def _analyze_trend(self, keyword: str, history: deque, 
                       previous_score: float) -> TrendAnalysis:
        """分析趋势"""
        current = history[-1]
        history_list = list(history)
        
        # 基本变化
        change = current.sentiment_score - previous_score
        change_percent = change / abs(previous_score) if previous_score != 0 else 0
        
        # 趋势方向
        direction = self._determine_direction(change)
        
        # 计算速度和加速度
        velocity, acceleration = self._calculate_dynamics(history_list)
        
        # 计算波动率
        volatility = self._calculate_volatility(history_list)
        
        # 检测信号
        signal = self._detect_signal(current.sentiment_score, change, 
                                     velocity, acceleration, volatility)
        
        # 异常检测
        is_anomaly, anomaly_score = self._check_anomaly(history_list)
        
        return TrendAnalysis(
            keyword=keyword,
            current_score=current.sentiment_score,
            previous_score=previous_score,
            change=change,
            change_percent=change_percent,
            direction=direction,
            signal=signal,
            velocity=velocity,
            acceleration=acceleration,
            volatility=volatility,
            history=history_list[-self.trend_window:],
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score
        )
    
    def _determine_direction(self, change: float) -> TrendDirection:
        """确定趋势方向"""
        if change > self.direction_thresholds['strong']:
            return TrendDirection.STRONG_UP
        elif change > self.direction_thresholds['normal']:
            return TrendDirection.UP
        elif change < -self.direction_thresholds['strong']:
            return TrendDirection.STRONG_DOWN
        elif change < -self.direction_thresholds['normal']:
            return TrendDirection.DOWN
        else:
            return TrendDirection.STABLE
    
    def _calculate_dynamics(self, history: List[TrendPoint]) -> Tuple[float, float]:
        """计算速度和加速度"""
        if len(history) < 2:
            return 0.0, 0.0
        
        # 速度：最近变化率
        recent = history[-min(3, len(history)):]
        time_diffs = []
        score_diffs = []
        
        for i in range(1, len(recent)):
            dt = (recent[i].timestamp - recent[i-1].timestamp).total_seconds() / 3600  # 小时
            if dt > 0:
                time_diffs.append(dt)
                score_diffs.append(recent[i].sentiment_score - recent[i-1].sentiment_score)
        
        if not time_diffs:
            return 0.0, 0.0
        
        # 平均速度
        velocities = [ds/dt for ds, dt in zip(score_diffs, time_diffs)]
        velocity = sum(velocities) / len(velocities)
        
        # 加速度：速度变化
        if len(velocities) > 1:
            acceleration = velocities[-1] - velocities[-2]
        else:
            acceleration = 0.0
        
        return velocity, acceleration
    
    def _calculate_volatility(self, history: List[TrendPoint]) -> float:
        """计算波动率"""
        if len(history) < 3:
            return 0.0
        
        scores = [p.sentiment_score for p in history[-10:]]  # 最近10个点
        mean = sum(scores) / len(scores)
        
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        return math.sqrt(variance)
    
    def _detect_signal(self, current: float, change: float, 
                       velocity: float, acceleration: float,
                       volatility: float) -> TrendSignal:
        """检测趋势信号"""
        # 极端值检测
        if current > 0.7:
            return TrendSignal.EXTREME_HIGH
        elif current < -0.7:
            return TrendSignal.EXTREME_LOW
        
        # 突破检测
        if abs(change) > 0.3 and abs(velocity) > 0.1:
            return TrendSignal.BREAKOUT_UP if change > 0 else TrendSignal.BREAKOUT_DOWN
        
        # 反转检测
        if velocity * acceleration < 0:  # 速度和加速度方向相反
            return TrendSignal.REVERSAL_UP if velocity < 0 else TrendSignal.REVERSAL_DOWN
        
        # 加速/减速
        if abs(acceleration) > 0.05:
            return TrendSignal.ACCELERATION if acceleration > 0 else TrendSignal.DECELERATION
        
        return TrendSignal.STABLE
    
    def _check_anomaly(self, history: List[TrendPoint]) -> Tuple[bool, float]:
        """检查是否异常"""
        if len(history) < 5:
            return False, 0.0
        
        scores = [p.sentiment_score for p in history]
        current = scores[-1]
        
        # 计算历史统计
        mean = sum(scores[:-1]) / len(scores[:-1])
        variance = sum((s - mean) ** 2 for s in scores[:-1]) / len(scores[:-1])
        std = math.sqrt(variance) if variance > 0 else 0.01
        
        # Z-score
        z_score = abs(current - mean) / std if std > 0 else 0
        
        is_anomaly = z_score > self.anomaly_threshold
        return is_anomaly, z_score
    
    def _generate_description(self, trend: TrendAnalysis) -> str:
        """生成趋势描述"""
        direction_desc = {
            TrendDirection.STRONG_UP: "强势上涨",
            TrendDirection.UP: "上涨",
            TrendDirection.STABLE: "稳定",
            TrendDirection.DOWN: "下跌",
            TrendDirection.STRONG_DOWN: "强势下跌"
        }
        
        signal_desc = {
            TrendSignal.BREAKOUT_UP: "向上突破",
            TrendSignal.BREAKOUT_DOWN: "向下突破",
            TrendSignal.REVERSAL_UP: "向上反转",
            TrendSignal.REVERSAL_DOWN: "向下反转",
            TrendSignal.ACCELERATION: "趋势加速",
            TrendSignal.DECELERATION: "趋势减速",
            TrendSignal.STABLE: "保持稳定",
            TrendSignal.EXTREME_HIGH: "达到极端高位",
            TrendSignal.EXTREME_LOW: "达到极端低位"
        }
        
        desc = f"舆情{direction_desc[trend.direction]}"
        desc += f"，当前分数{trend.current_score:+.2f}"
        desc += f"，变化{trend.change:+.2f}（{trend.change_percent:+.1%}）"
        desc += f"，信号：{signal_desc[trend.signal]}"
        
        if trend.is_anomaly:
            desc += f"，⚠️ 检测到异常波动（Z-score: {trend.anomaly_score:.2f}）"
        
        return desc
    
    def _generate_trading_implication(self, trend: TrendAnalysis) -> str:
        """生成交易建议"""
        # 基于趋势信号生成建议
        if trend.signal == TrendSignal.EXTREME_HIGH:
            return "情绪极端乐观，可能存在过热风险，建议谨慎或考虑反向操作"
        elif trend.signal == TrendSignal.EXTREME_LOW:
            return "情绪极端悲观，可能存在超卖机会，可考虑逢低布局"
        elif trend.signal == TrendSignal.BREAKOUT_UP:
            return "情绪向上突破，趋势转强，可考虑顺势做多"
        elif trend.signal == TrendSignal.BREAKOUT_DOWN:
            return "情绪向下突破，趋势转弱，可考虑顺势做空或观望"
        elif trend.signal == TrendSignal.REVERSAL_UP:
            return "情绪可能触底反弹，关注反转确认信号"
        elif trend.signal == TrendSignal.REVERSAL_DOWN:
            return "情绪可能见顶回落，注意风险控制"
        elif trend.direction in [TrendDirection.STRONG_UP, TrendDirection.UP]:
            return "情绪向好，趋势向上，可考虑偏多操作"
        elif trend.direction in [TrendDirection.STRONG_DOWN, TrendDirection.DOWN]:
            return "情绪转弱，趋势向下，建议谨慎或偏空操作"
        else:
            return "情绪稳定，无明显趋势，建议观望或轻仓操作"
    
    def _calculate_trend_confidence(self, trend: TrendAnalysis) -> float:
        """计算趋势置信度"""
        # 基于多个因素
        factors = []
        
        # 数据量
        if len(trend.history) >= 5:
            factors.append(0.8)
        elif len(trend.history) >= 3:
            factors.append(0.5)
        else:
            factors.append(0.2)
        
        # 波动率（低波动率 = 高置信度）
        volatility_score = max(0, 1 - trend.volatility * 2)
        factors.append(volatility_score)
        
        # 趋势强度
        strength_score = min(1, abs(trend.change) * 2 + 0.3)
        factors.append(strength_score)
        
        return sum(factors) / len(factors)
    
    def _save_trend_point(self, keyword: str, point: TrendPoint):
        """保存趋势点到文件"""
        try:
            filename = f"{keyword.replace(' ', '_')}_trend.json"
            filepath = os.path.join(self.data_dir, filename)
            
            # 读取现有数据
            data = []
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    data = json.load(f)
            
            # 添加新点
            data.append(point.to_dict())
            
            # 保留最近的数据
            data = data[-self.history_size:]
            
            # 保存
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"保存趋势数据失败: {e}")
    
    def load_history(self, keyword: str) -> bool:
        """从文件加载历史数据"""
        try:
            filename = f"{keyword.replace(' ', '_')}_trend.json"
            filepath = os.path.join(self.data_dir, filename)
            
            if not os.path.exists(filepath):
                return False
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # 转换为 TrendPoint
            points = []
            for item in data:
                point = TrendPoint(
                    timestamp=datetime.fromisoformat(item['timestamp']),
                    sentiment_score=item['sentiment_score'],
                    confidence=item['confidence'],
                    volume=item['volume']
                )
                points.append(point)
            
            # 存入历史
            self.history[keyword] = deque(points, maxlen=self.history_size)
            
            return True
            
        except Exception as e:
            print(f"加载历史数据失败: {e}")
            return False
    
    def get_all_keywords(self) -> List[str]:
        """获取所有追踪的关键词"""
        return list(self.history.keys())
