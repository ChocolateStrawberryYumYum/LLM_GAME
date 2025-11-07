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

SPYFALL_CATALOGUE = "\n".join([
    f"- {location}: {', '.join(roles)}"
    for location, roles in SPYFALL_LOCATIONS_DATA.items()
])

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
    
    # 30개 이상의 상세하고 구체적인 질문 예시 추가 (직관적 표현 사용 유도)
    question_examples = [
        "여기서 보통 몇 시에 퇴근(혹은 귀가)하니? 구체적인 시간을 말해 줘.",
        "이곳에서 일하면서(혹은 활동하면서) 느끼는 가장 큰 어려움이나 힘든 점은 뭐야?",
        "이 시설/장소는 보통 몇 시에 문을 닫거나 운영을 종료하는 거야?",
        "일 년 중 어느 계절에 사람들이 이곳을 가장 많이 방문하거나 이용하니? 특별한 이유라도 있어?",
        "혹시 여기에 두었던 OOO(장소와 관련된 물건, 예: 노란 구명조끼, 지점장의 도장)를 네가 치웠니? 어디로 옮긴 거야?",
        "이곳까지 대중교통(예: 지하철, 버스)을 이용해서 올 수 있어? 걸리는 시간은 얼마나 돼?",
        "이곳을 방문하거나 이용할 수 있는 최소 연령이 있니? (예: 초등학생들도 올 수 있어?)",
        "이곳의 시설 규모는 어느 정도야? (예: 몇 층 건물인지, 몇 명이 동시에 수용 가능한지)",
        "이곳에서 특별히 제공되는 서비스나 이벤트 같은 게 있니? (예: 주말 할인, 특별 공연)",
        "이곳의 주요 방문 목적은 뭐라고 생각해? (예: 휴식, 업무, 치료)",
        "평소 복장은 어떻게 되는 거야? (예: 유니폼, 정장, 편안한 복장)",
        "이곳을 가장 처음 알게 된 계기는 뭐야?",
        "혹시 이곳에서 가장 비싸거나 중요한 물건은 무엇이니?",
        "만약 이곳에 없다면 가장 그리울 것은 뭘까?",
        "이 주변에 유명하거나 추천할 만한 다른 장소가 있어?",
        "이곳의 소음 수준은 어떤 편이야? (예: 조용한 편인지, 시끄러운 편인지)",
        "이곳에서 일하면서(활동하면서) 얻는 가장 큰 보람은 뭐야?",
        "이곳에서 가장 인기 있는 메뉴나 활동은 뭐야?",
        "이곳에서 규칙이나 지켜야 할 사항 중 가장 중요하다고 생각되는 것은 뭐야?",
        "비가 오거나 날씨가 안 좋을 때 이곳의 분위기는 어떻게 변하니?",
        "이곳에 오기 위해 특별한 예약이나 절차가 필요해?",
        "이곳의 청소나 유지보수는 주로 누가 담당하는 거야?",
        "이곳에서 가장 자주 만나는 사람은 어떤 유형의 사람들일까?",
        "이곳에 도착하기 전에 거쳐야 하는 특별한 관문이나 보안 절차가 있니?",
        "이곳에서 근무(활동)한 지는 얼마나 되었어? 경력이 어떻게 돼?",
        "이곳을 상징하는 특별한 색깔이나 마스코트가 있어?",
        "이곳에 와서 가장 놀랐던 일이나 특이했던 경험이 있니?",
        "이곳에선 금지된 행위나 제한되는 활동이 있어?",
        "이곳에서 사용하는 특별한 전문 용어가 있다면 뭘까?",
        "이곳의 전기(혹은 물) 사용량은 많은 편이야?",
        "이곳에서 하루에 몇 시간 정도 머무르는 편이야?",
        "이 장소에서 가장 중요하게 여겨지는 가치는 뭐라고 생각해?"
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
            f"모든 질문은 **'언제' 대신 '몇 시에'처럼 직관적이고 구체적인 시점을 묻는 방식**을 사용해야 하며, **반드시 반말로 질문**해야 합니다."
            f"질문 예시: {'; '.join(question_examples)}"
        )
    else:
        # 비스파이 프롬프트
        return (
            f"당신은 **{chosen_location}**의 **{role}**입니다. "
            f"**당신은 지금부터 모든 대화에서 친근한 반말(예: ~야, ~하니, ~했어)을 사용해야 합니다. 절대 존댓말을 쓰지 마세요.** "
            f"당신의 이름은 {name}이며, 스파이에게 장소가 들키지 않도록 "
            f"**장소에 대한 정보를 절대적으로 절제해야 합니다.** "
            f"**당신의 역할이나 행위가 장소를 직접적으로 유추하게 만들어서는 안 됩니다.** "
            f"예를 들어, 역할이 '간호사'이더라도 '병원'이라는 단어나 '환자'라는 단어를 직접 사용해서는 안 됩니다. \n"
            f"**답변 생성 지침:**\n"
            f"1. **진실만 말하되, 최대한 모호하고 우회적으로 표현**하여 스파이가 장소를 알 수 없게 하세요.\n"
            f"2. 답변은 **15단어 이내**로 간결해야 하며, **반드시 반말로 답변**해야 합니다."
            f"3. 모든 답변은 질문에 **직관적이고 구체적으로** 보이는 어휘를 사용하여 답해야 합니다."
        )

