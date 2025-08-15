import feedparser
import csv
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import random
import os
from lxml import html


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


def extract_newswire_article_content(url, rss_summary=""):
    """뉴스와이어 기사 URL에서 본문과 작성자명을 추출"""
    try:
        session = requests.Session()

        headers = {
            "User-Agent": get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            # br 제거: requests는 기본적으로 brotli를 지원하지 않을 수 있음
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://api.newswire.co.kr/",
            "Cache-Control": "no-cache",
        }

        print(f"    접속 시도: {url[:80]}...")

        # 메인 페이지 방문 후 실제 기사 접근
        try:
            session.get("https://api.newswire.co.kr/", headers=headers, timeout=5)
            time.sleep(0.5)

            response = session.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            # 인코딩 보정
            try:
                if not response.encoding:
                    response.encoding = response.apparent_encoding
            except Exception:
                pass

            if len(response.content) < 2000:  # 2KB 미만이면 문제가 있을 수 있음
                print(f"    ⚠ 응답 크기가 작음 (크기: {len(response.content)} bytes)")

        except Exception as e:
            print(f"    ⚠ 웹페이지 접근 실패: {e}")
            return "", rss_summary if rss_summary else "웹페이지 접근 실패"

        # BeautifulSoup 준비 및 전체 텍스트 확보
        soup = BeautifulSoup(response.content, "html.parser")
        full_text = soup.get_text()

        # 작성자명 추출 - 보도자료 특성 고려
        reporter = ""
        reporter_patterns = [
            r"([가-힣]{2,4})\s*기자\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9.-]+)",  # 기자명 기자 이메일
            r"([가-힣]{2,4})\s*기자",  # 기자명 기자
            r"([가-힣]{2,4})\s*담당자",  # 담당자명 담당자
            r"([가-힣]{2,4})\s*대표",  # 대표명 대표
            r"([가-힣]{2,4})\s*매니저",  # 매니저명 매니저
            r"([가-힣]{2,4})\s*팀장",  # 팀장명 팀장
            r"([가-힣]{2,4})\s*실장",  # 실장명 실장
            r"([가-힣]{2,4})\s*부장",  # 부장명 부장
            r"([가-힣]{2,4})\s*과장",  # 과장명 과장
            r"([가-힣]{2,4})\s*차장",  # 차장명 차장
            r"문의\s*:\s*([가-힣]{2,4})",  # 문의: 담당자명
            r"연락처\s*:\s*([가-힣]{2,4})",  # 연락처: 담당자명
            r"Contact\s*:\s*([가-힣]{2,4})",  # Contact: 담당자명
        ]
        article_end = full_text[-1500:]
        for pattern in reporter_patterns:
            match = re.search(pattern, article_end)
            if match:
                reporter = match.group(1)
                reporter = re.sub(
                    r"기자|담당자|대표|매니저|팀장|실장|부장|과장|차장|문의|연락처|Contact", "", reporter
                ).strip()
                if 2 <= len(reporter) <= 4:
                    break

        # 본문 추출: 1) 지정된 XPath
        content = ""
        try:
            tree = html.fromstring(response.text)
            xpath_expr = "/html/body/div[1]/main/div/div/div/div[2]/section"
            text_nodes = tree.xpath(xpath_expr + "//text()")
            if text_nodes:
                content = " ".join(t.strip() for t in text_nodes if t and t.strip())
        except Exception:
            pass

        # 2) XPath 결과가 부족하면 CSS 기반 보완
        if len(content) < 100:
            content_selectors = [
                "div.article_content",
                'div[class*="article"]',
                'div[class*="content"]',
                'div[class*="news"]',
                'div[class*="text"]',
                "div.news_content",
                "div.view_content",
                "article",
                "main",
                'div[id*="article"]',
                "div.bodycontent",
                "div.story",
                "div.article_body",
                "div.articleView",
                "div.press_content",
                "div.release_content",
            ]
            for selector in content_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text().strip()
                    if len(text) > len(content):
                        content = text

        # 3) 여전히 짧으면 p 태그 순회
        if len(content) < 200:
            paragraphs = soup.find_all("p")
            content_parts = []
            for p in paragraphs:
                text = p.get_text().strip()
                if (
                    len(text) > 20
                    and not re.search(r"입력\s*\d{4}|수정\s*\d{4}|Copyright|저작권|뉴스와이어|newswire", text)
                    and not text.startswith(("▶", "☞", "※", "■", "▲", "[", "※", "◆", "○", "△"))
                    and "무단 전재" not in text
                    and "재배포 금지" not in text
                    and "기사제보" not in text
                    and "문의사항" not in text
                ):
                    content_parts.append(text)
            if content_parts:
                content = " ".join(content_parts)

        # 본문 정제
        content = clean_newswire_content(content)

        # RSS 요약이 더 좋으면 RSS 요약 사용
        if rss_summary and (len(content) < 100 or len(rss_summary) > len(content)):
            content = rss_summary
            print(f"    RSS 요약 채택 (길이: {len(rss_summary)})")

        print(f"    최종 본문 길이: {len(content)}")
        return reporter, content

    except Exception as e:
        print(f"    ❌ 에러: {e}")
        return "", rss_summary if rss_summary else f"오류: {str(e)}"


