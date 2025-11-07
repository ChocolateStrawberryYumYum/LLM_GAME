import streamlit as st
import random
import json
import os 
from dotenv import load_dotenv 
import time 
from openai import OpenAI
from typing import List, Dict, Any, Optional

# --- 환경 변수 로드 (코드 시작 시 실행) ---
load_dotenv()
# ----------------------------------------

# --- 1. 상수 및 데이터 정의 ---

# 8명의 플레이어 (AI 7명 + 나 1명)
PLAYER_NAMES = ["카더가든", "넉살", "오존", "목사님", "코드쿤스트", "키드밀리", "빠니보틀", "나"]

# 스파이폴 장소 및 역할 데이터
SPYFALL_LOCATIONS_DATA = {
    "비행기": ["승무원", "부기장", "승객", "숨어 탄 승객", "조종사", "항공 엔지니어"],
    "놀이공원": ["광대", "아이", "기계공", "운영자", "관광객", "보안 요원"],
    "은행": ["지점장", "창구 직원", "강도", "고객", "경비원", "컨설턴트"],
    "해변": ["구급대원", "패러글라이더", "음식 상인", "사진가", "휴가객", "엔터테인먼트 디렉터"],
    "카지노": ["딜러", "도박꾼", "바텐더", "경비원", "관리자", "카드 게임 전문가"],
    "서커스": ["광대", "곡예사", "동물 조련사", "마술사", "저글러", "서커스 관람객"],
    "대사관": ["대사", "외교관", "비서", "난민", "보안 요원", "변호사"],
    "병원": ["수석 의사", "인턴", "간호사", "환자", "외과의", "병리학자"],
    "호텔": ["호텔 매니저", "가정부", "접수원", "손님", "바텐더", "경비"],
    "영화 스튜디오": ["감독", "배우", "카메라맨", "의상 담당", "엑스트라", "스턴트맨"],
    "크루즈": ["선장", "승무원", "바텐더", "음악가", "요리사", "부유한 승객"],
    "경찰서": ["경찰관", "형사", "기자", "범죄자", "용의자", "변호사"],
    "레스토랑": ["셰프", "웨이터", "지배인", "고객", "음악가", "비평가"],
    "학교": ["교장", "교사", "학생", "체육 교사", "수위", "보안 요원"],
    "슈퍼마켓": ["계산원", "고객", "정육점 직원", "배달원", "보안 요원", "판매 촉진원"]
}
LOCATION_NAMES = list(SPYFALL_LOCATIONS_DATA.keys())

# LLM이 참고할 장소 및 역할 도감
SPYFALL_CATALOGUE = "\n".join([
    f"- {location}: {', '.join(roles)}"
    for location, roles in SPYFALL_LOCATIONS_DATA.items()
])

# Streamlit 표시용 장소 목록
LOCATION_LIST_FOR_DISPLAY = "\n".join(LOCATION_NAMES)

# OpenAI Tool (함수) 정의
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "accuse_spy",
            "description": "스파이가 아닌 플레이어들이 스파이라고 생각하는 한 명의 플레이어를 지목하여 게임을 끝냅니다. 스파이가 아닌 경우에만 이 함수를 호출할 수 있습니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "player_name": {
                        "type": "string",
                        "description": "스파이라고 확신하여 지목하는 플레이어의 이름입니다. 자신을 제외한 다른 플레이어여야 합니다."
                    }
                },
                "required": ["player_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "guess_location",
            "description": "스파이가 현재 장소가 무엇인지 추측하여 게임을 끝냅니다. 스파이인 경우에만 이 함수를 호출할 수 있습니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location_name": {
                        "type": "string",
                        "description": "스파이가 추측하는 장소의 이름입니다. 후보 장소 목록에 있는 이름 중 하나여야 합니다."
                    }
                },
                "required": ["location_name"]
            }
        }
    }
]

# --- 2. LLM 로직 함수 ---