def get_ai_response(player_data: Dict[str, Any], history: List[Dict[str, str]], 
                    target_player: str, client: OpenAI, chosen_location: str) -> Optional[Any]:
    
    system_prompt = create_system_prompt(player_data, chosen_location)
    
    # 턴 진행 중 AI의 액션 호출 방지
    current_turn_prompt = (
        f"현재 당신의 차례입니다. 당신은 플레이어 '{target_player}'에게 **새롭고 구체적인 질문 하나**를 해야 합니다. "
        f"이전에 다른 플레이어가 했던 질문과 비슷하거나 똑같은 질문은 절대 하지 마세요. "
        f"답변은 **[질문] 태그 없이** **실제 질문 내용**을 채워서 생성하세요. 답변은 **15단어 이내**로 간결하게 하세요. "
        f"**참고:** 게임을 종료하는 액션 함수(accuse_spy, guess_location)는 이 단계에서는 호출하지 마세요. 오직 질문만 하세요."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        *history, 
        {"role": "user", "content": current_turn_prompt}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview", 
            messages=messages,
            tools=TOOLS, 
            tool_choice="none", 
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
        f"당신은 질문을 받았습니다: '{question_text}' "
        f"당신의 역할과 상기된 답변 지침에 맞게 **15단어 이내**로 간결하게 답변하세요. 답변은 뒤에 **실제 답변 내용**을 채워서 생성하세요. 답변 앞에 어떤 식별자나 태그도 붙이지 마세요. 예: 저는 제 업무를 수행하고 있습니다."
    )
            
    answer_response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": target_prompt},
            *history,
            {"role": "user", "content": answer_prompt}
        ],
        temperature=0.8
    )
    
    answer_content = answer_response.choices[0].message.content.strip()
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
        st.error("환경 변수 'OPENAI_API_KEY'를 찾을 수 없습니다. 게임을 시작할 수 없습니다.")
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
    st.session_state.round_num = 1
    st.session_state.MAX_ROUNDS = 3 
    st.session_state.game_result = None
    st.session_state.action_window_open = False 

    # 플레이어에게 자신의 역할 표시
    my_role = players["나"]["role"]
    info_message = f"**당신의 역할:** **{my_role}** 입니다."
    if not players["나"]["is_spy"]:
        info_message += f" (비밀 장소: **{chosen_location}**)"
    st.success(info_message)
    st.toast("게임이 시작되었습니다! 🔥")


