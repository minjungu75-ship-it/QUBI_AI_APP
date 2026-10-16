import streamlit as st
import sqlite3
import hashlib
import time
import os
from google import genai
from google.genai import types

# 1. 페이지 설정
st.set_page_config(
    page_title="QUBI AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. 세션 상태 초기화
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "is_plan_paid" not in st.session_state:
    st.session_state.is_plan_paid = False
if "show_paywall" not in st.session_state:
    st.session_state.show_paywall = False
if "onboarding_complete" not in st.session_state:
    st.session_state.onboarding_complete = False
if "user_interest" not in st.session_state:
    st.session_state.user_interest = "일반 비즈니스 / 종합"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "language" not in st.session_state:
    st.session_state.language = "한국어"
if "bg_color" not in st.session_state:
    st.session_state.bg_color = "#121212"
if "bg_image_url" not in st.session_state:
    st.session_state.bg_image_url = ""
if "daily_media_count" not in st.session_state:
    st.session_state.daily_media_count = 0

# 3. 챗지피티 스타일의 완벽한 플랫 다크 테마 CSS (거슬리는 하단 회색 바 제거)
bg_style = f"background-color: {st.session_state.bg_color};"
if st.session_state.bg_image_url:
    bg_style += f" background-image: url('{st.session_state.bg_image_url}'); background-size: cover; background-position: center;"

st.markdown(f"""
<style>
    .stApp {{
        {bg_style}
        color: #ECECEC !important;
    }}
    .block-container {{
        padding-top: 1.5rem;
        padding-bottom: 8rem;
        max-width: 800px;
    }}
    p, span, label, div, h1, h2, h3, h4 {{
        color: #ECECEC !important;
    }}
    
    /* Streamlit 하단 고정 컨테이너 배경을 완전히 투명하게 만들어서 거슬리는 회색 바 제거 */
    div[data-testid="stChatInputContainer"] {{
        background-color: transparent !important;
        border: none !important;
    }}
    
    /* 챗지피티처럼 입력창 자체를 둥근 다크 톤 박스로 고정 */
    .stChatInput {{
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        width: 100%;
        max-width: 750px;
        z-index: 999;
    }}
    
    textarea[data-testid="stChatInputTextArea"] {{
        background-color: #212121 !important;
        color: #FFFFFF !important;
        border-radius: 12px !important;
        border: 1px solid #333333 !important;
    }}
    
    /* 말풍선 박스 완전 제거 (플랫 디자인) */
    .stChatMessage {{
        background-color: transparent !important;
        border: none !important;
        padding: 10px 0px;
        margin-bottom: 6px;
        color: #ECECEC !important;
        box-shadow: none !important;
    }}
    
    .streamlit-expanderHeader {{
        background-color: #1E1E1E !important;
        color: #ECECEC !important;
        border-radius: 8px;
        border: 1px solid #333333;
    }}
</style>
""", unsafe_allow_html=True)

# 4. 데이터베이스 설정 (SQLite 인증 및 고객센터)
DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            is_banned INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT DEFAULT '접수됨',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        admin_pass = hashlib.sha256("admin123!".encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, is_banned, is_admin) VALUES (?, ?, 0, 1)", ('admin', admin_pass))
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, is_banned, is_admin) VALUES (?, ?, 0, 0)", (username, hash_password(password)))
        conn.commit()
        conn.close()
        return True, "성공"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "이미 존재하는 아이디입니다."