def create_system_prompt(player_data: Dict[str, Any], chosen_location: str) -> str:
    name = player_data["name"]
    role = player_data["role"]
    
    question_examples = [
        "여기서 보통 몇 시에 퇴근(혹은 귀가)하니? 구체적인 시간을 말해 줘.",
        "일 년 중 어느 계절에 사람들이 이곳을 가장 많이 방문하니?",
        "이곳까지 대중교통을 이용해서 올 수 있어? 걸리는 시간은 얼마나 돼?",
        "이곳의 시설 규모는 어느 정도야?",
        "이곳에서 특별히 제공되는 서비스나 이벤트 같은 게 있니?",
    ]
    
    if player_data["is_spy"]:
        # 스파이 프롬프트
        return (
            f"당신은 스파이입니다. 당신은 현재 장소 **{chosen_location}**를 모릅니다. "
            f"**당신은 지금부터 모든 대화에서 친근한 반말(예: ~야, ~하니, ~했어)을 사용해야 합니다. 절대 존댓말을 쓰지 마세요.** "
            f"당신의 목표는 다른 플레이어들의 대화를 듣고 장소를 추측하거나, 다른 플레이어에게 스파이로 의심받지 않고 게임을 끝내는 것입니다. "
            f"참고를 위해 **스파이폴 장소 도감**이 제공됩니다. 이를 활용하여 장소와 역할을 유추하고, **다른 장소로 오해하도록 유도하는 질문과 답변을 생성**하세요.\n\n"
            f"**스파이폴 장소 도감:**\n{SPYFALL_CATALOGUE}\n\n"
            f"당신의 이름은 {name}이며, 자신이 스파이임을 절대 들키지 않도록 "
            f"최대한 모호하고 자연스럽게 연기해야 합니다. 당신의 답변은 **15단어 이내**로 간결해야 합니다.\n"
            f"**질문 생성 지침:** 다른 플레이어들이 했던 질문이나 답변의 내용을 참고하여 **새롭고 구체적인 질문**을 만드세요. "
            f"모든 질문은 **반드시 반말로 질문**해야 합니다."
            f"질문 예시: {'; '.join(question_examples)}"
        )
    else:
        # 비스파이 프롬프트
        return (
            f"당신은 **{chosen_location}**의 **{role}**입니다. "
            f"**당신은 지금부터 모든 대화에서 친근한 반말(예: ~야, ~하니, ~했어)을 사용해야 합니다. 절대 존댓말을 쓰지 마세요.** "
            f"당신의 이름은 {name}이며, 스파이에게 장소가 들키지 않도록 "
            f"**장소에 대한 정보를 절대적으로 절제해야 합니다.** "
            f"**당신의 역할이나 행위가 장소를 직접적으로 유추하게 만들어서는 안 됩니다.** \n"
            f"**답변 생성 지침:**\n"
            f"1. **진실만 말하되, 최대한 모호하고 우회적으로 표현**하여 스파이가 장소를 알 수 없게 하세요.\n"
            f"2. 답변은 **15단어 이내**로 간결해야 하며, **반드시 반말로 답변**해야 합니다."
        )

def get_ai_response(player_data: Dict[str, Any], history: List[Dict[str, str]], 
                    target_player: str, client: OpenAI, chosen_location: str) -> Optional[Any]:
    
    system_prompt = create_system_prompt(player_data, chosen_location)
    
    current_turn_prompt = (
        f"현재 당신의 차례야. 당신은 플레이어 '{target_player}'에게 **새롭고 구체적인 질문 하나**를 해야 해. "
        f"이전에 다른 플레이어가 했던 질문이나 비슷하거나 똑같은 질문은 절대 하지 마. "
        f"답변은 **[질문] 태그 없이** **실제 질문 내용**을 채워서 생성해. 답변은 **15단어 이내**로 간결하게 해야 해. "
        f"**주의: 모든 질문은 반말을 사용하고, 게임을 종료하는 액션 함수(accuse_spy, guess_location)는 이 단계에서는 호출하지 마. 오직 질문만 해.**"
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        *history, 
        {"role": "user", "content": current_turn_prompt}
    ]

    try:
        # GPT-4-turbo-preview 모델 사용 (지침 준수 강화)
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview", 
            messages=messages,
            tools=TOOLS, 
            tool_choice="none", # 턴 진행 중 액션 방지
            temperature=0.8 
        )
        return response.choices[0].message
    except Exception as e:
        st.error(f"OpenAI API 호출 오류: {e}")
        return None