def handle_game_action(action_type: str, action_data: str, questioner_name: str):
    """스파이 지목 또는 장소 추측 시 게임 종료 로직 처리"""
    st.session_state.game_history.append({"role": "user", "content": f"액션: {questioner_name}이(가) {action_type}({action_data}) 시도"})
    
    if action_type == "guess_location":
        # 스파이의 장소 추측
        location_name = action_data
        if st.session_state.players[questioner_name]["is_spy"]:
            if location_name == st.session_state.chosen_location:
                st.session_state.game_result = f"🎉 **게임 종료!** 스파이 **{questioner_name}**이(가) 장소 **'{location_name}'**을(를) 정확히 맞췄습니다. **스파이가 임무를 완료했습니다! (스파이 승리!)**"
            else:
                st.session_state.game_result = f"❌ 스파이 **{questioner_name}**이(가) 장소 **'{location_name}'**을(를) 추측했으나 틀렸습니다. (정답: {st.session_state.chosen_location})<br>**스파이가 자수했습니다! (비-스파이 승리!)**"
        else:
            st.warning(f"🚨 {questioner_name} (비-스파이)이(가) 부적절하게 장소 추측을 시도했습니다. 턴이 취소됩니다.")
            return

    elif action_type == "accuse_spy":
        # 비스파이의 스파이 지목
        accused_player = action_data
        if not st.session_state.players[questioner_name]["is_spy"]:
            if st.session_state.players.get(accused_player, {}).get("is_spy"):
                st.session_state.players[accused_player]["is_alive"] = False 
                st.session_state.game_result = f"🎉 **게임 종료!** 플레이어 **{questioner_name}**이(가) 스파이 **{accused_player}**을(를) 정확히 지목했습니다. **비-스파이 승리!**"
            else:
                st.session_state.game_result = f"😔 플레이어 **{questioner_name}**이(가) **{accused_player}**을(를) 지목했지만, 그는 스파이가 아닙니다.<br>스파이가 잡히지 않았으므로, **스파이 승리!**"
        else:
            st.warning(f"🚨 {questioner_name} (스파이)이(가) 부적절하게 스파이 지목을 시도했습니다. 턴이 취소됩니다.")
            return

    st.session_state.game_phase = "finished"
    st.session_state.current_player_index = -1 


def handle_ai_turn():
    """AI 턴 로직 처리 (질문)"""
    
    current_idx = st.session_state.current_player_index
    questioner_name = st.session_state.player_names_list[current_idx]
    
    # 살아있는 플레이어만 대상으로 질문
    alive_targets = [n for n in st.session_state.player_names_list if n != questioner_name and st.session_state.players[n]["is_alive"]]
    if not alive_targets:
        st.warning("질문할 대상이 없습니다. (모두 사망 또는 오류)")
        st.session_state.current_player_index = (current_idx + 1) % len(PLAYER_NAMES)
        return
        
    target_name = random.choice(alive_targets)
    st.session_state.current_target = target_name 
    
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

    # 질문 메시지 형식 수정: 대상 이름 제거, 괄호로 대상만 표시
    question_message = f"{questioner_name}이(가) 질문: {question_text} (대상: {target_name})"
    st.session_state.game_history.append({"role": "user", "content": question_message})
    st.rerun() 


def handle_ai_answer_process():
    """AI 질문에 대한 AI 답변 처리"""
    
    current_idx = st.session_state.current_player_index
    
    # 대화 기록의 가장 마지막 질문을 파싱
    last_question_message = st.session_state.game_history[-1]["content"]
    parts = last_question_message.split(" (대상: ")
    if len(parts) < 2:
        st.error("마지막 질문 메시지 형식이 잘못되었습니다.")
        st.session_state.current_player_index = (current_idx + 1) % len(PLAYER_NAMES)
        return
        
    target_name = parts[1][:-1].strip() 
    question_text = parts[0].split("이(가) 질문: ")[1].strip()
    questioner_name = parts[0].split("이(가) 질문: ")[0].strip()

    if target_name != "나":
        # 2초 딜레이 추가
        time.sleep(2) 
        
        with st.spinner(f"**{target_name}** AI가 답변 중입니다..."):
            answer_text = get_ai_answer(
                st.session_state.players[target_name], 
                st.session_state.game_history, 
                question_text, 
                st.session_state.client,
                st.session_state.chosen_location
            )
        
        answer_message = f"{target_name}의 답변: {answer_text}"
        st.session_state.game_history.append({"role": "assistant", "content": answer_message})
        
        st.session_state.current_player_index = (current_idx + 1) % len(PLAYER_NAMES)
        st.rerun() 

    else:
        # AI가 '나'에게 질문한 경우
        st.session_state.current_question = question_text
        st.session_state.game_phase = "human_answer_wait"
        st.toast(f"**{questioner_name}**의 질문에 답변해주세요!")
        st.rerun() 


