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


def extract_reporter_from_description(description):
    """RSS description에서 기자명 추출 (예: '이미영 | 2025-08-12')"""
    reporter = ""

    if description and "|" in description:
        parts = description.split("|")
        if len(parts) >= 2:
            potential_reporter = parts[0].strip()
            # 한글 이름 패턴 확인 (2-4글자)
            if len(potential_reporter) >= 2 and len(potential_reporter) <= 10:
                # 한글만 포함된 이름인지 확인
                if re.match(r"^[가-힣\s]+$", potential_reporter):
                    reporter = potential_reporter

    return reporter


def extract_gnews_article_content(url, rss_description=""):
    """경기도 뉴스포털 기사 URL에서 본문과 기자명을 추출"""
    try:
        session = requests.Session()

        headers = {
            "User-Agent": get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://gnews.gg.go.kr/",
            "Cache-Control": "no-cache",
        }

        print(f"    접속 시도: {url[:80]}...")

        # 메인 페이지 방문 후 실제 기사 접근
        try:
            session.get("https://gnews.gg.go.kr/", headers=headers, timeout=5)
            time.sleep(0.5)

            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # 경기도 뉴스포털은 일반적으로 접근 제한이 없음
            if len(response.content) < 3000:  # 3KB 미만이면 문제가 있을 수 있음
                print(f"    ⚠ 응답 크기가 작음 (크기: {len(response.content)} bytes)")

        except Exception as e:
            print(f"    ⚠ 웹페이지 접근 실패: {e}")
            # RSS description에서 기자명 추출 시도
            reporter = extract_reporter_from_description(rss_description)
            return reporter, rss_description if rss_description else "웹페이지 접근 실패"

        soup = BeautifulSoup(response.content, "html.parser")

        # RSS description에서 기자명 추출
        reporter = extract_reporter_from_description(rss_description)

        # 본문 추출 - 다양한 방법 시도
        content = ""
        full_text = soup.get_text()

        # 방법 1: 특정 태그에서 추출
        content_tags = ["div", "article", "main", "section"]
        for tag in content_tags:
            elements = soup.find_all(tag)
            for element in elements:
                text = element.get_text().strip()
                # 긴 텍스트를 본문으로 간주
                if len(text) > len(content) and len(text) > 100:
                    content = text

        # 방법 2: P 태그들을 모두 합치기
        if len(content) < 200:
            paragraphs = soup.find_all("p")
            content_parts = []

            for p in paragraphs:
                text = p.get_text().strip()
                if len(text) > 20:
                    # 불필요한 텍스트 제외
                    if not any(skip_word in text for skip_word in ["ⓒ", "#경기", "#Gyeonggi", "내일이 먼저"]):
                        content_parts.append(text)

            if content_parts:
                content = " ".join(content_parts)

        # 방법 3: 전체 텍스트에서 추출
        if len(content) < 100:
            lines = full_text.split("\n")
            content_lines = []

            for line in lines:
                line = line.strip()
                if len(line) > 30:  # 충분히 긴 라인만
                    # 불필요한 라인 제외
                    if not any(skip_word in line for skip_word in ["ⓒ", "#경기", "#Gyeonggi", "내일이 먼저"]):
                        content_lines.append(line)

            if content_lines:
                content = " ".join(content_lines[:10])  # 처음 10개 라인만

        # 본문 정제
        content = clean_gnews_content(content)

        # RSS description이 더 좋으면 RSS description 사용
        if rss_description and (len(content) < 100 or len(rss_description) > len(content)):
            content = rss_description
            print(f"    RSS description 채택 (길이: {len(rss_description)})")

        print(f"    최종 본문 길이: {len(content)}")
        return reporter, content

    except Exception as e:
        print(f"    ❌ 에러: {e}")
        reporter = extract_reporter_from_description(rss_description)
        return reporter, rss_description if rss_description else f"오류: {str(e)}"


