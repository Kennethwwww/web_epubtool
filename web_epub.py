import streamlit as st
import os
import tempfile
import shutil
import gc
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from bs4 import BeautifulSoup, NavigableString, Tag
from langdetect import detect
import ebooklib
from ebooklib import epub

# ==========================================
# 1. 文本修复专家
# ==========================================
class TextNormalizer:
    def __init__(self):
        self.sentence_endings = re.compile(r'[。！？…！””’\?\.!]$')
    def fix_punctuation(self, text):
        if not text: return ""
        replacements = [(r'\.\.\.+', '……'), (r'…\.', '……'), (r'—+', '——'),(r',', '，'), (r'\?', '？'), (r'!', '！'), (r':', '：'), (r';', '；'),(r'\(', '（'), (r'\)', '）')]
        new_text = text
        for pattern, sub in replacements: new_text = re.sub(pattern, sub, new_text)
        if '"' in new_text:
            parts = new_text.split('"')
            fixed_quote = ""
            for i, part in enumerate(parts):
                if i == len(parts) - 1: fixed_quote += part
                else:
                    quote_mark = "“" if i % 2 == 0 else "”"
                    fixed_quote += part + quote_mark
            new_text = fixed_quote
        return new_text.strip()
    def merge_broken_paragraphs(self, nodes):
        merged_nodes = []
        buffer_text = ""
        for type_, content in nodes:
            if type_ == 'img':
                if buffer_text: merged_nodes.append(('text', buffer_text)); buffer_text = ""
                merged_nodes.append((type_, content)); continue
            text = content.strip()
            if not text: continue
            if buffer_text: buffer_text += text
            else: buffer_text = text
            if self.sentence_endings.search(buffer_text): merged_nodes.append(('text', buffer_text)); buffer_text = ""
        if buffer_text: merged_nodes.append(('text', buffer_text))
        return merged_nodes

# ==========================================
# 2. 广告清洗模块
# ==========================================
class AdRemover:
    def __init__(self, custom_spam_list=None):
        self.domain_keywords = [".com", ".cn", ".net", ".org", "www.", "http", "https"]
        default_phrases = [
            "关注微信公众号", "微信搜索", "加群", "书友群", "官方群", "QQ群", "qq群",
            "求月票", "求推荐", "推荐票", "投推荐票", "月票", "打赏", "订阅", "求订阅", "鲜花", "评价票",
            "一秒记住", "下载APP", "下载客户端", "点击下一页", "点击继续阅读", "点击全文阅读", 
            "阅读模式", "浏览模式", "手机用户", "请访问", "浏览器", "搜小说", "看书网",
            "本章完", "未完待续", "防盗版", "盗版", "正版", "最新章节", "无弹窗", 
            "加入书架", "更新", "发布", "整理", "校对", "翻页", "章末", "精彩内容",
            "作者有话说", "PS：", "ps:", "（本章未完", "m.", "M."
        ]
        if custom_spam_list and len(custom_spam_list) > 0:
            self.spam_phrases = custom_spam_list
        else:
            self.spam_phrases = default_phrases
        self.regex_patterns = [
            re.compile(r'第.*?页', re.IGNORECASE),
            re.compile(r'^\s*PS[：:].*?$', re.IGNORECASE),
            re.compile(r'（.*?字）', re.IGNORECASE),
            re.compile(r'^\s*【.*?】\s*$', re.IGNORECASE)
        ]

    def is_spam(self, text):
        if not text: return True
        text = text.strip()
        if len(text) < 2 and not text.isdigit(): return True 
        for d in self.domain_keywords:
            if d in text.lower(): return True
        for p in self.spam_phrases:
            if p in text: return True
        for r in self.regex_patterns:
            if r.search(text): return True
        return False

# ==========================================
# 3. 核心处理逻辑 (V12.3: 修复变量名错误)
# ==========================================
class EbookPolisher:
    def __init__(self, input_path, output_path, config):
        self.input_path = input_path
        self.output_path = output_path
        self.book = epub.read_epub(input_path)
        self.language = 'zh'
        self.normalizer = TextNormalizer()
        self.config = config
        self.ad_remover = AdRemover(custom_spam_list=config.get('spam_keywords'))

    def detect_language(self):
        try:
            sample = ""
            count = 0
            for item in self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                content = item.get_content().decode('utf-8', errors='ignore')
                text = re.sub(r'<[^>]+>', '', content); sample += text[:200]; count += 1
                if count > 3: break
            lang = detect(sample)
            self.language = 'zh' if lang.startswith('zh') else 'en'
        except: self.language = 'zh'

    # --- 静态方法：SVG 纹样库 (变量名已修复) ---
    @staticmethod
    def generate_decoration_html(title, style, color):
        
        # 1. 祥云
        if style == '祥云':
            # 这里的 fill="{color}" 是关键，用于替换颜色
            svg_path = '<path d="M64.681 283.369c395.605 0 176.437 463.889 589.799 463.889h53.016c62.834 0 125.691-34.078 157.546-67.771 24.683-26.1 94.278-93.385 94.278-131.037v-33.134c0-59.061-50.783-119.289-112.657-119.289v-19.88c0-39.804-79.803-79.523-125.912-79.523h-59.644c-47.806 0-82.154 47.482-112.696 66.23-40.001 24.557-79.485 40.277-79.485 106.073v13.254c0 53.203 74.022 132.538 125.913 132.538h72.896c45.171 0 92.776-40.498 92.776-92.777v-13.253c0-37.206-43.813-72.896-79.523-72.896H654.48c-17.9 0-18.272 3.158-33.135 6.626 12.471-17.027 36.721-19.881 66.27-19.881h6.627c50.169 0 99.404 49.651 99.404 106.031v13.254c0 57.637-87.807 106.031-152.42 106.031h-19.881c-277.31 0-125.242-371.112-556.664-371.112v6.627z" fill="{color}"></path>'
            svg = f'<svg viewBox="0 0 1024 1024" width="40" height="40" xmlns="http://www.w3.org/2000/svg">{svg_path.replace("{color}", color)}</svg>'
            return f"""<div style="margin: 4em 0 3em 0; text-align:center;">
                        <div style="margin-bottom:10px;">{svg}</div>
                        <h1 style="font-weight:bold; margin:0; padding:0; font-family: 'Songti SC', serif; color:{color};">『 {title} 』</h1>
                       </div>"""
            
        # 2. 竹叶
        elif style == '竹叶':
            svg_path = '<path d="M564.319256 244.640744c-199.846698 110.258605-244.61693 385.905116-244.61693 385.905116s137.811349 62.035349 382.452093-158.505674C946.795163 251.522977 981.253953 0 981.253953 0s-217.088 134.38214-416.934697 244.640