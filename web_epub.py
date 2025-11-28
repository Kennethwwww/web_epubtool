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
# 3. 核心处理逻辑 (V16.0: 移除首字下沉)
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
                        <h1 style="font-weight:bold; font-family: Kaiti, serif; margin:0 auto; letter-spacing: 2px; color:{color}; text-align: center;">{title}</h1>
                       </div>"""

        elif style == '菱形':
            svg_path = '<path d="M484.352 607.459556a39.082667 39.082667 0 0 1 55.296 0l172.032 172.032a39.139556 39.139556 0 0 1 0 55.296L539.648 1006.933333a39.082667 39.082667 0 0 1-55.296 0L312.32 834.787556a39.082667 39.082667 0 0 1 0-55.296zM834.56 312.32l172.032 172.032a39.082667 39.082667 0 0 1 0 55.296L834.56 711.68a39.139556 39.139556 0 0 1-55.296 0l-172.032-172.032a39.082667 39.082667 0 0 1 0-55.296l172.032-172.032a39.082667 39.082667 0 0 1 55.296 0z m-589.824 0l172.032 172.032a39.082667 39.082667 0 0 1 0 55.296L244.736 711.68a39.139556 39.139556 0 0 1-55.296 0L17.408 539.648a39.082667 39.082667 0 0 1 0-55.296L189.44 312.32a39.082667 39.082667 0 0 1 55.296 0zM539.648 17.066667l172.032 172.088889a39.139556 39.139556 0 0 1 0 55.296L539.648 416.540444a39.082667 39.082667 0 0 1-55.296 0L312.32 244.508444a39.139556 39.139556 0 0 1 0-55.296L484.352 17.066667a39.082667 39.082667 0 0 1 55.296 0z" fill="{color}"></path>'
            svg = f'<svg viewBox="0 0 1024 1024" width="50" height="50" xmlns="http://www.w3.org/2000/svg" style="margin: 0 auto; display: block;">{svg_path.replace("{color}", color)}</svg>'
            return f"""<div style="{container_style}">
                        <div style="{svg_div_style}">{svg}</div>
                        <h1 style="{h1_style}">『 {title} 』</h1>
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
        
        # 移除首字下沉逻辑，所有段落统一缩进
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
        css_text = f"body {{ margin: 5px; background-color: #fff; font-family: 'Songti SC', serif; }} h1 {{ text-align: center; margin: 0 auto; display: block; }}"
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
# 5. Streamlit 界面 (V16.0 Final)
# ==========================================
st.set_page_config(page_title="电子书精排 V16.0", page_icon="🎨", layout="centered")

if 'processed_path' not in st.session_state:
    st.session_state.processed_path = None

# --- 上传区域 (Priority #1) ---
st.title("📚 电子书精排工具 V16.0")
st.markdown("**专为极致阅读体验打造**：一键去广告 · 智能断行修复 · 定制矢量纹样")

with st.container(border=True):
    st.subheader("📄 第一步：上传书籍")
    uploaded_file = st.file_uploader("支持 .epub 格式", type=["epub"], label_visibility="collapsed")

# --- 侧边栏配置 ---
with st.sidebar:
    st.header("🎨 排版定制")
    
    deco_options = ["祥云", "竹叶", "菱形", "Minimal (极简无图)"]
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
    
    demo_p_style = f"text-indent: {indent_map[indent_opt]}; margin: 0 0 1em 0; line-height: {lh_map[lh_opt]}; text-align: justify; display: block;"
    
    demo_content = f"""
    {demo_title_html}
    <p style="{demo_p_style}">这是一段排版预览文本。通过左侧边栏的选项，您可以实时查看到标题颜色、装饰风格、首行缩进以及行间距的变化效果。</p>
    <p style="{demo_p_style}">工具会自动处理断行修复、标点规范化以及广告过滤。预览框内的文字样式将与您最终导出的电子书保持一致（字体取决于阅读器设置）。</p>
    """
    st.markdown(demo_content, unsafe_allow_html=True)

# --- 逻辑处理与结果展示 ---
user_config = {
    'deco_style': deco_style_val,
    'title_color': title_color,
    'indent': indent_map[indent_opt],
    'line_height': lh_map[lh_opt],
    'spam_keywords': user_spam_list
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