def clean_gnews_content(content):
    """경기도 뉴스포털 기사 본문 정제 - 안전한 방법 사용"""
    if not content:
        return ""

    # 문자열 치환으로 불필요한 내용 제거 (정규식 사용 최소화)

    # 저작권 표시 제거
    content = content.replace("ⓒ 경기도청", "")
    content = content.replace("ⓒ 경기도", "")
    content = content.replace("내일이 먼저 시작되는 경기.", "")

    # 해시태그 제거 (간단한 방법)
    lines = content.split("\n")
    cleaned_lines = []
    for line in lines:
        if not line.strip().startswith("#"):
            cleaned_lines.append(line)
    content = "\n".join(cleaned_lines)

    # 공백 정리 (안전한 정규식만 사용)
    content = re.sub(r"\s+", " ", content).strip()

    # 길이 제한
    if len(content) > 1500:
        content = content[:1500] + "..."

    return content


def fetch_gnews_rss_to_csv(rss_url, category, writer, max_articles=30):
    """경기도 뉴스포털 RSS를 파싱하여 CSV writer에 추가"""

    print(f"경기도 뉴스포털 RSS 피드 파싱 중: {rss_url}")

    # RSS 파싱
    try:
        headers = {"User-Agent": get_random_user_agent()}
        response = requests.get(rss_url, headers=headers, timeout=10)
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
            # CDATA 제거 (안전한 방법)
            if "<![CDATA[" in title:
                title = title.replace("<![CDATA[", "").replace("]]>", "")

            link = entry.link

            # RSS deion 정보 추출 (기자명 | 날짜 형식)
            reporter = ""

            # deion 필드에서 기자명 정보 추출
            deion_value = entry.get("deion")
            if deion_value:
                deion_value = deion_value.strip()
                reporter = extract_reporter_from_description(deion_value)
                print(f"    deion에서 기자명 정보 발견: {deion_value} → {reporter}")
            elif hasattr(entry, "deion"):
                deion_value = entry.deion.strip()
                reporter = extract_reporter_from_description(deion_value)
                print(f"    deion 속성에서 기자명 정보 발견: {deion_value} → {reporter}")
            else:
                # deion이 없으면 description에서 찾기
                description_for_reporter = ""
                if hasattr(entry, "description"):
                    description_for_reporter = entry.description.strip()
                    description_for_reporter = re.sub(r"<[^>]+>", "", description_for_reporter)
                    reporter = extract_reporter_from_description(description_for_reporter)
                    print(f"    description에서 기자명 정보 발견: {description_for_reporter} → {reporter}")
                elif hasattr(entry, "summary"):
                    description_for_reporter = entry.summary.strip()
                    description_for_reporter = re.sub(r"<[^>]+>", "", description_for_reporter)
                    reporter = extract_reporter_from_description(description_for_reporter)
                    print(f"    summary에서 기자명 정보 발견: {description_for_reporter} → {reporter}")
                else:
                    print(f"    deion/description/summary 필드를 찾을 수 없음")

            # 본문 추출용 description 별도 처리
            description = ""
            if hasattr(entry, "description"):
                description = entry.description.strip()
                description = re.sub(r"<[^>]+>", "", description)
            elif hasattr(entry, "summary"):
                description = entry.summary.strip()
                description = re.sub(r"<[^>]+>", "", description)

            # 날짜 형식 변환
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                date = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d %H:%M:%S")
            elif hasattr(entry, "pubdate_parsed") and entry.pubdate_parsed:
                date = datetime(*entry.pubdate_parsed[:6]).strftime("%Y-%m-%d %H:%M:%S")
            else:
                date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print(f"[{i+1}/{total_count}] {title[:60]}...")

            # 기사 본문 추출 (기자명은 이미 추출됨)
            _, content = extract_gnews_article_content(link, description)

            # 최소 조건 확인
            if len(content.strip()) < 20:
                print(f"    ⚠ 본문이 너무 짧아 건너뜀 (길이: {len(content)})\n")
                continue

            # CSV에 쓰기 - 언론사, 제목, 날짜, 카테고리, 기자명, 본문 순
            writer.writerow(
                {
                    "언론사": "경기도뉴스포털",
                    "제목": title,
                    "날짜": date,
                    "카테고리": category,
                    "기자명": reporter if reporter else "미상",
                    "본문": content,
                }
            )

            success_count += 1
            print(f"    ✅ 성공! (기자: {reporter if reporter else '미상'}, 본문: {len(content)}자)")

            # 진행률 표시
            if (i + 1) % 5 == 0:
                print(f"\n📊 진행률: {i+1}/{total_count} ({(i+1)/total_count*100:.1f}%)")
                print(f"📈 성공률: {success_count}/{i+1} ({success_count/(i+1)*100:.1f}%)\n")

            # 랜덤 딜레이 (서버 부하 방지)
            delay = random.uniform(1.5, 2.5)
            time.sleep(delay)

        except KeyboardInterrupt:
            print("\n⚠ 사용자가 중단했습니다.")
            break
        except Exception as e:
            print(f"    ❌ 오류: {e}")
            continue

    print(f"\n{'='*70}")
    print(f"🎉 {category} 카테고리 완료!")
    print(f"📊 결과: {success_count}/{total_count}개 성공 ({success_count/total_count*100:.1f}%)")
    print(f"{'='*70}")

    return success_count


