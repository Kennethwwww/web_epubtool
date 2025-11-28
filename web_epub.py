import streamlit as st
import os
import tempfile
import shutil
import gc
import re
from bs4 import BeautifulSoup, NavigableString, Tag
from langdetect import detect
import ebooklib
from ebooklib import epub

# ==========================================
# 核心逻辑区 (V5.1 红色标题版逻辑 - 保持不变)
# ==========================================
class TextNormalizer:
    def __init__(self):
        self.sentence_endings = re.compile(r'[。！？…！””’\?\.!]$')
        
    def fix_punctuation(self, text):
        if not text: return ""
        replacements = [
            (r'\.\.\.+', '……'), (r'…\.', '……'), (r'—+', '——'),
            (r',', '，'), (r'\?', '？'), (r'!', '！'), (r':', '：'), (r';', '；'),
            (r'\(', '（'), (r'\)', '）'),
        ]
        new_text = text
        for pattern, sub in replacements:
            new_text = re.sub(pattern, sub, new_text)
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
                if buffer_text:
                    merged_nodes.append(('text', buffer_text))
                    buffer_text = ""
                merged_nodes.append((type_, content))
                continue
            text = content.strip()
            if not text: continue
            if buffer_text: buffer_text += text
            else: buffer_text = text
            if self.sentence_endings.search(buffer_text):
                merged_nodes.append(('text', buffer_text))
                buffer_text = ""
        if buffer_text: merged_nodes.append(('text', buffer_text))
        return merged_nodes

class AdRemover:
    def __init__(self, language='zh'):
        self.language = language
        self.domain_keywords = [".com", ".cn", ".net", ".org", "www.", "http"]
        self.spam_phrases = ["关注微信公众号", "微信搜索", "求月票", "推荐票", "一秒记住", "下载APP", "点击下一页", "点击继续阅读", "章末", "精彩内容", "m.", "M."]
        self.regex_patterns = [re.compile(r'第.*?页', re.IGNORECASE), re.compile(r'^\s*PS[：:].*?$', re.IGNORECASE)]

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