def get_ai_answer(player_data: Dict[str, Any], history: List[Dict[str, str]], 
                  question_text: str, client: OpenAI, chosen_location: str) -> str:
    
    target_prompt = create_system_prompt(player_data, chosen_location)
    answer_prompt = (
        f"당신은 질문을 받았어: '{question_text}' "
        f"당신의 역할과 상기된 답변 지침에 맞게 **15단어 이내**로 간결하게 반말로 답변해. 답변은 뒤에 **실제 답변 내용**을 채워서 생성해. 답변 앞에 어떤 식별자나 태그도 붙이지 마. 예: 나는 내 업무를 수행하고 있어."
    )
            
    answer_response = client.chat.completions.create(
        model="gpt-4-turbo-preview", # GPT-4-turbo-preview 모델 사용
        messages=[
            {"role": "system", "content": target_prompt},
            *history,
            {"role": "user", "content": answer_prompt}
        ],
        temperature=0.8
    )
    
    answer_content = answer_response.choices[0].message.content.strip()
    
    # 혹시 모를 태그 제거
    if answer_content.lower().startswith("나의 답변:"):
        answer_content = answer_content[len("나의 답변:"):].strip()
    if answer_content.lower().startswith("[답변]:"):
        answer_content = answer_content[len("[답변]:"):].strip()
        
    return answer_content


# --- 3. 게임 초기화 및 로직 함수 ---

def init_game():
    """게임 상태를 초기화하고 역할을 분배합니다."""
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        # 존댓말 변경: '없어.' -> '없습니다.'
        st.error("환경 변수 'OPENAI_API_KEY'를 찾을 수 **없습니다**. 게임을 시작할 수 **없습니다**.")
        st.session_state.game_phase = "setup"
        return

    try:
        st.session_state.client = OpenAI(api_key=api_key)
    except Exception as e:
        st.error(f"API 클라이언트 초기화 오류: {e}")
        return

    # 1. 장소 및 역할 무작위 선택
    chosen_location = random.choice(LOCATION_NAMES)
    location_roles = SPYFALL_LOCATIONS_DATA[chosen_location]

    # 2. 플레이어 역할 분배 (총 8명: 스파이 2명, 비스파이 6명)
    roles = ["스파이"] * 2
    if len(location_roles) >= 6:
        non_spy_roles = random.sample(location_roles, 6)
    else:
        non_spy_roles = random.choices(location_roles, k=6) 
        
    roles.extend(non_spy_roles)
    random.shuffle(roles)

    # 3. 세션 상태 저장
    players = {}
    for i, name in enumerate(PLAYER_NAMES):
        players[name] = {
            "role": roles[i],
            "is_spy": roles[i] == "스파이",
            "name": name,
            "display_role": roles[i] if roles[i] != "스파이" else "스파이",
            "is_alive": True 
        }

    # Streamlit Session State에 저장
    st.session_state.game_phase = "in_progress"
    st.session_state.players = players
    st.session_state.chosen_location = chosen_location
    st.session_state.game_history = []
    st.session_state.current_player_index = random.randint(0, 7)
    st.session_state.player_names_list = PLAYER_NAMES
    st.session_state.game_result = None
    st.session_state.action_window_open = False 
    
    # === 유저 요청 사항 반영: 게임 시작 후 바로 "play" 페이지로 이동 ===
    st.session_state.page = "play"
    # =========================================================

    # 플레이어에게 자신의 역할 표시
    my_role = players["나"]["role"]
    # 존댓말 변경: '네 역할은: ... 이야.' -> '당신의 역할은: ... 입니다.'
    info_message = f"**당신의 역할은:** **{my_role}** **입니다.**"
    if not players["나"]["is_spy"]:
        info_message += f" (비밀 장소: **{chosen_location}**)"
    st.success(info_message)
    # 존댓말 변경: '되었어! 🔥' -> '되었습니다! 🔥'
    st.toast("게임이 시작되었습니다! 🔥")


