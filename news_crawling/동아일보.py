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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 동아일보 기사 본문 추출 (다양한 선택자 시도)
        content_selectors = [
            'div.article_txt',           # 주요 본문 영역
            'div[data-article-body]',    # 본문 데이터 속성
            'div.news_view',             # 뉴스 뷰 영역
            'div.article-body',          # 기사 본문
            'div.view_txt',              # 본문 텍스트
            '.article_view .txt',        # 기사 뷰 텍스트
            '#article_txt',              # ID로 지정된 본문
            'div.news_txt_area',         # 뉴스 텍스트 영역
            'section.news_view',         # 섹션 뉴스 뷰
            'div.article_content'        # 기사 컨텐츠
        ]
        
        full_content = ""
        
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    # 불필요한 요소들 제거
                    for unwanted in element.find_all(['script', 'style', 'iframe', 'ins', 'div.ad', '.advertisement', '.related-articles']):
                        unwanted.decompose()
                    
                    # 텍스트 추출
                    text = element.get_text(separator='\n', strip=True)
                    if text and len(text) > len(full_content):
                        full_content = text
                        break
                
                if full_content:
                    break
        
        # 본문이 여전히 짧다면 다른 방법으로 시도
        if len(full_content) < 100:
            # p 태그들로 본문 구성 시도
            paragraphs = soup.find_all('p')
            paragraph_texts = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 20:  # 너무 짧은 텍스트는 제외
                    paragraph_texts.append(text)
            
            if paragraph_texts:
                candidate_content = '\n'.join(paragraph_texts)
                if len(candidate_content) > len(full_content):
                    full_content = candidate_content
        
        # 텍스트 정리
        if full_content:
            # 연속된 공백과 줄바꿈 정리
            full_content = re.sub(r'\n+', '\n', full_content)
            full_content = re.sub(r'\s+', ' ', full_content)
            full_content = full_content.strip()
        
        return full_content
        
    except Exception as e:
        print(f"본문 추출 중 오류: {e}")
        return ""

def extract_reporter_name(soup, article_text):
    """기자명을 추출하는 함수"""
    try:
        # 다양한 기자명 추출 패턴
        reporter_patterns = [
            # HTML에서 기자명 추출
            r'<span[^>]*class[^>]*reporter[^>]*>([^<]+)</span>',
            r'<div[^>]*class[^>]*reporter[^>]*>([^<]+)</div>',
            r'<p[^>]*class[^>]*reporter[^>]*>([^<]+)</p>',
            
            # 텍스트에서 기자명 추출
            r'([가-힣]{2,4})\s*기자(?:\s*=|\s*∙|\s*·|\s*입력|\s*수정|\s*작성)',
            r'기자\s*([가-힣]{2,4})(?:\s*=|\s*∙|\s*·)',
            r'([가-힣]{2,4})\s*특파원',
            r'([가-힣]{2,4})\s*논설위원',
            r'([가-힣]{2,4})\s*선임기자',
            r'([가-힣]{2,4})\s*편집위원',
            r'/\s*([가-힣]{2,4})\s*기자',
            r'=\s*([가-힣]{2,4})\s*기자',
            r'∙\s*([가-힣]{2,4})\s*기자',
            r'·\s*([가-힣]{2,4})\s*기자'
        ]
        
        # BeautifulSoup 객체에서 기자명 찾기
        if soup:
            reporter_elements = soup.find_all(['span', 'div', 'p'], class_=re.compile(r'reporter|writer|author'))
            for element in reporter_elements:
                text = element.get_text(strip=True)
                if '기자' in text:
                    match = re.search(r'([가-힣]{2,4})', text)
                    if match:
                        return match.group(1) + ' 기자'
        
        # 기사 텍스트에서 기자명 찾기
        full_text = str(soup) + '\n' + article_text if soup else article_text
        
        for pattern in reporter_patterns:
            matches = re.findall(pattern, full_text)
            if matches:
                reporter = matches[0].strip()
                if reporter and len(reporter) >= 2:
                    return reporter + (' 기자' if '기자' not in reporter else '')
        
        return "기자명 없음"
        
    except Exception as e:
        print(f"기자명 추출 중 오류: {e}")
        return "기자명 없음"