def handle_human_turn(user_input: str, target_name: str):
    """사람 플레이어 ('나')의 입력 처리 (질문/답변)"""
    
    current_idx = st.session_state.current_player_index
    questioner_name = st.session_state.player_names_list[current_idx]
    
    # (1) 답변 차례 (AI 질문에 대한 답변)
    if st.session_state.game_phase == "human_answer_wait":
        answer_message = f"나의 답변: {user_input}"
        st.session_state.game_history.append({"role": "assistant", "content": answer_message})

        st.session_state.current_player_index = (current_idx + 1) % len(PLAYER_NAMES)
        st.session_state.game_phase = "in_progress"
        del st.session_state.current_question 
        st.rerun() 
        
    # (2) 질문 차례 ('나'가 질문자)
    elif st.session_state.game_phase == "in_progress" and questioner_name == "나":
        
        # 질문 메시지 형식 수정: 대상 이름 제거, 괄호로 대상만 표시
        question_text = user_input
        question_message = f"{questioner_name}이(가) 질문: {question_text} (대상: {target_name})"
        st.session_state.game_history.append({"role": "user", "content": question_message})
        
        # 2초 딜레이 추가
        time.sleep(2) 

        # AI 답변 받기
        with st.spinner(f"**{target_name}** AI가 답변 중입니다..."):
            answer_text = get_ai_answer(
                st.session_state.players[target_name], 
                st.session_state.game_history, 
                question_text, 
                st.session_state.client,
                st.session_state.chosen_location
            )
        
        answer_message = f"{target_name}의 답변: {answer_text}"
        st.session_state.game_history.append({"role": "assistant", "content": answer_message})

        st.session_state.current_player_index = (current_idx + 1) % len(PLAYER_NAMES)
        st.rerun() 
            
    else:
        st.warning("지금은 당신의 차례가 아닙니다.")


def check_round_end():
    """턴 수를 확인하고 라운드 종료 처리"""
    # 마지막 턴이 답변(assistant)이었고, 현재 인덱스가 0이면 라운드 종료
    if st.session_state.current_player_index == 0 and st.session_state.game_history and st.session_state.game_history[-1]['role'] == 'assistant':
        
        if st.session_state.round_num >= st.session_state.MAX_ROUNDS:
            st.session_state.game_result = "**최대 라운드 도달.** 스파이가 잡히지 않았으므로, **스파이 승리!**"
            st.session_state.game_phase = "finished"
            return

        # 라운드 종료 후 액션 페이즈로 전환
        st.session_state.game_phase = "action_phase_wait"
        st.session_state.action_start_time = time.time()
        st.toast(f"✅ 라운드 {st.session_state.round_num} 종료! 액션 시간(10초)이 시작됩니다.")
        st.rerun()

def proceed_to_next_round():
    """액션 페이즈가 끝난 후 다음 라운드로 전환"""
    st.session_state.round_num += 1
    st.session_state.game_phase = "in_progress"
    st.toast(f"▶️ 새 라운드 {st.session_state.round_num} 시작!")
    st.rerun()

def display_player_info():
    """현재 플레이어 목록 및 역할 표시 (NameError 해결)"""
    st.header("🕵️‍♂️ 플레이어 목록")
    for name in st.session_state.player_names_list:
        player = st.session_state.players[name]
        
        # 게임 종료 후에는 모두의 역할 공개
        if st.session_state.game_phase == 'finished':
            # 스파이 지목 성공 시, 스파이 역할을 (역할: 스파이)로 변경
            role_display = f"**{player['display_role']}**" 
            
            if not player["is_alive"] and player['is_spy']:
                status = " 💀" # 사망 이모지
                # 역할 공개: 지목당한 스파이
                final_role_display = f"(역할: 스파이){status}" 
            elif not player["is_alive"] and not player['is_spy']:
                status = " 💀 (오지목)"
                final_role_display = f"(역할: {player['role']}){status}" 
            else:
                status = ""
                final_role_display = f"(역할: {player['role']}){status}" 
                
        else:
            # 게임 진행 중에는 나의 역할만 공개
            role_display = f"**{player['display_role']}**" if name == '나' else '???'
            final_role_display = f"(역할: {role_display})"
            status = ""

        is_current = (st.session_state.player_names_list[st.session_state.current_player_index] == name) and st.session_state.game_phase != 'finished' and st.session_state.game_phase != 'action_phase_wait'
        
        if is_current:
            st.markdown(f"**👉 {name}** {final_role_display}", unsafe_allow_html=True)
        else:
            st.markdown(f"**{name}** {final_role_display}")
            
    if st.session_state.game_phase == 'finished':
        st.markdown(f"---")
        st.info(f"비밀 장소: **{st.session_state.chosen_location}**")

