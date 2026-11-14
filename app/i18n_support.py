"""
Internationalization (i18n) Module
Provides multi-language support with automatic language detection and translation management
"""

import logging
import json
import os
from typing import Dict, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class TranslationManager:
    """Manage translations for multiple languages"""
    
    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'es': 'Español',
        'fr': 'Français',
        'de': 'Deutsch',
        'it': 'Italiano',
        'pt': 'Português',
        'ja': '日本語',
        'zh': '中文',
        'ru': 'Русский',
        'ar': 'العربية'
    }
    
    def __init__(self, default_language: str = 'en', translations_dir: str = 'app/i18n'):
        """
        Initialize translation manager
        
        Args:
            default_language: Default language code
            translations_dir: Directory containing translation files
        """
        self.default_language = default_language
        self.translations_dir = translations_dir
        self.translations: Dict[str, Dict[str, str]] = {}
        self.fallback_language = 'en'
        self._load_translations()
    
    def _load_translations(self):
        """Load all translation files"""
        if not os.path.exists(self.translations_dir):
            os.makedirs(self.translations_dir)
            logger.info(f"Created translations directory: {self.translations_dir}")
            return
        
        for lang_code in self.SUPPORTED_LANGUAGES.keys():
            lang_file = os.path.join(self.translations_dir, f"{lang_code}.json")
            if os.path.exists(lang_file):
                try:
                    with open(lang_file, 'r', encoding='utf-8') as f:
                        self.translations[lang_code] = json.load(f)
                    logger.info(f"Loaded translations for {lang_code}")
                except Exception as e:
                    logger.error(f"Failed to load translations for {lang_code}: {e}")
    
    def get(self, key: str, language: Optional[str] = None, **kwargs) -> str:
        """
        Get translated string
        
        Args:
            key: Translation key (e.g., "common.welcome")
            language: Language code (uses default if not specified)
            **kwargs: Variables for string interpolation
        
        Returns:
            Translated string
        """
        lang = language or self.default_language
        
        # Try requested language
        if lang in self.translations and key in self.translations[lang]:
            translation = self.translations[lang][key]
            return self._interpolate(translation, kwargs)
        
        # Fall back to English
        if lang != self.fallback_language:
            if self.fallback_language in self.translations and key in self.translations[self.fallback_language]:
                translation = self.translations[self.fallback_language][key]
                return self._interpolate(translation, kwargs)
        
        # Return key if no translation found
        return key
    
    @staticmethod
    def _interpolate(text: str, variables: Dict[str, str]) -> str:
        """Interpolate variables into translation string"""
        for var, value in variables.items():
            text = text.replace(f"{{{var}}}", str(value))
        return text
    
    def add_translation(self, key: str, value: str, language: str = 'en'):
        """Add or update a translation"""
        if language not in self.translations:
            self.translations[language] = {}
        
        self.translations[language][key] = value
    
    def save_translations(self, language: str):
        """Save translations to file"""
        if language not in self.translations:
            logger.warning(f"No translations for language: {language}")
            return False
        
        try:
            lang_file = os.path.join(self.translations_dir, f"{language}.json")
            with open(lang_file, 'w', encoding='utf-8') as f:
                json.dump(self.translations[language], f, ensure_ascii=False, indent=2)
            logger.info(f"Saved translations for {language}")
            return True
        except Exception as e:
            logger.error(f"Failed to save translations for {language}: {e}")
            return False
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported languages"""
        return self.SUPPORTED_LANGUAGES.copy()


class LanguageDetector:
    """Detect user language preferences"""
    
    @staticmethod
    def detect_from_browser(accept_language: str) -> str:
        """
        Detect language from Accept-Language header
        
        Args:
            accept_language: Accept-Language HTTP header value
        
        Returns:
            Language code (e.g., 'en', 'es')
        """
        if not accept_language:
            return 'en'
        
        # Parse Accept-Language header
        # Format: en-US,en;q=0.9,es;q=0.8
        languages = accept_language.split(',')
        supported = TranslationManager.SUPPORTED_LANGUAGES.keys()
        
        for lang in languages:
            parts = lang.split(';')[0].strip().lower().split('-')
            lang_code = parts[0]
            
            if lang_code in supported:
                return lang_code
        
        return 'en'
    
    @staticmethod
    def detect_from_user_agent(user_agent: str) -> Optional[str]:
        """
        Detect language from user agent
        
        Args:
            user_agent: User-Agent HTTP header
        
        Returns:
            Language code or None
        """
        if not user_agent:
            return None
        
        # Simple heuristic based on language patterns
        patterns = {
            'ja': ['Japanese', 'ja-JP'],
            'zh': ['Chinese', 'zh-CN', 'zh-TW'],
            'ar': ['Arabic', 'ar-'],
            'ru': ['Russian', 'ru-'],
        }
        
        for lang, keywords in patterns.items():
            for keyword in keywords:
                if keyword in user_agent:
                    return lang
        
        return None


class RTLSupport:
    """Right-to-Left language support"""
    
    RTL_LANGUAGES = {'ar', 'he', 'fa', 'ur'}
    
    @staticmethod
    def is_rtl(language: str) -> bool:
        """Check if language is right-to-left"""
        return language in RTLSupport.RTL_LANGUAGES
    
    @staticmethod
    def get_text_direction(language: str) -> str:
        """Get text direction for language"""
        return 'rtl' if RTLSupport.is_rtl(language) else 'ltr'
    
    @staticmethod
    def get_flex_direction(language: str) -> str:
        """Get flex direction for CSS"""
        return 'row-reverse' if RTLSupport.is_rtl(language) else 'row'


class DateTimeFormatter:
    """Format dates and times based on language/locale"""
    
    LOCALE_FORMATS = {
        'en': {'date': '%m/%d/%Y', 'time': '%I:%M %p', 'datetime': '%m/%d/%Y %I:%M %p'},
        'es': {'date': '%d/%m/%Y', 'time': '%H:%M', 'datetime': '%d/%m/%Y %H:%M'},
        'fr': {'date': '%d/%m/%Y', 'time': '%H:%M', 'datetime': '%d/%m/%Y %H:%M'},
        'de': {'date': '%d.%m.%Y', 'time': '%H:%M', 'datetime': '%d.%m.%Y %H:%M'},
        'it': {'date': '%d/%m/%Y', 'time': '%H:%M', 'datetime': '%d/%m/%Y %H:%M'},
        'pt': {'date': '%d/%m/%Y', 'time': '%H:%M', 'datetime': '%d/%m/%Y %H:%M'},
        'ja': {'date': '%Y年%m月%d日', 'time': '%H:%M', 'datetime': '%Y年%m月%d日 %H:%M'},
        'zh': {'date': '%Y年%m月%d日', 'time': '%H:%M', 'datetime': '%Y年%m月%d日 %H:%M'},
        'ru': {'date': '%d.%m.%Y', 'time': '%H:%M', 'datetime': '%d.%m.%Y %H:%M'},
        'ar': {'date': '%Y/%m/%d', 'time': '%H:%M', 'datetime': '%Y/%m/%d %H:%M'},
    }
    
    @staticmethod
    def format_date(date, language: str = 'en') -> str:
        """Format date for language"""
        fmt = DateTimeFormatter.LOCALE_FORMATS.get(language, DateTimeFormatter.LOCALE_FORMATS['en'])
        return date.strftime(fmt['date'])
    
    @staticmethod
    def format_time(time, language: str = 'en') -> str:
        """Format time for language"""
        fmt = DateTimeFormatter.LOCALE_FORMATS.get(language, DateTimeFormatter.LOCALE_FORMATS['en'])
        return time.strftime(fmt['time'])
    
    @staticmethod
    def format_datetime(dt, language: str = 'en') -> str:
        """Format datetime for language"""
        fmt = DateTimeFormatter.LOCALE_FORMATS.get(language, DateTimeFormatter.LOCALE_FORMATS['en'])
        return dt.strftime(fmt['datetime'])


class NumberFormatter:
    """Format numbers based on language/locale"""
    
    LOCALE_NUMBER_FORMATS = {
        'en': {'decimal': '.', 'thousands': ','},
        'es': {'decimal': ',', 'thousands': '.'},
        'fr': {'decimal': ',', 'thousands': ' '},
        'de': {'decimal': ',', 'thousands': '.'},
        'it': {'decimal': ',', 'thousands': '.'},
        'pt': {'decimal': ',', 'thousands': '.'},
        'ja': {'decimal': '.', 'thousands': ','},
        'zh': {'decimal': '.', 'thousands': ','},
        'ru': {'decimal': ',', 'thousands': ' '},
        'ar': {'decimal': ',', 'thousands': '.'},
    }
    
    @staticmethod
    def format_number(number: float, language: str = 'en', decimals: int = 2) -> str:
        """Format number for language"""
        fmt = NumberFormatter.LOCALE_NUMBER_FORMATS.get(language, NumberFormatter.LOCALE_NUMBER_FORMATS['en'])
        
        # Format with decimals
        formatted = f"{number:.{decimals}f}"
        
        # Replace decimal separator
        if fmt['decimal'] != '.':
            formatted = formatted.replace('.', fmt['decimal'])
        
        # Add thousands separator
        parts = formatted.split(fmt['decimal'])
        integer_part = parts[0]
        
        # Add thousands separator to integer part
        if len(integer_part) > 3:
            groups = []
            for i, digit in enumerate(reversed(integer_part)):
                if i > 0 and i % 3 == 0:
                    groups.insert(0, fmt['thousands'])
                groups.insert(0, digit)
            integer_part = ''.join(groups)
        
        if len(parts) > 1:
            formatted = integer_part + fmt['decimal'] + parts[1]
        else:
            formatted = integer_part
        
        return formatted
    
    @staticmethod
    def format_currency(amount: float, currency: str = 'USD', language: str = 'en') -> str:
        """Format currency for language"""
        formatted_number = NumberFormatter.format_number(amount, language)
        
        # Currency symbols
        symbols = {
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'JPY': '¥',
            'CHF': 'Fr',
        }
        
        symbol = symbols.get(currency, currency)
        
        # Position varies by language
        if language in ['en', 'es', 'pt']:
            return f"{symbol}{formatted_number}"
        else:
            return f"{formatted_number} {symbol}"


# Export functions
def get_translation(key: str, language: str = 'en', **kwargs) -> str:
    """Get translation (uses global manager)"""
    if hasattr(get_translation, '_manager'):
        return get_translation._manager.get(key, language, **kwargs)
    return key


def init_i18n(default_language: str = 'en', translations_dir: str = 'app/i18n') -> TranslationManager:
    """Initialize global translation manager"""
    manager = TranslationManager(default_language, translations_dir)
    get_translation._manager = manager
    logger.info("Internationalization (i18n) initialized")
    return manager