def parse_donga_rss_full_content():
    """동아일보 RSS를 파싱하여 전체 본문과 함께 CSV로 저장하는 함수"""
    
    rss_url = "https://rss.donga.com/total.xml"
    
    try:
        print("동아일보 RSS 피드를 가져오는 중...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(rss_url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        # XML 파싱
        root = ET.fromstring(response.content)
        items = root.findall('.//item')
        news_data = []
        
        print(f"총 {len(items)}개의 뉴스 항목을 발견했습니다.")
        print("각 기사의 전체 본문을 추출하는 중... (시간이 소요될 수 있습니다)")
        
        for i, item in enumerate(items):
            try:
                # 기본 정보 추출
                title = item.find('title').text if item.find('title') is not None else "제목 없음"
                title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                title = re.sub(r'<[^>]+>', '', title).strip()
                
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
                
                # 날짜 포맷 변환
                formatted_date = ""
                if pub_date:
                    try:
                        date_obj = datetime.strptime(pub_date.split(' +')[0], '%a, %d %b %Y %H:%M:%S')
                        formatted_date = date_obj.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        formatted_date = pub_date
                
                link = item.find('link').text if item.find('link') is not None else ""
                
                print(f"[{i+1}/{len(items)}] 처리 중: {title[:80]}...")
                
                if link:
                    # 전체 본문 추출
                    try:
                        article_response = requests.get(link, headers=headers, timeout=20)
                        article_response.encoding = 'utf-8'
                        soup = BeautifulSoup(article_response.text, 'html.parser')
                        
                        # 전체 본문 추출
                        full_content = extract_full_article_content(link)
                        
                        # 기자명 추출
                        reporter_name = extract_reporter_name(soup, full_content)
                        
                        # 본문이 너무 짧은 경우 RSS description도 포함
                        if len(full_content) < 200:
                            rss_description = item.find('description').text if item.find('description') is not None else ""
                            rss_description = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', rss_description)
                            rss_description = re.sub(r'<[^>]+>', '', rss_description).strip()
                            
                            if rss_description:
                                full_content = rss_description + '\n\n' + full_content if full_content else rss_description
                        
                        # 데이터 저장
                        news_data.append({
                            '제목': title,
                            '날짜': formatted_date,
                            '기자명': reporter_name,
                            '본문': full_content
                        })
                        
                        # 서버 부하 방지
                        time.sleep(1)
                        
                    except Exception as e:
                        print(f"  ➤ 기사 처리 중 오류: {e}")
                        # 오류가 발생해도 RSS 기본 정보는 저장
                        description = item.find('description').text if item.find('description') is not None else ""
                        description = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', description)
                        description = re.sub(r'<[^>]+>', '', description).strip()
                        
                        news_data.append({
                            '제목': title,
                            '날짜': formatted_date,
                            '기자명': "기자명 없음",
                            '본문': description
                        })
                        continue
                
            except Exception as e:
                print(f"RSS 항목 처리 중 오류: {e}")
                continue
        
        # CSV 파일로 저장
        if news_data:
            filename = f"동아일보_전체본문_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = ['제목', '날짜', '기자명', '본문']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                writer.writerows(news_data)
            
            print(f"\n✅ 성공적으로 {len(news_data)}개의 뉴스를 저장했습니다!")
            print(f"📁 파일명: {filename}")
            
            # 통계 정보 출력
            total_chars = sum(len(item['본문']) for item in news_data)
            avg_chars = total_chars // len(news_data) if news_data else 0
            print(f"📊 평균 본문 길이: {avg_chars:,}자")
            print(f"📊 총 본문 길이: {total_chars:,}자")
            
            return filename
        else:
            print("❌ 추출된 뉴스 데이터가 없습니다.")
            return None
            
    except Exception as e:
        print(f"❌ RSS 파싱 중 오류 발생: {e}")
        return None

def parse_donga_category_rss_full(category='total', max_articles=None):
    """특정 카테고리의 동아일보 RSS에서 전체 본문을 추출하는 함수"""
    
    category_urls = {
        'total': 'https://rss.donga.com/total.xml',
        'politics': 'https://rss.donga.com/politics.xml',
        'national': 'https://rss.donga.com/national.xml',
        'economy': 'https://rss.donga.com/economy.xml',
        'international': 'https://rss.donga.com/international.xml',
        'culture': 'https://rss.donga.com/culture.xml',
        'sports': 'https://rss.donga.com/sports.xml'
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
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                
                response = requests.get(rss_url, headers=headers, timeout=30)
                response.raise_for_status()
                response.encoding = 'utf-8'
                
                root = ET.fromstring(response.content)
                items = root.findall('.//item')
                
                # 최대 기사 수 제한
                if max_articles and len(items) > max_articles:
                    items = items[:max_articles]
                    print(f"⚠️  최대 {max_articles}개 기사로 제한합니다.")
                
                news_data = []
                print(f"총 {len(items)}개의 뉴스 항목을 발견했습니다.")
                print("각 기사의 전체 본문을 추출하는 중...")
                
                for i, item in enumerate(items):
                    try:
                        title = item.find('title').text if item.find('title') is not None else "제목 없음"
                        title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                        title = re.sub(r'<[^>]+>', '', title).strip()
                        
                        pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
                        formatted_date = ""
                        if pub_date:
                            try:
                                date_obj = datetime.strptime(pub_date.split(' +')[0], '%a, %d %b %Y %H:%M:%S')
                                formatted_date = date_obj.strftime('%Y-%m-%d %H:%M:%S')
                            except:
                                formatted_date = pub_date
                        
                        link = item.find('link').text if item.find('link') is not None else ""
                        
                        print(f"[{i+1}/{len(items)}] 처리 중: {title[:60]}...")
                        
                        if link:
                            try:
                                full_content = extract_full_article_content(link)
                                
                                article_response = requests.get(link, headers=headers, timeout=20)
                                soup = BeautifulSoup(article_response.text, 'html.parser')
                                reporter_name = extract_reporter_name(soup, full_content)
                                
                                if len(full_content) < 200:
                                    rss_description = item.find('description').text if item.find('description') is not None else ""
                                    rss_description = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', rss_description)
                                    rss_description = re.sub(r'<[^>]+>', '', rss_description).strip()
                                    
                                    if rss_description:
                                        full_content = rss_description + '\n\n' + full_content if full_content else rss_description
                                
                                news_data.append({
                                    '제목': title,
                                    '날짜': formatted_date,
                                    '기자명': reporter_name,
                                    '본문': full_content
                                })
                                
                                time.sleep(1)
                                
                            except Exception as e:
                                print(f"  ➤ 기사 처리 중 오류: {e}")
                                continue
                    
                    except Exception as e:
                        print(f"RSS 항목 처리 중 오류: {e}")
                        continue
                
                # CSV 저장
                if news_data:
                    filename = f"동아일보_{category}_전체본문_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    
                    with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                        fieldnames = ['제목', '날짜', '기자명', '본문']
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(news_data)
                    
                    print(f"\n✅ 성공적으로 {len(news_data)}개의 {category} 뉴스를 저장했습니다!")
                    print(f"📁 파일명: {filename}")
                    
                    total_chars = sum(len(item['본문']) for item in news_data)
                    avg_chars = total_chars // len(news_data) if news_data else 0
                    print(f"📊 평균 본문 길이: {avg_chars:,}자")
                    
                    return filename
                else:
                    print("❌ 추출된 뉴스 데이터가 없습니다.")
                    return None
                    
            except Exception as e:
                print(f"❌ RSS 파싱 중 오류 발생: {e}")
                return None
        
        return category_parse()
    
    return modified_parse()

if __name__ == "__main__":
    print("🗞️  동아일보 RSS 전체 본문 크롤링")
    print("=" * 60)
    
    # 사용자 선택
    print("\n📋 옵션을 선택하세요:")
    print("1. 전체 뉴스 (전체 본문 추출)")
    print("2. 특정 카테고리 뉴스")
    print("3. 빠른 테스트 (최대 5개 기사)")
    
    try:
        choice = input("\n선택 (1-3): ").strip()
        
        if choice == "1":
            print("\n🚀 전체 뉴스 수집을 시작합니다...")
            result = parse_donga_rss_full_content()
            
        elif choice == "2":
            print("\n📂 카테고리를 선택하세요:")
            categories = ['total', 'politics', 'national', 'economy', 'international', 'culture', 'sports']
            for i, cat in enumerate(categories, 1):
                print(f"{i}. {cat}")
            
            cat_choice = input("\n카테고리 번호 또는 이름: ").strip()
            
            if cat_choice.isdigit() and 1 <= int(cat_choice) <= len(categories):
                selected_category = categories[int(cat_choice) - 1]
            elif cat_choice in categories:
                selected_category = cat_choice
            else:
                selected_category = 'total'
                print("⚠️  잘못된 선택입니다. 전체 뉴스로 진행합니다.")
            
            print(f"\n🚀 {selected_category} 카테고리 뉴스 수집을 시작합니다...")
            result = parse_donga_category_rss_full(selected_category)
            
        elif choice == "3":
            print("\n🚀 테스트 모드 (최대 5개 기사)로 시작합니다...")
            result = parse_donga_category_rss_full('total', max_articles=5)
            
        else:
            print("⚠️  잘못된 선택입니다. 전체 뉴스로 진행합니다.")
            result = parse_donga_rss_full_content()
        
        if result:
            print(f"\n🎉 완료! 파일이 저장되었습니다: {result}")
        else:
            print("\n❌ 작업이 실패했습니다.")
            
    except KeyboardInterrupt:
        print("\n\n⚠️  사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
