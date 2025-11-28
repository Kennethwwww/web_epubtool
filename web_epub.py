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
        self.domain_keywords = [".com", ".cn", ".net", ".org", "www.", "http"]
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
# 3. 核心处理逻辑 (V15.1 修复版)
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

    # --- 静态方法：SVG 纹样库 ---
    @staticmethod
    def generate_decoration_html(title, style, color):
        container_style = "margin: 4em auto 3em auto; text-align:center; width: 100%; display: block; border: none;"
        svg_div_style = "margin: 0 auto 10px auto; text-align:center; display: block; width: 100%;"
        h1_style = f"font-weight:bold; margin:0 auto; padding:0; font-family: 'Songti SC', serif; color:{color}; text-align: center;"

        if style == '祥云':
            svg_path = '<path d="M64.681 283.369c395.605 0 176.437 463.889 589.799 463.889h53.016c62.834 0 125.691-34.078 157.546-67.771 24.683-26.1 94.278-93.385 94.278-131.037v-33.134c0-59.061-50.783-119.289-112.657-119.289v-19.88c0-39.804-79.803-79.523-125.912-79.523h-59.644c-47.806 0-82.154 47.482-112.696 66.23-40.001 24.557-79.485 40.277-79.485 106.073v13.254c0 53.203 74.022 132.538 125.913 132.538h72.896c45.171 0 92.776-40.498 92.776-92.777v-13.253c0-37.206-43.813-72.896-79.523-72.896H654.48c-17.9 0-18.272 3.158-33.135 6.626 12.471-17.027 36.721-19.881 66.27-19.881h6.627c50.169 0 99.404 49.651 99.404 106.031v13.254c0 57.637-87.807 106.031-152.42 106.031h-19.881c-277.31 0-125.242-371.112-556.664-371.112v6.627z" fill="{color}"></path>'
            svg = f'<svg viewBox="0 0 1024 1024" width="40" height="40" xmlns="http://www.w3.org/2000/svg" style="margin: 0 auto; display: block;">{svg_path.replace("{color}", color)}</svg>'
            return f"""<div style="{container_style}">
                        <div style="{svg_div_style}">{svg}</div>
                        <h1 style="{h1_style}">『 {title} 』</h1>
                       </div>"""
            
        elif style == '竹叶':
            svg_path = '<path d="M564.319256 244.640744c-199.846698 110.258605-244.61693 385.905116-244.61693 385.905116s137.811349 62.035349 382.452093-158.505674C946.795163 251.522977 981.253953 0 981.253953 0s-217.088 134.38214-416.934697 244.640744zM354.161116 761.474977c-113.711628-13.788279-279.099535 51.676279-279.099535 51.676279s-79.276651 51.676279 189.487628 151.623442c268.764279 99.923349 554.76986-41.364837 554.769861-41.364838-31.029581-13.788279-351.47014-148.122791-465.157954-161.934883zM37.149767 482.375442C47.485023 392.811163 140.502326 20.670512 140.502326 20.670512c34.482605 44.794047 106.829395 220.517209 127.499907 434.152186 20.670512 213.611163-117.164651 285.981767-117.164652 285.981767C102.63814 709.798698 26.814512 571.963535 37.149767 482.375442z" fill="{color}"></path>'
            svg = f'<svg viewBox="0 0 1024 1024" width="50" height="50" xmlns="http://www.w3.org/2000/svg" style="margin: 0 auto; display: block;">{svg_path.replace("{color}", color)}</svg>'
            return f"""<div style="{container_style}">
                        <div style="{svg_div_style}">{svg}</div>
                        <h1 style="{h1_style}">『 {title} 』</h1>
                       </div>"""

        elif style == '牡丹':
            svg_path = '<path d="M440.139079 595.068411c-46.893458-77.517757-93.404112-106.419439-139.34056-86.705047 57.420561 40.194393 89.384673 76.943551 95.892336 109.864673-58.186168 33.878131-91.681495-100.485981 141.063178 6.890467 35.983551 36.174953 63.545421 72.541308 68.521869 36.366355 4.785047 71.775701-14.163738 87.853458-47.276262 18.757383-46.319252 20.862804-93.021308 6.507664-140.29757 34.452336-14.163738 66.799252-23.54243 96.849345-28.518878-28.901682 148.145047-39.620187 285.571589-32.346915 412.279626 4.210841-58.186168 11.866916-88.619065 23.159626-91.298692 0 21.819813 1.531215 32.921121 4.593645 33.303926 1.339813-59.717383 8.038879-83.068411 20.288598-70.053084-0.957009 22.394019 0.191402 33.112523 3.636635 32.346915 14.163738-144.891215 28.901682-251.119252 44.213832-318.301308 41.917009 11.101308 59.525981 26.796262 52.635514 47.08486-6.699065 17.991776-13.398131 30.050093-20.288598 35.983551-18.757383 22.011215-23.925234 43.831028-15.694953 65.459439 13.398131 8.038879 33.112523 1.531215 58.951775-19.331588 62.014206-44.596636 115.606729-75.412336 160.586168-92.255701 12.058318-6.316262 21.819813-14.546542 29.475888-24.882243-33.303925-2.679626-52.826916-0.765607-58.186168 5.550654 3.828037-7.847477 11.29271-14.929346 22.202617-21.245608-28.327477 8.995888-58.186168 22.202617-89.576075 39.620187 17.226168-38.663178 10.909907-66.416449-19.331589-83.068411-28.71028-14.546542-63.162617-20.48-103.357009-17.608972 12.632523-58.760374 26.60486-102.591402 41.534206-131.875888-60.865794-14.35514-97.806355 33.686729-110.630281 143.934206-55.697944 9.18729-99.720374 21.628411-131.875888 37.89757z m151.207477-255.521495c6.12486 0 11.101308 4.976449 11.101308 11.101308s-4.976449 11.101308-11.101308 11.101309-11.101308-4.976449-11.101308-11.101309 4.976449-11.101308 11.101308-11.101308z m-51.678505 62.779813c5.550654 0 10.144299 4.593645 10.144299 10.144299s-4.593645 10.144299-10.144299 10.144299-10.144299-4.593645-10.144299-10.144299 4.593645-10.144299 10.144299-10.144299z m-34.069532-35.026542c8.23028 0 14.737944 6.699065 14.737943 14.737944 0 8.23028-6.699065 14.737944-14.737943 14.737944-8.23028 0-14.737944-6.699065-14.737944-14.737944 0-8.23028 6.699065-14.737944 14.737944-14.737944z m-84.791028-37.89757c10.718505 0 19.331589 8.613084 19.331588 19.331589s-8.613084 19.331589-19.331588 19.331588-19.331589-8.613084-19.331589-19.331588 8.613084-19.331589 19.331589-19.331589z m-69.096075 79.431776c8.613084 0 15.694953 7.081869 15.694953 15.694953s-7.081869 15.694953-15.694953 15.694953-15.694953-7.081869-15.694954-15.694953 7.081869-15.694953 15.694954-15.694953z m244.420187-9.18729c-21.054206 39.428785-34.069533 80.005981-38.663178 121.731589-4.019439-53.975327-0.765607-98.763364 10.144299-134.746916 3.828037-7.464673 9.378692-10.718505 16.651963-10.144299 20.288598 2.488224 24.116636 10.144299 12.058318 22.968224z m-78.474767 56.272149c-4.976449 22.585421-2.488224 43.831028 7.464673 63.736823 2.105421-36.940561 7.656075-63.162617 16.651963-78.474767-13.780935 0.191402-21.819813 5.16785-23.925234 14.737944z m-40.577196-6.507663c2.679626 27.179065 7.847477 57.037757 15.694953 89.576075-0.191402-58.760374 3.445234-102.017196 11.101309-130.153271-20.097196 10.909907-29.093084 24.308037-26.796262 40.577196z m-25.839252-31.389907c4.402243 27.561869 6.890467 64.50243 7.464673 110.630281-14.546542-49.19028-30.624299-86.896449-48.04187-113.501309 23.925234-22.394019 37.514766-21.437009 40.577197 2.679626z m-44.213832 41.534206c11.484112 8.613084 22.202617 39.620187 32.346916 93.21271-22.202617-47.276262-49.19028-77.134953-81.154393-89.576075 18.948785-14.737944 35.409346-15.886355 48.807477-3.636635zM204.906182 625.69271c41.725607-42.108411 91.681495-40.577196 149.48486 4.593645-38.280374-9.18729-75.603738 4.402243-111.58729 40.577196-12.632523 6.699065-28.136075 3.636636-37.323364-7.273271s-9.378692-26.796262-0.574206-37.89757z m608.849346-193.698691c-15.31215-9.761495-46.510654-10.909907-93.21271-3.636636 106.802243-73.498318 175.898318-83.642617 207.479626-30.432897 25.839252-3.253832 49.955888 13.780935 55.506542 39.237383s-9.378692 50.912897-34.260935 58.568972c-22.585421 56.27215-78.091963 76.75215-166.136822 61.822804 50.912897-4.019439 79.048972-13.972336 84.02542-29.475888-24.882243-3.06243-46.510654-8.038879-64.50243-14.737944 35.409346-13.015327 57.229159-27.561869 65.45944-43.448224-40.96-1.722617-71.584299-5.933458-92.255701-12.823925 22.394019-7.273271 35.026542-15.503551 37.89757-24.882243z m-90.341682-167.85944c-27.561869-4.210841-54.740935 17.034766-81.154393 63.736823 33.303925-126.133832 97.806355-195.995514 193.698692-209.393645 24.116636 1.531215 39.811589 13.015327 47.08486 34.069533 24.308037-8.421682 51.104299 2.105421 63.354018 24.690841s6.507664 50.721495-13.589532 66.60785c18.565981 16.269159 24.690841 42.682617 15.120747 65.650841-9.570093 22.776822-32.921121 36.940561-57.611962 35.026542-51.295701-2.871028-102.017196 15.694953-152.164486 55.315141 16.843364-29.093084 43.448224-57.420561 80.197383-84.791028-22.202617-5.742056-47.850467 1.531215-76.560748 22.202616 38.663178-45.553645 58.186168-68.330467 58.186168-68.330467-27.370467-6.12486-58.951776 5.16785-94.935327 34.069533 3.253832-18.37458-38.663178z m-202.120374-66.416448c-24.116636 18.374579-39.428785 47.850467-46.127851 88.619065-9.761495-188.339439 22.968224-273.513271 97.806355-255.521495 44.979439-41.534206 87.470654-40.577196 127.282243 2.679626 57.420561-14.35514 90.533084 2.679626 99.720374 50.721495-86.513645 32.72972-142.594393 108.142056-167.859439 226.045608-11.29271-37.514766-12.24972-72.158505-2.679626-104.314019-12.632523-0.191402-27.179065 13.589533-43.448224 41.534206-0.574206-44.405234 1.531215-76.75215 6.507663-96.849346-33.112523 3.828037-54.549533 32.538318-64.50243 85.748037 0.191402-16.269159-1.914019-29.093084-6.507663-38.663177z m-229.682243 80.197383c11.675514 47.08486 18.757383 88.810467 21.245607 125.368224-37.706168-90.724486-89.384673-132.06729-155.035514-124.602617-21.819813-69.096075-4.402243-115.798131 52.635514-140.29757-18.374579-40.385794-6.699065-73.498318 35.026542-99.720373 40.194393-22.585421 74.455327-13.015327 102.4 28.518878 53.783925-17.800374 90.533084-5.359252 109.864673 37.89757-7.847477 53.018318-5.933458 111.778692 5.550654 176.281122-17.226168-29.093084-35.026542-51.678505-53.592523-67.373458-11.866916 22.776822-15.503551 44.02243-11.101308 63.736822-26.413458-52.635514-52.635514-81.92-78.474767-87.662056 5.359252 47.08486 13.206729 85.556636 22.968225 115.223925-13.780935-21.628411-31.007103-30.815701-51.678505-27.753271z m-52.635514 239.826542c49.955888 13.398131 78.283364 31.198505 84.791028 53.592523-63.928224-20.671402-117.137944-13.206729-159.629159 22.202617-54.166729-25.073645-80.005981-57.037757-77.517757-95.892336C52.933098 471.231402 37.238145 441.755514 39.534967 409.025794c5.550654-53.20972 33.303925-76.560748 83.068411-70.053084 79.814579-51.104299 143.168598-23.54243 190.062056 83.068411-34.069533-16.843364-43.256822-10.718505-27.753271 18.37458-31.77271-16.843364-57.420561-19.331589-76.560747-7.464673 18.183178 29.284486 42.682617 50.14729 73.881121 62.779813-26.60486 4.402243-41.151402 11.866916-43.448224 22.202617z m172.453084 227.768224c4.019439-25.839252 3.636636-50.530093-0.957009-73.881121-28.71028 13.015327-47.850467 34.260935-57.229159 63.736822-2.105421 15.694953 8.613084 30.241495 24.116635 32.921122 15.694953 2.679626 30.624299-7.273271 33.878131-22.776823z" fill="{color}"></path>'
            svg = f'<svg viewBox="0 0 1024 1024" width="50" height="50" xmlns="http://www.w3.org/2000/svg">{svg_path.replace("{color}", color)}</svg>'
            return f"""<div style="margin: 4em 0 3em 0; text-align:center;">
                        <div style="margin-bottom:10px;">{svg}</div>
                        <h1 style="font-weight:bold; margin:0; padding:0; line-height:1.4; color:{color};">『 {title} 』</h1>
                       </div>"""

        else: # Minimal
            return f'<h1 style="text-align:center; font-weight:bold; margin:1.5em auto; color:{color}; width:100%; display:block;">{title}</h1>'

    # --- 实例方法 ---
    def get_decoration_html(self, title):
        style = self.config.get('deco_style', 'Minimal')
        color = self.config.get('title_color', '#cc0000')
        return EbookPolisher.generate_decoration_html(title, style, color)

    def reconstruct_chapter(self, content):
        try: soup = BeautifulSoup(content, 'lxml')
        except: soup = BeautifulSoup(content, 'html.parser')
        
        raw_nodes = []
        original_title = ""
        h_tags = soup.find_all(['h1', 'h2', 'h3'])
        if h_tags: original_title = h_tags[0].get_text().strip()
        
        for br in soup.find_all("br"): br.replace_with("\n")
        for elem in soup.body.descendants:
            if isinstance(elem, NavigableString):
                text = str(elem).strip()
                if text:
                    for line in text.split('\n'):
                        if line.strip(): raw_nodes.append(('text', line.strip()))
            elif isinstance(elem, Tag) and elem.name == 'img':
                if elem.has_attr('src'): raw_nodes.append(('img', elem['src']))

        final_title = original_title
        if not final_title and raw_nodes:
            first = raw_nodes[0]
            if first[0] == 'text':
                txt = first[1]
                if len(txt) < 30 and re.search(r'第.*?章', txt): final_title = txt

        check_range = 6 
        clean_title_chars = re.sub(r'\s+', '', final_title) if final_title else ""
        temp_nodes = raw_nodes[:]
        while temp_nodes and check_range > 0:
            node_type, node_text = temp_nodes[0]
            if node_type == 'img': break 
            is_duplicate = False
            clean_node_chars = re.sub(r'\s+', '', node_text)
            if final_title and clean_node_chars in clean_title_chars: is_duplicate = True
            if final_title and clean_title_chars in clean_node_chars and len(node_text) < len(final_title) + 10: is_duplicate = True
            if len(node_text) < 30 and re.search(r'^第\s*[0-9零一二三四五六七八九十百千]+\s*[章节卷部]', node_text): is_duplicate = True
            if is_duplicate: temp_nodes.pop(0); check_range -= 1
            else: break
        
        merged_nodes = self.normalizer.merge_broken_paragraphs(temp_nodes)

        new_soup = BeautifulSoup("<html><head></head><body></body></html>", 'html.parser')
        body = new_soup.body

        if final_title:
            html_str = self.get_decoration_html(final_title)
            title_tag = BeautifulSoup(html_str, 'html.parser')
            body.append(title_tag)

        indent = self.config.get('indent', '2em')
        line_height = self.config.get('line_height', '1.8')
        
        # V15.1 核心：强制首段无缩进
        dropcap_class = ""
        if self.config.get('enable_dropcaps', False):
            dropcap_class = " class='drop-cap'"
        
        p_style = f"text-indent: {indent}; margin: 0 0 1em 0; line-height: {line_height}; text-align: justify; display: block;"
        p_style_no_indent = f"text-indent: 0 !important; margin: 0 0 1em 0; line-height: {line_height}; text-align: justify; display: block;"
        
        first_para = True
        for type_, content in merged_nodes:
            if type_ == 'text':
                if self.ad_remover.is_spam(content): continue
                fixed = self.normalizer.fix_punctuation(content)
                if not fixed: continue
                
                p = new_soup.new_tag("p")
                
                # 物理首字下沉逻辑
                if first_para and self.config.get('enable_dropcaps', False) and len(fixed) > 0:
                    p['style'] = p_style_no_indent # 关键：首段强制无缩进
                    
                    span = new_soup.new_tag("span", attrs={'class': 'drop-cap'})
                    span.string = fixed[0]
                    p.append(span)
                    p.append(fixed[1:])
                    first_para = False
                else:
                    p['style'] = p_style
                    p.string = fixed
                     
                body.append(p)
            elif type_ == 'img':
                p_img = new_soup.new_tag("p")
                p_img['style'] = "text-align: center; text-indent: 0; margin: 1em 0;"
                img = new_soup.new_tag("img", src=content)
                img['style'] = "max-width: 100%; height: auto;" 
                p_img.append(img)
                body.append(p_img)

        return new_soup.prettify()

    def process(self):
        self.detect_language()
        
        # 物理首字下沉 CSS (修正版)
        dropcap_css = ""
        if self.config.get('enable_dropcaps', False):
            dropcap_css = """
            span.drop-cap {
                font-size: 3.2em;
                font-weight: bold;
                float: left;
                line-height: 0.85;
                margin-right: 6px;
                margin-top: 4px;
                color: inherit;
                display: block; /* 增强兼容性 */
            }
            """
            
        css_text = f"""
        body {{ margin: 5px; background-color: #fff; font-family: 'Songti SC', serif; }}
        h1 {{ text-align: center; margin: 0 auto; display: block; }}
        {dropcap_css}
        """
        nav_css = epub.EpubItem(uid="style_nav", file_name="style/base.css", media_type="text/css", content=css_text)
        self.book.add_item(nav_css)

        items = list(self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        total = len(items); progress_bar = st.progress(0); status_text = st.empty()
        for i, item in enumerate(items):
            try:
                progress = int((i / total) * 100); progress_bar.progress(progress); status_text.text(f"正在处理: {item.file_name} ...")
                raw = item.get_content(); new_c = self.reconstruct_chapter(raw); item.set_content(str(new_c).encode('utf-8'))
            except Exception as e: pass
            if i % 50 == 0: gc.collect()
        progress_bar.progress(100); status_text.text("处理完成！"); epub.write_epub(self.output_path, self.book)

# ==========================================
# 5. Streamlit 界面 (V15.1 Final)
# ==========================================
st.set_page_config(page_title="电子书精排 V15.1", page_icon="🎨", layout="centered")

if 'processed_path' not in st.session_state:
    st.session_state.processed_path = None

# --- 上传区域 (Priority #1) ---
st.title("📚 电子书精排工具 V15.1")
st.markdown("**专为极致阅读体验打造**：一键去广告 · 智能断行修复 · 定制矢量纹样")

with st.container(border=True):
    st.subheader("📄 第一步：上传书籍")
    uploaded_file = st.file_uploader("支持 .epub 格式", type=["epub"], label_visibility="collapsed")

# --- 侧边栏配置 ---
with st.sidebar:
    st.header("🎨 排版定制")
    
    enable_dropcaps = st.checkbox("首字下沉 (Drop Caps)", value=False)
    
    deco_options = ["祥云", "竹叶", "牡丹", "菱形", "Minimal (极简无图)"]
    deco_style = st.selectbox("章节标题风格", deco_options, index=0)
    deco_style_val = deco_style.split(" ")[0] 
    
    title_color = st.color_picker("章节标题颜色", "#cc0000")
    
    col_s1, col_s2 = st.columns(2)
    with col_s1: indent_opt = st.selectbox("首行缩进", ["2字符", "1字符", "无缩进"], index=0)
    with col_s2: lh_opt = st.selectbox("行间距", ["1.8倍 (默认)", "1.5倍", "1.0倍 (紧凑)", "2.0倍"], index=0)
    
    indent_map = {"2字符": "2em", "1字符": "1em", "无缩进": "0"}
    lh_map = {"1.8倍 (默认)": "1.8", "1.5倍": "1.5", "1.0倍 (紧凑)": "1.0", "2.0倍": "2.0"}
    
    st.divider()
    with st.expander("🛡️ 广告过滤关键词", expanded=False):
        st.caption("默认已内置最强广告词库。您可在此添加额外的关键词：")
        user_spam_text = st.text_area("额外关键词 (每行一个)", height=100)
        user_spam_list = [line.strip() for line in user_spam_text.split('\n') if line.strip()]
    st.divider()
    with st.expander("📧 Kindle 推送配置"):
        sender_email = st.text_input("发件邮箱", placeholder="xxx@qq.com")
        sender_password = st.text_input("授权码", type="password")
        kindle_email = st.text_input("Kindle邮箱")
    if st.button("🔄 重置所有设置"):
        st.cache_data.clear()
        if st.session_state.processed_path and os.path.exists(st.session_state.processed_path):
            try: os.remove(st.session_state.processed_path)
            except: pass
        st.session_state.processed_path = None
        st.rerun()

# --- 预览区域 (Priority #2, Collapsed) ---
st.write("")
with st.expander("🎨 点击展开/折叠 排版效果预览", expanded=False):
    demo_title_html = EbookPolisher.generate_decoration_html("第一章 预览效果", deco_style_val, title_color)
    
    # 预览 CSS 逻辑 (模拟物理效果)
    dropcap_css = ""
    first_para_class = ""
    # 预览中的第一段文本
    first_char = "这"
    rest_text = "是一段排版预览文本。通过左侧边栏的选项，您可以实时查看到标题颜色、装饰风格、首行缩进以及行间距的变化效果。"
    
    if enable_dropcaps:
        dropcap_css = """
        <style>
        span.drop-cap-preview {
            font-size: 3.2em;
            font-weight: bold;
            float: left;
            line-height: 0.85;
            margin-right: 6px;
            margin-top: 4px;
            color: inherit;
        }
        </style>
        """
        demo_text_html = f'<span class="drop-cap-preview">{first_char}</span>{rest_text}'
        # 首字下沉段落强制无缩进
        demo_p_style_first = f"text-indent: 0; margin: 0 0 1em 0; line-height: {lh_map[lh_opt]}; text-align: justify; display: block;"
    else:
        demo_text_html = first_char + rest_text
        demo_p_style_first = f"text-indent: {indent_map[indent_opt]}; margin: 0 0 1em 0; line-height: {lh_map[lh_opt]}; text-align: justify; display: block;"

    demo_p_style_normal = f"text-indent: {indent_map[indent_opt]}; margin: 0 0 1em 0; line-height: {lh_map[lh_opt]}; text-align: justify; display: block;"
    
    demo_content = f"""
    {dropcap_css}
    {demo_title_html}
    <p style="{demo_p_style_first}">{demo_text_html}</p>
    <p style="{demo_p_style_normal}">工具会自动处理断行修复、标点规范化以及广告过滤。预览框内的文字样式将与您最终导出的电子书保持一致（字体取决于阅读器设置）。</p>
    """
    st.markdown(demo_content, unsafe_allow_html=True)

# --- 逻辑处理与结果展示 ---
user_config = {
    'deco_style': deco_style_val,
    'title_color': title_color,
    'indent': indent_map[indent_opt],
    'line_height': lh_map[lh_opt],
    'spam_keywords': user_spam_list,
    'enable_dropcaps': enable_dropcaps
}

if uploaded_file is not None:
    st.info(f"已就绪: {uploaded_file.name}")
    
    if st.button("🚀 开始精排处理", type="primary", use_container_width=True):
        with st.spinner('正在根据您的设定重构书籍...'):
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp_in:
                    tmp_in.write(uploaded_file.getvalue())
                    input_path = tmp_in.name
                
                output_path = input_path.replace(".epub", "_定制版.epub")
                polisher = EbookPolisher(input_path, output_path, user_config)
                polisher.process()
                
                st.session_state.processed_path = output_path
                st.balloons()
                st.success("✅ 处理完成！")
            except Exception as e:
                st.error(f"❌ 错误: {str(e)}")
            finally:
                if os.path.exists(input_path): os.remove(input_path)
                # 修复点：确保文件不被删除，供下载使用
                gc.collect()

    if st.session_state.processed_path and os.path.exists(st.session_state.processed_path):
        with open(st.session_state.processed_path, "rb") as f:
            file_data = f.read()
        
        st.divider()
        with st.container(border=True):
            st.subheader("🎉 第二步：获取文件")
            
            c1, c2 = st.columns(2)
            
            with c1:
                st.markdown("##### 📥 下载到本地")
                st.download_button(
                    label="点击下载文件",
                    data=file_data,
                    file_name=f"精排_{uploaded_file.name}",
                    mime="application/epub+zip",
                    use_container_width=True,
                    type="primary"
                )
                
            with c2:
                st.markdown("##### 📤 传送到 Kobo")
                st.link_button("跳转 send.djazz.se", "https://send.djazz.se", use_container_width=True)
                st.caption("提示：请先下载左侧文件，再跳转上传。")
            
            st.write("")
            st.markdown("##### 📧 推送到 Kindle")
            if sender_email and sender_password and kindle_email:
                if st.button("确认发送邮件", use_container_width=True):
                    with st.spinner("正在发送..."):
                        success, msg = send_email_to_kindle(
                            st.session_state.processed_path, 
                            f"精排_{uploaded_file.name}", 
                            sender_email, 
                            sender_password, 
                            kindle_email
                        )
                        if success: st.success("✅ 发送成功！请检查 Kindle。")
                        else: st.error(f"❌ 发送失败: {msg}")
            else:
                st.info("请先在左侧边栏配置邮箱信息。")