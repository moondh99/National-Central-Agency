import feedparser
import csv
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time


def extract_article_content(url):
    """기사 URL에서 본문과 기자명을 추출 (개선된 버전)"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # 연합뉴스 전용 구조: 기자명과 본문 우선 추출
        yn_article = soup.select_one("div.story-news.article")
        if yn_article:
            # 기자명
            reporter_elem = soup.select_one(".writer-zone01 .tit-name")
            reporter = reporter_elem.get_text().replace("기자", "").strip() if reporter_elem else ""
            # 본문
            content = yn_article.get_text().strip()
            content = clean_article_content(content)
            return reporter, content

        # 기자명 추출 (연합뉴스 패턴 개선)
        reporter = ""

        # 1. 본문에서 기자명 패턴 찾기
        article_text = soup.get_text()
        reporter_patterns = [
            r"(\([^)]*=연합뉴스\)\s*([가-힣]{2,4})\s*기자)",  # (지역=연합뉴스) 기자명 기자
            r"([가-힣]{2,4})\s*기자\s*=",  # 기자명 기자 =
            r"=\s*([가-힣]{2,4})\s*기자",  # = 기자명 기자
            r"([가-힣]{2,4})기자\s*구독",  # 기자명기자 구독
        ]

        for pattern in reporter_patterns:
            match = re.search(pattern, article_text)
            if match:
                if len(match.groups()) > 1:
                    reporter = match.group(2)  # 두 번째 그룹이 기자명
                else:
                    reporter = match.group(1)
                reporter = re.sub(r"기자|특파원|연합뉴스", "", reporter).strip()
                break

        # 2. 이메일 주소에서 기자명 추출 시도
        if not reporter:
            email_pattern = r"([a-z0-9]+)@yna\.co\.kr"
            email_match = re.search(email_pattern, article_text)
            if email_match:
                reporter = email_match.group(1)

        # 본문 추출 (개선된 버전)
        content = ""

        # 불필요한 요소들 미리 제거
        for unwanted in soup.find_all(
            ["script", "style", "nav", "header", "footer", "aside", "figure", "iframe", "form"]
        ):
            unwanted.decompose()

        # 댓글, 공유 버튼 등 제거
        for unwanted_class in soup.find_all(
            class_=re.compile(r"comment|share|social|related|recommend|bookmark|print")
        ):
            unwanted_class.decompose()

        # 본문 추출 시도
        content_selectors = [
            "div.story-news-article",
            "div.article-txt",
            "div.news-article",
            "div.article-content",
            "article",
            'div[class*="article"]',
            'div[class*="content"]',
        ]

        for selector in content_selectors:
            content_element = soup.select_one(selector)
            if content_element:
                content = content_element.get_text().strip()
                break

        # 본문이 없으면 전체 텍스트에서 추출
        if not content:
            content = soup.get_text()

        # 본문 정제
        content = clean_article_content(content)

        return reporter, content

    except Exception as e:
        print(f"Error extracting content from {url}: {e}")
        return "", ""


def clean_article_content(content):
    """기사 본문 정제"""
    if not content:
        return ""

    # 불필요한 문구들 제거
    remove_patterns = [
        r"구독\s*구독중\s*이전\s*다음",
        r"제보는\s*카카오톡\s*okjebo",
        r"<저작권자\(c\)\s*연합뉴스.*?>",
        r"\d{4}/\d{2}/\d{2}\s*\d{2}:\d{2}\s*송고",
        r"\d{4}년\d{2}월\d{2}일\s*\d{2}시\d{2}분\s*송고",
        r"#[가-힣\w\s]*",  # 해시태그 제거
        r"댓글\s*좋아요\s*슬퍼요\s*화나요\s*후속요청\s*북마크",
        r"공유\s*공유하기\s*카카오톡\s*페이스북\s*X\s*페이스북\s*메신저\s*네이버\s*밴드",
        r"URL\s*복사\s*닫기\s*URL이\s*복사되었습니다",
        r"글자크기\s*본문\s*글자\s*크기\s*조정.*?닫기",
        r"프린트\s*제보",
        r"관련\s*뉴스",
        r"인공지능이\s*자동으로\s*줄인.*?읽어야\s*합니다\.",
    ]

    for pattern in remove_patterns:
        content = re.sub(pattern, "", content, flags=re.IGNORECASE)

    # 여러 공백과 줄바꿈을 정리
    content = re.sub(r"\s+", " ", content)
    content = content.strip()

    # 너무 짧거나 긴 경우 처리
    if len(content) < 50:
        return ""

    return content


def fetch_yonhap_rss_to_csv(rss_url, output_file, max_articles=50):
    """연합뉴스 RSS를 파싱하여 CSV로 저장 (개선된 버전)"""

    print(f"RSS 피드 파싱 중: {rss_url}")
    feed = feedparser.parse(rss_url)

    if not feed.entries:
        print("RSS 피드에서 기사를 찾을 수 없습니다.")
        return

    success_count = 0
    total_count = min(len(feed.entries), max_articles)

    # CSV 파일 생성
    with open(output_file, "w", newline="", encoding="utf-8-sig") as csvfile:
        fieldnames = ["제목", "날짜", "기자명", "본문"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        print(f"총 {total_count}개 기사 처리 중...")

        for i, entry in enumerate(feed.entries[:max_articles]):
            try:
                # 기본 정보 추출
                title = entry.title.strip()
                link = entry.link

                # 날짜 형식 변환
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    date = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                print(f"처리 중 [{i+1}/{total_count}]: {title[:50]}...")

                # RSS dc:creator에서 기자명 추출 우선, 없으면 본문에서 추출
                rss_reporter = ""
                if hasattr(entry, "dc_creator"):
                    rss_reporter = entry.dc_creator.strip()
                elif hasattr(entry, "author"):
                    rss_reporter = entry.author.strip()
                # 본문 및 추가 기자명 추출
                reporter, content = extract_article_content(link)
                if rss_reporter:
                    reporter = rss_reporter

                # 유효성 검사
                if len(content.strip()) < 30:
                    print(f"  ⚠ 본문이 너무 짧아 건너뜀")
                    continue

                # CSV에 쓰기
                writer.writerow(
                    {"제목": title, "날짜": date, "기자명": reporter if reporter else "미상", "본문": content}
                )

                success_count += 1
                print(f"  ✓ 완료 (기자: {reporter if reporter else '미상'})")

                # 서버 부하 방지를 위한 딜레이
                time.sleep(0.5)

            except Exception as e:
                print(f"  ❌ 오류: {e}")
                continue

    print(f"\n{'='*50}")
    print(f"CSV 파일 저장 완료: {output_file}")
    print(f"성공적으로 처리된 기사: {success_count}/{total_count}")
    print(f"{'='*50}")


# 메인 실행: 모든 카테고리 통합 수집 후 단일 CSV 저장
if __name__ == "__main__":
    # 연합뉴스 RSS URL 옵션들
    rss_options = {
        "전체": "https://www.yna.co.kr/rss/news.xml",
        "정치": "https://www.yna.co.kr/rss/politics.xml",
        "경제": "https://www.yna.co.kr/rss/economy.xml",
        "사회": "https://www.yna.co.kr/rss/society.xml",
        "국제": "https://www.yna.co.kr/rss/international.xml",
        "문화": "https://www.yna.co.kr/rss/culture.xml",
    }
    rows = []
    for category, rss_url in rss_options.items():
        print(f"RSS 피드 파싱 중: {rss_url}")
        feed = feedparser.parse(rss_url)
        entries = feed.entries[:20]
        for entry in entries:
            title = entry.title.strip()
            # 날짜 변환
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                date = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d %H:%M:%S")
            else:
                date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 기자명 RSS dc:creator 우선
            reporter = entry.dc_creator.strip() if hasattr(entry, "dc_creator") else ""
            if not reporter and hasattr(entry, "author"):
                reporter = entry.author.strip()
            # 본문 추출
            rpt, content = extract_article_content(entry.link)
            if not reporter:
                reporter = rpt
            # 유효성
            if len(content) < 30:
                continue
            rows.append(
                {
                    "언론사": "연합뉴스",
                    "제목": title,
                    "날짜": date,
                    "카테고리": category,
                    "기자명": reporter if reporter else "미상",
                    "본문": content,
                }
            )
            time.sleep(0.5)
    # CSV 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"results/연합뉴스_전체_{timestamp}.csv"
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"CSV 파일 저장 완료: {filename} (총 {len(rows)}개 기사)")
