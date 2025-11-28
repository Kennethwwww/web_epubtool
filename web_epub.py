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
        default_phrases = ["关注微信公众号", "微信搜索", "求月票", "推荐票", "一秒记住", "下载APP", "点击下一页", "点击继续阅读", "章末", "精彩内容", "m.", "M."]
        
        if custom_spam_list and len(custom_spam_list) > 0:
            self.spam_phrases = custom_spam_list
        else:
            self.spam_phrases = default_phrases
            
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

# ==========================================
# 3. 核心处理逻辑 (Config支持)
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

    def get_decoration_html(self, title):
        style = self.config.get('deco_style', 'Classic')
        color = self.config.get('title_color', '#cc0000')
        
        if style == 'Minimal':
            return f'<h1 style="text-align:center; font-weight:bold; margin:1.5em 0; color:{color};">{title}</h1>'
        elif style == 'Cloud':
            svg = f"""<div style="text-align:center; margin-bottom:10px;"><svg viewBox="0 0 1024 1024" width="30" height="30" xmlns="http://www.w3.org/2000/svg"><path d="M866.9 166.9c-16.6-11.6-38.6-8.2-50.8 7.3-26.6 34.2-56.6 57.6-89.6 70.1-9.9-46-34.4-86.8-69.4-116.6-43.8-37.2-100-57.8-158.2-57.8-57.6 0-113.2 20-156.6 56.4-36.2 30.2-61.2 71.8-70.6 118.2-34.6-13.8-66-39.6-92.4-76.4-11.4-15.8-33.6-19.8-50.2-9-17.2 11.2-21.8 33.8-10.4 50.2 41.8 59.8 96.6 97.4 158 109.8 11.8 62 67.2 108.2 133.4 108.2 30.6 0 59.4-10 82.6-27 23.2 16.6 51.6 26.6 82.2 26.6 66.8 0 122.6-47.2 133.8-110.2 59.6-14.2 112.4-52 150.8-109.4 11.2-16.6 6.8-39.2-10.6-50.4z" fill="{color}"/></svg></div>"""
            h1 = f'<h1 style="text-align:center; font-weight:bold; margin:0; padding:0; color:{color};">『 {title} 』</h1>'
            return f'<div style="margin: 3em 0 2em 0; border-bottom: 1px solid #eee; padding-bottom: 20px;">{svg}{h1}</div>'
        else: # Classic
            deco = f'<div style="font-size: 2em; color: #555; margin-bottom: 15px;">❖</div>'
            h1 = f'<h1 style="font-size: 1.8em; font-weight: bold; margin: 0; padding: 0; line-height: 1.4; color: {color};">{title}</h1>'
            return f'<div style="margin: 4em 1em 3em 1em; text-align: center; border-bottom: 2px solid #333; padding-bottom: 15px;">{deco}{h1}</div>'

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
        p_style = f"text-indent: {indent}; margin: 0 0 1em 0; line-height: {line_height}; text-align: justify; display: block;"
        
        for type_, content in merged_nodes:
            if type_ == 'text':
                if self.ad_remover.is_spam(content): continue
                fixed = self.normalizer.fix_punctuation(content)
                if not fixed: continue
                p = new_soup.new_tag("p")
                p.string = fixed
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
        total = len(items); progress_bar = st.progress(0); status_text = st.empty()
        for i, item in enumerate(items):
            try:
                progress = int((i / total) * 100); progress_bar.progress(progress); status_text.text(f"正在处理: {item.file_name} ...")
                raw = item.get_content(); new_c = self.reconstruct_chapter(raw); item.set_content(str(new_c).encode('utf-8'))
            except Exception as e: pass
            if i % 50 == 0: gc.collect()
        progress_bar.progress(100); status_text.text("处理完成！"); epub.write_epub(self.output_path, self.book, {})