def handle_game_action(action_type: str, action_data: str, questioner_name: str):
    """스파이 지목 또는 장소 추측 시 게임 종료 로직 처리"""
    # 존댓말 변경: '시도했어.' -> '시도했습니다.'
    st.session_state.game_history.append({"role": "user", "content": f"액션: {questioner_name}이(가) {action_type}({action_data}) 시도했습니다."})
    
    if action_type == "guess_location":
        # 스파이의 장소 추측
        location_name = action_data
        if st.session_state.players[questioner_name]["is_spy"]:
            if location_name == st.session_state.chosen_location:
                # 존댓말 변경: '맞췄어.' -> '맞췄습니다.'
                st.session_state.game_result = f"🎉 **게임 종료!** 스파이 **{questioner_name}**이(가) 장소 **'{location_name}'**을(를) 정확히 맞췄습니다. **스파이 승리!**"
            else:
                # 존댓말 변경: '틀렸어.' '자수했어!' -> '틀렸습니다.' '자수했습니다!'
                st.session_state.game_result = f"❌ 스파이 **{questioner_name}**이(가) 장소 **'{location_name}'**을(를) 추측했지만 틀렸습니다. (정답: {st.session_state.chosen_location})<br>**스파이가 자수했습니다! (비-스파이 승리!)**"
        else:
            # 존댓말 변경: '시도했어.' '취소돼.' -> '시도했습니다.' '취소됩니다.'
            st.warning(f"🚨 {questioner_name} (비-스파이)이(가) 뜬금없이 장소 추측을 시도했습니다. 턴이 취소됩니다.")
            return

    elif action_type == "accuse_spy":
        # 비스파이의 스파이 지목
        accused_player = action_data
        if not st.session_state.players[questioner_name]["is_spy"]:
            if st.session_state.players.get(accused_player, {}).get("is_spy"):
                # 존댓말 변경: '지목했어.' -> '지목했습니다.'
                st.session_state.game_result = f"🎉 **게임 종료!** 플레이어 **{questioner_name}**이(가) 스파이 **{accused_player}**을(를) 정확히 지목했습니다. **비-스파이 승리!**"
            else:
                # 존댓말 변경: '아니었어.' -> '아니었습니다.'
                st.session_state.game_result = f"😔 플레이어 **{questioner_name}**이(가) **{accused_player}**을(를) 지목했지만, 그는 스파이가 아니었습니다.<br>스파이가 잡히지 않았으므로, **스파이 승리!**"
        else:
            # 존댓말 변경: '시도했어.' '취소돼.' -> '시도했습니다.' '취소됩니다.'
            st.warning(f"🚨 {questioner_name} (스파이)이(가) 자기들끼리 지목을 시도했습니다. 턴이 취소됩니다.")
            return

    st.session_state.game_phase = "finished"
    st.session_state.current_player_index = -1 


def handle_ai_turn():
    """AI 턴 로직 처리 (질문)"""
    
    current_idx = st.session_state.current_player_index
    questioner_name = st.session_state.player_names_list[current_idx]
    
    # 살아있는 플레이어만 대상으로 질문
    alive_targets = [n for n in st.session_state.player_names_list if n != questioner_name]
    if not alive_targets:
        # 존댓말 변경: '없어. (오류)' -> '없습니다. (오류)'
        st.warning("질문할 대상이 없습니다. (오류)")
        return
        
    target_name = random.choice(alive_targets)
    st.session_state.current_target = target_name 
    
    # 존댓말 변경: '중이야...' -> '중입니다...'
    with st.spinner(f"**{questioner_name}** AI가 생각 중입니다..."):
        response_message = get_ai_response(
            st.session_state.players[questioner_name],
            st.session_state.game_history,
            target_name,
            st.session_state.client,
            st.session_state.chosen_location
        )
        
    if response_message is None:
        return 

    question_text = response_message.content

    # 질문 메시지 형식: 🕵️ {질문자}이(가) {대상}에게 질문: {질문 내용}
    question_message = f"🕵️ {questioner_name}이(가) {target_name}에게 질문: {question_text}"
    st.session_state.game_history.append({"role": "user", "content": question_message})
    
    # === 핵심 수정 부분 (target_name이 '나'일 때의 phase 전환) ===
    # AI가 '나'에게 질문한 경우 -> 사람이 답변해야 하므로 phase를 변경
    if target_name == "나":
        st.session_state.game_phase = "human_answer_wait" 
        # 존댓말 변경: '답변해 줘!' -> '답변해 주세요!'
        st.toast(f"**{questioner_name}**의 질문에 반말로 답변해 주세요!")
    # AI가 다른 AI에게 질문한 경우 -> 다음 턴은 AI 답변 턴
    else:
        # Phase는 in_progress를 유지하고, 다음 턴 렌더링에서 AI 답변 버튼이 나오도록 유도
        pass 
    
    st.rerun() 


