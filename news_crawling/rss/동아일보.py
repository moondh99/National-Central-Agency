import requests
import xml.etree.ElementTree as ET
import csv
import re
from datetime import datetime
from bs4 import BeautifulSoup
import time


def extract_full_article_content(url):
    """동아일보 기사 URL에서 전체 본문을 추출하는 함수"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        response.encoding = "utf-8"

        soup = BeautifulSoup(response.text, "html.parser")

        # 뉴스 본문 추출: 원문 페이지에서 지정된 XPath에 해당하는 부분(CSS 선택자로 변환)
        content_element = soup.select_one(
            "html > body > div:nth-of-type(1) > div:nth-of-type(1) > main > div:nth-of-type(2) > div > div:nth-of-type(1) > section:nth-of-type(1)"
        )
        if content_element:
            # 불필요한 요소 제거
            for unwanted in content_element.find_all(
                ["script", "style", "iframe", "ins", "div.ad", "advertisement", "related-articles"]
            ):
                unwanted.decompose()

            full_content = content_element.get_text(separator="\n", strip=True)
            # 정리: 연속된 줄바꿈과 공백 정리
            full_content = re.sub(r"\n+", "\n", full_content)
            full_content = re.sub(r"\s+", " ", full_content)
            return full_content.strip()
        else:
            return ""

    except Exception as e:
        print(f"본문 추출 중 오류: {e}")
        return ""


def extract_reporter_name(soup, article_text):
    """기자명을 추출하는 함수"""
    try:
        # 추가: 지정된 위치에서 기자명 추출 (CSS 선택자로 변환)
        reporter_element = soup.select_one(
            "html > body > div:nth-of-type(1) > div:nth-of-type(1) > main > div:nth-of-type(2) > div > div:nth-of-type(1) > div:nth-of-type(3)"
        )
        if reporter_element:
            reporter_text = reporter_element.get_text(strip=True)
            if reporter_text:
                if "기자" not in reporter_text:
                    reporter_text += " 기자"
                return reporter_text

        # 다양한 기자명 추출 패턴 (기존 로직)
        reporter_patterns = [
            # HTML에서 기자명 추출
            r"<span[^>]*class[^>]*reporter[^>]*>([^<]+)</span>",
            r"<div[^>]*class[^>]*reporter[^>]*>([^<]+)</div>",
            r"<p[^>]*class[^>]*reporter[^>]*>([^<]+)</p>",
            # 텍스트에서 기자명 추출
            r"([가-힣]{2,4})\s*기자(?:\s*=|\s*∙|\s*·|\s*입력|\s*수정|\s*작성)",
            r"기자\s*([가-힣]{2,4})(?:\s*=|\s*∙|\s*·)",
            r"([가-힣]{2,4})\s*특파원",
            r"([가-힣]{2,4})\s*논설위원",
            r"([가-힣]{2,4})\s*선임기자",
            r"([가-힣]{2,4})\s*편집위원",
            r"/\s*([가-힣]{2,4})\s*기자",
            r"=\s*([가-힣]{2,4})\s*기자",
            r"∙\s*([가-힣]{2,4})\s*기자",
            r"·\s*([가-힣]{2,4})\s*기자",
        ]

        # BeautifulSoup 객체에서 기자명 찾기 (기존 로직)
        if soup:
            reporter_elements = soup.find_all(["span", "div", "p"], class_=re.compile(r"reporter|writer|author"))
            for element in reporter_elements:
                text = element.get_text(strip=True)
                if "기자" in text:
                    match = re.search(r"([가-힣]{2,4})", text)
                    if match:
                        return match.group(1) + " 기자"

        # 기사 텍스트에서 기자명 찾기 (기존 로직)
        full_text = str(soup)

        for pattern in reporter_patterns:
            matches = re.findall(pattern, full_text)
            if matches:
                reporter = matches[0].strip()
                if reporter and len(reporter) >= 2:
                    return reporter + (" 기자" if "기자" not in reporter else "")

        return "기자명 없음"

    except Exception as e:
        print(f"기자명 추출 중 오류: {e}")
        return "기자명 없음"


def parse_donga_rss_full_content(max_articles=None):
    """동아일보 RSS를 파싱하여 전체 본문 데이터를 반환하는 함수"""

    rss_url = "https://rss.donga.com/total.xml"

    try:
        print("동아일보 RSS 피드를 가져오는 중...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        response = requests.get(rss_url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = "utf-8"

        # XML 파싱
        root = ET.fromstring(response.content)
        items = root.findall(".//item")
        news_data = []

        # 최대 기사 수 제한
        if max_articles and len(items) > max_articles:
            items = items[:max_articles]
            print(f"⚠️  최대 {max_articles}개 기사로 제한합니다.")

        print(f"총 {len(items)}개의 뉴스 항목을 발견했습니다.")
        print("각 기사의 전체 본문을 추출하는 중... (시간이 소요될 수 있습니다)")

        for i, item in enumerate(items):
            try:
                # 기본 정보 추출
                title = item.find("title").text if item.find("title") is not None else "제목 없음"
                title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", title)
                title = re.sub(r"<[^>]+>", "", title).strip()

                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""

                # 날짜 포맷 변환
                formatted_date = ""
                if pub_date:
                    try:
                        date_obj = datetime.strptime(pub_date.split(" +")[0], "%a, %d %b %Y %H:%M:%S")
                        formatted_date = date_obj.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_date = pub_date

                link = item.find("link").text if item.find("link") is not None else ""

                print(f"[{i+1}/{len(items)}] 처리 중: {title[:80]}...")

                if link:
                    try:
                        article_response = requests.get(link, headers=headers, timeout=20)
                        article_response.encoding = "utf-8"
                        soup = BeautifulSoup(article_response.text, "html.parser")

                        # 전체 본문 추출
                        full_content = extract_full_article_content(link)

                        # 기자명 추출
                        reporter_name = extract_reporter_name(soup, full_content)

                        # 본문이 너무 짧은 경우 RSS description도 포함
                        if len(full_content) < 200:
                            rss_description = (
                                item.find("description").text if item.find("description") is not None else ""
                            )
                            rss_description = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", rss_description)
                            rss_description = re.sub(r"<[^>]+>", "", rss_description).strip()

                            if rss_description:
                                full_content = (
                                    rss_description + "\n\n" + full_content if full_content else rss_description
                                )

                        # 데이터 저장 (언론사: 동아일보, 카테고리: 전체)
                        news_data.append(
                            {
                                "언론사": "동아일보",
                                "제목": title,
                                "날짜": formatted_date,
                                "카테고리": "전체",
                                "기자명": reporter_name,
                                "본문": full_content,
                            }
                        )

                        # 서버 부하 방지
                        time.sleep(1)

                    except Exception as e:
                        print(f"  ➤ 기사 처리 중 오류: {e}")
                        # 오류가 발생해도 RSS 기본 정보는 저장
                        description = item.find("description").text if item.find("description") is not None else ""
                        description = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", description)
                        description = re.sub(r"<[^>]+>", "", description).strip()

                        news_data.append(
                            {
                                "언론사": "동아일보",
                                "제목": title,
                                "날짜": formatted_date,
                                "카테고리": "전체",
                                "기자명": "기자명 없음",
                                "본문": description,
                            }
                        )
                        continue

            except Exception as e:
                print(f"RSS 항목 처리 중 오류: {e}")
                continue

        # CSV 저장 대신 뉴스 데이터를 반환
        if news_data:
            print(f"\n✅ 성공적으로 {len(news_data)}개의 뉴스를 수집했습니다!")
            total_chars = sum(len(item["본문"]) for item in news_data)
            avg_chars = total_chars // len(news_data) if news_data else 0
            print(f"📊 평균 본문 길이: {avg_chars:,}자")
            print(f"📊 총 본문 길이: {total_chars:,}자")
            return news_data
        else:
            print("❌ 추출된 뉴스 데이터가 없습니다.")
            return []

    except Exception as e:
        print(f"❌ RSS 파싱 중 오류 발생: {e}")
        return []


def parse_donga_category_rss_full(category="total", max_articles=None):
    """특정 카테고리의 동아일보 RSS에서 전체 본문을 추출하는 함수"""

    category_urls = {
        "total": "https://rss.donga.com/total.xml",
        "politics": "https://rss.donga.com/politics.xml",
        "national": "https://rss.donga.com/national.xml",
        "economy": "https://rss.donga.com/economy.xml",
        "international": "https://rss.donga.com/international.xml",
    }

    if category not in category_urls:
        print(f"❌ 지원하지 않는 카테고리입니다.")
        print(f"✅ 지원 카테고리: {', '.join(category_urls.keys())}")
        return None

    print(f"📰 {category} 카테고리 뉴스를 수집합니다.")

    # 전역 변수 수정하여 특정 카테고리 URL 사용
    global rss_url
    original_url = "https://rss.donga.com/total.xml"

    # 함수 내에서 URL 변경
    import types

    def modified_parse():
        # parse_donga_rss_full_content 함수의 rss_url을 임시 변경
        func_code = parse_donga_rss_full_content.__code__
        func_globals = parse_donga_rss_full_content.__globals__.copy()

        # 새로운 함수 생성 (카테고리 URL 사용)
        def category_parse():
            rss_url = category_urls[category]

            try:
                print(f"📡 {category} RSS 피드를 가져오는 중...")
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }

                response = requests.get(rss_url, headers=headers, timeout=30)
                response.raise_for_status()
                response.encoding = "utf-8"

                root = ET.fromstring(response.content)
                items = root.findall(".//item")

                # 최대 기사 수 제한
                if max_articles and len(items) > max_articles:
                    items = items[:max_articles]
                    print(f"⚠️  최대 {max_articles}개 기사로 제한합니다.")

                news_data = []
                print(f"총 {len(items)}개의 뉴스 항목을 발견했습니다.")
                print("각 기사의 전체 본문을 추출하는 중...")

                for i, item in enumerate(items):
                    try:
                        title = item.find("title").text if item.find("title") is not None else "제목 없음"
                        title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", title)
                        title = re.sub(r"<[^>]+>", "", title).strip()

                        pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                        formatted_date = ""
                        if pub_date:
                            try:
                                date_obj = datetime.strptime(pub_date.split(" +")[0], "%a, %d %b %Y %H:%M:%S")
                                formatted_date = date_obj.strftime("%Y-%m-%d %H:%M:%S")
                            except:
                                formatted_date = pub_date

                        link = item.find("link").text if item.find("link") is not None else ""

                        print(f"[{i+1}/{len(items)}] 처리 중: {title[:60]}...")

                        if link:
                            try:
                                full_content = extract_full_article_content(link)

                                article_response = requests.get(link, headers=headers, timeout=20)
                                soup = BeautifulSoup(article_response.text, "html.parser")
                                reporter_name = extract_reporter_name(soup, full_content)

                                if len(full_content) < 200:
                                    rss_description = (
                                        item.find("description").text if item.find("description") is not None else ""
                                    )
                                    rss_description = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", rss_description)
                                    rss_description = re.sub(r"<[^>]+>", "", rss_description).strip()

                                    if rss_description:
                                        full_content = (
                                            rss_description + "\n\n" + full_content if full_content else rss_description
                                        )

                                news_data.append(
                                    {
                                        "언론사": "동아일보",
                                        "제목": title,
                                        "날짜": formatted_date,
                                        "카테고리": category,
                                        "기자명": reporter_name,
                                        "본문": full_content,
                                    }
                                )

                                time.sleep(1)

                            except Exception as e:
                                print(f"  ➤ 기사 처리 중 오류: {e}")
                                continue

                    except Exception as e:
                        print(f"RSS 항목 처리 중 오류: {e}")
                        continue

                # CSV 저장 대신 데이터 반환
                if news_data:
                    print(f"\n✅ 성공적으로 {len(news_data)}개의 {category} 뉴스를 수집했습니다!")

                    total_chars = sum(len(item["본문"]) for item in news_data)
                    avg_chars = total_chars // len(news_data) if news_data else 0
                    print(f"📊 평균 본문 길이: {avg_chars:,}자")

                    return news_data
                else:
                    print("❌ 추출된 뉴스 데이터가 없습니다.")
                    return []

            except Exception as e:
                print(f"❌ RSS 파싱 중 오류 발생: {e}")
                return []

        return category_parse()

    return modified_parse()


# 새 함수: 수집된 뉴스 데이터를 CSV로 저장하는 함수
def save_news_csv(news_data):
    """언론사, 제목, 날짜, 카테고리, 기자명, 본문 순으로 뉴스 데이터를 CSV 파일로 저장하는 함수"""
    import os
    from datetime import datetime

    # results 폴더가 없으면 생성
    if not os.path.exists("results"):
        os.makedirs("results")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"results/동아일보_전체_{timestamp}.csv"
    fieldnames = ["언론사", "제목", "날짜", "카테고리", "기자명", "본문"]

    with open(filename, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in news_data:
            # 각 열의 순서를 보장하며 row 데이터 저장
            writer.writerow(
                {
                    "언론사": row.get("언론사", ""),
                    "제목": row.get("제목", ""),
                    "날짜": row.get("날짜", ""),
                    "카테고리": row.get("카테고리", ""),
                    "기자명": row.get("기자명", ""),
                    "본문": row.get("본문", ""),
                }
            )

    print(f"📁 파일명: {filename}")
    return filename


if __name__ == "__main__":
    print("🗞️  동아일보 RSS 전체 본문 크롤링 (모든 카테고리)")
    print("=" * 60)

    try:
        # 모든 카테고리 수집
        categories = ["total", "politics", "national", "economy", "international"]
        all_news_data = []

        for category in categories:
            print(f"\n🚀 {category} 카테고리 뉴스 수집을 시작합니다... (최대 20개)")

            if category == "total":
                news_data = parse_donga_rss_full_content(max_articles=20)
            else:
                news_data = parse_donga_category_rss_full(category, max_articles=20)

            if news_data:
                # 카테고리 정보 업데이트
                for item in news_data:
                    item["카테고리"] = category
                all_news_data.extend(news_data)
                print(f"✅ {category} 카테고리: {len(news_data)}개 기사 수집 완료")
            else:
                print(f"❌ {category} 카테고리: 수집된 뉴스가 없습니다.")

        if all_news_data:
            saved_file = save_news_csv(all_news_data)
            print(f"\n🎉 완료! 총 {len(all_news_data)}개 기사 CSV 파일 저장: {saved_file}")
        else:
            print("❌ 수집된 뉴스 데이터가 없습니다.")

    except KeyboardInterrupt:
        print("\n\n⚠️  사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