def check_login(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT username, is_banned, is_admin FROM users WHERE username = ? AND password = ?", (username, hash_password(password)))
    user = c.fetchone()
    conn.close()
    return user

def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT username, is_banned, created_at FROM users WHERE is_admin = 0")
    users = c.fetchall()
    conn.close()
    return users

def toggle_ban_user(username, ban_status):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = ? WHERE username = ?", (1 if ban_status else 0, username))
    conn.commit()
    conn.close()

def add_support_ticket(username, title, content):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO support_tickets (username, title, content) VALUES (?, ?, ?)", (username, title, content))
    conn.commit()
    conn.close()

def get_support_tickets():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, username, title, content, status, created_at FROM support_tickets ORDER BY id DESC")
    tickets = c.fetchall()
    conn.close()
    return tickets

def update_ticket_status(ticket_id, status):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE support_tickets SET status = ? WHERE id = ?", (status, ticket_id))
    conn.commit()
    conn.close()

init_db()

# 5. Gemini API 클라이언트
def get_gemini_client():
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

client = get_gemini_client()

# 6. 사이드바 메뉴
with st.sidebar:
    st.title("⚙️ QUBI 설정 & 메뉴")
    
    with st.expander("🎨 배경 테마 커스텀", expanded=False):
        color_choice = st.color_picker("배경색 선택", value=st.session_state.bg_color)
        if color_choice != st.session_state.bg_color:
            st.session_state.bg_color = color_choice
            st.rerun()
            
        custom_img = st.text_input("배경 이미지 URL", value=st.session_state.bg_image_url, placeholder="https://...")
        if custom_img != st.session_state.bg_image_url:
            st.session_state.bg_image_url = custom_img
            st.rerun()
            
        if st.button("기본 다크모드 복원", use_container_width=True):
            st.session_state.bg_color = "#121212"
            st.session_state.bg_image_url = ""
            st.rerun()

    st.divider()

    if not st.session_state.logged_in:
        auth_mode = st.radio("접속 모드", ["로그인", "회원가입"], key="auth_mode")
        user_input = st.text_input("아이디", key="auth_user")
        pass_input = st.text_input("비밀번호", type="password", key="auth_pass")
        
        if auth_mode == "로그인":
            if st.button("로그인", use_container_width=True):
                user = check_login(user_input, pass_input)
                if user:
                    if user[1] == 1:
                        st.error("⚠️ 관리자에 의해 차단된 계정입니다.")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.username = user[0]
                        st.session_state.is_admin = bool(user[2])
                        st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
        else:
            if st.button("회원가입", use_container_width=True):
                if user_input and pass_input:
                    success, msg = register_user(user_input, pass_input)
                    if success:
                        st.success("회원가입 성공! 로그인해 주세요.")
                    else:
                        st.warning(msg)
                else:
                    st.warning("아이디와 비밀번호를 모두 입력해 주세요.")
    else:
        st.write(f"👤 **{st.session_state.username}** 님 접속 중")
        plan_str = "💎 Pro (무제한)" if st.session_state.is_plan_paid else "🌱 Standard (15장 제한)"
        st.caption(f"플랜 상태: {plan_str}")
        
        if not st.session_state.is_plan_paid:
            if st.button("💎 플랜 업그레이드 (월 9,900원)", use_container_width=True):
                st.session_state.show_paywall = True
                st.rerun()
        
        if st.button("로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.is_admin = False
            st.session_state.onboarding_complete = False
            st.session_state.show_paywall = False
            st.rerun()

    st.divider()

    if st.session_state.logged_in:
        with st.expander("👤 프로필 및 관심사 변경", expanded=False):
            st.session_state.user_interest = st.selectbox(
                "주요 관심 분야",
                ["일반 비즈니스 / 종합", "IT / 기술 / 코딩", "소상공인 / 마케팅", "디자인 / 크리에이티브", "학술 / 연구"],
                index=0
            )
            st.session_state.language = st.selectbox(
                "🌐 언어 선택",
                ["한국어", "English", "日本語", "中文"],
                index=0
            )

    if st.session_state.logged_in:
        with st.expander("🎧 고객센터 (1:1 문의)", expanded=False):
            t_title = st.text_input("문의 제목", placeholder="제목을 입력하세요")
            t_content = st.text_area("문의 내용", placeholder="내용을 입력하세요")
            if st.button("문의 접수하기", use_container_width=True):
                if t_title and t_content:
                    add_support_ticket(st.session_state.username, t_title, t_content)
                    st.success("문의가 접수되었습니다.")
                else:
                    st.warning("제목과 내용을 모두 입력해 주세요.")

    if st.session_state.is_admin:
        st.divider()
        st.subheader("👑 관리자 대시보드")
        with st.expander("사용자 Ban 관리", expanded=False):
            for u in get_all_users():
                u_name, is_banned, _ = u
                c1, c2 = st.columns([2, 1])
                c1.write(f"**{u_name}** ({'차단됨' if is_banned else '정상'})")
                if is_banned:
                    if c2.button("해제", key=f"unban_{u_name}"):
                        toggle_ban_user(u_name, False)
                        st.rerun()
                else:
                    if c2.button("Ban", key=f"ban_{u_name}"):
                        toggle_ban_user(u_name, True)
                        st.rerun()

        with st.expander("🎧 1:1 문의함 관리", expanded=False):
            for t in get_support_tickets():
                t_id, t_user, t_title, t_content, t_status, _ = t
                st.markdown(f"**[{t_id}] {t_title}** ({t_user})")
                st.caption(f"내용: {t_content} | 상태: {t_status}")
                if t_status == "접수됨":
                    if st.button("답변 완료 처리", key=f"res_{t_id}"):
                        update_ticket_status(t_id, "답변 완료")
                        st.rerun()
                st.divider()

    st.divider()
    if st.button("🗑️ 대화 기록 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# 7. 온보딩 화면
if st.session_state.logged_in and not st.session_state.onboarding_complete:
    st.markdown("## 👋 QUBI AI에 오신 것을 환영합니다!")
    st.write("맞춤형 컨설팅을 위한 최초 설정을 진행합니다.")
    sel_lang = st.selectbox("사용하실 언어를 선택하세요", ["한국어", "English", "日本語", "中文"])
    sel_int = st.selectbox("관심 있는 분야를 선택해 주세요", ["일반 비즈니스 / 종합", "IT / 기술 / 코딩", "소상공인 / 마케팅", "디자인 / 크리에이티브", "학술 / 연구"])
    
    if st.button("설정 완료하고 시작하기", type="primary", use_container_width=True):
        st.session_state.language = sel_lang
        st.session_state.user_interest = sel_int
        st.session_state.onboarding_complete = True
        st.rerun()
    st.stop()

# 8. 결제 유도 화면 (Paywall)
if st.session_state.logged_in and st.session_state.show_paywall:
    st.markdown("---")
    st.markdown("# 💎 QUBI Pro 플랜으로 업그레이드하세요!")
    st.markdown("### 월 **9,900원**으로 무제한 미디어 분석과 고성능 기능을 누려보세요.")
    
    st.info("""
    ✨ **Pro 플랜 혜택 안내**
    - 📸 하루 미디어(사진/오디오) 업로드 **무제한** (무료 플랜은 15장 제한)
    - 🚀 최우선 응답 속도 및 최고급 AI 브레인 전용 라우팅
    """)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💎 월 9,900원에 Pro 시작하기", type="primary", use_container_width=True):
            st.session_state.is_plan_paid = True
            st.session_state.show_paywall = False
            st.success("🎉 QUBI Pro 플랜이 성공적으로 적용되었습니다!")
            time.sleep(1)
            st.rerun()
    with c2:
        if st.button("아니요, 계속 무료로 이용하기", use_container_width=True):
            st.session_state.show_paywall = False
            st.rerun()
    st.markdown("---")
    st.stop()

# 9. 메인 채팅 화면 (깔끔한 챗지피티 플랫 스타일)
col_top1, col_top2 = st.columns([4, 1])
with col_top1:
    st.markdown("### 🤖 QUBI AI")
with col_top2:
    if st.session_state.logged_in and not st.session_state.is_plan_paid:
        if st.button("✨ 플랜 업그레이드", use_container_width=True):
            st.session_state.show_paywall = True
            st.rerun()

if not client:
    st.error("⚠️ GEMINI_API_KEY가 설정되지 않았습니다. Streamlit Secrets를 확인해 주세요.")
    st.stop()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if len(st.session_state.messages) == 0:
    st.info(f"👋 안녕하세요 {st.session_state.username if st.session_state.logged_in else '방문자'}님! [{st.session_state.user_interest}] 모드입니다. 대화를 시작해 보세요.")

if not st.session_state.is_plan_paid:
    st.caption(f"📸 오늘 미디어 사용 량: {st.session_state.daily_media_count} / 15장 (무료 제한)")
else:
    st.caption("💎 QUBI Pro 플랜 이용 중 (무제한)")

with st.expander("➕ 이미지 및 미디어 파일 첨부", expanded=False):
    uploaded_files = st.file_uploader("파일 업로드", type=["png", "jpg", "jpeg", "mp3", "wav"], accept_multiple_files=True)
    camera_photo = st.camera_input("카메라 촬영")

if user_prompt := st.chat_input("메시지를 입력하세요..."):
    total_files = (len(uploaded_files) if uploaded_files else 0) + (1 if camera_photo else 0)
    if not st.session_state.is_plan_paid and (st.session_state.daily_media_count + total_files > 15):
        st.session_state.show_paywall = True
        st.warning("⚠️ 무료 플랜의 하루 미디어 업로드 한도(15장)를 초과했습니다. Pro 플랜을 확인해 주세요!")
        time.sleep(1)
        st.rerun()
    
    if not st.session_state.is_plan_paid:
        st.session_state.daily_media_count += total_files

    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            system_prompt = (
                f"You are QUBI AI, a professional assistant. "
                f"User interest: [{st.session_state.user_interest}]. "
                f"Stay strictly objective, neutral, and respond in {st.session_state.language}."
            )
            
            contents = []
            for msg in st.session_state.messages:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])]
                ))

            if uploaded_files:
                for uf in uploaded_files:
                    contents.append(types.Part.from_bytes(data=uf.read(), mime_type=uf.type))
            if camera_photo:
                contents.append(types.Part.from_bytes(data=camera_photo.read(), mime_type="image/jpeg"))

            response = client.models.generate_content_stream(
                model='gemini-2.5-flash',
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.7
                )
            )

            for chunk in response:
                if chunk.text:
                    chunk_text = str(chunk.text)
                    full_response += chunk_text
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            st.error(f"오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")