class EbookPolisher:
    def __init__(self, input_path, output_path):
        self.input_path = input_path
        self.output_path = output_path
        self.book = epub.read_epub(input_path)
        self.language = 'zh'
        self.ad_remover = None
        self.normalizer = TextNormalizer()

    def detect_language(self):
        try:
            sample = ""
            count = 0
            for item in self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                content = item.get_content().decode('utf-8', errors='ignore')
                text = re.sub(r'<[^>]+>', '', content)
                sample += text[:200]
                count += 1
                if count > 3: break
            lang = detect(sample)
            self.language = 'zh' if lang.startswith('zh') else 'en'
        except: self.language = 'zh'
        self.ad_remover = AdRemover(self.language)

    def reconstruct_chapter(self, content):
        try: soup = BeautifulSoup(content, 'lxml')
        except: soup = BeautifulSoup(content, 'html.parser')
        new_soup = BeautifulSoup("<html><head></head><body></body></html>", 'html.parser')
        body = new_soup.body

        original_title = ""
        h_tags = soup.find_all(['h1', 'h2', 'h3'])
        if h_tags: original_title = h_tags[0].get_text().strip()

        raw_nodes = []
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

        # 去重逻辑
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
            if is_duplicate:
                temp_nodes.pop(0)
                check_range -= 1
            else: break

        merged_nodes = self.normalizer.merge_broken_paragraphs(temp_nodes)

        if final_title:
            header_div = new_soup.new_tag("div")
            header_div['style'] = "margin: 4em 1em 3em 1em; text-align: center; border-bottom: 2px solid #333; padding-bottom: 15px;"
            deco = new_soup.new_tag("div")
            deco.string = "❖"
            deco['style'] = "font-size: 2em; color: #555; margin-bottom: 15px;"
            h1 = new_soup.new_tag("h1")
            h1.string = final_title
            h1['style'] = "font-size: 1.8em; font-weight: bold; margin: 0; padding: 0; line-height: 1.4; color: #cc0000;"
            header_div.append(deco)
            header_div.append(h1)
            body.append(header_div)

        p_style = "text-indent: 2em; margin: 0 0 1em 0; line-height: 1.8; text-align: justify; display: block; font-size: 1em;"
        
        for type_, content in merged_nodes:
            if type_ == 'text':
                if self.ad_remover.is_spam(content): continue
                fixed_content = self.normalizer.fix_punctuation(content)
                if not fixed_content: continue
                p = new_soup.new_tag("p")
                p.string = fixed_content
                p['style'] = p_style
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
        css_text = "body { margin: 5px; background-color: #fff; font-family: 'Songti SC', serif; }" 
        nav_css = epub.EpubItem(uid="style_nav", file_name="style/base.css", media_type="text/css", content=css_text)
        self.book.add_item(nav_css)

        items = list(self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        total = len(items)
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, item in enumerate(items):
            try:
                progress = int((i / total) * 100)
                progress_bar.progress(progress)
                status_text.text(f"正在处理: {item.file_name} ...")
                raw = item.get_content()
                new_c = self.reconstruct_chapter(raw)
                item.set_content(str(new_c).encode('utf-8'))
            except Exception as e: pass
            
            if i % 50 == 0: gc.collect()
        
        progress_bar.progress(100)
        status_text.text("处理完成！正在准备下载...")
        epub.write_epub(self.output_path, self.book, {})

# ==========================================
# 4. Streamlit 网页界面 (新增传输按钮)
# ==========================================

st.set_page_config(page_title="电子书精排 V5.2", page_icon="📚", layout="centered")

with st.sidebar:
    st.header("⚙️ 操作菜单")
    if st.button("🔄 重置/处理下一本", type="primary"):
        st.cache_data.clear()
        st.rerun()
    st.info("如果遇到错误，请点击上方重置按钮。")
    st.divider()
    st.markdown("🔗 **常用链接**")
    st.link_button("📤 打开 Kobo/Kindle 无线传输", "https://send.djazz.se")

st.title("📚 电子书精排 V5.2 (传送版)")
st.markdown("专为手机阅读优化：智能断行修复 | 标点规范 | 去除广告 | 红色章节标题")
st.divider()

uploaded_file = st.file_uploader("请上传 EPUB 文件", type=["epub"])

if uploaded_file is not None:
    st.success(f"📄 已加载: {uploaded_file.name}")
    
    start_btn = st.button("🚀 开始精排处理", type="primary")
    
    if start_btn:
        with st.spinner('正在进行智能重构，请耐心等待...'):
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp_in:
                    tmp_in.write(uploaded_file.getvalue())
                    input_path = tmp_in.name
                
                output_path = input_path.replace(".epub", "_精排版.epub")
                
                polisher = EbookPolisher(input_path, output_path)
                polisher.process()
                
                with open(output_path, "rb") as f:
                    result_data = f.read()
                
                st.balloons()
                st.success("✅ 精排完成！")
                st.markdown("---")
                
                # ==== 核心修改区：下载与传输按钮并排显示 ====
                col1, col2 = st.columns(2)
                
                with col1:
                    # 1. 下载按钮
                    st.download_button(
                        label="📥 1. 下载文件到本地",
                        data=result_data,
                        file_name=f"精排_{uploaded_file.name}",
                        mime="application/epub+zip",
                        use_container_width=True,
                        type="primary"
                    )
                
                with col2:
                    # 2. 传输跳转按钮
                    st.link_button(
                        label="📤 2. 去 Kobo/Kindle 传输",
                        url="https://send.djazz.se",
                        use_container_width=True
                    )
                
                st.caption("ℹ️ 操作提示：请先点击左侧按钮【下载文件】，然后点击右侧按钮跳转网页，将下载好的文件上传即可。")
                # ========================================
                
            except Exception as e:
                st.error(f"❌ 发生错误: {str(e)}")
            finally:
                if 'input_path' in locals() and os.path.exists(input_path): os.remove(input_path)
                if 'output_path' in locals() and os.path.exists(output_path): os.remove(output_path)
                gc.collect()