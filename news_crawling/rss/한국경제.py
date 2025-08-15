import feedparser
import csv
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import random
import os

NEWS_OUTLET = "한국경제"


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


def extract_hankyung_article_content(url, rss_summary=""):
    """한국경제 기사 URL에서 본문과 기자명을 추출"""
    try:
        session = requests.Session()

        headers = {
            "User-Agent": get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.hankyung.com/",
            "Cache-Control": "no-cache",
        }

        print(f"    접속 시도: {url[:80]}...")

        # 메인 페이지 방문 후 실제 기사 접근
        try:
            session.get("https://www.hankyung.com/", headers=headers, timeout=5)
            time.sleep(0.5)

            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # 응답 크기 체크
            if len(response.content) < 5000:  # 5KB 미만이면 문제가 있을 수 있음
                print(f"    ⚠ 응답 크기가 작음 (크기: {len(response.content)} bytes)")

        except Exception as e:
            print(f"    ⚠ 웹페이지 접근 실패: {e}")
            return "", rss_summary if rss_summary else "웹페이지 접근 실패"

        soup = BeautifulSoup(response.content, "html.parser")
        full_text = soup.get_text()

        # 기자명 추출 - 한국경제 패턴에 맞게 수정
        reporter = ""
        reporter_patterns = [
            r"([가-힣]{2,4})\s*기자\s*([a-zA-Z0-9_.+-]+@hankyung\.com)",  # 기자명 기자 이메일@hankyung.com
            r"([가-힣]{2,4})\s*기자\s*[a-zA-Z0-9_.+-]+@hankyung\.com",  # 기자명 기자 이메일
            r"([가-힣]{2,4})\s*기자",  # 기자명 기자
            r"기자\s*([가-힣]{2,4})",  # 기자 기자명
            r"([가-힣]{2,4})\s*특파원",  # 기자명 특파원
            r"([가-힣]{2,4})\s*편집위원",  # 기자명 편집위원
            r"([가-힣]{2,4})\s*팀장",  # 기자명 팀장
            r"([가-힣]{2,4})\s*기자\s*=",  # 기자명 기자 =
        ]

        # 기사 본문 끝 부분에서 기자명을 찾는 것이 더 정확
        article_end = full_text[-1000:]  # 마지막 1000자에서 찾기

        for pattern in reporter_patterns:
            match = re.search(pattern, article_end)
            if match:
                reporter = match.group(1)
                reporter = re.sub(r"기자|특파원|편집위원|팀장", "", reporter).strip()
                if 2 <= len(reporter) <= 4:
                    break

        # 본문 추출 - 원문 페이지의 본문 컨테이너에서만 텍스트 수집
        content = ""

        # 우선순위: 정확한 본문 컨테이너 선택
        container = soup.select_one('div.article-body#articletxt[itemprop="articleBody"]')
        if not container:
            container = soup.select_one("div.article-body")
        if not container:
            container = soup.select_one("article")

        def _has_ad_class(el):
            cls = el.get("class") or []
            if isinstance(cls, str):
                cls = [cls]
            combined = " ".join([c.lower() for c in cls])
            ad_keys = [
                "ad",
                "ad-area",
                "ad_wrap",
                "ad-wrap",
                "ad-box",
                "promotion",
                "promo",
                "sns",
                "share",
                "tag",
                "related",
                "recommend",
                "subscribe",
                "banner",
                "thumb",
            ]
            return any(k in combined for k in ad_keys)

        if container:
            # 불필요한 요소 제거
            for el in container.find_all(["figure", "script", "style", "noscript", "iframe", "aside"]):
                el.decompose()
            for el in container.find_all(True):
                if _has_ad_class(el):
                    el.decompose()

            # 컨테이너 내부 텍스트 수집 (br 구분 보존)
            content = container.get_text(separator=" ", strip=True)
            # 기자명 탐색은 본문 끝단을 우선 사용
            container_text = container.get_text(separator=" ", strip=True)
            article_end = container_text[-800:] if len(container_text) > 0 else full_text[-1000:]
        else:
            # 폴백: 기존의 범용 선택자 사용
            content_selectors = [
                "div.article-body",
                'div[class*="article"]',
                'div[class*="content"]',
                'div[class*="news"]',
                "div.wrap_cont",
                "article",
                "main",
                'div[id*="article"]',
                "div.text",
            ]
            for selector in content_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(separator=" ", strip=True)
                    if len(text) > len(content):
                        content = text
            article_end = full_text[-1000:]

        # 본문 정제
        content = clean_hankyung_content(content)

        print(f"    최종 본문 길이: {len(content)}")
        return reporter, content

    except Exception as e:
        print(f"    ❌ 에러: {e}")
        return "", rss_summary if rss_summary else f"오류: {str(e)}"