def handle_ai_answer_process():
    """AI 질문에 대한 AI 답변 처리"""
    
    # 대화 기록의 가장 마지막 질문을 파싱
    last_question_message = st.session_state.game_history[-1]["content"]
    
    # '🕵️ ' 접두사 제거 후 파싱
    clean_message = last_question_message.replace("🕵️ ", "")
    
    parts = clean_message.split("에게 질문: ")
    if len(parts) < 2:
        # 존댓말 변경: '잘못되었어.' -> '잘못되었습니다.'
        st.error("마지막 질문 메시지 형식이 잘못되었습니다.")
        return
        
    questioner_name_from_msg = parts[0].split("이(가) ")[0].strip() # 질문자 
    target_name_from_msg = parts[0].split("이(가) ")[1].strip() # 답변자 
    question_text = parts[1].strip()
    
    target_name = target_name_from_msg

    if target_name != "나":
        time.sleep(2) 
        
        # 존댓말 변경: '중이야...' -> '중입니다...'
        with st.spinner(f"**{target_name}** AI가 답변 중입니다..."):
            answer_text = get_ai_answer(
                st.session_state.players[target_name], 
                st.session_state.game_history, 
                question_text, 
                st.session_state.client,
                st.session_state.chosen_location
            )
        
        answer_message = f"🤖 {target_name}의 답변: {answer_text}"
        st.session_state.game_history.append({"role": "assistant", "content": answer_message})
        
        # === 핵심 변경: 답변자(Target)가 다음 질문자(current_player_index)가 됩니다. ===
        next_questioner_index = st.session_state.player_names_list.index(target_name)
        st.session_state.current_player_index = next_questioner_index
        # =======================================================================
        st.rerun() 

    else:
        st.error("시스템 오류: AI 답변 턴에 사람이 답변할 차례입니다. (Phase 전환 오류)")


def handle_human_turn(user_input: str, target_name: str):
    """사람 플레이어 ('나')의 입력 처리 (질문/답변)"""
    
    questioner_name = st.session_state.player_names_list[st.session_state.current_player_index]
    
    # (1) 답변 차례 (AI 질문에 대한 답변)
    if st.session_state.game_phase == "human_answer_wait":
        answer_message = f"🙋‍♂️ 나의 답변: {user_input}"
        st.session_state.game_history.append({"role": "assistant", "content": answer_message})

        # === 핵심 변경: 답변자('나', index 7)가 다음 질문자가 됩니다. ===
        next_questioner_index = st.session_state.player_names_list.index("나") 
        st.session_state.current_player_index = next_questioner_index
        # ===================================================================

        st.session_state.game_phase = "in_progress" # 질문 턴으로 전환
        st.rerun() 
        
    # (2) 질문 차례 ('나'가 질문자)
    elif st.session_state.game_phase == "in_progress" and questioner_name == "나":
        
        # 질문 메시지 형식: 🕵️ {질문자}이(가) {대상}에게 질문: {질문 내용}
        question_text = user_input
        question_message = f"🕵️ {questioner_name}이(가) {target_name}에게 질문: {question_text}"
        st.session_state.game_history.append({"role": "user", "content": question_message})
        
        time.sleep(2) 

        # AI 답변 받기
        # 존댓말 변경: '중이야...' -> '중입니다...'
        with st.spinner(f"**{target_name}** AI가 답변 중입니다..."):
            answer_text = get_ai_answer(
                st.session_state.players[target_name], 
                st.session_state.game_history, 
                question_text, 
                st.session_state.client,
                st.session_state.chosen_location
            )
        
        answer_message = f"🤖 {target_name}의 답변: {answer_text}"
        st.session_state.game_history.append({"role": "assistant", "content": answer_message})

        # === 핵심 변경: 답변자(Target)가 다음 질문자가 됩니다. ===
        next_questioner_index = st.session_state.player_names_list.index(target_name)
        st.session_state.current_player_index = next_questioner_index
        # ===================================================================
        st.rerun() 
            
    else:
        # 존댓말 변경: '네 차례가 아니야.' -> '당신의 차례가 아닙니다.'
        st.warning("지금은 당신의 차례가 아닙니다.")

