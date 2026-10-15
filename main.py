import streamlit as st
import json
import os
from datetime import datetime
from google import genai
from google.genai import types

# ----------------------------------------------------
# 0. 전역 페이지 설정 및 상단 UI (언어 & 검색)
# ----------------------------------------------------
st.set_page_config(
    page_title="BizAI Creator - 1인 사업가 맞춤 플랫폼", 
    page_icon="🚀", 
    layout="centered",
    initial_sidebar_state="expanded"
)

# 상단 헤더 영역: 글로벌 언어 선택 (좌) & 기록 검색창 (우)
top_col1, top_col2 = st.columns([1, 1])

with top_col1:
    selected_language = st.selectbox(
        "🌍 Language / 언어 선택",
        ["🇰🇷 한국어 (Korean)", "🇺🇸 English", "🇯🇵 日本語", "🇨🇳 中文"],
        index=0
    )

with top_col2:
    search_keyword = st.text_input(
        "🔍 대화/기록 검색", 
        placeholder="검색어를 입력하세요..."
    )

st.title("🚀 소상공인 & 1인 창업가 전용 AI 브레인")
st.markdown("---")

# 파일 데이터베이스 경로 정의
USER_DB_FILE = "users_db.json"
USAGE_FILE = "usage_limit.json"
today_str = datetime.now().strftime("%Y-%m-%d")