def clean_hankyung_content(content):
    """한국경제 기사 본문 정제"""
    if not content:
        return ""

    # 불필요한 문구들 제거 - 한국경제 특성에 맞게 수정
    remove_patterns = [
        r"입력\s*\d{4}\.\d{2}\.\d{2}.*?\d{2}:\d{2}",
        r"수정\s*\d{4}\.\d{2}\.\d{2}.*?\d{2}:\d{2}",
        r"한국경제.*무단.*전재.*금지",
        r"무단.*전재.*재배포.*금지",
        r"저작권.*한국경제",
        r"관련기사.*더보기",
        r"페이스북.*트위터.*카카오",
        r"구독.*신청",
        r"광고",
        r"[가-힣]{2,4}\s*기자\s*[a-zA-Z0-9_.+-]+@hankyung\.com",  # 기자 이메일 제거
        r"연합뉴스.*제공",  # 뉴스 출처 제거
        r"한국경제.*제공",  # 사진 출처 제거
        r"한경닷컴",
        r"ⓒ.*한국경제",
        r"경제TV.*증권.*부동산",  # 한국경제 메뉴 제거
    ]

    for pattern in remove_patterns:
        content = re.sub(pattern, "", content, flags=re.IGNORECASE)

    # 공백 정리
    content = re.sub(r"\s+", " ", content).strip()

    # 길이 제한
    if len(content) > 1500:
        content = content[:1500] + "..."

    return content