def clean_newswire_content(content):
    """뉴스와이어 기사 본문 정제"""
    if not content:
        return ""

    # 불필요한 문구들 제거 - 뉴스와이어 특성에 맞게 수정
    remove_patterns = [
        r"입력\s*\d{4}[-./]\d{2}[-./]\d{2}.*?\d{2}:\d{2}",
        r"수정\s*\d{4}[-./]\d{2}[-./]\d{2}.*?\d{2}:\d{2}",
        r"업데이트\s*\d{4}[-./]\d{2}[-./]\d{2}.*?\d{2}:\d{2}",
        r"뉴스와이어.*무단.*전재.*금지",
        r"무단.*전재.*재배포.*금지",
        r"저작권.*뉴스와이어",
        r"관련기사.*더보기",
        r"페이스북.*트위터.*카카오",
        r"구독.*신청",
        r"광고",
        r"보도자료.*문의",
        r"기사.*문의",
        r"newswire\.co\.kr",
        r"ⓒ.*뉴스와이어",
        r"Newswire",
        r"NEWS.*WIRE",
        r"문의사항.*연락처",
        r"홈페이지.*바로가기",
        r"Press.*Release",
        r"보도자료.*끝",
        r"이상.*끝",
        r"\*\*\*.*끝.*\*\*\*",
        r"---.*끝.*---",
        r"Copyright.*\d{4}.*뉴스와이어",
    ]

    for pattern in remove_patterns:
        content = re.sub(pattern, "", content, flags=re.IGNORECASE)

    # 공백 정리
    content = re.sub(r"\s+", " ", content).strip()

    # 길이 제한
    if len(content) > 2000:
        content = content[:2000] + "..."

    return content


