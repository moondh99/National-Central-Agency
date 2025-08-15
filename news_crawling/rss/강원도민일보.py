import feedparser
import csv
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import random
import os


def get_random_user_agent():
    """랜덤 User-Agent 반환"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    ]
    return random.choice(user_agents)


def extract_kado_article_content(url, rss_summary="", rss_author=""):
    """강원도민일보 기사 URL에서 본문 추출 (기자명은 RSS에서 가져옴)"""
    try:
        session = requests.Session()

        headers = {
            "User-Agent": get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.kado.net/",
            "Cache-Control": "no-cache",
        }

        print(f"    접속 시도: {url[:80]}...")

        # 메인 페이지 방문 후 실제 기사 접근
        try:
            session.get("https://www.kado.net/", headers=headers, timeout=5)
            time.sleep(0.5)

            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            if len(response.content) < 3000:  # 3KB 미만이면 문제가 있을 수 있음
                print(f"    ⚠ 응답 크기가 작음 (크기: {len(response.content)} bytes)")

        except Exception as e:
            print(f"    ⚠ 웹페이지 접근 실패: {e}")
            return rss_author, rss_summary if rss_summary else "웹페이지 접근 실패"

        soup = BeautifulSoup(response.content, "html.parser")

        # 본문 추출 - 제공된 XPath 경로를 CSS 선택자로 변환
        # XPath: /html/body/div[1]/div/section/div[4]/div/section/article/div[2]/div/article[1]/p
        content = ""

        try:
            # 정확한 CSS 선택자로 본문 추출
            content_selectors = [
                "body > div:nth-child(1) > div > section > div:nth-child(4) > div > section > article > div:nth-child(2) > div > article:nth-child(1) p",
                "section article div:nth-child(2) div article:first-child p",  # 조금 더 유연한 선택자
                "article div:nth-child(2) div article p",  # 더 간단한 선택자
                "div[class*='article'] p",  # article 클래스가 포함된 div 내의 p 태그
                "article p",  # article 태그 내의 모든 p 태그
            ]

            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    content_parts = []
                    for p in elements:
                        text = p.get_text().strip()
                        if len(text) > 10:  # 의미있는 길이의 텍스트만
                            content_parts.append(text)

                    if content_parts:
                        content = " ".join(content_parts)
                        print(f"    본문 추출 성공 (선택자: {selector[:50]}...)")
                        break

            # 위 방법이 실패하면 모든 p 태그에서 본문 추출
            if len(content) < 100:
                print("    기본 선택자로 본문 추출 시도...")
                paragraphs = soup.find_all("p")
                content_parts = []

                for p in paragraphs:
                    text = p.get_text().strip()
                    if (
                        len(text) > 20
                        and not re.search(r"입력\s*\d{4}|수정\s*\d{4}|Copyright|저작권|강원도민일보|kado", text)
                        and not text.startswith(("▶", "☞", "※", "■", "▲", "[", "※", "◆", "○", "△"))
                        and "@kado.net" not in text
                        and "무단 전재" not in text
                        and "재배포 금지" not in text
                        and "기사제보" not in text
                    ):
                        content_parts.append(text)

                if content_parts:
                    content = " ".join(content_parts)

        except Exception as e:
            print(f"    본문 추출 중 오류: {e}")

        # 본문 정제
        content = clean_kado_content(content)

        # RSS 요약이 더 좋으면 RSS 요약 사용
        if rss_summary and (len(content) < 100 or len(rss_summary) > len(content)):
            content = rss_summary
            print(f"    RSS 요약 채택 (길이: {len(rss_summary)})")

        print(f"    최종 본문 길이: {len(content)}")
        return rss_author, content

    except Exception as e:
        print(f"    ❌ 에러: {e}")
        return rss_author, rss_summary if rss_summary else f"오류: {str(e)}"


def clean_kado_content(content):
    """강원도민일보 기사 본문 정제"""
    if not content:
        return ""

    # 불필요한 문구들 제거 - 강원도민일보 특성에 맞게 수정
    remove_patterns = [
        r"입력\s*\d{4}[-./]\d{2}[-./]\d{2}.*?\d{2}:\d{2}",
        r"수정\s*\d{4}[-./]\d{2}[-./]\d{2}.*?\d{2}:\d{2}",
        r"업데이트\s*\d{4}[-./]\d{2}[-./]\d{2}.*?\d{2}:\d{2}",
        r"강원도민일보.*무단.*전재.*금지",
        r"무단.*전재.*재배포.*금지",
        r"저작권.*강원도민일보",
        r"관련기사.*더보기",
        r"페이스북.*트위터.*카카오",
        r"구독.*신청",
        r"광고",
        r"[가-힣]{2,4}\s*기자\s*[a-zA-Z0-9_.+-]+@kado\.net",  # 기자 이메일 제거
        r"연합뉴스.*제공",  # 뉴스 출처 제거
        r"뉴시스.*제공",  # 뉴스 출처 제거
        r"강원도민일보.*제공",  # 사진 출처 제거
        r"ⓒ.*강원도민일보",
        r"kado\.net",
        r"기사제보.*문의",
        r"독자투고.*문의",
        r"청소년.*보호.*책임자",
        r"개인정보.*처리.*방침",
        r"이메일.*무단.*수집.*거부",
        r"Copyright.*\d{4}.*강원도민일보",
        r"강원.*춘천.*원주.*속초",  # 지역 관련 반복 문구
        r"도민일보.*NEWS",
    ]

    for pattern in remove_patterns:
        content = re.sub(pattern, "", content, flags=re.IGNORECASE)

    # 공백 정리
    content = re.sub(r"\s+", " ", content).strip()

    # 길이 제한
    if len(content) > 1800:
        content = content[:1800] + "..."

    return content


def fetch_kado_rss_to_csv(rss_url, category_name, writer, max_articles=30):
    """강원도민일보 RSS를 파싱하여 CSV에 저장 (단일 파일에 추가)"""

    print(f"강원도민일보 RSS 피드 파싱 중: {rss_url}")

    # RSS 파싱
    try:
        headers = {"User-Agent": get_random_user_agent()}
        response = requests.get(rss_url, headers=headers, timeout=10)
        # 강원도민일보 RSS는 UTF-8 인코딩 사용
        response.encoding = "utf-8"
        feed = feedparser.parse(response.content)
    except:
        feed = feedparser.parse(rss_url)

    if not feed.entries:
        print("❌ RSS 피드에서 기사를 찾을 수 없습니다.")
        return 0

    print(f"✅ RSS에서 {len(feed.entries)}개 기사 발견")

    success_count = 0
    total_count = min(len(feed.entries), max_articles)

    print(f"총 {total_count}개 기사 처리 시작...\n")

    for i, entry in enumerate(feed.entries[:max_articles]):
        try:
            # 기본 정보 추출
            title = entry.title.strip()
            title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", title)

            link = entry.link

            # RSS 요약 정보 추출
            summary = ""
            if hasattr(entry, "description"):
                summary = entry.description.strip()
                # HTML 태그와 CDATA 제거
                summary = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", summary, flags=re.DOTALL)
                summary = re.sub(r"<[^>]+>", "", summary)  # HTML 태그 제거
                summary = clean_kado_content(summary)

            # RSS에서 기자명 추출
            author = ""
            if hasattr(entry, "author"):
                author = entry.author.strip()
                # 기자명 정제 (불필요한 문구 제거)
                author = re.sub(r"기자|특파원|편집위원|팀장|선임기자|수석기자", "", author).strip()

            # 날짜 형식 변환
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                date = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d %H:%M:%S")
            else:
                date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print(f"[{i+1}/{total_count}] {title[:50]}...")

            # 기사 본문 추출 (기자명은 RSS에서 가져옴)
            reporter, content = extract_kado_article_content(link, summary, author)

            # 최소 조건 확인
            if len(content.strip()) < 20:
                print(f"    ⚠ 본문이 너무 짧아 건너뜀 (길이: {len(content)})\n")
                continue

            # CSV에 쓰기 (언론사명 추가)
            writer.writerow(
                {
                    "언론사": "강원도민일보",
                    "제목": title,
                    "날짜": date,
                    "카테고리": category_name,
                    "기자명": reporter if reporter else "미상",
                    "본문": content,
                }
            )

            success_count += 1
            print(
                f"    ✅ 성공! (카테고리: {category_name}, 기자: {reporter if reporter else '미상'}, 본문: {len(content)}자)"
            )

            # 진행률 표시
            if (i + 1) % 5 == 0:
                print(f"\n📊 진행률: {i+1}/{total_count} ({(i+1)/total_count*100:.1f}%)")
                print(f"📈 성공률: {success_count}/{i+1} ({success_count/(i+1)*100:.1f}%)\n")

            # 랜덤 딜레이 (서버 부하 방지)
            delay = random.uniform(1.5, 3.0)
            time.sleep(delay)

        except KeyboardInterrupt:
            print("\n⚠ 사용자가 중단했습니다.")
            break
        except Exception as e:
            print(f"    ❌ 오류: {e}")
            continue

    print(f"\n{'='*50}")
    print(f"🎉 {category_name} 카테고리 완료!")
    print(f"📊 결과: {success_count}/{total_count}개 성공 ({success_count/total_count*100:.1f}%)")
    print(f"{'='*50}")

    return success_count


# 사용 예시
if __name__ == "__main__":
    # 강원도민일보 RSS URL 옵션들 (지정된 카테고리만)
    kado_rss_options = {
        "전체기사": "https://www.kado.net/rss/allArticle.xml",
        "정치": "https://www.kado.net/rss/S1N1.xml",
        "경제": "https://www.kado.net/rss/S1N2.xml",
        "사회": "https://www.kado.net/rss/S1N3.xml",
        "문화": "https://www.kado.net/rss/S1N4.xml",
        "지역": "https://www.kado.net/rss/S1N6.xml",
        "오피니언": "https://www.kado.net/rss/S1N8.xml",
    }

    print("강원도민일보 RSS 수집기 (강원도 지역언론)")
    print("=" * 60)

    # 각 카테고리별로 20개씩 자동 수집
    max_articles = 20
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    total_categories = len(kado_rss_options)
    current_category = 0
    total_success = 0

    print(f"총 {total_categories}개 카테고리에서 각각 {max_articles}개씩 기사 수집을 시작합니다.")
    print("모든 기사는 하나의 CSV 파일에 저장됩니다.\n")

    # results 디렉토리 생성
    os.makedirs("results", exist_ok=True)

    # 단일 CSV 파일 생성
    output_file = f"results/강원도민일보_전체_{timestamp}.csv"

    with open(output_file, "w", newline="", encoding="utf-8-sig") as csvfile:
        fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for category, rss_url in kado_rss_options.items():
            current_category += 1

            print(f"🚀 [{current_category}/{total_categories}] {category} 카테고리 수집 시작!")
            print(f"🔗 RSS URL: {rss_url}\n")

            # 실행
            success_count = fetch_kado_rss_to_csv(rss_url, category, writer, max_articles)
            total_success += success_count

            # 카테고리 간 휴식 시간
            if current_category < total_categories:
                print(f"\n⏰ 다음 카테고리까지 5초 대기...\n")
                time.sleep(5)

    print(f"\n🎉 모든 카테고리 수집 완료!")
    print(f"📊 총 {total_categories}개 카테고리에서 {total_success}개 기사 수집 성공")
    print(f"📁 저장 파일: {output_file}")
    print(
        f"📈 전체 성공률: {total_success}/{total_categories * max_articles}개 ({total_success/(total_categories * max_articles)*100:.1f}%)"
    )
