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
# 3. 核心处理逻辑 (V8.0: 修复方法调用)
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

    # --- 静态方法：供预览和生成使用 (修复点：提取为静态方法) ---
    @staticmethod
    def generate_decoration_html(title, style, color):
        if style == 'Minimal':
            return f'<h1 style="text-align:center; font-weight:bold; margin:1.5em 0; color:{color};">{title}</h1>'
        elif style == 'Oriental':
            svg = f"""<div style="text-align:center; margin-bottom:15px; opacity: 0.8;"><svg width="60" height="30" viewBox="0 0 1024 512" xmlns="http://www.w3.org/2000/svg"><path d="M512 64c-35.2 0-64 28.8-64 64 0 16 6.4 30.4 17.6 41.6-27.2 27.2-68.8 41.6-113.6 35.2-41.6-6.4-76.8-33.6-92.8-73.6-6.4-16-24-24-40-19.2-16 4.8-24 22.4-19.2 38.4 22.4 56 72 94.4 131.2 102.4 11.2 1.6 22.4 1.6 33.6 1.6 44.8 0 86.4-16 118.4-44.8 8 9.6 19.2 14.4 30.4 14.4 11.2 0 22.4-4.8 30.4-14.4 32 28.8 73.6 44.8 118.4 44.8 11.2 0 22.4 0 33.6-1.6 59.2-8 108.8-46.4 131.2-102.4 4.8-16-3.2-33.6-19.2-38.4-16-4.8-33.6 3.2-40 19.2-16 40-51.2 67.2-92.8 73.6-44.8 6.4-86.4-8-113.6-35.2 11.2-11.2 17.6-25.6 17.6-41.6 0-35.2-28.8-64-64-64H512z" fill="{color}"/></svg></div>"""
            h1 = f'<h1 style="text-align:center; font-weight:bold; margin:0; padding:0; font-family: \'Songti SC\', serif; color:{color};">『 {title} 』</h1>'
            return f'<div style="margin: 4em 0 3em 0; text-align:center;">{svg}{h1}</div>'
        elif style == 'Bamboo':
            svg = f"""<div style="text-align:center; margin-bottom:10px;"><svg width="50" height="40" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg"><path d="M480 480l-64 128-64-64c-32-32-64-32-96 0s-32 96 0 128l64 64 128-64c32-16 96-16 128 16s32 96 0 128l-64 64 64-128c32-64 32-128 0-192s-96-64-128-32l-64 64-128-64c-64-32-128-32-192 0s-64 96-32 128l64 64 64-128z" fill="{color}"/></svg></div>"""
            h1 = f'<h1 style="text-align:center; font-weight:bold; font-family: Kaiti, serif; margin:0; letter-spacing: 2px; color:{color};">{title}</h1>'
            return f'<div style="margin: 3em 0 2em 0; border-top: 1px solid #eee; border-bottom: 1px solid #eee; padding: 15px 0;">{svg}{h1}</div>'
        elif style == 'Vintage':
            svg = f"""<div style="text-align:center; margin:15px 0;"><svg width="100%" height="20" viewBox="0 0 400 20" xmlns="http://www.w3.org/2000/svg"><path d="M0 10 Q100 0 200 10 T400 10" fill="none" stroke="{color}" stroke-width="1.5"/></svg></div>"""
            h1 = f'<h1 style="font-weight: bold; margin: 0; color: {color}; font-size: 1.6em; font-family: Georgia, serif;">{title}</h1>'
            return f'<div style="margin: 4em 1em; text-align: center;">{svg}{h1}{svg}</div>'
        elif style == 'Flower':
            svg = f"""<div style="text-align:center; margin-bottom:10px;"><svg width="40" height="40" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg"><path d="M512 0c-28.8 0-54.4 12.8-70.4 35.2-16-22.4-41.6-35.2-70.4-35.2-48 0-86.4 38.4-86.4 86.4 0 25.6 11.2 48 28.8 64-22.4 6.4-38.4 27.2-38.4 51.2 0 28.8 22.4 51.2 51.2 51.2 12.8 0 25.6-4.8 35.2-12.8 12.8 25.6 38.4 44.8 67.2 44.8 41.6 0 76.8-33.6 76.8-76.8 0-16-4.8-30.4-12.8-41.6 22.4 9.6 48 16 73.6 16s51.2-6.4 73.6-16c-8 11.2-12.8 25.6-12.8 41.6 0 41.6 33.6 76.8 76.8 76.8 28.8 0 54.4-19.2 67.2-44.8 9.6 8 22.4 12.8 35.2 12.8 28.8 0 51.2-22.4 51.2-51.2 0-24-16-44.8-38.4-51.2 17.6-16 28.8-38.4 28.8-64 0-48-38.4-86.4-86.4-86.4-28.8 0-54.4 12.8-70.4 35.2-16-22.4-41.6-35.2-70.4-35.2z" fill="{color}"/></svg></div>"""
            h1 = f'<h1 style="text-align:center; font-weight:bold; margin:0; color:{color};">✿ {title} ✿</h1>'
            return f'<div style="margin: 3em 0; text-align: center;">{svg}{h1}</div>'
        else:
            deco = f'<div style="font-size: 2em; color: #555; margin-bottom: 15px;">❖</div>'
            h1 = f'<h1 style="font-size: 1.8em; font-weight: bold; margin: 0; padding: 0; line-height: 1.4; color: {color};">{title}</h1>'
            return f'<div style="margin: 4em 1em 3em 1em; text-align: center; border-bottom: 2px solid #333; padding-bottom: 15px;">{deco}{h1}</div>'

    # --- 实例方法：内部调用 ---
    def get_decoration_html(self, title):
        style = self.config.get('deco_style', 'Classic')
        color = self.config.get('title_color', '#cc0000')
        # 修复点：调用静态方法
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
        progress_bar.progress(100); status_text.text("处理完成！"); epub.write_epub(self.output_path, self.book)