def fetch_newswire_rss_to_csv(rss_url, output_file, max_articles=30):
    """뉴스와이어 RSS를 파싱하여 CSV로 저장"""

    print(f"뉴스와이어 RSS 피드 파싱 중: {rss_url}")

    # RSS 파싱
    try:
        headers = {"User-Agent": get_random_user_agent()}
        response = requests.get(rss_url, headers=headers, timeout=10)
        # 뉴스와이어 RSS는 UTF-8 인코딩 사용
        response.encoding = "utf-8"
        feed = feedparser.parse(response.content)
    except:
        feed = feedparser.parse(rss_url)

    if not feed.entries:
        print("❌ RSS 피드에서 보도자료를 찾을 수 없습니다.")
        return

    print(f"✅ RSS에서 {len(feed.entries)}개 보도자료 발견")

    success_count = 0
    total_count = min(len(feed.entries), max_articles)

    # CSV 파일 생성
    with open(output_file, "w", newline="", encoding="utf-8-sig") as csvfile:
        fieldnames = ["제목", "날짜", "카테고리", "담당자명", "본문"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        print(f"총 {total_count}개 보도자료 처리 시작...\n")

        for i, entry in enumerate(feed.entries[:max_articles]):
            try:
                # 기본 정보 추출
                title = entry.title.strip()
                title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", title)

                link = entry.link

                # 카테고리 추출 (뉴스와이어 RSS 구조에 맞게)
                category = ""
                if hasattr(entry, "category"):
                    category = entry.category.strip()
                elif hasattr(entry, "tags") and entry.tags:
                    category = entry.tags[0].term if entry.tags else ""

                # URL에서 카테고리 추출 시도 (뉴스와이어 URL 구조 기반)
                if not category:
                    url_category_map = {
                        # 전체 및 인기
                        "rss/all": "전체",
                        # 산업별
                        "industry/600": "기술",
                        "industry/400": "산업",
                        "industry/1200": "헬스",
                        "industry/900": "생활",
                        "industry/300": "자동차",
                        "industry/100": "경제",
                        "industry/200": "금융",
                        "industry/800": "문화",
                        "industry/1300": "레저",
                        "industry/1100": "교육",
                        "industry/1900": "사회",
                        "industry/1500": "환경",
                        "industry/1400": "정치",
                        # 영문 뉴스
                        "english": "English News",
                        # 지역별
                        "region/1": "인천경기",
                        "region/2": "대전충청",
                        "region/3": "광주전라",
                        "region/4": "대구경북",
                        "region/5": "부산울산경남",
                        "region/6": "강원",
                        "region/7": "강원",
                        "region/8": "충북",
                        "region/9": "전북",
                        "region/10": "제주",
                        "region/11": "해외",
                        "region/123": "정치",
                    }

                    for url_part, cat_name in url_category_map.items():
                        if url_part in rss_url:
                            category = cat_name
                            break

                # RSS 요약 정보 추출
                summary = ""
                if hasattr(entry, "description"):
                    summary = entry.description.strip()
                    # HTML 태그와 CDATA 제거
                    summary = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", summary, flags=re.DOTALL)
                    summary = re.sub(r"<[^>]+>", "", summary)  # HTML 태그 제거
                    summary = clean_newswire_content(summary)

                # 날짜 형식 변환
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    date = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                print(f"[{i+1}/{total_count}] {title[:50]}...")

                # 기사 본문 및 담당자명 추출
                reporter, content = extract_newswire_article_content(link, summary)

                # 최소 조건 확인
                if len(content.strip()) < 30:
                    print(f"    ⚠ 본문이 너무 짧아 건너뜀 (길이: {len(content)})\n")
                    continue

                # CSV에 쓰기
                writer.writerow(
                    {
                        "제목": title,
                        "날짜": date,
                        "카테고리": category if category else "미분류",
                        "담당자명": reporter if reporter else "미상",
                        "본문": content,
                    }
                )

                success_count += 1
                print(
                    f"    ✅ 성공! (카테고리: {category}, 담당자: {reporter if reporter else '미상'}, 본문: {len(content)}자)"
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

        print(f"\n{'='*70}")
        print(f"🎉 완료! CSV 파일 저장: {output_file}")
        print(f"📊 최종 결과: {success_count}/{total_count}개 성공 ({success_count/total_count*100:.1f}%)")
        print(f"{'='*70}")


# 사용 예시
def collect_newswire_rss(rss_url, max_articles=20):
    """뉴스와이어 RSS를 파싱하여 행 리스트로 반환"""
    rows = []
    print(f"뉴스와이어 RSS 파싱: {rss_url}")
    try:
        headers = {"User-Agent": get_random_user_agent()}
        response = requests.get(rss_url, headers=headers, timeout=10)
        response.encoding = "utf-8"
        feed = feedparser.parse(response.content)
    except Exception:
        feed = feedparser.parse(rss_url)

    if not feed.entries:
        print("❌ RSS 피드에서 항목을 찾지 못했습니다.")
        return rows

    total_count = min(len(feed.entries), max_articles)
    print(f"✅ {total_count}개 항목 처리 예정")

    for i, entry in enumerate(feed.entries[:max_articles]):
        try:
            title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", entry.title.strip())
            link = entry.link

            # 카테고리
            category = ""
            if hasattr(entry, "category"):
                category = entry.category.strip()
            elif hasattr(entry, "tags") and entry.tags:
                category = entry.tags[0].term if entry.tags else ""

            # URL 매핑 보조
            if not category:
                url_category_map = {
                    "rss/all": "전체",
                    "industry/600": "기술",
                    "industry/400": "산업",
                    "industry/1200": "헬스",
                    "industry/900": "생활",
                    "industry/300": "자동차",
                    "industry/100": "경제",
                    "industry/200": "금융",
                    "industry/800": "문화",
                    "industry/1300": "레저",
                    "industry/1100": "교육",
                    "industry/1900": "사회",
                    "industry/1500": "환경",
                    "industry/1400": "정치",
                    "english": "English News",
                    "region/1": "인천경기",
                    "region/2": "대전충청",
                    "region/3": "광주전라",
                    "region/4": "대구경북",
                    "region/5": "부산울산경남",
                    "region/6": "강원",
                    "region/7": "강원",
                    "region/8": "충북",
                    "region/9": "전북",
                    "region/10": "제주",
                    "region/11": "해외",
                    "region/123": "정치",
                }
                for url_part, cat_name in url_category_map.items():
                    if url_part in rss_url:
                        category = cat_name
                        break

            # 요약
            summary = ""
            if hasattr(entry, "description"):
                summary = entry.description.strip()
                summary = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", summary, flags=re.DOTALL)
                summary = re.sub(r"<[^>]+>", "", summary)
                summary = clean_newswire_content(summary)

            # 날짜
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                date = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d %H:%M:%S")
            else:
                date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print(f"[{i+1}/{total_count}] {title[:50]}...")
            reporter, content = extract_newswire_article_content(link, summary)
            if len(content.strip()) < 30:
                print(f"    ⚠ 본문이 너무 짧아 건너뜀 (길이: {len(content)})")
                continue

            rows.append(
                {
                    "언론사": "뉴스와이어",
                    "제목": title,
                    "날짜": date,
                    "카테고리": category if category else "미분류",
                    "기자명": reporter if reporter else "미상",
                    "본문": content,
                }
            )

            time.sleep(random.uniform(1.5, 3.0))
        except Exception as e:
            print(f"    ❌ 오류: {e}")
            continue

    return rows


if __name__ == "__main__":
    # 뉴스와이어 RSS URL 옵션들 (첨부된 이미지 기반)
    newswire_rss_options = {
        # 전체
        "전체": "https://api.newswire.co.kr/rss/all",
        # 산업별
        "기술": "https://api.newswire.co.kr/rss/industry/600",
        "산업": "https://api.newswire.co.kr/rss/industry/400",
        "헬스": "https://api.newswire.co.kr/rss/industry/1200",
        "생활": "https://api.newswire.co.kr/rss/industry/900",
        "자동차": "https://api.newswire.co.kr/rss/industry/300",
        "경제": "https://api.newswire.co.kr/rss/industry/100",
        "금융": "https://api.newswire.co.kr/rss/industry/200",
        "문화": "https://api.newswire.co.kr/rss/industry/800",
        "레저": "https://api.newswire.co.kr/rss/industry/1300",
        "교육": "https://api.newswire.co.kr/rss/industry/1100",
        "사회": "https://api.newswire.co.kr/rss/industry/1900",
        "환경": "https://api.newswire.co.kr/rss/industry/1500",
        "정치": "https://api.newswire.co.kr/rss/industry/1400",
        # 영문 뉴스
        "English News": "https://api.newswire.co.kr/rss/english",
        # 지역별 (주요 지역만)
        "서울": "https://api.newswire.co.kr/rss/region/1",
        "인천경기": "https://api.newswire.co.kr/rss/region/2",
        "대전충남": "https://api.newswire.co.kr/rss/region/3",
        "광주전남": "https://api.newswire.co.kr/rss/region/4",
        "부산울산경남": "https://api.newswire.co.kr/rss/region/5",
        "대구경북": "https://api.newswire.co.kr/rss/region/6",
        "강원": "https://api.newswire.co.kr/rss/region/7",
        "충북": "https://api.newswire.co.kr/rss/region/8",
        "전북": "https://api.newswire.co.kr/rss/region/9",
        "제주": "https://api.newswire.co.kr/rss/region/10",
        "해외": "https://api.newswire.co.kr/rss/region/11",
    }
    # 자동 수집 대상: 지정된 10개 분류 + 모든 지역 분류
    target_categories = ["전체", "기술", "산업", "생활", "경제", "금융", "교육", "사회", "환경", "정치"]
    # 지역 분류: URL에 '/region/'이 포함된 항목 전부
    region_categories = [k for k, v in newswire_rss_options.items() if "/region/" in v]

    # 결과 디렉터리 보장
    os.makedirs("results", exist_ok=True)

    # 공통 타임스탬프 (한 번의 실행에서 일관성 있게)
    run_ts = datetime.now().strftime("%Y%m%d_%H%M")

    all_rows = []
    # 지정 카테고리 수집 (각 20개)
    for cat in target_categories:
        if cat not in newswire_rss_options:
            print(f"⚠ 경고: '{cat}' RSS URL이 정의되어 있지 않습니다. 건너뜀.")
            continue
        rss_url = newswire_rss_options[cat]
        print(f"\n🚀 '{cat}' 카테고리에서 20개 보도자료 수집 시작!")
        rows = collect_newswire_rss(rss_url, max_articles=1)
        all_rows.extend(rows)
        time.sleep(random.uniform(1.0, 2.0))

    # 지역 전체 수집
    print("\n📍 지역별 전체 수집 시작...")
    for region in region_categories:
        rss_url = newswire_rss_options[region]
        print(f"\n🚀 지역 '{region}'에서 20개 보도자료 수집 시작!")
        rows = collect_newswire_rss(rss_url, max_articles=1)
        all_rows.extend(rows)
        time.sleep(random.uniform(1.0, 2.0))
    # 하나의 CSV로 저장
    combined_path = f"results/뉴스와이어_전체_{run_ts}.csv"
    with open(combined_path, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)
    print(f"\n✅ 모든 카테고리 및 지역 수집이 완료되었습니다. 총 {len(all_rows)}건")
    print(f"📁 저장 파일: {combined_path}")