def display_player_info():
    """현재 플레이어 목록 및 역할 표시"""
    st.header("🕵️‍♂️ 플레이어 목록")
    for name in st.session_state.player_names_list:
        player = st.session_state.players[name]
        
        # 게임 종료 후에는 모두의 역할 공개
        if st.session_state.game_phase == 'finished':
            final_role_display = f"(역할: {player['role']})"
            
        else:
            # 게임 진행 중에는 나의 역할만 공개
            role_display = f"**{player['display_role']}**" if name == '나' else '???'
            final_role_display = f"(역할: {role_display})"

        is_current = (st.session_state.player_names_list[st.session_state.current_player_index] == name) and st.session_state.game_phase not in ['finished', 'human_answer_wait']
        
        if is_current:
            st.markdown(f"**👉 {name}** {final_role_display}", unsafe_allow_html=True)
        else:
            st.markdown(f"**{name}** {final_role_display}")
            
    if st.session_state.game_phase == 'finished':
        st.markdown(f"---")
        st.info(f"비밀 장소: **{st.session_state.chosen_location}**")

# --- 4. Streamlit UI 페이지 구성 ---

def set_page(page_name: str):
    """페이지를 전환하는 헬퍼 함수"""
    st.session_state.page = page_name
    st.rerun()

def render_sidebar():
    """사이드바 구성 요소 렌더링"""
    
    st.sidebar.header("🗺️ 메뉴")
    openai_key_exists = os.environ.get("OPENAI_API_KEY") is not None
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🏠 홈 화면", use_container_width=True):
        set_page("home")

    if st.sidebar.button("📝 게임 설명", use_container_width=True):
        set_page("info")
        
    # 게임 진행 페이지로의 이동 버튼
    if st.sidebar.button("▶️ 게임 진행", use_container_width=True, disabled=(st.session_state.get("game_phase") == "setup")):
        set_page("play")

    st.sidebar.markdown("---")
    # 게임 시작/재시작 버튼
    if st.sidebar.button("🔥 게임 시작 / 재시작", use_container_width=True, disabled=not openai_key_exists):
        init_game() 
        st.rerun() 
        
    if st.session_state.get("game_phase") not in ["setup", None, "finished"]:
        st.sidebar.markdown("---")
        st.sidebar.subheader("나의 역할")
        player_me = st.session_state.players["나"]
        st.sidebar.markdown(f"**{player_me['role']}**")
        if not player_me["is_spy"]:
            st.sidebar.markdown(f"(비밀 장소: **{st.session_state.chosen_location}**)")


