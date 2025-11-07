import pygame
import time
import random
import sys

# --- 1. 기본 환경 설정 및 Pygame 초기화 ---
pygame.init()

# 화면 설정
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("카페 타이푼: LLM 오더 - 최종 버전")
clock = pygame.time.Clock()
FPS = 60

# 색상
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (50, 200, 50)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
RED = (255, 50, 50)
BROWN = (139, 69, 19)
GRAY = (200, 200, 200)

# 📌 폰트 설정 (사장님 환경에 맞게 경로를 수정해주세요!)
# Windows 예시: 'C:/Windows/Fonts/malgunbd.ttf'
# macOS 예시: '/System/Library/Fonts/Supplemental/AppleGothic.ttf'
KOREAN_FONT_PATH = 'C:/Windows/Fonts/malgunbd.ttf' 

try:
    font_small = pygame.font.Font(KOREAN_FONT_PATH, 18)
    font_medium = pygame.font.Font(KOREAN_FONT_PATH, 24)
    font_large = pygame.font.Font(KOREAN_FONT_PATH, 48)
except FileNotFoundError:
    print("Warning: 한글 폰트 파일을 찾을 수 없습니다. 기본 폰트로 대체합니다.")
    font_small = pygame.font.Font(None, 18)
    font_medium = pygame.font.Font(None, 24)
    font_large = pygame.font.Font(None, 48)

# --- 2. 게임 데이터 및 상수 ---
MAX_FAILED_ORDERS = 3
INITIAL_TIME_LIMIT = 30.0
INITIAL_INTERVAL = 15.0 

INGREDIENTS = {
    'ICE': '얼음', 'WATER': '물', 'MILK': '우유', 'SHOT': '샷',
    'SYRUP_S': '딸기', 'SYRUP_M': '망고', 'SYRUP_G': '청포도',
    'SODA': '탄산수', 'WHIP': '휘핑', 'CHIP': '초코칩',
    'BLENDER': '믹서기', 'TRASH': '쓰레기통'
}

INGREDIENT_VISUALS = {
    'ICE': (180, 220, 255, '제빙기'), 'WATER': (150, 150, 255, '정수기'),
    'MILK': (255, 255, 250, '우유팩'), 'SHOT': (70, 40, 0, '커피머신'),
    'SYRUP_S': (255, 100, 150, '딸기시럽'), 'SYRUP_M': (255, 200, 50, '망고시럽'),
    'SYRUP_G': (150, 255, 150, '청포도시럽'), 'SODA': (100, 200, 255, '탄산수'),
    'WHIP': (255, 255, 255, '휘핑크림'), 'CHIP': (80, 50, 0, '초코칩통'),
    'BLENDER': (100, 100, 150, '믹서기'), 'TRASH': (50, 50, 50, '쓰레기통')
}

