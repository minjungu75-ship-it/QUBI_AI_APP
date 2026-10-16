
# 8. Paywall Screen (Pro 플랜 결제 유도)
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# 9. Main Chat Interface (ChatGPT Style & Clean Media Limit Handling)
# ---------------------------------------------------------
col_top1, col_top2 = st.columns([4, 1])
with col_top1:
    st.markdown("### 🤖 QUBI AI")
with col_top2:
    if st.session_state.logged_in and not st.session_state.is_plan_paid:
        if st.button("✨ 업그레이드", use_container_width=True):
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

# 미디어 15장 제한 체크 및 16장째 반투명/차단 효과 처리
media_limit_reached = (not st.session_state.is_plan_paid) and (st.session_state.daily_media_count >= 15)

if media_limit_reached:
    upload_label = "➕ 🔒 이미지 및 미디어 첨부 (무료 한도 15장 초과 - Pro 필요)"
else:
    upload_label = f"➕ 이미지 및 미디어 파일 첨부 (오늘 남은 무료: {15 - st.session_state.daily_media_count}장)"

with st.expander(upload_label, expanded=False):
    if media_limit_reached:
        st.warning("⚠️ 오늘의 무료 미디어 업로드 한도(15장)를 모두 사용하셨습니다.")
        if st.button("💎 Pro 플랜으로 무제한 이용하기", use_container_width=True):
            st.session_state.show_paywall = True
            st.rerun()
    else:
        uploaded_files = st.file_uploader("파일 업로드", type=["png", "jpg", "jpeg", "mp3", "wav"], accept_multiple_files=True)
        camera_photo = st.camera_input("카메라 촬영")

if user_prompt := st.chat_input("메시지를 입력하세요..."):
    # 파일 변수 안전 할당
    cur_files = uploaded_files if ('uploaded_files' in locals() and uploaded_files and not media_limit_reached) else []
    cur_cam = camera_photo if ('camera_photo' in locals() and camera_photo and not media_limit_reached) else None
    
    total_files = len(cur_files) + (1 if cur_cam else 0)
    if not st.session_state.is_plan_paid and (st.session_state.daily_media_count + total_files > 15):
        st.session_state.show_paywall = True
        st.warning("⚠️ 무료 미디어 한도(15장)를 초과했습니다!")
        time.sleep(1)
        st.rerun()
    
    if not st.session_state.is_plan_paid and total_files > 0:
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

            if cur_files:
                for uf in cur_files:
                    contents.append(types.Part.from_bytes(data=uf.read(), mime_type=uf.type))
            if cur_cam:
                contents.append(types.Part.from_bytes(data=cur_cam.read(), mime_type="image/jpeg"))

            response = client.models.generate_content_stream(
                model='gemini-2.5-flash',
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.7
                )
            )

            for chunk in response:
                if chunk and getattr(chunk, 'text', None):
                    full_response += str(chunk.text)
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            st.error(f"오류가 발생했습니다: 안전한 처리를 위해 잠시 후 다시 시도해 주세요.")



                  