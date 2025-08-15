import feedparser
import csv
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import random


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


def extract_onseoul_article_content(url, rss_summary=""):
    """서울자치신문 기사 URL에서 본문과 기자명을 추출"""
    try:
        session = requests.Session()

        headers = {
            "User-Agent": get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "http://www.onseoul.net/",
            "Cache-Control": "no-cache",
        }

        print(f"    접속 시도: {url[:80]}...")

        # 메인 페이지 방문 후 실제 기사 접근
        try:
            session.get("http://www.onseoul.net/", headers=headers, timeout=5)
            time.sleep(0.5)

            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # 서울자치신문은 일반적으로 접근 제한이 없음
            if len(response.content) < 3000:  # 3KB 미만이면 문제가 있을 수 있음
                print(f"    ⚠ 응답 크기가 작음 (크기: {len(response.content)} bytes)")

        except Exception as e:
            print(f"    ⚠ 웹페이지 접근 실패: {e}")
            return "", rss_summary if rss_summary else "웹페이지 접근 실패"

        soup = BeautifulSoup(response.content, "html.parser")
        full_text = soup.get_text()

        # 기자명 추출 - 서울자치신문 패턴에 맞게 수정
        reporter = ""

        # 서울자치신문은 기사 하단에 기자명이 표시됨
        reporter_patterns = [
            r"([가-힣]{2,4})\s*기자\s*[0-9]{4}-[0-9]{2}-[0-9]{2}",  # 기자명 기자 날짜
            r"([가-힣]{2,4})\s*기자",  # 기자명 기자
            r"기자\s*([가-힣]{2,4})",  # 기자 기자명
            r"([가-힣]{2,4})\s*특파원",  # 기자명 특파원
        ]

        # 기사 끝 부분에서 기자명 찾기
        article_end = full_text[-500:]

        for pattern in reporter_patterns:
            match = re.search(pattern, article_end)
            if match:
                reporter = match.group(1)
                reporter = re.sub(r"기자|특파원", "", reporter).strip()
                if len(reporter) >= 2 and len(reporter) <= 4:
                    break

        # 본문 추출 - 서울자치신문 HTML 구조에 맞게 수정
        content = ""

        # 방법 1: 기사 본문 구조 찾기
        content_selectors = [
            "div.user-content",  # 사용자 콘텐츠 영역
            'div[class*="article"]',  # article 관련 클래스
            'div[class*="content"]',  # content 관련 클래스
            'div[class*="news"]',  # news 관련 클래스
            "article",  # article 태그
            "main",  # main 태그
        ]

        for selector in content_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text().strip()
                if len(text) > len(content):
                    content = text

        # 방법 2: P 태그 기반 추출
        if len(content) < 200:
            paragraphs = soup.find_all("p")
            content_parts = []

            for p in paragraphs:
                text = p.get_text().strip()
                if (
                    len(text) > 20
                    and not re.search(
                        r"입력\s*\d{4}\.\d{2}\.\d{2}|Copyright|저작권|서울자치신문|www\.onseoul\.net", text
                    )
                    and not text.startswith(("▶", "☞", "※", "■", "▲", "["))
                    and not re.search(r"[가-힣]{2,4}\s*기자\s*\d{4}-\d{2}-\d{2}", text)
                ):
                    content_parts.append(text)

            if content_parts:
                content = " ".join(content_parts)

        # 방법 3: 전체 텍스트에서 추출 (최후 수단)
        if len(content) < 100:
            # 제목 이후 본문 시작 지점 찾기
            lines = full_text.split("\n")
            content_lines = []
            article_started = False

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # 기사 시작 감지 - 이미지 다음부터 본문 시작
                if not article_started and (
                    len(line) > 30
                    and not line.startswith(("서명옥", "김정민", "박현수"))
                    and not re.search(r"\.(png|jpg|jpeg)$", line)
                ):
                    article_started = True

                # 기사 본문 수집
                if article_started and len(line) > 10:
                    # 불필요한 라인 제외
                    if not re.search(
                        r"Copyright|저작권|서울자치신문|www\.onseoul\.net|[가-힣]{2,4}\s*기자\s*\d{4}-\d{2}-\d{2}", line
                    ):
                        content_lines.append(line)

                # 기사 끝 감지
                if re.search(r"[가-힣]{2,4}\s*기자\s*\d{4}-\d{2}-\d{2}", line):
                    break

            if content_lines:
                content = " ".join(content_lines)

        # 본문 정제
        content = clean_onseoul_content(content)

        # RSS 요약이 더 좋으면 RSS 요약 사용
        if rss_summary and (len(content) < 100 or len(rss_summary) > len(content)):
            content = rss_summary
            print(f"    RSS 요약 채택 (길이: {len(rss_summary)})")

        print(f"    최종 본문 길이: {len(content)}")
        return reporter, content

    except Exception as e:
        print(f"    ❌ 에러: {e}")
        return "", rss_summary if rss_summary else f"오류: {str(e)}"