def append_hankyung_rss_to_writer(rss_url, writer, max_articles=30, category_hint: str | None = None):
    """한국경제 RSS를 파싱하여 주어진 writer에 행을 추가"""

    print(f"한국경제 RSS 피드 파싱 중: {rss_url}")

    # RSS 파싱
    try:
        headers = {"User-Agent": get_random_user_agent()}
        response = requests.get(rss_url, headers=headers, timeout=10)
        response.encoding = "utf-8"
        feed = feedparser.parse(response.content)
    except Exception:
        feed = feedparser.parse(rss_url)

    if not feed.entries:
        print("❌ RSS 피드에서 기사를 찾을 수 없습니다.")
        return 0, 0

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

            # 카테고리 추출
            category = ""
            if hasattr(entry, "category") and entry.category:
                category = entry.category.strip()
            elif hasattr(entry, "tags") and entry.tags:
                try:
                    category = entry.tags[0].term or ""
                except Exception:
                    category = ""
            # URL에서 카테고리 추출 시도
            if not category and isinstance(link, str):
                url_category_map = {
                    "/economy/": "경제",
                    "/finance/": "증권",
                    "/realestate/": "부동산",
                    "/politics/": "정치",
                    "/society/": "사회",
                    "/international/": "국제",
                    "/life/": "생활",
                    "/sports/": "스포츠",
                    "/it/": "IT",
                    "/video/": "VIDEO",
                    "/opinion/": "오피니언",
                    "/entertainment/": "연예",
                }
                for url_part, cat_name in url_category_map.items():
                    if url_part in link:
                        category = cat_name
                        break
            # 힌트 사용
            if not category and category_hint:
                category = category_hint

            # RSS 요약 정보 추출 (본문 정제에 사용될 수 있으나, 우선 원문 본문 사용)
            summary = ""
            if hasattr(entry, "description") and entry.description:
                summary = entry.description.strip()
                summary = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", summary, flags=re.DOTALL)
                summary = re.sub(r"<[^>]+>", "", summary)
                summary = clean_hankyung_content(summary)

            # 날짜 형식 변환
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                date = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d %H:%M:%S")
            else:
                date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 기자명은 RSS author에서 추출
            reporter = ""
            if hasattr(entry, "author") and entry.author:
                reporter = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", str(entry.author)).strip()

            print(f"[{i+1}/{total_count}] {title[:60]}...")

            # 기사 본문 추출 (원문 페이지)
            _ignored_reporter, content = extract_hankyung_article_content(link, summary)

            # 최소 조건 확인
            if len(content.strip()) < 20:
                print(f"    ⚠ 본문이 너무 짧아 건너뜀 (길이: {len(content)})\n")
                continue

            # CSV에 쓰기 (열 순서: 언론사, 제목, 날짜, 카테고리, 기자명, 본문)
            writer.writerow(
                {
                    "언론사": NEWS_OUTLET,
                    "제목": title,
                    "날짜": date,
                    "카테고리": category if category else "미분류",
                    "기자명": reporter if reporter else "미상",
                    "본문": content,
                }
            )

            success_count += 1
            print(
                f"    ✅ 성공! (카테고리: {category}, 기자: {reporter if reporter else '미상'}, 본문: {len(content)}자)"
            )

            # 진행률 표시
            if (i + 1) % 5 == 0:
                print(f"\n📊 진행률: {i+1}/{total_count} ({(i+1)/total_count*100:.1f}%)")
                print(f"📈 성공률: {success_count}/{i+1} ({success_count/(i+1)*100:.1f}%)\n")

            # 랜덤 딜레이 (서버 부하 방지)
            delay = random.uniform(1.0, 2.5)
            time.sleep(delay)

        except KeyboardInterrupt:
            print("\n⚠ 사용자가 중단했습니다.")
            break
        except Exception as e:
            print(f"    ❌ 오류: {e}")
            continue

    return success_count, total_count


# 자동 수집 실행 예시 (모든 카테고리를 20개씩 수집)
if __name__ == "__main__":
    # 한국경제 RSS URL 옵션들
    hankyung_rss_options = {
        "전체뉴스": "https://www.hankyung.com/feed/all-news",
        "경제": "https://www.hankyung.com/feed/economy",
        "증권": "https://www.hankyung.com/feed/finance",
        "부동산": "https://www.hankyung.com/feed/realestate",
        "정치": "https://www.hankyung.com/feed/politics",
        "사회": "https://www.hankyung.com/feed/society",
        "국제": "https://www.hankyung.com/feed/international",
        "IT": "https://www.hankyung.com/feed/it",
        "생활": "https://www.hankyung.com/feed/life",
        "오피니언": "https://www.hankyung.com/feed/opinion",
    }

    max_articles = 20
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    print("한국경제 RSS 자동 수집기 (카테고리별 20개 → 단일 CSV)\n" + "=" * 50)

    # 단일 CSV 파일 준비
    output_file = f"results/{NEWS_OUTLET}_전체_{timestamp}.csv"
    out_dir = os.path.dirname(output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_file, "w", newline="", encoding="utf-8-sig") as csvfile:
        fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        total_success = 0
        total_expected = 0

        for category_name, rss_url in hankyung_rss_options.items():
            print(f"\n🚀 [{category_name}] 카테고리에서 {max_articles}개 기사 수집 시작!")
            print(f"📁 저장 파일: {output_file}\n")
            success, expected = append_hankyung_rss_to_writer(
                rss_url, writer, max_articles, category_hint=category_name
            )
            total_success += success
            total_expected += expected
            # 카테고리 간 간격 (서버 부하 방지)
            time.sleep(random.uniform(1.5, 3.0))

    print(f"\n{'='*70}")
    print(f"🎉 완료! CSV 파일 저장: {output_file}")
    if total_expected:
        print(
            f"📊 최종 결과: {total_success}/{total_expected*len(hankyung_rss_options)}개 시도 중 {total_success}건 성공"
        )
    print(f"{'='*70}")