# 사용 예시
if __name__ == "__main__":
    # 경기도 뉴스포털 RSS URL 옵션들
    gnews_rss_options = {
        "정치": "https://gnews.gg.go.kr/rss/categoryRssSearch.do?kwd=E001&policyCode=E001",
        "복지": "https://gnews.gg.go.kr/rss/categoryRssSearch.do?kwd=E002&policyCode=E002",
        "교육": "https://gnews.gg.go.kr/rss/categoryRssSearch.do?kwd=E003&policyCode=E003",
        "주택": "https://gnews.gg.go.kr/rss/categoryRssSearch.do?kwd=E004&policyCode=E004",
        "환경": "https://gnews.gg.go.kr/rss/categoryRssSearch.do?kwd=E005&policyCode=E005",
        "문화": "https://gnews.gg.go.kr/rss/categoryRssSearch.do?kwd=E006&policyCode=E006",
        "교통": "https://gnews.gg.go.kr/rss/categoryRssSearch.do?kwd=E007&policyCode=E007",
        "안전": "https://gnews.gg.go.kr/rss/categoryRssSearch.do?kwd=E008&policyCode=E008",
        "보도자료": "https://gnews.gg.go.kr/rss/gnewsRssBodo.do",
        "경기뉴스광장": "https://gnews.gg.go.kr/rss/gnewsZoneRss.do",
        "일일뉴스": "https://gnews.gg.go.kr/rss/gnewsDailyRss.do",
        "나의경기도": "https://gnews.gg.go.kr/rss/gnewsMyGyeonggiRss.do",
    }

    # 모든 카테고리에 대해 자동으로 20개씩 수집하여 하나의 CSV 파일에 저장
    print("경기도 뉴스포털 RSS 자동 수집기")
    print("=" * 60)
    print("모든 카테고리에서 각각 20개씩 기사를 수집하여 하나의 CSV 파일에 저장합니다.")
    print("=" * 60)

    max_articles = 20
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = f"results/경기도뉴스포털_전체_{timestamp}.csv"

    total_categories = len(gnews_rss_options)
    current_category = 0
    total_success_count = 0

    # 단일 CSV 파일 생성
    with open(output_file, "w", newline="", encoding="utf-8-sig") as csvfile:
        fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for category, rss_url in gnews_rss_options.items():
            current_category += 1

            print(f"\n🚀 [{current_category}/{total_categories}] {category} 카테고리 수집 시작!")
            print(f"🔗 RSS URL: {rss_url}")
            print("-" * 60)

            try:
                # 실행
                success_count = fetch_gnews_rss_to_csv(rss_url, category, writer, max_articles)
                total_success_count += success_count

                print(f"✅ {category} 카테고리 수집 완료! ({success_count}개 기사)")

                # 다음 카테고리 전에 잠시 대기 (서버 부하 방지)
                if current_category < total_categories:
                    print("⏳ 다음 카테고리 수집을 위해 3초 대기 중...")
                    time.sleep(3)

            except KeyboardInterrupt:
                print(f"\n⚠ 사용자가 중단했습니다. ({current_category}/{total_categories} 완료)")
                break
            except Exception as e:
                print(f"❌ {category} 카테고리 수집 중 오류: {e}")
                continue

    print(f"\n{'='*60}")
    print(f"🎉 전체 수집 완료!")
    print(f"📊 처리된 카테고리: {current_category}/{total_categories}")
    print(f"📈 총 수집 기사: {total_success_count}개")
    print(f"📁 저장 파일: {output_file}")
    print(f"{'='*60}")