INGREDIENT_POSITIONS = {
    'ICE': (50, SCREEN_HEIGHT // 2 + 55), 'WATER': (150, SCREEN_HEIGHT // 2 + 55),
    'MILK': (250, SCREEN_HEIGHT // 2 + 55), 'SHOT': (350, SCREEN_HEIGHT // 2 + 55),
    'SYRUP_S': (450, SCREEN_HEIGHT // 2 + 55), 'SYRUP_M': (550, SCREEN_HEIGHT // 2 + 55),
    'SYRUP_G': (650, SCREEN_HEIGHT // 2 + 55), 'SODA': (750, SCREEN_HEIGHT // 2 + 55),
    'WHIP': (850, SCREEN_HEIGHT // 2 + 55), 'CHIP': (950, SCREEN_HEIGHT // 2 + 55),
    'BLENDER': (1150, SCREEN_HEIGHT // 2 + 55),
    'TRASH': (SCREEN_WIDTH - 50, SCREEN_HEIGHT - 50)
}
INGREDIENT_SIZE = 80
TRASH_SIZE = 80

# --- 3. 클래스 정의 ---

class Order:
    """손님의 주문 정보와 제한 시간을 관리하는 클래스"""
    def __init__(self, menu_name, required_steps):
        self.menu_name = menu_name
        self.required_steps = required_steps
        self.start_time = time.time()
        self.time_limit = INITIAL_TIME_LIMIT

    def get_remaining_time(self):
        return self.time_limit - (time.time() - self.start_time)

    def get_time_color(self):
        remaining = self.get_remaining_time()
        if remaining > 20: return GREEN
        elif remaining > 10: return YELLOW
        elif remaining > 5: return ORANGE
        else: return RED

    def get_display_text(self):
        return f"{self.menu_name}"

class PlayerCup:
    """플레이어가 조작하는 컵과 그 내용물을 관리하는 클래스"""
    def __init__(self, x, y, width=50, height=80):
        self.contents = {}
        self.rect = pygame.Rect(x, y, width, height)
        self.is_dragging = False
        self.offset_x, self.offset_y = 0, 0
        self.original_pos = (x, y)

    def add_ingredient(self, ingredient_key):
        if ingredient_key == 'BLENDER':
            if any(key.startswith('SYRUP_') for key in self.contents):
                self.contents['BLENDED'] = True
        else:
            self.contents[ingredient_key] = self.contents.get(ingredient_key, 0) + 1
        
    def reset(self):
        self.contents = {}
        self.rect.topleft = self.original_pos

    def check_match(self, order):
        """현재 컵의 내용물이 주문에 맞는지 확인"""
        required = order.required_steps.copy()
        current = self.contents.copy()

        # 1. 믹서기 처리 확인
        if required.get('BLENDER'):
            if not current.get('BLENDED'): return False
            del required['BLENDER']
            if 'BLENDED' in current: del current['BLENDED']
        elif 'BLENDED' in current and current['BLENDED']:
            return False

        # 2. 필수 재료 확인
        for key, count in required.items():
            if current.get(key, 0) != count:
                return False

        # 3. 불필요한 재료 확인
        required_keys = set(required.keys())
        current_keys = set(k for k, v in current.items() if v > 0)
        
        if 'BLENDED' in current_keys: current_keys.remove('BLENDED')
        
        for key in current_keys:
            if key not in required_keys:
                return False

        return True
    
    def get_layer_config(self):
        """컵 내용물의 시각적 레이어 정보를 반환"""
        contents = self.contents
        shot_count = contents.get('SHOT', 0)
        syrup_key = next((k for k in contents.keys() if k.startswith('SYRUP_') and contents[k] > 0), None)
        is_blended = contents.get('BLENDED', False)

        layer_config = []
        total_height_ratio = 0.01 

        # 1층: 얼음 (ICE)
        if contents.get('ICE', 0) > 0 and not is_blended:
            layer_config.append({'color': INGREDIENT_VISUALS['ICE'][:3], 'height_ratio': 0.2})
            total_height_ratio += 0.2

        # 2층: 시럽/샷 (SHOT, SYRUP_*)
        base_color = None
        if syrup_key:
            base_color = INGREDIENT_VISUALS[syrup_key][:3]
        elif shot_count > 0:
            base_color = INGREDIENT_VISUALS['SHOT'][:3]

        if base_color and not is_blended:
            layer_config.append({'color': base_color, 'height_ratio': 0.2})
            total_height_ratio += 0.2

        # 3층: 주 음료 (MILK, WATER, SODA) - 남은 공간을 모두 채움
        main_liquid_color = None
        if contents.get('MILK', 0) > 0:
            main_liquid_color = INGREDIENT_VISUALS['MILK'][:3]
        elif contents.get('SODA', 0) > 0:
            main_liquid_color = INGREDIENT_VISUALS['SODA'][:3]
        elif contents.get('WATER', 0) > 0:
            # 스무디 처리 (색상 연하게)
            if is_blended:
                 syrup_color = list(INGREDIENT_VISUALS[syrup_key][:3])
                 main_liquid_color = tuple(min(255, c + 50) for c in syrup_color)
            else:
                 main_liquid_color = INGREDIENT_VISUALS['WATER'][:3]

        if main_liquid_color:
            remaining_ratio = max(0.01, 1.0 - total_height_ratio)
            layer_config.append({'color': main_liquid_color, 'height_ratio': remaining_ratio})
            
        return layer_config


# --- 4. 주문 파싱 및 생성 로직 ---

def parse_order_to_steps(order_text):
    steps = {}
    text = order_text.lower()
    
    # 1. 온도 처리 (아이스는 논커피 포함 기본으로 간주)
    is_ice = 'ice' in text or '아이스' in text or '에이드' in text or '스무디' in text
    if is_ice:
        steps['ICE'] = 1

    # 2. 베이스 음료 처리 (샷 추가 제거, 샷 1개 고정)
    if '아메리카노' in text:
        steps['WATER'] = 1
        steps['SHOT'] = 1 
    elif '라떼' in text:
        steps['MILK'] = 1
        steps['SHOT'] = 1
    
    # 3. 논커피 시럽 처리
    syrups = []
    if '딸기' in text and ('에이드' in text or '스무디' in text): syrups.append('SYRUP_S')
    if '망고' in text and ('에이드' in text or '스무디' in text): syrups.append('SYRUP_M')
    if '청포도' in text and ('에이드' in text or '스무디' in text): syrups.append('SYRUP_G')
    
    if len(syrups) >= 1: 
        steps[syrups[0]] = 1
    
    # 4. 논커피 제조 방식
    if '에이드' in text:
        steps['SODA'] = 1
    elif '스무디' in text:
        steps['WATER'] = steps.get('WATER', 0) + 1
        steps['BLENDER'] = 1
        
    # 5. 토핑 추가
    if '휘핑크림' in text:
        steps['WHIP'] = 1
    elif '초코칩' in text:
        steps['CHIP'] = 1

    return steps

def generate_llm_order():
    """랜덤한 메뉴 텍스트를 생성하여 LLM의 주문을 모방합니다."""
    menu_type = random.choice(['coffee', 'noncoffee'])
    
    if menu_type == 'coffee':
        temp = random.choice(['ice', 'hot'])
        base = random.choice(['아메리카노', '라떼']) 
        topping = random.choice(['', ' 휘핑크림 토핑 추가', ' 초코칩 토핑 추가'])
        
        menu_text = f"{temp} {base}{topping} 주세요." 
    else: # noncoffee
        syrup = random.choice(['딸기', '망고', '청포도'])
        style = random.choice(['에이드', '스무디'])
        
        menu_text = f"{syrup} {style} 만들어주세요."
        
    required_steps = parse_order_to_steps(menu_text)
    return menu_text, required_steps


# --- 5. 게임 초기화 및 변수 ---
orders = []
player_cup = PlayerCup(SCREEN_WIDTH // 2 - 25, SCREEN_HEIGHT - 120)
last_customer_time = time.time()
customer_interval = INITIAL_INTERVAL
failed_orders_count = 0
score = 0
game_over = False


# --- 6. 드로잉 함수 ---

def draw_table():
    table_rect = pygame.Rect(0, SCREEN_HEIGHT // 2, SCREEN_WIDTH, 150)
    pygame.draw.rect(screen, BROWN, table_rect)
    pygame.draw.line(screen, BLACK, (0, SCREEN_HEIGHT // 2), (SCREEN_WIDTH, SCREEN_HEIGHT // 2), 3)

def draw_ingredients():
    for key, pos in INGREDIENT_POSITIONS.items():
        rect = pygame.Rect(pos[0] - INGREDIENT_SIZE // 2, pos[1] - INGREDIENT_SIZE // 2, INGREDIENT_SIZE, INGREDIENT_SIZE)
        
        color, visual_text = INGREDIENT_VISUALS[key][:3], INGREDIENT_VISUALS[key][3]
        
        pygame.draw.rect(screen, color, rect, 0, 5)
        pygame.draw.rect(screen, BLACK, rect, 2, 5)
        
        # 텍스트는 하나만 중앙에 표시
        name_text = font_medium.render(visual_text, True, BLACK)
        name_rect = name_text.get_rect(center=rect.center)
        screen.blit(name_text, name_rect)
        
        yield key, rect

def draw_orders():
    for i, order in enumerate(orders):
        x = 10 + i * 250
        y = 10
        order_rect = pygame.Rect(x, y, 240, 80)
        color = order.get_time_color()
        
        pygame.draw.rect(screen, color, order_rect, 0, 5)
        pygame.draw.rect(screen, BLACK, order_rect, 2, 5)
        
        name_text = font_medium.render(order.get_display_text(), True, BLACK)
        time_text = font_medium.render(f"{order.get_remaining_time():.1f}s", True, BLACK)
        
        screen.blit(name_text, (x + 5, y + 5))
        screen.blit(time_text, (x + 5, y + 40))
        
        yield i, order_rect

def draw_player_cup():
    cup_rect = player_cup.rect
    contents = player_cup.contents
    
    cup_inner_height = cup_rect.height - 6
    cup_inner_width = cup_rect.width - 6
    cup_inner_x = cup_rect.x + 3
    cup_inner_y = cup_rect.y + 3
    
    # 1. 컵을 배경색(투명한 유리)으로 채움
    pygame.draw.rect(screen, (240, 240, 255), (cup_inner_x, cup_inner_y, cup_inner_width, cup_inner_height), 0, 5)
    
    # 2. 층 그리기
    layer_config = player_cup.get_layer_config()
    current_y = cup_inner_y + cup_inner_height
    
    for layer in reversed(layer_config): 
        layer_h = int(cup_inner_height * layer['height_ratio'])
        if layer_h > 0:
            current_y -= layer_h
            # 층을 그릴 때, 컵의 둥근 모서리를 고려해야 하지만, 간단하게 직사각형으로 처리
            pygame.draw.rect(screen, layer['color'], (cup_inner_x, current_y, cup_inner_width, layer_h), 0, 0)
        
    # 컵 외곽선
    pygame.draw.rect(screen, BLACK, cup_rect, 3, 5)
    
    # 4층: 토핑 시각화 (컵 위에 텍스트)
    if contents.get('WHIP', 0) > 0:
        whip_text = font_small.render("휘핑", True, BLACK)
        screen.blit(whip_text, (cup_rect.x + 5, cup_rect.y - 20))
    if contents.get('CHIP', 0) > 0:
        chip_text = font_small.render("초코", True, BLACK)
        screen.blit(chip_text, (cup_rect.x + 30, cup_rect.y - 20))
        
    # 현재 실패 횟수 표시
    fail_text = font_medium.render(f"실패: {failed_orders_count}/{MAX_FAILED_ORDERS}", True, RED)
    screen.blit(fail_text, (SCREEN_WIDTH - 200, 10))
    
    # 점수 표시
    score_text = font_medium.render(f"점수: {score}", True, BLACK)
    screen.blit(score_text, (SCREEN_WIDTH - 200, 40))


# --- 7. 메인 게임 루프 ---

def run_game():
    global orders, last_customer_time, customer_interval, failed_orders_count, score, game_over
    
    current_ingredient_rects = list(draw_ingredients())

    running = True
    while running:
        current_time = time.time()
        mouse_pos = pygame.mouse.get_pos()
        
        # --- 이벤트 처리 ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            elif not game_over:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if player_cup.rect.collidepoint(mouse_pos):
                        player_cup.is_dragging = True
                        player_cup.offset_x = player_cup.rect.x - mouse_pos[0]
                        player_cup.offset_y = player_cup.rect.y - mouse_pos[1]
                
                elif event.type == pygame.MOUSEBUTTONUP:
                    if player_cup.is_dragging:
                        player_cup.is_dragging = False
                        
                        # A. 쓰레기통에 드롭: 리셋
                        trash_rect = pygame.Rect(INGREDIENT_POSITIONS['TRASH'][0] - TRASH_SIZE // 2, 
                                                 INGREDIENT_POSITIONS['TRASH'][1] - TRASH_SIZE // 2, 
                                                 TRASH_SIZE, TRASH_SIZE)
                        if trash_rect.collidepoint(event.pos):
                            player_cup.reset()
                            
                        # B. 재료에 드롭: 재료 추가
                        ingredient_added = False
                        for key, rect in current_ingredient_rects:
                            if key not in ['TRASH'] and rect.collidepoint(event.pos):
                                player_cup.add_ingredient(key)
                                ingredient_added = True
                                break
                        
                        # C. 주문 목록에 드롭: 완료 시도
                        if not ingredient_added:
                            for i, order_rect in draw_orders():
                                if order_rect.collidepoint(event.pos):
                                    order = orders[i]
                                    if player_cup.check_match(order):
                                        # 성공!
                                        score += int(order.time_limit * 10 / max(1, order.get_remaining_time()))
                                        orders.pop(i)
                                        player_cup.reset() 
                                        break
                                    else:
                                        # 실패! 
                                        player_cup.rect.topleft = player_cup.original_pos
                                        print("❌ 잘못된 메뉴입니다!")
                                        break
                        
        # --- 업데이트 로직 ---
        if not game_over:
            
            if player_cup.is_dragging:
                player_cup.rect.x = mouse_pos[0] + player_cup.offset_x
                player_cup.rect.y = mouse_pos[1] + player_cup.offset_y
                
            if current_time - last_customer_time > customer_interval:
                menu_text, required_steps = generate_llm_order()
                orders.append(Order(menu_text, required_steps))
                last_customer_time = current_time
                customer_interval = max(5, customer_interval * 0.95) 

            orders_to_remove = []
            for i, order in enumerate(orders):
                if order.get_remaining_time() <= 0:
                    orders_to_remove.append(i)
                    failed_orders_count += 1
            
            for index in sorted(orders_to_remove, reverse=True):
                orders.pop(index)

            if failed_orders_count >= MAX_FAILED_ORDERS:
                game_over = True

        # --- 드로잉 ---
        screen.fill(WHITE)

        draw_table()
        current_ingredient_rects = list(draw_ingredients())
        list(draw_orders())
        draw_player_cup()

        if game_over:
            game_over_text = font_large.render("GAME OVER", True, RED)
            score_final_text = font_large.render(f"최종 점수: {score}", True, BLACK)
            
            rect_go = game_over_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50))
            rect_score = score_final_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50))
            
            screen.blit(game_over_text, rect_go)
            screen.blit(score_final_text, rect_score)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    run_game()