# --- 4. Streamlit UI 구성 ---

def main():
    st.set_page_config(layout="wide")
    st.title("스파이폴 봇전")
    
    # 세션 상태 초기화
    if "game_phase" not in st.session_state:
        st.session_state.game_phase = "setup"
        st.session_state.current_player_index = 0 

    # 환경 변수 확인
    openai_key_exists = os.environ.get("OPENAI_API_KEY") is not None

    # ------------------
    # 사이드바 (설정)
    # ------------------
    with st.sidebar:
        st.header("게임 설정")
        if not openai_key_exists:
            st.warning("⚠️ 환경 변수 'OPENAI_API_KEY'가 설정되지 않았습니다.")
        if st.button("게임 시작 / 재시작", use_container_width=True, disabled=not openai_key_exists):
            init_game() 
            st.rerun() 
        
        if st.session_state.get("game_phase", "setup") != "setup":
            st.markdown("---")
            st.subheader("나의 역할")
            player_me = st.session_state.players["나"]
            st.markdown(f"**{player_me['role']}**")
            if not player_me["is_spy"]:
                st.markdown(f"(비밀 장소: **{st.session_state.chosen_location}**)")

    
    if st.session_state.game_phase == "setup":
        if openai_key_exists:
            st.info("환경 변수 설정이 확인되었습니다. '게임 시작' 버튼을 눌러주세요.")
        else:
             st.info("게임을 시작하려면 환경 변수 'OPENAI_API_KEY'가 설정되어 있어야 합니다.")
        return

    # 게임 진행 중
    col1, col2 = st.columns([1, 2])

    with col1:
        if st.session_state.game_phase != 'setup':
            is_spy = st.session_state.players['나']['is_spy']
            location = st.session_state.chosen_location
            
            if is_spy:
                st.markdown(f"## 🤫 장소: **???**")
            else:
                st.markdown(f"## 📍 장소: **{location}**")
            
            st.markdown("---")
        
        display_player_info() # NameError 해결

        st.markdown(f"---")
        if st.session_state.game_phase != 'finished':
            st.markdown(f"**라운드:** {st.session_state.round_num} / {st.session_state.MAX_ROUNDS}")

        with st.expander("📍 모든 장소 목록 보기"):
            st.markdown(LOCATION_LIST_FOR_DISPLAY)


    with col2:
        st.header("💬 대화 기록")

        # 대화 기록 컨테이너
        chat_container = st.container(height=500)
        with chat_container:
            for message in st.session_state.game_history:
                role_icon = "🕵️" if message["role"] == "user" else "🤖"
                st.markdown(f"**{role_icon} {message['content']}**", unsafe_allow_html=True)
        
        # ------------------
        # 입력 및 턴 관리
        # ------------------
        
        # 액션 페이즈 (라운드 종료 후)
        if st.session_state.game_phase == "action_phase_wait":
            
            elapsed_time = time.time() - st.session_state.action_start_time
            time_limit = 10
            
            action_window_open = elapsed_time < time_limit

            st.markdown(f"**📣 액션 시간!** (남은 시간: {max(0, round(time_limit - elapsed_time))}초)", unsafe_allow_html=True)
            st.warning("스파이라고 확신한다면, 지금 지목하거나 장소를 맞추세요!")

            col_a, col_g, col_n = st.columns([1, 1, 1])
            player_me = st.session_state.players["나"]
            
            alive_targets = [n for n in st.session_state.player_names_list if n != "나" and st.session_state.players[n]["is_alive"]]

            # 비스파이: 스파이 지목하기
            if not player_me["is_spy"]:
                with col_a:
                    with st.popover("🕵️ 스파이 지목하기", disabled=not action_window_open):
                        accuse_player_name = st.selectbox("스파이라고 생각하는 플레이어 지목", alive_targets, key="accuse_player_action")
                        if st.button("스파이 지목 제출", key="accuse_spy_btn_action", use_container_width=True, disabled=not action_window_open):
                            handle_game_action("accuse_spy", accuse_player_name, "나")
                            st.rerun()
            # 스파이: 장소 맞추기
            else:
                with col_g:
                    with st.popover("📍 장소 맞추기", disabled=not action_window_open):
                        guess_location_name = st.selectbox("장소를 추측합니다.", LOCATION_NAMES, key="guess_loc_action")
                        if st.button("장소 추측 제출", key="guess_loc_btn_action", use_container_width=True, disabled=not action_window_open):
                            handle_game_action("guess_location", guess_location_name, "나")
                            st.rerun()

            with col_n:
                if not action_window_open or st.button("액션 생략 / 다음 라운드 진행", key="proceed_btn", use_container_width=True):
                    if action_window_open:
                        st.toast("액션 기회를 놓쳤습니다. 다음 라운드로 진행합니다.")
                    proceed_to_next_round()
                    
        # 일반 턴 진행 (질문/답변)
        elif st.session_state.game_phase == "in_progress":
            check_round_end() 
            
            if st.session_state.game_phase == "action_phase_wait" or st.session_state.game_phase == "finished":
                st.rerun() 
                return

            current_player = st.session_state.player_names_list[st.session_state.current_player_index]
            
            # AI 턴 (질문)
            is_ai_turn_to_ask = (current_player != "나") and (not st.session_state.game_history or st.session_state.game_history[-1]['role'] == 'assistant')
            # AI 턴 (답변)
            is_ai_turn_to_answer = (current_player != "나") and st.session_state.game_history and st.session_state.game_history[-1]['role'] == 'user' and not 'current_question' in st.session_state

            if is_ai_turn_to_ask:
                st.info(f"**AI 턴:** {current_player}의 차례입니다.")
                if st.button(f"**{current_player}**의 턴 진행", use_container_width=True, key="ai_turn_q"):
                    handle_ai_turn()
            
            elif is_ai_turn_to_answer:
                 st.info(f"**AI 답변 턴:** 답변 진행 중...")
                 if st.button(f"AI 답변 확인", use_container_width=True, key="ai_turn_a"):
                     handle_ai_answer_process()


            # 사람 플레이어('나')의 답변 대기 턴
            elif st.session_state.game_phase == "human_answer_wait":
                questioner = st.session_state.player_names_list[st.session_state.current_player_index]
                
                # 질문 메시지 파싱
                last_question = st.session_state.game_history[-1]["content"]
                question_text = last_question.split("이(가) 질문: ")[1].split(" (대상: 나)")[0]
                
                st.warning(f"**{questioner}**이(가) 당신에게 질문했습니다: **{question_text}**")
                
                user_answer = st.text_input("당신의 답변", key="answer_input_key")
                
                if st.button("답변 제출", use_container_width=True, disabled=not user_answer):
                    handle_human_turn(user_answer, "") 
            
            # 사람 플레이어('나')의 질문 턴
            elif current_player == "나" and st.session_state.game_phase == "in_progress":
                st.info(f"**나의 턴:** 누구에게 질문하시겠습니까?")
                
                alive_targets = [n for n in st.session_state.player_names_list if n != "나" and st.session_state.players[n]["is_alive"]]
                target_name = st.selectbox("질문 대상 선택", alive_targets, key="human_target_select")
                
                user_input = st.text_input("질문 내용", placeholder="구체적이고 직관적인 질문을 해보세요.", key="user_input_key")

                if st.button("질문 제출", use_container_width=True, disabled=not user_input or not target_name, key="human_ask_btn"):
                    handle_human_turn(user_input, target_name)

        
        elif st.session_state.game_phase == "finished":
            st.markdown("---")
            st.markdown(f"## 🏆 게임 종료")
            st.markdown(st.session_state.game_result, unsafe_allow_html=True)
            if st.button("게임 다시 시작", use_container_width=True):
                 st.session_state.game_phase = "setup"
                 st.rerun() 


if __name__ == "__main__":
    main()