def render_home_page():
    """홈 화면 렌더링 (요청에 따라 UI 대폭 수정)"""
    
    openai_key_exists = os.environ.get("OPENAI_API_KEY") is not None
    
    # 1. 제목, 부제 크기 키우기 (HTML)
    st.markdown(
        "<h1 style='text-align: center; color: #FF4B4B; font-size: 5em; margin-bottom: 0.1em;'>🤫 AI 스파이폴 봇전 🕵️‍♀️</h1>", 
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='text-align: center; font-size: 2em; margin-top: 0;'>8명의 플레이어 중 2명의 스파이를 찾아라!</p>", 
        unsafe_allow_html=True
    )
    
    # 3. 버튼 정중앙부터 조금 밑에 배치 (간격 띄우기)
    st.markdown("<div style='height: 150px;'></div>", unsafe_allow_html=True)
    
    # 4. 버튼 사이즈 조절 및 중앙 정렬을 위한 Custom CSS Inject
    BUTTON_HEIGHT = 70 
    BUTTON_WIDTH = 350 # 70 * 5
    
    # CSS를 사용하여 버튼 크기를 고정하고, 버튼 컨테이너를 중앙 정렬
    custom_css = f"""
    <style>
    /* [🔥 게임 시작] 버튼 */
    div[data-testid="stKey-home_start_btn"] > button {{
        height: {BUTTON_HEIGHT}px;
        width: {BUTTON_WIDTH}px;
        font-size: 1.5em; 
        margin-bottom: 15px; /* 버튼 사이 세로 간격 */
    }}

    /* [📝 게임 설명 보기] 버튼 */
    div[data-testid="stKey-home_info_btn"] > button {{
        height: {BUTTON_HEIGHT}px;
        width: {BUTTON_WIDTH}px;
        font-size: 1.5em; 
    }}
    
    /* 버튼을 담고 있는 컨테이너를 중앙에 정렬 */
    /* st.columns를 사용하기 때문에, 중앙 column 내부의 stVerticalBlock을 중앙 정렬 */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {{
        display: flex;
        flex-direction: column;
        align-items: center; 
    }}
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

    # 중앙 정렬을 위해 컬럼 사용
    _, col_center, _ = st.columns([1, BUTTON_WIDTH/400 + 0.5, 1]) 

    with col_center:
        # 1. [🔥 게임 시작] 버튼
        if st.button("🔥 게임 시작", key="home_start_btn", disabled=not openai_key_exists): 
            init_game()

        # 2. [📝 게임 설명 보기] 버튼
        if st.button("📝 게임 설명 보기", key="home_info_btn"):
            set_page("info")

    if not openai_key_exists:
        st.warning("⚠️ 환경 변수 'OPENAI_API_KEY'가 설정되어 있어야 게임을 시작할 수 있습니다.")


def render_info_page():
    """게임 설명 페이지 렌더링"""
    st.header("📝 AI 스파이폴 봇전 규칙")
    st.markdown("---")
    
    st.subheader("1. 게임의 기본")
    st.markdown("- **플레이어:** 8명 (AI 7명 + 당신 1명)입니다.")
    st.markdown("- **역할:** 비-스파이 6명 (각자 역할이 있음), 스파이 2명으로 나뉩니다.")
    st.markdown("- **장소:** 비-스파이는 비밀 장소와 자신의 역할을 알지만, 스파이는 자신이 스파이라는 것만 압니다.")
    
    st.subheader("2. 턴 진행")
    st.markdown("- **턴 진행:** 질문을 받은 플레이어가 답변 후 다음 질문자가 됩니다.")
    st.markdown("- **질문:** 플레이어들은 돌아가며 다른 플레이어 한 명을 지목해서 질문합니다.")
    st.markdown("- **모든 질문과 답변은 장소에 대한 정보를 간접적으로 담아야 합니다.** 하지만 너무 노골적이면 스파이가 장소를 알게 되겠죠?")
    st.markdown("- AI들은 **친근한 반말**로 대화합니다. 당신도 반말로 대화해 주셔야 합니다.")
    
    st.subheader("3. 승리 조건")
    st.markdown(f"게임은 **계속 진행**됩니다. 게임 종료는 당신의 **[스파이 지목하기]** 또는 **[장소 맞추기]** 액션으로만 결정됩니다.")
    
    st.markdown("#### **A. 비-스파이 승리**")
    st.markdown("- 비-스파이 플레이어가 **스파이를 정확하게 지목**했을 때.")
    st.markdown("- 스파이가 **장소 추측에 실패**했을 때.")
    st.markdown("#### **B. 스파이 승리**")
    st.markdown("- 스파이가 **비밀 장소를 정확하게 추측**했을 때.")
    st.markdown("- 스파이/비-스파이 모두 게임을 종료하는 액션을 취하지 않고 **무한히 진행**될 경우, 스파이가 잠재적으로 승리합니다.")

    st.subheader("4. 액션 타이밍")
    st.markdown("- 당신의 턴(질문 차례)에 **항상** 액션 기회가 주어집니다. 신중하게 결정해 주세요.")
    st.markdown("- 이 때, **비-스파이**는 스파이를 지목하거나, **스파이**는 장소를 추측할 수 있습니다.")
    st.markdown("- 지목/추측은 단 한 번의 기회입니다. 성공하면 게임이 종료됩니다.")


def render_play_page():
    """게임 진행 페이지 렌더링"""
    
    if st.session_state.get("game_phase") in ["setup", None]:
        st.warning("게임이 아직 시작되지 않았습니다. '🔥 게임 시작' 버튼을 눌러주세요.")
        return

    col1, col2 = st.columns([1, 2])

    with col1:
        # 현재 장소 정보를 가장 위에 명확히 표시
        is_spy = st.session_state.players['나']['is_spy']
        location = st.session_state.chosen_location
        
        if is_spy:
            st.markdown(f"## 🤫 장소: **???**")
        else:
            st.markdown(f"## 📍 장소: **{location}**")
        
        st.markdown("---")
        
        display_player_info() 

        with st.expander("📍 모든 장소 목록 보기"):
            st.markdown(LOCATION_LIST_FOR_DISPLAY)


    with col2:
        st.header("💬 대화 기록")

        # 대화 기록 컨테이너
        chat_container = st.container(height=500)
        with chat_container:
            for message in st.session_state.game_history:
                # 액션 메시지는 특별히 강조
                if message["content"].startswith("액션:"):
                    st.markdown(f"**📢 {message['content']}**", unsafe_allow_html=True)
                    continue
                # 질문과 답변에 아이콘과 텍스트를 조합하여 표시
                if message["role"] == "user":
                    st.markdown(f"**{message['content']}**", unsafe_allow_html=True)
                else:
                    st.markdown(f"**{message['content']}**", unsafe_allow_html=True)
        
        # ------------------
        # 입력 및 턴 관리
        # ------------------
        
        # 사람 플레이어('나')의 답변 대기 턴 (AI가 나에게 질문했을 때)
        if st.session_state.game_phase == "human_answer_wait":
            
            # AI가 '나'에게 질문한 내용은 이미 game_history[-1]에 있습니다.
            # 질문자 파싱
            last_message_content = st.session_state.game_history[-1]["content"]
            questioner = last_message_content.split("이(가) ")[0].replace("🕵️ ", "")
            question_text = last_message_content.split("에게 질문: ")[1].strip()
            
            st.warning(f"**{questioner}**이(가) 당신에게 질문했습니다: **{question_text}**")
            
            user_answer = st.text_input("당신의 답변을 반말로 입력해 주세요.", key="answer_input_key")
            
            if st.button("답변 제출", use_container_width=True, disabled=not user_answer):
                handle_human_turn(user_answer, "") 
        
        # 일반 턴 진행 (질문/답변) - phase가 in_progress일 때만 작동
        elif st.session_state.game_phase == "in_progress":
            
            current_player = st.session_state.player_names_list[st.session_state.current_player_index]
            last_message_role = st.session_state.game_history[-1]['role'] if st.session_state.game_history else 'assistant'

            # AI 턴 (질문) - current_player가 AI이고, 마지막 메시지가 답변이거나 게임 시작인 경우
            is_ai_turn_to_ask = (current_player != "나") and (last_message_role == 'assistant')
            
            # AI 턴 (답변) - current_player는 이전 질문자 AI이지만, 마지막 메시지가 AI->AI 질문인 경우
            is_ai_turn_to_answer = (current_player != "나") and (last_message_role == 'user') and ("에게 질문: " in st.session_state.game_history[-1]["content"])

            # 사람 플레이어('나')의 질문 턴 (사람이 다음 질문자가 되었을 때)
            is_human_turn_to_ask = (current_player == "나")

            if is_ai_turn_to_ask:
                st.info(f"**AI 턴 (질문):** {current_player}의 차례입니다.")
                if st.button(f"**{current_player}**의 턴 진행", use_container_width=True, key="ai_turn_q"):
                    handle_ai_turn()
            
            elif is_ai_turn_to_answer:
                 # 질문 메시지에서 대상이 '나'가 아님을 확인 (이미 human_answer_wait에서 걸러졌어야 함)
                 target_name_from_msg = st.session_state.game_history[-1]["content"].split("에게 질문: ")[0].split("이(가) ")[1].strip()

                 if target_name_from_msg != "나":
                    st.info(f"**AI 답변 턴:** {target_name_from_msg}가 답변 진행 중입니다...")
                    if st.button(f"AI 답변 확인", use_container_width=True, key="ai_turn_a"):
                        handle_ai_answer_process()
                 else:
                     st.error("시스템 오류: AI가 '나'에게 질문했지만, 답변 대기 상태로 전환되지 않았습니다.")


            elif is_human_turn_to_ask:
                st.info(f"**당신의 턴입니다:** 누구에게 질문하거나 액션을 취하시겠어요?")
                
                alive_targets = [n for n in st.session_state.player_names_list if n != "나"]
                target_name = st.selectbox("질문 대상 선택", alive_targets, key="human_target_select")
                
                user_input = st.text_input("질문 내용을 반말로 입력해 주세요.", placeholder="구체적이고 직관적인 질문을 해 주세요.", key="user_input_key")

                # 지목/추측 액션은 팝오버로 분리 (항시 버튼)
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