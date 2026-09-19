import os
import re
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# 1. 게임 전용 디스코드 웹후크 URL
# 환경 변수를 쓰시거나, 아래 우측 큰따옴표 안에 직접 "https://discord.com/api/webhooks/..." 형태로 넣으셔도 됩니다.
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_GAME") or "여기에_디스코드_웹후크_주소_입력"

# 2. 게임/상품권 전용 키워드 및 목표 가격 설정 (단위: 원)
# - 숫자 입력: 해당 금액 이하일 때만 알림
# - None 입력: 가격 상관없이 키워드 감지 시 무조건 알림 (무료/할인)
TARGET_ITEMS = {
    # --- [플랫폼 및 무료 배포] ---
    "EPIC": None, "에픽": None, "FREE": None, "무료": None,
    "STEAM": None, "스팀": None,

    # --- [콘솔] ---
    "PS5": None, "PLAYSTATION": None, "플스": None,
    "SWITCH": None, "스위치": None, "닌텐도": None,
    "XBOX": None, "엑박": None,

    # --- [상품권 및 화폐] ---
    "네이버페이": None, "문화상품권": None, "문상": None,
    
    # --- [특정 타이틀 예시] ---
    # "GTA": 30000,
    # "GTA5": 30000,
}

def extract_price(text):
    """제목이나 본문 텍스트에서 가격 추출"""
    man_match = re.search(r'(\d+(?:\.\d+)?)\s*만\s*원?', text)
    if man_match:
        return int(float(man_match.group(1)) * 10000)
        
    won_match = re.search(r'([\d,]+)\s*원', text)
    if won_match:
        price_str = won_match.group(1).replace(',', '')
        if price_str.isdigit():
            return int(price_str)
            
    return None

def send_discord_message(message):
    """디스코드 웹후크 메시지 전송"""
    if not DISCORD_WEBHOOK_URL or "여기에_" in DISCORD_WEBHOOK_URL:
        print("[경고] 디스코드 웹후크 URL이 설정되지 않았습니다.")
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print(f"디스코드 전송 실패: {e}")

def check_game_sale_info():
    html = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="ko-KR"
            )
            page = context.new_page()
            
            # 퀘이사존 타사핫딜 게시판 중 '게임/S/W' 카테고리(category=15)
            target_url = "https://quasarzone.com/bbs/qb_saleinfo?category=15"
            page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            
            html = page.content()
            browser.close()
    except Exception as e:
        print(f"Playwright 로딩 오류: {e}")
        return

    soup = BeautifulSoup(html, "html.parser")
    links = soup.select("a.subject-link, a[href*='/views/'], a[href*='qb_saleinfo']")
    
    valid_posts = []
    visited_links = set()

    for a in links:
        href = a.get("href", "")
        if not href or href in visited_links:
            continue
        
        if "/views/" in href or "qb_saleinfo" in href:
            title = a.get_text(strip=True)
            if len(title) > 3:
                visited_links.add(href)
                full_link = "https://quasarzone.com" + href if href.startswith("/") else href
                parent_text = a.parent.get_text() if a.parent else title
                valid_posts.append((title, full_link, parent_text))

    if not valid_posts:
        print("게시글을 가져오지 못했거나 수집된 글이 없습니다.")
        return

    print(f"총 {len(valid_posts)}개의 게임 게시글 수집 완료. 키워드 검사 시작...")
    
    found_count = 0

    for title, full_link, price_text in valid_posts:
        title_upper = title.upper()

        for keyword, max_price in TARGET_ITEMS.items():
            if keyword.upper() in title_upper:
                price = extract_price(price_text) or extract_price(title)
                
                # 가격 조건 충족 여부 확인
                if max_price is None or price is None or price <= max_price:
                    print(f"[게임 핫딜 감지] 키워드: {keyword} | 제목: {title}")
                    
                    price_info = f"💰 감지 가격: {price:,}원" if price else "💰 가격 정보 미기재/무료"
                    target_info = f" (목표가: {max_price:,}원 이하)" if max_price else ""
                    
                    msg = f"🎮 **게임 핫딜 감지!**\n**제목**: {title}\n{price_info}{target_info}\n🔗 [게시글 바로가기]({full_link})"
                    send_discord_message(msg)
                    found_count += 1
                    break

    print(f"검사 완료: 총 {found_count}개의 게임 핫딜 알림을 전송했습니다.")

if __name__ == "__main__":
    check_game_sale_info()