# ==========================================
# 4. 邮件发送函数
# ==========================================
def send_email_to_kindle(file_path, file_name, sender_email, sender_password, kindle_email):
    if "@gmail.com" in sender_email:
        smtp_server = "smtp.gmail.com"; smtp_port = 587
    elif "@qq.com" in sender_email:
        smtp_server = "smtp.qq.com"; smtp_port = 465
    elif "@163.com" in sender_email:
        smtp_server = "smtp.163.com"; smtp_port = 465
    else:
        smtp_server = "smtp." + sender_email.split("@")[1]; smtp_port = 465
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = kindle_email
    msg['Subject'] = "Convert"
    with open(file_path, "rb") as f:
        part = MIMEApplication(f.read(), Name=file_name)
    part['Content-Disposition'] = f'attachment; filename="{file_name}"'
    msg.attach(part)
    try:
        if smtp_port == 465: server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else: server = smtplib.SMTP(smtp_server, smtp_port); server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, kindle_email, msg.as_string())
        server.quit()
        return True, "发送成功"
    except Exception as e: return False, str(e)

# ==========================================
# 5. Streamlit 界面 (V8.0 Final)
# ==========================================
st.set_page_config(page_title="电子书精排 V8.0", page_icon="🎨", layout="centered")

if 'processed_path' not in st.session_state:
    st.session_state.processed_path = None

with st.sidebar:
    st.header("🎨 排版定制")
    deco_options = ["Classic (经典菱形)", "Oriental (东方如意)", "Bamboo (水墨竹节)", "Vintage (西式复古)", "Flower (工笔繁花)", "Minimal (极简无图)"]
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

st.title("🎨 电子书精排 V8.0")
st.caption("新增实时预览功能 | 修复文件丢失Bug | Kobo/Kindle 流程优化")

# === 实时预览区域 (V8.0 特性) ===
st.markdown("### 👁️ 效果预览")
with st.container(border=True):
    # 调用静态方法生成预览 HTML
    demo_title_html = EbookPolisher.generate_decoration_html("第一章 预览效果", deco_style_val, title_color)
    demo_p_style = f"text-indent: {indent_map[indent_opt]}; margin: 0 0 1em 0; line-height: {lh_map[lh_opt]}; text-align: justify; display: block;"
    
    demo_content = f"""
    {demo_title_html}
    <p style="{demo_p_style}">这是一段排版预览文本。通过左侧边栏的选项，您可以实时查看到标题颜色、装饰风格、首行缩进以及行间距的变化效果。</p>
    <p style="{demo_p_style}">工具会自动处理断行修复、标点规范化以及广告过滤。预览框内的文字样式将与您最终导出的电子书保持一致（字体取决于阅读器设置）。</p>
    """
    st.markdown(demo_content, unsafe_allow_html=True)
# =================

user_config = {
    'deco_style': deco_style_val,
    'title_color': title_color,
    'indent': indent_map[indent_opt],
    'line_height': lh_map[lh_opt],
    'spam_keywords': user_spam_list
}

uploaded_file = st.file_uploader("请上传 EPUB 文件", type=["epub"])

if uploaded_file is not None:
    st.info(f"即将使用当前预览的配置处理文件...")
    
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
                st.success("✅ 处理完成！请按下方步骤操作：")
                
            except Exception as e:
                st.error(f"❌ 错误: {str(e)}")
            finally:
                if os.path.exists(input_path): os.remove(input_path)
                # 修复点：不再删除 output_path，确保可下载
                gc.collect()

    if st.session_state.processed_path and os.path.exists(st.session_state.processed_path):
        with open(st.session_state.processed_path, "rb") as f:
            file_data = f.read()
        
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📥 第一步：下载")
            st.download_button(
                label="保存文件到本地",
                data=file_data,
                file_name=f"精排_{uploaded_file.name}",
                mime="application/epub+zip",
                use_container_width=True,
                type="primary"
            )
        
        with c2:
            st.subheader("📤 第二步：Kobo 传输")
            st.warning("请先下载文件，点击下方按钮跳转后，再上传刚才下载的文件。")
            st.link_button("跳转 send.djazz.se", "https://send.djazz.se", use_container_width=True)
        
        st.divider()
        st.subheader("📧 Kindle 专属通道")
        if sender_email and sender_password and kindle_email:
            if st.button("📧 确认发送到 Kindle", use_container_width=True):
                with st.spinner("正在发送邮件..."):
                    success, msg = send_email_to_kindle(
                        st.session_state.processed_path, 
                        f"精排_{uploaded_file.name}", 
                        sender_email, 
                        sender_password, 
                        kindle_email
                    )
                    if success: st.success("✅ 邮件已发送！请检查您的 Kindle。")
                    else: st.error(f"❌ 发送失败: {msg}")
        else:
            st.info("如需使用 Kindle 推送，请先在左侧边栏配置邮箱信息。")