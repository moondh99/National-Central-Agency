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


def extract_kmib_article_content(url, rss_summary=""):
    """국민일보 기사 URL에서 본문과 기자명을 추출"""
    try:
        session = requests.Session()

        headers = {
            "User-Agent": get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.kmib.co.kr/",
            "Cache-Control": "no-cache",
        }

        print(f"    접속 시도: {url[:80]}...")

        # 메인 페이지 방문 후 실제 기사 접근
        try:
            session.get("https://www.kmib.co.kr/", headers=headers, timeout=5)
            time.sleep(0.5)

            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # 국민일보는 일반적으로 접근 제한이 없으므로 기본 크기 체크
            if len(response.content) < 5000:  # 5KB 미만이면 문제가 있을 수 있음
                print(f"    ⚠ 응답 크기가 작음 (크기: {len(response.content)} bytes)")

        except Exception as e:
            print(f"    ⚠ 웹페이지 접근 실패: {e}")
            return "", rss_summary if rss_summary else "웹페이지 접근 실패"

        soup = BeautifulSoup(response.content, "html.parser")
        full_text = soup.get_text()

        # 기자명 추출 - 국민일보 패턴에 맞게 수정
        reporter = ""
        reporter_patterns = [
            r"([가-힣]{2,4})\s*기자\s*([a-zA-Z0-9_.+-]+@kmib\.co\.kr)",  # 기자명 기자 이메일@kmib.co.kr
            r"([가-힣]{2,4})\s*기자\s*[a-zA-Z0-9_.+-]+@kmib\.co\.kr",  # 기자명 기자 이메일
            r"([가-힣]{2,4})\s*기자",  # 기자명 기자
            r"기자\s*([가-힣]{2,4})",  # 기자 기자명
            r"([가-힣]{2,4})\s*특파원",  # 기자명 특파원
            r"([가-힣]{2,4})\s*팀장",  # 기자명 팀장
        ]

        # 기사 본문 끝 부분에서 기자명을 찾는 것이 더 정확
        article_end = full_text[-1000:]  # 마지막 1000자에서 찾기

        for pattern in reporter_patterns:
            match = re.search(pattern, article_end)
            if match:
                reporter = match.group(1)
                reporter = re.sub(r"기자|특파원|팀장", "", reporter).strip()
                if len(reporter) >= 2 and len(reporter) <= 4:
                    break

        # 본문 추출 - 국민일보 HTML 구조에 맞게 수정
        content = ""

        # 방법 1: 지정된 XPath(/html/body/div[1]/div/section/article/div[1]/div[1])에 해당하는 본문 추출
        xpath_like_selectors = [
            "html > body > div:nth-of-type(1) > div > section > article > div:nth-of-type(1) > div:nth-of-type(1)",
            "body > div:nth-of-type(1) > div > section > article > div:nth-of-type(1) > div:nth-of-type(1)",
        ]

        for sel in xpath_like_selectors:
            target_element = soup.select_one(sel)
            if target_element and len(target_element.get_text(strip=True)) > 50:
                content = target_element.get_text().strip()
                break

        # 방법 2: 백업용 - 기존 선택자들
        if len(content) < 200:
            content_selectors = [
                "div.article_txt",  # 국민일보 기사 본문 클래스
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

        # 방법 2: P 태그 기반 추출 (국민일보 특성에 맞게 수정)
        if len(content) < 200:
            paragraphs = soup.find_all("p")
            content_parts = []

            for p in paragraphs:
                text = p.get_text().strip()
                if (
                    len(text) > 20
                    and not re.search(r"입력\s*\d{4}|업데이트\s*\d{4}|Copyright|저작권|국민일보|GoodNews paper", text)
                    and not text.startswith(("▶", "☞", "※", "■", "▲", "[", "※"))
                    and "@kmib.co.kr" not in text
                ):
                    content_parts.append(text)

            if content_parts:
                content = " ".join(content_parts)

        # 본문 정제
        content = clean_kmib_content(content)

        # RSS 요약이 더 좋으면 RSS 요약 사용
        if rss_summary and (len(content) < 100 or len(rss_summary) > len(content)):
            content = rss_summary
            print(f"    RSS 요약 채택 (길이: {len(rss_summary)})")

        print(f"    최종 본문 길이: {len(content)}")
        return reporter, content

    except Exception as e:
        print(f"    ❌ 에러: {e}")
        return "", rss_summary if rss_summary else f"오류: {str(e)}"


def clean_kmib_content(content):
    """국민일보 기사 본문 정제"""
    if not content:
        return ""

    # 불필요한 문구들 제거 - 국민일보 특성에 맞게 수정
    remove_patterns = [
        r"입력\s*\d{4}\.\d{2}\.\d{2}.*?\d{2}:\d{2}",
        r"업데이트\s*\d{4}\.\d{2}\.\d{2}.*?\d{2}:\d{2}",
        r"GoodNews paper.*국민일보",
        r"무단.*전재.*금지",
        r"AI학습.*이용.*금지",
        r"관련기사.*더보기",
        r"페이스북.*트위터.*카카오",
        r"구독.*신청",
        r"광고",
        r"[가-힣]{2,4}\s*기자\s*[a-zA-Z0-9_.+-]+@kmib\.co\.kr",  # 기자 이메일 제거
        r"LCK\s*제공",  # 사진 출처 제거
        r"연합뉴스.*제공",  # 사진 출처 제거
    ]

    for pattern in remove_patterns:
        content = re.sub(pattern, "", content, flags=re.IGNORECASE)

    # 공백 정리
    content = re.sub(r"\s+", " ", content).strip()

    # 길이 제한
    if len(content) > 1500:
        content = content[:1500] + "..."

    return content


def _is_valid_korean_name(name: str) -> bool:
    """2~4자 한글 이름이며 금지어가 아닌지 검사"""
    if not name:
        return False
    name = str(name).strip()
    invalid_terms = {
        "서비스",
        "국민일보",
        "관리자",
        "운영자",
        "데스크",
        "편집",
        "온라인",
        "뉴스",
    }
    if name in invalid_terms:
        return False
    return re.fullmatch(r"[가-힣]{2,4}", name) is not None


def parse_reporter_from_author(author_info: str) -> str:
    """RSS author 문자열에서 기자명만 추출

    예) "김세훈 기자 ksh3712@kyunghyang.com" -> "김세훈"
        "작성자 김세훈 기자" -> "김세훈"
        "기자 김세훈" -> "김세훈"
        "<![CDATA[ 김세훈 기자 ksh3712@kyunghyang.com ]]>" -> "김세훈" (CDATA 처리 추가)
    """
    if not author_info:
        return ""

    # CDATA 제거 및 공백 정리 (기존과 동일하지만, 더 강력하게 처리)
    text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", author_info, flags=re.DOTALL).strip()
    text = re.sub(r"\s+", " ", text)

    # 언론사명만 있는 경우 배제
    if text in {"국민일보", "서비스"}:
        return ""

    # 패턴 목록 (기존 패턴 유지, 필요 시 일반화)
    patterns = [
        r"([가-힣]{2,4})\s*기자\s*[a-zA-Z0-9_.+-]+@[a-zA-Z0-9.-]+",  # 이름 기자 email (예: 김세훈 기자 ksh3712@kyunghyang.com)
        r"([가-힣]{2,4})\s*(?:인턴)?기자",  # 이름 (인턴)기자
        r"기자\s*([가-힣]{2,4})",  # 기자 이름
        r"([가-힣]{2,4})\s*특파원",  # 이름 특파원
        r"([가-힣]{2,4})\s*팀장",  # 이름 팀장
        r"작성자\s*([가-힣]{2,4})\s*기자",  # 작성자 이름 기자 (추가 패턴)
    ]

    for p in patterns:
        m = re.search(p, text)
        if m:
            name = m.group(1).strip()
            # 방어적 후처리 (기자, 인턴 등 제거)
            name = re.sub(r"(기자|인턴|특파원|팀장|작성자)$", "", name).strip()
            if _is_valid_korean_name(name):
                return name

    # 일반 텍스트에 포함된 "이름 기자 email" 패턴을 후순위로 한 번 더 시도
    m = re.search(r"([가-힣]{2,4})\s*기자\s*[a-zA-Z0-9_.+-]+@[a-zA-Z0-9.-]+", text)
    if m:
        name = m.group(1).strip()
        if _is_valid_korean_name(name):
            return name

    return ""


def get_rss_reporter(entry) -> tuple[str, str]:
    """feedparser entry에서 기자명 후보 문자열을 모아 파싱한다.
    반환: (기자명, 원본문자열) — 기자명을 못 찾으면 ("", 마지막 검사 원본 or "").
    """
    candidates: list[str] = []
    # 0) description CDATA 내 텍스트에서 기자명 우선 시도
    try:
        desc = getattr(entry, "description", None)
        if desc:
            # CDATA 제거 후 태그 제거
            text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", str(desc), flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            name = parse_reporter_from_author(text)
            if _is_valid_korean_name(name):
                return name, "description"
    except Exception:
        pass
    # 1) author
    if hasattr(entry, "author") and entry.author:
        candidates.append(str(entry.author))
    # 2) author_detail.name
    if hasattr(entry, "author_detail") and entry.author_detail:
        try:
            name_val = getattr(entry.author_detail, "name", None)
        except Exception:
            name_val = None
        if name_val:
            candidates.append(str(name_val))
    # 3) dc:creator (feedparser는 dc:creator를 dc_creator로 매핑하는 경우가 있음)
    dc_val = getattr(entry, "dc_creator", None) or getattr(entry, "creator", None)
    if dc_val:
        candidates.append(str(dc_val))
    # 4) authors 리스트
    if hasattr(entry, "authors") and entry.authors:
        for a in entry.authors:
            # dict-like or object with name
            try:
                nm = a.get("name") if isinstance(a, dict) else getattr(a, "name", None)
            except Exception:
                nm = None
            if nm:
                candidates.append(str(nm))

    # 중복 제거, 공백 정리
    seen = set()
    normalized = []
    for c in candidates:
        s = re.sub(r"\s+", " ", c).strip()
        if s and s not in seen:
            seen.add(s)
            normalized.append(s)

    last_src = ""
    for src in normalized:
        last_src = src
        name = parse_reporter_from_author(src)
        if _is_valid_korean_name(name):
            return name, src
    return "", last_src


def fetch_kmib_rss_to_csv(rss_url, output_file, max_articles=30):
    """국민일보 RSS를 파싱하여 CSV로 저장"""

    print(f"국민일보 RSS 피드 파싱 중: {rss_url}")

    # RSS 파싱
    try:
        headers = {"User-Agent": get_random_user_agent()}
        response = requests.get(rss_url, headers=headers, timeout=10)
        # 국민일보 RSS는 EUC-KR 인코딩 사용
        response.encoding = "euc-kr"
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

                # 카테고리 추출
                category = ""
                if hasattr(entry, "category"):
                    category = entry.category.strip()

                # RSS 요약 정보 추출
                summary = ""
                if hasattr(entry, "description"):
                    summary = entry.description.strip()
                    # HTML 태그와 CDATA 제거
                    summary = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", summary, flags=re.DOTALL)
                    summary = re.sub(r"<[^>]+>", "", summary)  # HTML 태그 제거
                    summary = clean_kmib_content(summary)

                # RSS에서 기자명 추출 (여러 필드 검사)
                rss_reporter, rss_src = get_rss_reporter(entry)
                if rss_reporter:
                    print(f"    🔎 RSS 기자명: '{rss_reporter}' ← {rss_src}")
                else:
                    if rss_src:
                        print(f"    ⚠ RSS 기자명 파싱 실패. 원본: {rss_src}")
                    else:
                        print("    ⚠ RSS에 기자 관련 필드 없음")

                # 날짜 형식 변환
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    date = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                print(f"[{i+1}/{total_count}] {title[:60]}...")

                # 기사 본문 및 기자명 추출 (웹)
                reporter, content = extract_kmib_article_content(link, summary)

                # 최종 기자명 결정: RSS > 웹 > 미상 (유효성 검증)
                final_reporter = (
                    rss_reporter
                    if _is_valid_korean_name(rss_reporter)
                    else (reporter if _is_valid_korean_name(reporter) else "미상")
                )

                # 최소 조건 확인
                if len(content.strip()) < 20:
                    print(f"    ⚠ 본문이 너무 짧아 건너뜀 (길이: {len(content)})\n")
                    continue

                # CSV에 쓰기
                writer.writerow(
                    {
                        "언론사": "국민일보",
                        "제목": title,
                        "날짜": date,
                        "카테고리": category if category else "미분류",
                        "기자명": final_reporter,
                        "본문": content,
                    }
                )

                success_count += 1
                print(f"    ✅ 성공! (카테고리: {category}, 기자: {final_reporter}, 본문: {len(content)}자)")

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

        print(f"\n{'='*70}")
        print(f"🎉 완료! CSV 파일 저장: {output_file}")
        print(f"📊 최종 결과: {success_count}/{total_count}개 성공 ({success_count/total_count*100:.1f}%)")
        print(f"{'='*70}")


# 사용 예시
if __name__ == "__main__":
    # 국민일보 RSS URL 옵션들 (전체기사, 정치, 경제, 사회, 국제, 문화만)
    kmib_rss_options = {
        "전체기사": "https://www.kmib.co.kr/rss/data/kmibRssAll.xml",
        "정치": "https://www.kmib.co.kr/rss/data/kmibPolRss.xml",
        "경제": "https://www.kmib.co.kr/rss/data/kmibEcoRss.xml",
        "사회": "https://www.kmib.co.kr/rss/data/kmibSocRss.xml",
        "국제": "https://www.kmib.co.kr/rss/data/kmibIntRss.xml",
        "문화": "https://www.kmib.co.kr/rss/data/kmibCulRss.xml",
    }

    print("국민일보 RSS 자동 수집기")
    print("=" * 50)
    print("각 카테고리별로 20개씩 자동 수집합니다.")
    print(f"수집 카테고리: {', '.join(kmib_rss_options.keys())}")
    print("=" * 50)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    max_articles = 20
    output_file = f"results/국민일보_전체_{timestamp}.csv"

    print(f"\n📁 통합 저장 파일: {output_file}")
    print("-" * 50)

    # 하나의 CSV 파일에 모든 카테고리 데이터 저장
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", newline="", encoding="utf-8-sig") as csvfile:
        fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        total_success = 0
        total_processed = 0

        # 각 카테고리별로 수집하여 같은 파일에 추가
        for category, rss_url in kmib_rss_options.items():
            print(f"\n🚀 {category} 카테고리 수집 시작!")
            print("-" * 30)

            # RSS 파싱
            try:
                headers = {"User-Agent": get_random_user_agent()}
                response = requests.get(rss_url, headers=headers, timeout=10)
                response.encoding = "euc-kr"
                feed = feedparser.parse(response.content)
            except:
                feed = feedparser.parse(rss_url)

            if not feed.entries:
                print(f"❌ {category} RSS 피드에서 기사를 찾을 수 없습니다.")
                continue

            print(f"✅ {category}에서 {len(feed.entries)}개 기사 발견")

            success_count = 0
            total_count = min(len(feed.entries), max_articles)

            for i, entry in enumerate(feed.entries[:max_articles]):
                try:
                    # 기본 정보 추출
                    title = entry.title.strip()
                    title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", title)

                    link = entry.link

                    # RSS에서 기자명 추출 (헬퍼 사용, 여러 필드 검사)
                    rss_reporter, rss_src = get_rss_reporter(entry)
                    if rss_reporter:
                        print(f"    ✅ RSS에서 기자명 추출: '{rss_reporter}' ← {rss_src}")
                    else:
                        if rss_src:
                            print(f"    ⚠ RSS 기자명 파싱 실패. 원본: {rss_src}")
                        else:
                            print("    ⚠ RSS에 기자 관련 필드 없음")

                    # RSS 요약 정보 추출
                    summary = ""
                    if hasattr(entry, "description"):
                        summary = entry.description.strip()
                        summary = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", summary, flags=re.DOTALL)
                        summary = re.sub(r"<[^>]+>", "", summary)
                        summary = clean_kmib_content(summary)

                    # 날짜 형식 변환
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        date = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    print(f"  [{i+1}/{total_count}] {title[:50]}...")

                    # 기사 본문 추출 (웹 크롤링에서 기자명도 함께 추출)
                    web_reporter, content = extract_kmib_article_content(link, summary)

                    # 최종 기자명 결정: RSS > 웹 > 미상 (유효성 검증)
                    final_reporter = (
                        rss_reporter
                        if _is_valid_korean_name(rss_reporter)
                        else (web_reporter if _is_valid_korean_name(web_reporter) else "미상")
                    )

                    print(f"    📰 최종 기자명: '{final_reporter}' (RSS: '{rss_reporter}', 웹: '{web_reporter}')")

                    # 최소 조건 확인
                    if len(content.strip()) < 20:
                        print(f"    ⚠ 본문이 너무 짧아 건너뜀")
                        continue

                    # CSV에 쓰기
                    writer.writerow(
                        {
                            "언론사": "국민일보",
                            "제목": title,
                            "날짜": date,
                            "카테고리": category,
                            "기자명": final_reporter,
                            "본문": content,
                        }
                    )

                    success_count += 1
                    print(f"    ✅ 성공! (기자: {final_reporter})")

                    # 랜덤 딜레이
                    delay = random.uniform(1.0, 2.5)
                    time.sleep(delay)

                except KeyboardInterrupt:
                    print("\n⚠ 사용자가 중단했습니다.")
                    break
                except Exception as e:
                    print(f"    ❌ 오류: {e}")
                    continue

            total_success += success_count
            total_processed += total_count
            print(f"✅ {category} 완료: {success_count}/{total_count}개 성공\n")

    print(f"\n{'='*70}")
    print(f"🎉 모든 카테고리 수집 완료!")
    print(f"📁 저장 파일: {output_file}")
    print(f"📊 최종 결과: {total_success}개 기사 수집 완료")
    print(f"{'='*70}")