# ==========================================
# 4. 邮件发送函数 (修复：补全缺失的函数)
# ==========================================
def send_email_to_kindle(file_path, file_name, sender_email, sender_password, kindle_email):
    # 自动推断 SMTP 服务器
    if "@gmail.com" in sender_email:
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
    elif "@qq.com" in sender_email:
        smtp_server = "smtp.qq.com"
        smtp_port = 465
    elif "@163.com" in sender_email:
        smtp_server = "smtp.163.com"
        smtp_port = 465
    else:
        # 默认尝试 465 端口
        smtp_server = "smtp." + sender_email.split("@")[1]
        smtp_port = 465

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = kindle_email
    msg['Subject'] = "Convert"
    
    with open(file_path, "rb") as f:
        part = MIMEApplication(f.read(), Name=file_name)
    part['Content-Disposition'] = f'attachment; filename="{file_name}"'
    msg.attach(part)
    
    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
        
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, kindle_email, msg.as_string())
        server.quit()
        return True, "发送成功"
    except Exception as e:
        return False, str(e)

# ==========================================
# 5. Streamlit 界面
# ==========================================

st.set_page_config(page_title="电子书精排 V6.0", page_icon="🎨", layout="centered")

with st.sidebar:
    st.header("🎨 排版定制")
    deco_style = st.selectbox("章节标题风格", ["Classic (经典菱形)", "Cloud (红色祥云)", "Minimal (极简无图)"], index=0)
    deco_style_val = deco_style.split(" ")[0] 
    title_color = st.color_picker("章节标题颜色", "#cc0000")
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        indent_opt = st.selectbox("首行缩进", ["2字符", "1字符", "无缩进"], index=0)
    with col_s2:
        lh_opt = st.selectbox("行间距", ["1.8倍", "1.5倍", "2.0倍"], index=0)
    indent_map = {"2字符": "2em", "1字符": "1em", "无缩进": "0"}
    lh_map = {"1.8倍": "1.8", "1.5倍": "1.5", "2.0倍": "2.0"}
    
    st.divider()
    with st.expander("🛡️ 广告过滤关键词 (可编辑)", expanded=False):
        default_spam = "关注微信公众号\n微信搜索\n求月票\n推荐票\n一秒记住\n下载APP\n点击下一页\n点击继续阅读\n章末\n精彩内容\nm.\nM."
        spam_text = st.text_area("每行一个关键词", value=default_spam, height=150)
        spam_list = [line.strip() for line in spam_text.split('\n') if line.strip()]

    st.divider()
    with st.expander("📧 Kindle 推送配置"):
        sender_email = st.text_input("发件邮箱", placeholder="xxx@qq.com")
        sender_password = st.text_input("授权码", type="password")
        kindle_email = st.text_input("Kindle邮箱")

    if st.button("🔄 重置所有设置"):
        st.cache_data.clear()
        st.rerun()

st.title("🎨 电子书精排 V6.0 (定制版)")
st.caption("现在，您可以完全掌控书籍的排版风格了。")

user_config = {
    'deco_style': deco_style_val,
    'title_color': title_color,
    'indent': indent_map[indent_opt],
    'line_height': lh_map[lh_opt],
    'spam_keywords': spam_list
}

uploaded_file = st.file_uploader("请上传 EPUB 文件", type=["epub"])

if uploaded_file is not None:
    st.info(f"当前配置：{deco_style_val} | 颜色 {title_color} | 缩进 {indent_opt}")
    
    if st.button("🚀 开始定制化处理", type="primary"):
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
                gc.collect()

    if 'processed_path' in st.session_state and st.session_state.processed_path:
        if os.path.exists(st.session_state.processed_path):
            with open(st.session_state.processed_path, "rb") as f:
                file_data = f.read()
            
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    label="📥 下载到本地",
                    data=file_data,
                    file_name=f"精排_{uploaded_file.name}",
                    mime="application/epub+zip",
                    use_container_width=True
                )
            with c2:
                st.link_button("📤 Kobo 传输 (djazz)", "https://send.djazz.se", use_container_width=True)
            
            if sender_email and sender_password and kindle_email:
                if st.button("📧 推送到 Kindle", use_container_width=True):
                    with st.spinner("正在发送邮件..."):
                        success, msg = send_email_to_kindle(
                            st.session_state.processed_path, 
                            f"精排_{uploaded_file.name}", 
                            sender_email, 
                            sender_password, 
                            kindle_email
                        )
                        if success: st.success("邮件已发送！")
                        else: st.error(f"发送失败: {msg}")