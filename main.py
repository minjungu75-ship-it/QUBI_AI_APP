import streamlit as st
import sqlite3
import hashlib
import json
import time
import os
from google import genai
from google.genai import types

# ---------------------------------------------------------
# 1. Page Configuration (Full Width & Default Dark Theme)
# ---------------------------------------------------------
st.set_page_config(
    page_title="QUBI AI - Professional AI SaaS Platform",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------------------------------------------------------
# 2. Session State Initialization
# ---------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "is_plan_paid" not in st.session_state:
    st.session_state.is_plan_paid = False  # Pro(유료) 여부
if "show_paywall" not in st.session_state:
    st.session_state.show_paywall = False  # 월 9,900원 결제 화면 표시 여부
if "onboarding_complete" not in st.session_state:
    st.session_state.onboarding_complete = False
if "user_interest" not in st.session_state:
    st.session_state.user_interest = "일반 비즈니스 / 종합 브레인"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "language" not in st.session_state:
    st.session_state.language = "한국어"
if "bg_color" not in st.session_state:
    st.session_state.bg_color = "#121212"  # 기본 검정색 다크모드
if "bg_image_url" not in st.session_state:
    st.session_state.bg_image_url = ""
if "daily_media_count" not in st.session_state:
    st.session_state.daily_media_count = 0  # 하루 미디어 사용 량 (무료 기준 최대 15장)

# ---------------------------------------------------------
# 3. Dynamic Custom CSS (ChatGPT Style Floating UI & Dark Theme)
# ---------------------------------------------------------
bg_style = f"background-color: {st.session_state.bg_color};"
if st.session_state.bg_image_url:
    bg_style += f" background-image: url('{st.session_state.bg_image_url}'); background-size: cover; background-position: center;"

st.markdown(f"""
<style>
    .stApp {{
        {bg_style}
        color: #FFFFFF;
    }}
    .block-container {{
        padding-top: 2rem;
        padding-bottom: 7rem;
        max-width: 1000px;
    }}
    .stChatInput {{
        position: fixed;
        bottom: 25px;
        max-width: 950px;
        z-index: 999;
    }}
    .stChatMessage {{
        border-radius: 16px;
        padding: 14px;
        margin-bottom: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }}
    h1, h2, h3 {{
        color: #F8F9FA;
    }}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 4. Database Setup (SQLite Auth, Admin Ban & Support Tickets)
# ---------------------------------------------------------
DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 사용자 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            is_banned INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 1:1 고객센터 문의 테이블
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
    # 기본 관리자 계정 자동 생성 (없을 경우)
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
        return False, "⚠️ 이미 존재하는 아이디입니다."

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

# ---------------------------------------------------------
# 5. Gemini API Client Initialization
# ---------------------------------------------------------
def get_gemini_client():
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

client = get_gemini_client()

# ---------------------------------------------------------
# 6. Sidebar Menu (설정, 테마, 계정, 프로 십자가, 1:1 고객센터, 관리자 대시보드)
# ---------------------------------------------------------
with st.sidebar:
    st.title("⚙️ QUBI AI 제어판")
    st.caption("프로페셔널 AI SaaS 플랫폼 관리 센터")
    
    # 🎨 배경 테마 커스텀 섹션 (이모티콘 및 직관성 복원)
    with st.expander("🎨 배경 테마 커스텀", expanded=False):
        st.write("나만의 감성적인 작업 환경을 만들어보세요!")
        color_choice = st.color_picker("🎨 채팅 배경색 선택", value=st.session_state.bg_color)
        if color_choice != st.session_state.bg_color:
            st.session_state.bg_color = color_choice
            st.rerun()
            
        custom_img = st.text_input("🖼️ 배경 이미지 URL", value=st.session_state.bg_image_url, placeholder="https://example.com/image.jpg")
        if custom_img != st.session_state.bg_image_url:
            st.session_state.bg_image_url = custom_img
            st.rerun()
            
        if st.button("🔄 기본 다크 모드(#121212) 복원", use_container_width=True):
            st.session_state.bg_color = "#121212"
            st.session_state.bg_image_url = ""
            st.rerun()

    st.divider()

    # 👤 회원 계정 및 로그인 / 회원가입 영역
    if not st.session_state.logged_in:
        st.subheader("🔐 로그인 및 회원가입")
        auth_mode = st.radio("접속 모드 선택", ["로그인", "회원가입"], key="auth_mode")
        user_input = st.text_input("👤 아이디", key="auth_user", placeholder="사용자 ID 입력")
        pass_input = st.text_input("🔑 비밀번호", type="password", key="auth_pass", placeholder="비밀번호 입력")
        
        if auth_mode == "로그인":
            if st.button("🚀 로그인 하기", use_container_width=True):
                user = check_login(user_input, pass_input)
                if user:
                    if user[1] == 1:  # is_banned 체크
                        st.error("🚫 [차단됨] 관리자에 의해 접근이 제한된 계정입니다.")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.username = user[0]
                        st.session_state.is_admin = bool(user[2])
                        st.success(f"🎉 환영합니다, {user[0]}님!")
                        st.rerun()
                else:
                    st.error("❌ 아이디 또는 비밀번호가 올바르지 않습니다.")
        else:
            if st.button("✨ 회원가입 하기", use_container_width=True):
                if user_input and pass_input:
                    success, msg = register_user(user_input, pass_input)
                    if success:
                        st.success("🎉 회원가입 성공! 로그인 탭에서 로그인해 주세요.")
                    else:
                        st.warning(msg)
                else:
                    st.warning("⚠️ 아이디와 비밀번호를 모두 입력해 주세요.")
    else:
        st.success(f"✨ **{st.session_state.username}** 님 접속 중")
        plan_label = "💎 QUBI Pro (유료 무제한)" if st.session_state.is_plan_paid else "🌱 QUBI Standard (무료: 사진 15장)"
        st.info(f"📌 플랜: {plan_label}")
        
        # Pro 업그레이드 유도 버튼 (사이드바)
        if not st.session_state.is_plan_paid:
            if st.button("💎 Pro 플랜 업그레이드 (월 9,900원)", use_container_width=True):
                st.session_state.show_paywall = True
                st.rerun()
        
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.is_admin = False
            st.session_state.onboarding_complete = False
            st.session_state.show_paywall = False
            st.rerun()

    st.divider()

    # 🎯 개인 프로필 및 관심사 변경
    if st.session_state.logged_in:
        with st.expander("🎯 프로필 및 관심사 설정", expanded=False):
            st.session_state.user_interest = st.selectbox(
                "💡 주요 관심 분야",
                ["일반 비즈니스 / 종합 브레인", "IT / 기술 / 코딩 전문", "소상공인 / 마케팅 / 창업 전략", "디자인 / 크리에이티브 기획", "학술 / 연구 / 전문 분석"],
                index=0
            )
            st.session_state.language = st.selectbox(
                "🌐 서비스 언어 선택",
                ["한국어", "English", "日本語", "中文"],
                index=["한국어", "English", "日本語", "中文"].index(st.session_state.language)
            )

    # 🎧 1:1 고객센터 (문의하기)
    if st.session_state.logged_in:
        with st.expander("🎧 1:1 고객센터 (문의 & 건의)", expanded=False):
            st.write("궁금한 점이나 불편사항을 남겨주시면 신속하게 도와드립니다.")
            ticket_title = st.text_input("📌 문의 제목", placeholder="예: 기능 오류 제안 또는 문의")
            ticket_content = st.text_area("📝 문의 내용", placeholder="자세한 내용을 적어주세요.")
            if st.button("📩 1:1 문의 접수", use_container_width=True):
                if ticket_title and ticket_content:
                    add_support_ticket(st.session_state.username, ticket_title, ticket_content)
                    st.success("🎉 문의가 안전하게 접수되었습니다!")
                else:
                    st.warning("⚠️ 제목과 내용을 모두 입력해 주세요.")

    # 👑 관리자 모드 (Ban 권한 및 1:1 문의함 관리)
    if st.session_state.is_admin:
        st.divider()
        st.subheader("👑 Owner Admin Center")
        
        with st.expander("🛡️ 유저 관리 및 계정 Ban 센터", expanded=False):
            st.write("악성 유저 관리 및 차단 제어")
            users_list = get_all_users()
            if not users_list:
                st.caption("등록된 일반 유저가 없습니다.")
            for u in users_list:
                u_name, is_banned, created_at = u
                status_str = "🚫 [차단됨]" if is_banned else "✅ [정상]"
                col1, col2 = st.columns([2, 1])
                col1.write(f"**{u_name}**\n{status_str}")
                if is_banned:
                    if col2.button("🔓 해제", key=f"unban_{u_name}"):
                        toggle_ban_user(u_name, False)
                        st.rerun()
                else:
                    if col2.button("🚫 Ban", key=f"ban_{u_name}"):
                        toggle_ban_user(u_name, True)
                        st.rerun()

        with st.expander("🎧 1:1 고객센터 문의함 관리", expanded=False):
            tickets = get_support_tickets()
            if not tickets:
                st.caption("접수된 문의 내역이 없습니다.")
            for t in tickets:
                t_id, t_user, t_title, t_content, t_status, t_time = t
                st.markdown(f"**[{t_id}] {t_title}**")
                st.caption(f"👤 작성자: {t_user} | 📌 상태: {t_status}\n💬 내용: {t_content}")
                if t_status == "접수됨":
                    if st.button("✅ 답변 완료 처리", key=f"resolve_{t_id}"):
                        update_ticket_status(t_id, "답변 완료")
                        st.rerun()
                st.divider()

    st.divider()
    if st.button("🗑️ 전체 대화 기록 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ---------------------------------------------------------
# 7. Onboarding Flow (로그인 후 관심사 및 언어 최초 설정)
# ---------------------------------------------------------
if st.session_state.logged_in and not st.session_state.onboarding_complete:
    st.markdown("## 🎉 QUBI AI에 오신 것을 환영합니다!")
    st.markdown("#### ✨ 맞춤형 AI 컨설팅 환경을 세팅하기 위한 최초 온보딩 과정입니다.")
    st.info("💡 입력해주신 관심사는 AI가 회원님의 배경을 완벽히 이해하는 데 사용되며, 항상 치우치지 않는 객관적이고 전문적인 시각을 유지합니다.")
    
    selected_lang = st.selectbox("🌐 서비스 언어를 선택하세요", ["한국어", "English", "日本語", "中文"])
    selected_interest = st.selectbox("🎯 주요 관심 분야를 선택해 주세요", ["일반 비즈니스 / 종합 브레인", "IT / 기술 / 코딩 전문", "소상공인 / 마케팅 / 창업 전략", "디자인 / 크리에이티브 기획", "학술 / 연구 / 전문 분석"])
    
    if st.button("🚀 설정 완료하고 QUBI 시작하기", type="primary", use_container_width=True):
        st.session_state.language = selected_lang
        st.session_state.user_interest = selected_interest
        st.session_state.onboarding_complete = True
        st.rerun()
    st.stop()

# ---------------------------------------------------------
# 8. Paywall Screen (월 9,900원 결제 유도 모달/화면)
# ---------------------------------------------------------
if st.session_state.logged_in and st.session_state.show_paywall:
    st.markdown("---")
    st.markdown("# 💎 QUBI Pro 플랜으로 비즈니스를 가속화하세요!")
    st.markdown("### 🚀 월 **9,900원**으로 무제한 미디어 분석 및 최상급 AI 브레인을 누려보세요.")
    
    st.success("""
    🌟 **QUBI Pro 전용 특권 안내**
    - 📸 하루 미디어(사진/오디오/카메라) 업로드 **무제한 허용** (무료 플랜은 15장 제한)
    - ⚡ 최우선 고성능 AI 모델 라우팅 및 쾌적한 응답 속도
    - 🎯 심층 전문 컨설팅 및 데이터 저장·내보내기 지원
    """)
    
    col_pay1, col_pay2 = st.columns(2)
    with col_pay1:
        if st.button("💎 월 9,900원에 Pro 시작하기", type="primary", use_container_width=True):
            st.session_state.is_plan_paid = True
            st.session_state.show_paywall = False
            st.success("🎉 축하합니다! QUBI Pro 플랜이 성공적으로 적용되었습니다!")
            time.sleep(1.5)
            st.rerun()
    with col_pay2:
        if st.button("아니요, 괜찮습니다 (계속 무료로 이용하기)", use_container_width=True):
            st.session_state.show_paywall = False
            st.rerun()
    st.markdown("---")
    st.stop()

# ---------------------------------------------------------
# 9. Main Chat Interface (Multi-modal & Stream Processing)
# ---------------------------------------------------------
st.markdown("### 🚀 QUBI AI Brain - Professional Assistant")

if not client:
    st.error("⚠️ [설정 오류] GEMINI_API_KEY가 설정되지 않았습니다. Streamlit Cloud의 Advanced settings에서 Secrets를 확인해 주세요.")
    st.stop()

# 대화 내용 출력
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if len(st.session_state.messages) == 0:
    st.info(f"👋 안녕하세요 **{st.session_state.username if st.session_state.logged_in else '방문자'}**님! 현재 **[{st.session_state.user_interest}]** 모드로 설정되어 있습니다. 무엇이든 질문하시거나 미디어를 첨부해 대화를 시작해보세요.")

# 📸 미디어 파일 첨부 (카메라 / 파일 업로드 / 오디오) - 무료 기준 하루 15장 제한 적용
if not st.session_state.is_plan_paid:
    st.caption(f"📸 오늘 미디어 사용 량: **{st.session_state.daily_media_count} / 15개** (무료 제한) | [💎 Pro로 업그레이드](?upgrade=true)")
else:
    st.caption("💎 QUBI Pro 플랜 이용 중 (미디어 무제한 활성화)")

with st.expander("📷/🎙️ 이미지 촬영 및 멀티모달 미디어 파일 첨부 (최대 15장)", expanded=False):
    uploaded_files = st.file_uploader("📂 이미지 또는 오디오 파일 업로드", type=["png", "jpg", "jpeg", "mp3", "wav"], accept_multiple_files=True)
    camera_photo = st.camera_input("📸 즉석 사진 촬영")

# 채팅 입력 및 처리
if user_prompt := st.chat_input("메시지를 입력하세요 (예: 비즈니스 아이디어 검토, 기획서 작성 등)..."):
    # 파일 한도 체크 (무료 플랜 기준 하루 15장)
    total_files = (len(uploaded_files) if uploaded_files else 0) + (1 if camera_photo else 0)
    if not st.session_state.is_plan_paid and (st.session_state.daily_media_count + total_files > 15):
        st.session_state.show_paywall = True
        st.warning("⚠️ 무료 플랜의 하루 미디어 업로드 한도(15장)를 초과했습니다. Pro 플랜으로 업그레이드해 주세요!")
        time.sleep(1.5)
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
            # 객관성 유지 시스템 프롬프트 (사용자 성향 반영하되 편향 방지)
            system_prompt = (
                f"You are QUBI AI, a professional smart business consultant and general AI brain. "
                f"The user's background interest is [{st.session_state.user_interest}]. "
                f"Acknowledge the user's background naturally without bias. Stay strictly objective, neutral, and highly analytical. "
                f"Respond helpfully in {st.session_state.language}."
            )
            
            # Gemini 최신 API 컨텐츠 구조 구축
            contents = []
            for msg in st.session_state.messages:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])]
                ))

            # 미디어 첨부 처리 (이미지/카메라/오디오)
            if uploaded_files:
                for uf in uploaded_files:
                    bytes_data = uf.read()
                    mime = uf.type
                    contents.append(types.Part.from_bytes(data=bytes_data, mime_type=mime))
            if camera_photo:
                bytes_data = camera_photo.read()
                contents.append(types.Part.from_bytes(data=bytes_data, mime_type="image/jpeg"))

            # 스트리밍 응답 요청 (Gemini 2.5 Flash)
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
                    full_response += chunk.text
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            lang = st.session_state.language
            if lang == "English":
                st.error(f"An error occurred: {str(e)}")
            elif lang == "日本語":
                st.error(f"エラーが発生しました: {str(e)}")
            elif lang == "中文":
                st.error(f"发生错误: {str(e)}")
            else:
                st.error(f"오류가 발생했습니다: {str(e)}")
