#!/usr/bin/env python3
"""
多语言情绪分析器
支持多种语言的情绪分析，包含翻译和本地化处理
"""

import os
import re
import json
import requests
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from dotenv import load_dotenv

from .sentiment_engine import SentimentEngine, SentimentScore, SentimentLabel, SentimentIntensity

load_dotenv('/Users/lsl_mac/.openclaw/workspace/projects/polymarket-arbitrage/config/.env')


class Language(Enum):
    """支持的语言"""
    EN = "en"  # 英语
    ZH = "zh"  # 中文
    JA = "ja"  # 日语
    KO = "ko"  # 韩语
    ES = "es"  # 西班牙语
    FR = "fr"  # 法语
    DE = "de"  # 德语
    PT = "pt"  # 葡萄牙语
    RU = "ru"  # 俄语
    AR = "ar"  # 阿拉伯语
    AUTO = "auto"  # 自动检测


@dataclass
class MultilingualResult:
    """多语言分析结果"""
    original_text: str
    detected_language: str
    translated_text: Optional[str]
    sentiment: SentimentScore
    language_confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'original_text': self.original_text[:200] + '...' if len(self.original_text) > 200 else self.original_text,
            'detected_language': self.detected_language,
            'translated_text': self.translated_text[:200] + '...' if self.translated_text and len(self.translated_text) > 200 else self.translated_text,
            'sentiment': self.sentiment.to_dict(),
            'language_confidence': self.language_confidence
        }


