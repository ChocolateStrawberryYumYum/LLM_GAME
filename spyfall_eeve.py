import streamlit as st
                col_ask, col_action = st.columns([2, 1])

                with col_ask:
                    if st.button("질문 제출", use_container_width=True, disabled=not user_input or not target_name, key="human_ask_btn"):
                        handle_human_turn(user_input, target_name)
                
                with col_action:
                    player_me = st.session_state.players["나"]
                    
                    if not player_me["is_spy"]:
                        with st.popover("🕵️ 스파이 지목하기", use_container_width=True): 
                            accuse_player_name = st.selectbox("스파이 지목", alive_targets, key="accuse_player_action_q")
                            if st.button("지목 제출", key="accuse_spy_btn_q", use_container_width=True):
                                handle_game_action("accuse_spy", accuse_player_name, "나")
                                st.rerun()
                    else:
                        with st.popover("📍 장소 맞추기", use_container_width=True): 
                            guess_location_name = st.selectbox("장소 추측", LOCATION_NAMES, key="guess_loc_btn_q_select")
                            if st.button("추측 제출", key="guess_loc_btn_q", use_container_width=True):
                                handle_game_action("guess_location", guess_location_name, "나")
                                st.rerun()

        
        elif st.session_state.game_phase == "finished":
            st.markdown("---")
            st.markdown(f"## 🏆 게임 종료")
            st.markdown(st.session_state.game_result, unsafe_allow_html=True)
            if st.button("게임 다시 시작하기", use_container_width=True):
                 st.session_state.page = "home"
                 st.session_state.game_phase = "setup"
                 st.rerun() 


def main():
    st.set_page_config(
        layout="wide", 
        initial_sidebar_state="auto", 
        page_title="AI 스파이폴 봇전", 
        menu_items=None 
    )
    
    # 세션 상태 초기화 및 페이지 설정
    if "game_phase" not in st.session_state:
        st.session_state.game_phase = "setup"
        st.session_state.page = "home"
        st.session_state.current_player_index = 0
    
    # 사이드바 렌더링
    render_sidebar()

    # 페이지 라우팅
    if st.session_state.page == "home":
        render_home_page()
    elif st.session_state.page == "info":
        render_info_page()
    elif st.session_state.page == "play":
        render_play_page()


if __name__ == "__main__":
    main()