# ----------------------------------------------------
# 1. 데이터 베이스 관리 함수
# ----------------------------------------------------
def load_users():
    if os.path.exists(USER_DB_FILE):
        try:
            with open(USER_DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users):
    with open(USER_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_memory(username):
    filename = f"memory_{username}.json"
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_memory(username, messages):
    filename = f"memory_{username}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=4)

def load_usage(username):
    if os.path.exists(USAGE_FILE):
        try:
            with open(USAGE_FILE, "r", encoding="utf-8") as f:
                all_usage = json.load(f)
                user_data = all_usage.get(username, {})
                if user_data.get("date") == today_str:
                    return user_data
        except:
            pass
    return {"date": today_str, "chat_count": 0, "image_count": 0}

def save_usage(username, usage_data):
    all_usage = {}
    if os.path.exists(USAGE_FILE):
        try:
            with open(USAGE_FILE, "r", encoding="utf-8") as f:
                all_usage = json.load(f)
        except:
            pass
    all_usage[username] = usage_data
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(all_usage, f, ensure_ascii=False, indent=4)


# ----------------------------------------------------
# 2. 사이드바: 회원 인증 및 플랫폼 제어판
# ----------------------------------------------------
st.sidebar.header("🔐 회원 인증 및 계정")

users_db = load_users()

if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

# 미로그인 상태 처리
if not st.session_state.logged_in_user:
    auth_mode = st.sidebar.radio("접속 모드", ["로그인", "회원가입"])
    
    input_id = st.sidebar.text_input("아이디")
    input_pw = st.sidebar.text_input("비밀번호", type="password")
    
    if auth_mode == "회원가입":
        if st.sidebar.button("회원가입 완료"):
            if input_id in users_db:
                st.sidebar.error("이미 존재하는 아이디입니다.")
            elif input_id and input_pw:
                users_db[input_id] = {
                    "password": input_pw, 
                    "tier": "무료 체험 회원",
                    "onb_done": False,
                    "industry": "",
                    "goal": ""
                }
                save_users(users_db)
                st.sidebar.success("가입 성공! 로그인해 주세요.")
            else:
                st.sidebar.warning("모든 항목을 입력해주세요.")
    else:
        if st.sidebar.button("로그인"):
            if input_id in users_db and users_db[input_id]["password"] == input_pw:
                st.session_state.logged_in_user = input_id
                st.sidebar.success(f"환영합니다, {input_id}님!")
                st.rerun()
            else:
                st.sidebar.error("아이디 또는 비밀번호가 틀렸습니다.")
                
    st.stop()

# 로그인 성공 후 유저 정보
current_user = st.session_state.logged_in_user
user_info = users_db.get(current_user, {"tier": "무료 체험 회원", "onb_done": False})
current_tier = user_info["tier"]

# ----------------------------------------------------
# 2-1. [핵심 UX 온보딩]: 신규 가입 후 최초 1회 관심사 및 목적 설문 화면
# ----------------------------------------------------
if not user_info.get("onb_done", False):
    st.markdown("---")
    st.subheader("🎯 환영합니다! 맞춤형 AI 비서 설정을 위해 딱 한 가지만 여쭤볼게요.")
    st.write("입력하신 정보는 AI가 회원님의 사업을 완벽히 이해하고 맞춤 컨설팅을 제공하는 데 영구적으로 활용됩니다.")
    
    with st.form("onboarding_form"):
        ind_input = st.selectbox(
            "1. 현재 종사하고 계신 업종이나 주된 관심사는 무엇인가요?",
            ["카페/요식업 사장님", "스마트스토어/이커머스 셀러", "1인 콘텐츠 크리에이터 (유튜브/블로그)", "스타트업 기획자 / 1인 창업", "기타 프리랜서"]
        )
        
        goal_input = st.selectbox(
            "2. 이 앱을 통해 가장 먼저 해결하고 싶은 목적은 무엇인가요?",
            ["브랜드 로고 및 비주얼 이미지 제작", "인스타그램/블로그 마케팅 문구 및 카피라이팅 작성", "사업 아이디어 기획 및 심층 브레인스토밍", "고객 응대 및 실무 문서 자동화"]
        )
        
        submit_onb = st.form_submit_button("맞춤형 AI 시작하기 🚀")
        if submit_onb:
            users_db[current_user]["industry"] = ind_input
            users_db[current_user]["goal"] = goal_input
            users_db[current_user]["onb_done"] = True
            save_users(users_db)
            st.success("설정이 완료되었습니다! 잠시 후 메인 화면으로 이동합니다.")
            st.rerun()
    st.stop()

st.sidebar.info(f"👤 **{current_user}** 님\n- 등급: **{current_tier}**\n- 업종: {user_info.get('industry', '일반')}")

usage = load_usage(current_user)
if current_tier == "무료 체험 회원":
    rem_chats = max(0, 7 - usage["chat_count"])
    rem_images = max(0, 7 - usage["image_count"])
    st.sidebar.markdown(f"**⏳ 일일 잔여 한도 ({today_str})**")
    st.sidebar.write(f"- 대화: {rem_chats}/7회\n- 이미지: {rem_images}/7장")

st.sidebar.markdown("---")

app_mode = st.sidebar.selectbox(
    "📋 서비스 메뉴",
    [
        "💬 AI 지능형 맞춤 대화", 
        "🎨 고화질 로고 & 비전 이미지", 
        "⚙️ 마이페이지 & 계정 설정", 
        "❓ 자주 묻는 질문 (FAQ) & 고객센터"
    ]
)

st.sidebar.markdown("---")

st.sidebar.header("💳 구독 및 빌링")
if current_tier == "무료 체험 회원":
    if st.sidebar.button("✨ 프로페셔널 구독 (9,900원/월)"):
        users_db[current_user]["tier"] = "프로 유료 회원"
        save_users(users_db)
        st.sidebar.success("🎉 결제 성공! 프로 회원으로 즉시 승급되었습니다.")
        st.rerun()
else:
    st.sidebar.success("👑 프로페셔널 무제한 이용 중")
    if st.sidebar.button("테스트용: 무료 회원으로 등급 변경"):
        users_db[current_user]["tier"] = "무료 체험 회원"
        save_users(users_db)
        st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("🗑️ 대화 기록 초기화"):
    mem_file = f"memory_{current_user}.json"
    if os.path.exists(mem_file):
        os.remove(mem_file)
    st.sidebar.success("대화 기록이 초기화되었습니다.")
    st.rerun()

if st.sidebar.button("🔒 로그아웃"):
    st.session_state.logged_in_user = None
    st.rerun()

# ----------------------------------------------------
# 3. 개발자 API 키 보호 (서버 은닉)
# ----------------------------------------------------
try:
    MASTER_API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    MASTER_API_KEY = st.sidebar.text_input("개발자 테스트용 API Key", type="password")

if not MASTER_API_KEY:
    st.warning("⚠️ API Key가 설정되지 않았습니다. 개발자 키를 설정해주세요.")
    st.stop()

client = genai.Client(api_key=MASTER_API_KEY)

if "English" in selected_language:
    lang_prompt_rule = "Please respond fluently in English."
elif "日本語" in selected_language:
    lang_prompt_rule = "流暢な日本語で回答してください。"
elif "中文" in selected_language:
    lang_prompt_rule = "请用流利的中文回答。"
else:
    lang_prompt_rule = "한국어로 자연스럽고 친절하게 답변해주세요."


# ----------------------------------------------------
# 4. 메인 화면 영역 (메뉴에 따른 전환)
# ----------------------------------------------------
if app_mode == "💬 AI 지능형 맞춤 대화":
    st.subheader(f"💬 {user_info.get('industry', '비즈니스')} 맞춤형 AI 컨설턴트")
    
    if current_tier == "프로 유료 회원":
        st.markdown("✨ **[프로 페셔널 모드]** 심층 분석 리액션 & 무제한 대화가 활성화되었습니다.")
    else:
        st.markdown("👤 **[일반 무료 모드]** 하루 7회 한도가 적용됩니다.")

    messages = load_memory(current_user)

    if search_keyword:
        st.info(f"🔍 '{search_keyword}' 검색 결과 필터링 중...")
        display_messages = [m for m in messages if search_keyword.lower() in m["content"].lower()]
    else:
        display_messages = messages

    for msg in display_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if not search_keyword:
        if prompt := st.chat_input("사업 아이디어나 필요한 업무 내용을 입력하세요..."):
            if current_tier == "무료 체험 회원" and usage["chat_count"] >= 7:
                st.error("🚨 오늘 무료 대화 횟수(7회)를 모두 사용하셨습니다. 프로 멤버십으로 업그레이드해 주세요.")
            else:
                if current_tier == "무료 체험 회원":
                    usage["chat_count"] += 1
                    save_usage(current_user, usage)

                messages.append({"role": "user", "content": prompt})
                save_memory(current_user, messages)
                
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    with st.spinner("회원님의 사업 맥락을 반영하여 답변을 생성 중입니다..."):
                        try:
                            user_ind = user_info.get("industry", "일반 사업자")
                            user_g = user_info.get("goal", "업무 지원")

                            if current_tier == "프로 유료 회원":
                                system_persona = (
                                    f"너는 최고급 1인 창업 전문 AI 컨설턴트다. 현재 사용자는 '{user_ind}'에 종사하며, "
                                    f"주요 목적은 '{user_g}'이다. 사용자는 소중한 유료 프로 회원이다. "
                                    f"답변 시작 시 찬사와 감탄을 담은 특별한 프리미엄 리액션('사장님의 탁월한 시야와 사업적 통찰이 돋보이는 방향입니다!')을 먼저 더해주고, "
                                    f"해당 업종 실무에 즉시 적용 가능한 깊이 있는 분석과 실행 계획을 제공해라. 다음 언어 규칙을 준수해라: {lang_prompt_rule}"
                                )
                            else:
                                system_persona = (
                                    f"너는 친절한 비즈니스 도우미다. 사용자는 '{user_ind}'이며 목적은 '{user_g}'이다. "
                                    f"이 맥락을 고려하여 정확히 답변해라. 다음 언어 규칙을 준수해라: {lang_prompt_rule}"
                                )

                            full_contents = f"[{system_persona}]\n\n사용자 질문: {prompt}"

                            response = client.models.generate_content(
                                model='gemini-2.5-flash',
                                contents=full_contents
                            )
                            answer = response.text
                            st.markdown(answer)
                            
                            messages.append({"role": "assistant", "content": answer})
                            save_memory(current_user, messages)
                            
                            st.rerun()
                        except Exception as e:
                            st.error(f"오류가 발생했습니다: {e}")

elif app_mode == "🎨 고화질 로고 & 비전 이미지":
    st.subheader("🎨 소상공인 브랜드 로고 및 비전 이미지 생성기")
    st.info(f"💡 현재 등록된 업종인 **[{user_info.get('industry', '비즈니스')}]**에 어울리는 브랜딩 비주얼을 만들어보세요!")
    
    img_prompt = st.text_area("이미지 설명 (영어나 한국어로 자유롭게 입력)", placeholder="Minimalist modern round logo for a cafe...", height=100)
    aspect_ratio = st.selectbox("비율 선택", ["1:1 (정사각형)", "16:9 (가로형)", "9:16 (세로형)"])

    if st.button("고화질 이미지 생성 🚀"):
        if current_tier == "무료 체험 회원" and usage["image_count"] >= 7:
            st.error("🚨 오늘 무료 이미지 생성 횟수(7장)를 모두 소모하셨습니다. 프로 구독을 이용해 보세요.")
        elif img_prompt:
            with st.spinner("이미지를 렌더링 중입니다..."):
                try:
                    if current_tier == "무료 체험 회원":
                        usage["image_count"] += 1
                        save_usage(current_user, usage)

                    ratio_map = {"1:1 (정사각형)": "1:1", "16:9 (가로형)": "16:9", "9:16 (세로형)": "9:16"}
                    
                    result = client.models.generate_images(
                        model='imagen-3.0-generate-002',
                        prompt=img_prompt,
                        config=types.GenerateImagesConfig(
                            number_of_images=1,
                            aspect_ratio=ratio_map[aspect_ratio],
                            output_mime_type="image/png"
                        )
                    )
                    
                    for gen_img in result.generated_images:
                        st.success("이미지 생성 완료!")
                        st.image(gen_img.image.image_bytes, use_column_width=True)
                        
                    st.rerun()
                except Exception as e:
                    st.error(f"이미지 생성 실패: {e}")
        else:
            st.warning("설명을 입력해 주세요.")

elif app_mode == "⚙️ 마이페이지 & 계정 설정":
    st.subheader("⚙️ 마이페이지 및 설정")
    st.write(f"계정: **{current_user}** | 현재 등급: **{current_tier}**")
    st.write(f"🏢 등록된 업종: **{user_info.get('industry', '미설정')}**")
    st.write(f"🎯 주요 목적: **{user_info.get('goal', '미설정')}**")
    
    st.markdown("---")
    st.markdown("### 🔑 비밀번호 변경")
    new_pw = st.text_input("새로운 비밀번호 입력", type="password")
    confirm_pw = st.text_input("새로운 비밀번호 확인", type="password")
    
    if st.button("비밀번호 변경 저장"):
        if new_pw and new_pw == confirm_pw:
            users_db[current_user]["password"] = new_pw
            save_users(users_db)
            st.success("비밀번호가 성공적으로 변경되었습니다!")
        else:
            st.error("비밀번호가 일치하지 않거나 입력되지 않았습니다.")
            
    st.markdown("---")
    st.markdown("### 🎨 테마 설정")
    theme = st.radio("화면 테마 선택", ["기본 시스템 테마", "다크 모드", "라이트 모드"])
    st.caption("※ Streamlit 우측 상단 '⋮' 메뉴의 Settings에서도 자유롭게 변경 가능합니다.")

else:
    st.subheader("❓ 자주 묻는 질문 (FAQ) & 고객 지원")
    
    with st.expander("Q. 무료 회원과 프로 유료 회원의 차이는 무엇인가요?"):
        st.write("무료 회원은 일일 대화 7회 및 이미지 생성 7장 제한이 있습니다. 프로 회원은 월 9,900원으로 무제한 이용과 함께 사업 업종이 반영된 심층 컨설팅 리액션 혜택을 받습니다.")
        
    with st.expander("Q. 일일 사용량 한도는 언제 리셋되나요?"):
        st.write("매일 자정(00:00)에 자동으로 사용량이 초기화됩니다.")

    with st.expander("Q. 내 사업 정보(업종/목적)를 수정할 수 있나요?"):
        st.write("현재 버전에서는 계정별 최초 설정된 정보가 유지되며, 추가 변경 기능은 추후 업데이트될 예정입니다.")

    st.markdown("---")
    st.subheader("📩 1:1 고객 문의")
    st.text_area("문의 사항을 적어주시면 개발자 팀에 전송됩니다.", height=100)
    if st.button("문의 보내기"):
        st.success("문의가 정상적으로 접수되었습니다. 빠른 시일 내에 답변드리겠습니다.")