class MultilingualAnalyzer:
    """多语言情绪分析器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # 基础情绪分析引擎
        self.base_engine = SentimentEngine(config)
        
        # 翻译 API 配置
        self.translation_api = self.config.get('translation_api', 'google')  # google, deepl, libre
        self.google_api_key = os.getenv('GOOGLE_TRANSLATE_API_KEY')
        self.deepl_api_key = os.getenv('DEEPL_API_KEY')
        self.libre_url = os.getenv('LIBRETRANSLATE_URL', 'https://libretranslate.com')
        
        # 缓存
        self.translation_cache: Dict[str, str] = {}
        self.cache_max_size = self.config.get('cache_max_size', 1000)
        
        # 语言检测配置
        self.language_patterns = self._load_language_patterns()
        
        # 多语言情绪词汇库
        self.multilingual_lexicon = self._load_multilingual_lexicon()
    
    def analyze(self, text: str, target_language: str = 'en') -> MultilingualResult:
        """
        分析多语言文本的情绪
        
        Args:
            text: 文本内容
            target_language: 翻译目标语言（用于情绪分析）
        
        Returns:
            MultilingualResult: 分析结果
        """
        # 检测语言
        detected_lang, confidence = self._detect_language(text)
        
        # 如果不是英语，翻译
        translated = None
        if detected_lang != 'en':
            translated = self._translate(text, detected_lang, 'en')
        
        # 使用翻译后的文本进行情绪分析
        analysis_text = translated if translated else text
        
        # 如果翻译失败，尝试使用原始语言分析
        if not translated and detected_lang != 'en':
            sentiment = self._analyze_in_native_language(text, detected_lang)
        else:
            sentiment = self.base_engine.analyze_single(analysis_text, 'en')
        
        return MultilingualResult(
            original_text=text,
            detected_language=detected_lang,
            translated_text=translated,
            sentiment=sentiment,
            language_confidence=confidence
        )
    
    def analyze_batch(self, texts: List[Tuple[str, str]], 
                      target_language: str = 'en') -> List[MultilingualResult]:
        """
        批量分析多语言文本
        
        Args:
            texts: [(text, language), ...] 列表，language 可为 'auto'
            target_language: 翻译目标语言
        """
        results = []
        
        for text, lang in texts:
            if lang == 'auto':
                result = self.analyze(text, target_language)
            else:
                # 已知语言
                translated = None
                if lang != 'en':
                    translated = self._translate(text, lang, 'en')
                
                analysis_text = translated if translated else text
                sentiment = self.base_engine.analyze_single(analysis_text, 'en')
                
                result = MultilingualResult(
                    original_text=text,
                    detected_language=lang,
                    translated_text=translated,
                    sentiment=sentiment,
                    language_confidence=1.0
                )
            
            results.append(result)
        
        return results
    
    def _detect_language(self, text: str) -> Tuple[str, float]:
        """
        检测语言
        
        Returns:
            (language_code, confidence)
        """
        # 使用字符特征进行简单检测
        scores = {}
        
        # 中文检测
        zh_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        if zh_chars > 0:
            scores['zh'] = zh_chars / len(text)
        
        # 日文检测
        ja_chars = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', text))
        if ja_chars > 0:
            scores['ja'] = ja_chars / len(text)
        
        # 韩文检测
        ko_chars = len(re.findall(r'[\uac00-\ud7af]', text))
        if ko_chars > 0:
            scores['ko'] = ko_chars / len(text)
        
        # 阿拉伯语检测
        ar_chars = len(re.findall(r'[\u0600-\u06ff]', text))
        if ar_chars > 0:
            scores['ar'] = ar_chars / len(text)
        
        # 俄语检测（西里尔字母）
        ru_chars = len(re.findall(r'[\u0400-\u04ff]', text))
        if ru_chars > 0:
            scores['ru'] = ru_chars / len(text)
        
        # 如果没有检测到其他语言特征，默认为英语
        if not scores:
            return 'en', 0.8
        
        # 返回分数最高的语言
        best_lang = max(scores, key=scores.get)
        return best_lang, scores[best_lang]
    
    def _translate(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """
        翻译文本
        
        Args:
            text: 原文
            source_lang: 源语言
            target_lang: 目标语言
        
        Returns:
            翻译后的文本，失败返回 None
        """
        # 检查缓存
        cache_key = f"{source_lang}:{target_lang}:{hash(text[:100])}"
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]
        
        translated = None
        
        # 尝试不同的翻译 API
        if self.google_api_key:
            translated = self._translate_google(text, source_lang, target_lang)
        elif self.deepl_api_key:
            translated = self._translate_deepl(text, source_lang, target_lang)
        else:
            translated = self._translate_libre(text, source_lang, target_lang)
        
        # 缓存结果
        if translated:
            self._manage_cache()
            self.translation_cache[cache_key] = translated
        
        return translated
    
    def _translate_google(self, text: str, source: str, target: str) -> Optional[str]:
        """使用 Google Translate API"""
        try:
            url = "https://translation.googleapis.com/language/translate/v2"
            params = {
                'key': self.google_api_key,
                'q': text,
                'source': source,
                'target': target,
                'format': 'text'
            }
            
            response = requests.post(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return data['data']['translations'][0]['translatedText']
            
        except Exception as e:
            print(f"Google Translate 错误: {e}")
            return None
    
    def _translate_deepl(self, text: str, source: str, target: str) -> Optional[str]:
        """使用 DeepL API"""
        try:
            url = "https://api-free.deepl.com/v2/translate"  # 或 api.deepl.com
            data = {
                'auth_key': self.deepl_api_key,
                'text': text,
                'source_lang': source.upper(),
                'target_lang': target.upper()
            }
            
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result['translations'][0]['text']
            
        except Exception as e:
            print(f"DeepL 错误: {e}")
            return None
    
    def _translate_libre(self, text: str, source: str, target: str) -> Optional[str]:
        """使用 LibreTranslate API"""
        try:
            url = f"{self.libre_url}/translate"
            data = {
                'q': text,
                'source': source,
                'target': target
            }
            
            response = requests.post(url, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result.get('translatedText')
            
        except Exception as e:
            print(f"LibreTranslate 错误: {e}")
            return None
    
    def _analyze_in_native_language(self, text: str, language: str) -> SentimentScore:
        """使用原始语言进行情绪分析"""
        lexicon = self.multilingual_lexicon.get(language, {})
        positive = lexicon.get('positive', [])
        negative = lexicon.get('negative', [])
        
        if not positive and not negative:
            # 没有该语言的词汇库，返回中性
            return SentimentScore(
                score=0.0,
                label=SentimentLabel.NEUTRAL,
                intensity=SentimentIntensity.WEAK,
                confidence=0.0
            )
        
        # 计算情绪分数
        text_lower = text.lower()
        positive_count = sum(1 for word in positive if word in text_lower)
        negative_count = sum(1 for word in negative if word in text_lower)
        
        total = positive_count + negative_count
        if total == 0:
            score = 0.0
            confidence = 0.0
        else:
            score = (positive_count - negative_count) / total
            confidence = min(1.0, total / 10)
        
        label = self._score_to_label(score)
        intensity = self._score_to_intensity(abs(score), confidence)
        
        return SentimentScore(
            score=score,
            label=label,
            intensity=intensity,
            confidence=confidence
        )
    
    def _manage_cache(self):
        """管理缓存大小"""
        if len(self.translation_cache) >= self.cache_max_size:
            # 删除一半的缓存
            keys_to_remove = list(self.translation_cache.keys())[:self.cache_max_size // 2]
            for key in keys_to_remove:
                del self.translation_cache[key]
    
    def _score_to_label(self, score: float) -> SentimentLabel:
        """分数转标签"""
        if score <= -0.6:
            return SentimentLabel.VERY_BEARISH
        elif score <= -0.2:
            return SentimentLabel.BEARISH
        elif score <= 0.2:
            return SentimentLabel.NEUTRAL
        elif score <= 0.6:
            return SentimentLabel.BULLISH
        else:
            return SentimentLabel.VERY_BULLISH
    
    def _score_to_intensity(self, abs_score: float, confidence: float) -> SentimentIntensity:
        """分数转强度"""
        combined = (abs_score + confidence) / 2
        
        if combined >= 0.8:
            return SentimentIntensity.STRONG
        elif combined >= 0.5:
            return SentimentIntensity.MODERATE
        else:
            return SentimentIntensity.WEAK
    
    def _load_language_patterns(self) -> Dict[str, List[str]]:
        """加载语言特征模式"""
        return {
            'zh': [r'[\u4e00-\u9fff]'],
            'ja': [r'[\u3040-\u309f]', r'[\u30a0-\u30ff]'],
            'ko': [r'[\uac00-\ud7af]'],
            'ar': [r'[\u0600-\u06ff]'],
            'ru': [r'[\u0400-\u04ff]'],
            'es': [r'\b(el|la|los|las|un|una|es|son|está|están)\b'],
            'fr': [r'\b(le|la|les|un|une|est|sont|le|la)\b'],
            'de': [r'\b(der|die|das|ist|sind|ein|eine)\b'],
            'pt': [r'\b(o|a|os|as|um|uma|é|são)\b']
        }
    
    def _load_multilingual_lexicon(self) -> Dict[str, Dict[str, List[str]]]:
        """加载多语言情绪词汇库"""
        return {
            'zh': {
                'positive': [
                    '好', '优秀', '成功', '赢', '增长', '上涨', '提升', '改善',
                    '强劲', '乐观', '信心', '希望', '突破', '牛市', '利好',
                    '收益', '盈利', '反弹', '回升', '走强', '看涨'
                ],
                'negative': [
                    '坏', '差', '失败', '亏损', '下跌', '下降', '疲软', '悲观',
                    '危机', '风险', '威胁', '担忧', '问题', '熊市', '利空',
                    '衰退', '萎缩', '暴跌', '崩盘', '动荡', '走弱', '看跌'
                ]
            },
            'ja': {
                'positive': [
                    '良い', '成功', '勝利', '成長', '上昇', '改善', '強い',
                    '楽観', '希望', '利益', '増加', '向上', '好調'
                ],
                'negative': [
                    '悪い', '失敗', '損失', '下落', '低下', '悪化', '弱い',
                    '悲観', '危機', 'リスク', '問題', '不調', '減少'
                ]
            },
            'ko': {
                'positive': [
                    '좋다', '성공', '승리', '성장', '상승', '개선', '강하다',
                    '낙관', '희망', '이익', '증가', '향상', '호조'
                ],
                'negative': [
                    '나쁘다', '실패', '손실', '하락', '저하', '악화', '약하다',
                    '비관', '위기', '위험', '문제', '부진', '감소'
                ]
            },
            'es': {
                'positive': [
                    'bueno', 'excelente', 'éxito', 'ganar', 'crecimiento', 'subida',
                    'mejora', 'fuerte', 'optimista', 'esperanza', 'beneficio'
                ],
                'negative': [
                    'malo', 'terrible', 'fracaso', 'perder', 'caída', 'empeora',
                    'débil', 'pesimista', 'crisis', 'riesgo', 'problema'
                ]
            },
            'de': {
                'positive': [
                    'gut', 'ausgezeichnet', 'erfolg', 'gewinn', 'wachstum', 'anstieg',
                    'verbesserung', 'stark', 'optimistisch', 'hoffnung', 'gewinn'
                ],
                'negative': [
                    'schlecht', 'schrecklich', 'misserfolg', 'verlust', 'rückgang',
                    'verschlechterung', 'schwach', 'pessimistisch', 'krise', 'risiko'
                ]
            }
        }
    
    def get_supported_languages(self) -> List[str]:
        """获取支持的语言列表"""
        return [lang.value for lang in Language if lang != Language.AUTO]
