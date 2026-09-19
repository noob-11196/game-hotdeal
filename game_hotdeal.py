import os
import re
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_GAME") or "여기에_디스코드_웹후크_주소_입력"

# 게임/상품권 전용 키워드 및 목표 가격 설정 (단위: 원)
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
}

def extract_price(text):
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
    if not DISCORD_WEBHOOK_URL or "여기에_" in DISCORD_WEBHOOK_URL:
        print("[경고] 디스코드 웹후크 URL이 설정되지 않았습니다.")
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print(f"디스코드 전송 실패: {e}")

def check_game_sale_info():
    # 한국 시간 기준 (UTC+9)
    kst = timezone(timedelta(hours=9))
    now_kst = datetime.now(kst)

    # 매일 오전 09:00~09:30 사이에 생존 신고 알림 전송
    if now_kst.hour == 9 and now_kst.minute < 30:
        send_discord_message("🟢 **[게임 핫딜 봇]** 서버가 정상 작동 중입니다. (매일 정기 점검 알림)")

    html = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                locale="ko-KR"
            )
            page = context.new_page()
            
            target_url = "https://quasarzone.com/bbs/qb_saleinfo?category=15"
            page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            
            html = page.content()
            browser.close()
    except Exception as e:
        error_msg = f"🚨 **[게임 핫딜 봇 오류 발생]**\n크롤링 중 에러가 발생했습니다:\n{e}"
        print(error_msg)
        send_discord_message(error_msg)
        return

    soup = BeautifulSoup(html, "html.parser")
    
    # 범용 링크 셀렉터로 모든 게시글 태그 탐색
    links = soup.find_all("a", href=True)
    
    valid_posts = []
    visited_links = set()

    for a in links:
        href = a["href"]
        # 게시글 상세페이지 링크 구조 감지 (/bbs/qb_saleinfo/views/...)
        if "/views/" in href and "qb_saleinfo" in href:
            if href in visited_links:
                continue
            
            title = a.get_text(strip=True)
            if len(title) > 3:
                visited_links.add(href)
                full_link = "https://quasarzone.com" + href if href.startswith("/") else href
                parent_text = a.parent.parent.get_text(separator=" ", strip=True) if a.parent and a.parent.parent else title
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
                
                if max_price is None or price is None or price <= max_price:
                    print(f"[게임 핫딜 감지] 키워드: {keyword} | 제목: {title}")
                    
                    price_info = f"💰 감지 가격: {price:,}원" if price else "💰 가격 정보 미기재/무료"
                    target_info = f" (목표가: {max_price:,}원 이하)" if max_price else ""
                    
                    msg = f"🎮 **게임 핫딜 감지!**\n**제목**: {title}\n{price_info}{target_info}\n🔗 {full_link}"
                    send_discord_message(msg)
                    found_count += 1
                    break

    print(f"검사 완료: 총 {found_count}개의 게임 핫딜 알림을 전송했습니다.")

if __name__ == "__main__":
    check_game_sale_info()