def clean_onseoul_content(content):
    """서울자치신문 기사 본문 정제"""
    if not content:
        return ""

    # 불필요한 문구들 제거 - 서울자치신문 특성에 맞게 수정
    remove_patterns = [
        r"입력\s*\d{4}\.\d{2}\.\d{2}.*?\d{2}:\d{2}",
        r"[가-힣]{2,4}\s*기자\s*\d{4}-\d{2}-\d{2}.*?\d{2}:\d{2}",
        r"Copyright.*www\.onseoul\.net.*reserved",
        r"서울자치신문.*무단.*전재.*금지",
        r"관련기사.*더보기",
        r"페이스북.*트위터.*카카오",
        r"구독.*신청",
        r"광고",
        r"사진.*제공",  # 사진 출처 제거
        r"포스터.*jpg",  # 포스터 파일명 제거
        r"서울자치신문.*칼럼필진",  # 칼럼 소개 제거
    ]

    for pattern in remove_patterns:
        content = re.sub(pattern, "", content, flags=re.IGNORECASE)

    # 공백 정리
    content = re.sub(r"\s+", " ", content).strip()

    # 길이 제한
    if len(content) > 1500:
        content = content[:1500] + "..."

    return content


def fetch_onseoul_rss_to_csv(rss_url, output_file, max_articles=30, category="전체기사"):  # category 추가
    """서울자치신문 RSS를 파싱하여 CSV로 저장"""

    print(f"서울자치신문 RSS 피드 파싱 중: {rss_url}")

    # RSS 파싱
    try:
        headers = {"User-Agent": get_random_user_agent()}
        response = requests.get(rss_url, headers=headers, timeout=10)
        feed = feedparser.parse(response.content)
    except:
        feed = feedparser.parse(rss_url)

    if not feed.entries:
        print("❌ RSS 피드에서 기사를 찾을 수 없습니다.")
        return

    print(f"✅ RSS에서 {len(feed.entries)}개 기사 발견")

    success_count = 0
    total_count = min(len(feed.entries), max_articles)

    # CSV 파일 생성
    with open(output_file, "w", newline="", encoding="utf-8-sig") as csvfile:
        fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

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
                    summary = clean_onseoul_content(summary)
                elif hasattr(entry, "summary"):
                    summary = entry.summary.strip()
                    summary = re.sub(r"<[^>]+>", "", summary)
                    summary = clean_onseoul_content(summary)

                # 날짜 형식 변환
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    date = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d %H:%M:%S")
                elif hasattr(entry, "pubdate_parsed") and entry.pubdate_parsed:
                    date = datetime(*entry.pubdate_parsed[:6]).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                print(f"[{i+1}/{total_count}] {title[:60]}...")

                # RSS에서 기자명 추출
                if hasattr(entry, "author") and entry.author:
                    author_text = entry.author.strip()
                    match = re.search(r"([가-힣]{2,4})", author_text)
                    reporter = match.group(1) + " 기자" if match else author_text
                else:
                    reporter = "미상"
                # 본문은 RSS description 사용
                content = summary

                if not content.strip():
                    print(f"    ⚠ 본문이 비어있어 건너뜀")
                    continue

                # CSV에 쓰기
                writer.writerow(
                    {
                        "언론사": "서울자치신문",
                        "제목": title,
                        "날짜": date,
                        "카테고리": category,
                        "기자명": reporter,
                        "본문": content,
                    }
                )

                success_count += 1
                print(f"    ✅ 성공! (기자: {reporter}, 본문: {len(content)}자)")

                # 진행률 표시
                if (i + 1) % 5 == 0:
                    print(f"\n📊 진행률: {i+1}/{total_count} ({(i+1)/total_count*100:.1f}%)")
                    print(f"📈 성공률: {success_count}/{i+1} ({success_count/(i+1)*100:.1f}%)\n")

                # 랜덤 딜레이 (서버 부하 방지)
                delay = random.uniform(1.0, 2.0)
                time.sleep(delay)

            except KeyboardInterrupt:
                print("\n⚠ 사용자가 중단했습니다.")
                break
            except Exception as e:
                print(f"    ❌ 오류: {e}")
                continue

        print(f"\n{'='*70}")
        print(f"🎉 완료! CSV 파일 저장: {output_file}")
        print(f"📊 최종 결과: {success_count}/{total_count}개 성공 ({success_count/total_count*100:.1f}%)")
        print(f"{'='*70}")


# 사용 예시
if __name__ == "__main__":
    # 자동 실행: 전체 카테고리에서 20개 기사 수집
    rss_url = "https://www.onseoul.net/rss/allArticle.xml"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = f"results/서울자치신문_전체_{timestamp}.csv"
    print(f"🚀 전체 카테고리에서 20개 기사 수집 시작!")
    print(f"📁 저장 파일: {output_file}\n")
    fetch_onseoul_rss_to_csv(rss_url, output_file, max_articles=20, category="전체")
