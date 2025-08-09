import os
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import shutil
import re
from webdriver_manager.chrome import ChromeDriverManager


class UijeongbuPolicyDownloader:
    def __init__(self, download_dir="uijeongbu_policies", show_browser=True, max_files=None):
        self.url = "https://www.ui4u.go.kr/mayor/contents.do?mId=0203020300"
        self.download_dir = os.path.abspath(download_dir)
        self.show_browser = show_browser
        self.max_files = max_files

        # 10개 정책목표 카테고리
        self.categories = {
            "1": "1_아이가_행복한_도시",
            "2": "2_어르신이_행복한_도시",
            "3": "3_청년이_바꾸는_도시",
            "4": "4_장애인이_행복한_도시",
            "5": "5_교통이_편리한_도시",
            "6": "6_문화를_향유하는_도시",
            "7": "7_삶의_질이_높은_도시",
            "8": "8_일자리가_풍부한_도시",
            "9": "9_체육복지가_실현되는_도시",
            "10": "10_지구와_함께_공존하는_도시",
        }

        self.downloaded_files = []
        self.failed_downloads = []

        self._setup_logging()
        self._create_directories()

    def _setup_logging(self):
        """로깅 설정"""
        log_file = os.path.join(self.download_dir, f"download_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
        )
        self.logger = logging.getLogger(__name__)

    def _create_directories(self):
        """디렉토리 구조 생성"""
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

        for folder_name in self.categories.values():
            folder_path = os.path.join(self.download_dir, folder_name)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)

    def _setup_webdriver(self):
        """Chrome WebDriver 설정"""
        try:
            chrome_options = Options()

            prefs = {
                "download.default_directory": self.download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0,
                "profile.default_content_setting_values.automatic_downloads": 1,
            }
            chrome_options.add_experimental_option("prefs", prefs)

            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")
            chrome_options.add_argument("--disable-popup-blocking")

            if not self.show_browser:
                chrome_options.add_argument("--headless")

            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)

            driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": self.download_dir})

            return driver

        except Exception as e:
            self.logger.error(f"WebDriver 설정 실패: {e}")
            raise

    def _handle_download_permission_popup(self, driver):
        """다운로드 권한 팝업 자동 처리"""
        try:
            driver.execute_script(
                """
                if (window.confirm) {
                    window.confirm = function() { return true; };
                }
                if (window.alert) {
                    window.alert = function() { return true; };
                }
            """
            )
        except:
            pass

    def _scroll_and_load_content(self, driver):
        """페이지 스크롤하여 모든 콘텐츠 로드"""
        try:
            self.logger.info("페이지 스크롤 시작...")

            # 여러 번 스크롤해서 모든 콘텐츠 로드
            for i in range(5):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)

            self.logger.info("스크롤 완료")

        except Exception as e:
            self.logger.error(f"스크롤 실패: {e}")

    def _extract_download_links(self, driver):
        """단순화된 다운로드 링크 추출 - 모든 goFile 링크 처리"""
        try:
            self.logger.info("다운로드 링크 추출 중...")

            # 페이지 HTML 저장 (디버그용)
            with open(os.path.join(self.download_dir, "page_source.html"), "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            self.logger.info("페이지 소스 저장: page_source.html")

            soup = BeautifulSoup(driver.page_source, "html.parser")

            # 모든 goFile 링크를 찾아서 단순 처리
            all_gofile_links = soup.find_all("a", onclick=re.compile(r"goFile\("))
            self.logger.info(f"발견된 goFile 링크: {len(all_gofile_links)}개")

            if not all_gofile_links:
                self.logger.error("goFile 링크를 찾을 수 없습니다!")
                return []

            download_data = []

            for idx, link in enumerate(all_gofile_links):
                try:
                    onclick = link.get("onclick", "")
                    link_text = link.get_text(strip=True)

                    # goFile 함수 파라미터 추출
                    match = re.search(r"goFile\('([^']+)',\s*'([^']+)'(?:,\s*'([^']*)')?\)", onclick)
                    if not match:
                        self.logger.debug(f"goFile 파라미터 추출 실패: {onclick}")
                        continue

                    filename = match.group(1)
                    filepath = match.group(2)

                    # 파일명에서 정책번호 추출 (파일명이 "1-1.pdf" 같은 형식인 경우)
                    policy_number = "1"  # 기본값
                    policy_match = re.search(r"^(\d+)", filename)
                    if policy_match:
                        policy_number = policy_match.group(1)

                    # 링크 주변 텍스트에서 정책번호 찾기
                    parent_element = link.parent
                    context_text = ""
                    for _ in range(5):  # 5단계까지 상위 요소 확인
                        if parent_element:
                            context_text += " " + parent_element.get_text()
                            parent_element = parent_element.parent
                        else:
                            break

                    # 컨텍스트에서 정책번호 추출
                    context_policy_match = re.search(r"(\d+)\s*[\w가-힣]*\s*도시", context_text)
                    if context_policy_match:
                        policy_number = context_policy_match.group(1)

                    # 카테고리 결정
                    category = self.categories.get(policy_number, f"정책_{policy_number}")

                    # 문서 타입 추정 (링크 텍스트나 파일명으로)
                    doc_type = "문서"
                    if "카드" in link_text or "card" in filename.lower() or "card" in link_text.lower():
                        doc_type = "공약카드"
                    elif "계획" in link_text or "plan" in filename.lower():
                        doc_type = "실천계획서"
                    else:
                        # 순서로 추정 (짝수는 공약카드, 홀수는 실천계획서)
                        doc_type = "공약카드" if idx % 2 == 1 else "실천계획서"

                    # 사업명 추정 (링크 주변 텍스트에서)
                    business_name = f"정책사업_{idx+1:03d}"

                    # 주변 텍스트에서 사업명 추출 시도
                    business_match = re.search(r"(\d+\.?\s*[가-힣\s]{5,50})", context_text)
                    if business_match:
                        business_name = business_match.group(1).strip()[:50]

                    download_data.append(
                        {
                            "filename": filename,
                            "filepath": filepath,
                            "category": category,
                            "policy_number": policy_number,
                            "business_name": business_name,
                            "department": "담당부서",
                            "doc_type": doc_type,
                            "onclick": onclick,
                            "link_text": link_text,
                            "index": idx + 1,
                        }
                    )

                    self.logger.debug(f"추가: [{policy_number}] {business_name} ({doc_type}) - {filename}")

                except Exception as e:
                    self.logger.warning(f"링크 {idx+1} 처리 중 오류: {e}")
                    continue

            self.logger.info(f"추출 완료: {len(download_data)}개")

            # 문서 타입별 통계
            doc_stats = {}
            for item in download_data:
                doc_type = item["doc_type"]
                doc_stats[doc_type] = doc_stats.get(doc_type, 0) + 1

            self.logger.info("문서 타입별 통계:")
            for doc_type, count in doc_stats.items():
                self.logger.info(f"  {doc_type}: {count}개")

            # max_files 제한 적용
            if self.max_files and len(download_data) > self.max_files:
                download_data = download_data[: self.max_files]
                self.logger.info(f"최대 파일 수 제한 적용: {self.max_files}개")

            return download_data

        except Exception as e:
            self.logger.error(f"링크 추출 실패: {e}")
            return []

    def _download_file(self, driver, download_info, file_index):
        """개별 파일 다운로드"""
        try:
            filename = download_info["filename"]
            doc_type = download_info["doc_type"]
            business_name = download_info["business_name"]

            self.logger.info(f"다운로드 시작: [{download_info['policy_number']}] {business_name} ({doc_type})")

            # 다운로드 전 파일 목록
            before_files = set(os.listdir(self.download_dir))

            # 첫 번째 파일 다운로드 시 권한 처리
            if file_index == 1:
                self.logger.info("첫 번째 파일 다운로드 - 권한 설정 중...")
                self._handle_download_permission_popup(driver)

            # JavaScript 실행
            js_script = f"goFile('{download_info['filename']}', '{download_info['filepath']}')"
            self.logger.debug(f"JavaScript 실행: {js_script}")
            driver.execute_script(js_script)

            # 첫 번째 다운로드 후 권한 팝업 처리
            if file_index == 1:
                time.sleep(3)
                self._handle_download_permission_popup(driver)

            # 다운로드 완료 대기
            max_wait = 30
            wait_time = 0

            while wait_time < max_wait:
                time.sleep(2)
                wait_time += 2

                try:
                    current_files = set(os.listdir(self.download_dir))
                    new_files = current_files - before_files

                    pdf_files = [f for f in new_files if f.endswith(".pdf")]
                    if pdf_files:
                        downloaded_file = pdf_files[0]
                        src_path = os.path.join(self.download_dir, downloaded_file)

                        if os.path.exists(src_path) and os.path.getsize(src_path) > 0:
                            time.sleep(1)

                            # 파일을 카테고리 폴더로 이동 (원본 파일명 유지)
                            category_folder = os.path.join(self.download_dir, download_info["category"])
                            dst_path = os.path.join(category_folder, downloaded_file)

                            # 중복 파일명 처리 (원본 파일명 기준)
                            counter = 1
                            while os.path.exists(dst_path):
                                name, ext = os.path.splitext(downloaded_file)
                                new_filename = f"{name}_{counter}{ext}"
                                dst_path = os.path.join(category_folder, new_filename)
                                counter += 1
                            else:
                                new_filename = downloaded_file

                            shutil.move(src_path, dst_path)

                            self.downloaded_files.append(
                                {
                                    "filename": new_filename,
                                    "original_filename": downloaded_file,
                                    "category": download_info["category"],
                                    "business_name": business_name,
                                    "doc_type": doc_type,
                                    "policy_number": download_info["policy_number"],
                                    "path": dst_path,
                                }
                            )

                            self.logger.info(f"다운로드 완료: {new_filename}")
                            return True
                except Exception as e:
                    self.logger.debug(f"다운로드 체크 중 오류: {e}")

                # 두 번째 파일부터는 권한 팝업 재처리
                if file_index == 2:
                    self._handle_download_permission_popup(driver)

            self.logger.warning(f"다운로드 타임아웃: [{download_info['policy_number']}] {business_name} ({doc_type})")
            self.failed_downloads.append(
                {
                    "filename": filename,
                    "business_name": business_name,
                    "doc_type": doc_type,
                    "error": "다운로드 타임아웃",
                }
            )
            return False

        except Exception as e:
            error_msg = (
                f"다운로드 실패: [{download_info.get('policy_number', '?')}] {business_name} ({doc_type}) - {str(e)}"
            )
            self.logger.error(error_msg)
            self.failed_downloads.append(
                {
                    "filename": download_info["filename"],
                    "business_name": download_info.get("business_name", "Unknown"),
                    "doc_type": download_info.get("doc_type", "Unknown"),
                    "error": str(e),
                }
            )
            return False

    def _generate_report(self):
        """결과 보고서 생성"""
        try:
            report_file = os.path.join(self.download_dir, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

            # 통계 계산
            category_stats = {}
            doc_type_stats = {}

            for file_info in self.downloaded_files:
                category = file_info["category"]
                doc_type = file_info["doc_type"]

                if category not in category_stats:
                    category_stats[category] = []
                category_stats[category].append(file_info)

                doc_type_stats[doc_type] = doc_type_stats.get(doc_type, 0) + 1

            with open(report_file, "w", encoding="utf-8") as f:
                f.write("의정부시 정책 문서 다운로드 결과\n")
                f.write("=" * 60 + "\n")
                f.write(f"실행 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"총 성공: {len(self.downloaded_files)}개\n")
                f.write(f"총 실패: {len(self.failed_downloads)}개\n\n")

                f.write("문서 타입별 통계:\n")
                for doc_type, count in doc_type_stats.items():
                    f.write(f"  {doc_type}: {count}개\n")
                f.write("\n")

                f.write("카테고리별 다운로드 현황:\n")
                f.write("-" * 50 + "\n")
                for category, files in category_stats.items():
                    f.write(f"{category}: {len(files)}개\n")
                    for file_info in files:
                        f.write(f"  - {file_info['filename']}\n")
                f.write("\n")

                if self.failed_downloads:
                    f.write("실패한 파일:\n")
                    f.write("-" * 30 + "\n")
                    for failed in self.failed_downloads:
                        f.write(
                            f"- {failed.get('business_name', 'Unknown')} ({failed.get('doc_type', 'Unknown')}): {failed['error']}\n"
                        )

            self.logger.info(f"보고서 생성: {report_file}")

        except Exception as e:
            self.logger.error(f"보고서 생성 실패: {e}")

    def run(self):
        """메인 실행"""
        self.logger.info("=" * 60)
        self.logger.info("의정부시 정책 문서 자동 다운로드 시작")
        self.logger.info("🔧 단순화된 링크 추출 방식")
        self.logger.info("=" * 60)

        driver = None

        try:
            driver = self._setup_webdriver()

            self.logger.info(f"웹페이지 접속: {self.url}")
            driver.get(self.url)

            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # 페이지 로딩을 충분히 기다림
            time.sleep(5)

            self._scroll_and_load_content(driver)

            download_list = self._extract_download_links(driver)

            if not download_list:
                self.logger.error("다운로드할 파일이 없습니다.")
                self.logger.info("page_source.html 파일을 확인해서 실제 HTML 구조를 분석하세요.")
                return

            self.logger.info(f"총 {len(download_list)}개 파일 다운로드 시작")

            for i, download_info in enumerate(download_list, 1):
                success = self._download_file(driver, download_info, i)

                if success and i == 1:
                    self.logger.info("🎉 첫 번째 파일 다운로드 성공!")

                # 다운로드 간격
                time.sleep(1 if i > 2 else 3)

            # 최종 통계
            doc_stats = {}
            for item in self.downloaded_files:
                doc_type = item["doc_type"]
                doc_stats[doc_type] = doc_stats.get(doc_type, 0) + 1

            self.logger.info("=" * 60)
            self.logger.info("다운로드 완료!")
            self.logger.info(f"✅ 총 성공: {len(self.downloaded_files)}개")
            for doc_type, count in doc_stats.items():
                self.logger.info(f"   - {doc_type}: {count}개")
            self.logger.info(f"❌ 총 실패: {len(self.failed_downloads)}개")
            self.logger.info("=" * 60)

            self._generate_report()

        except Exception as e:
            self.logger.error(f"실행 중 오류: {e}")

        finally:
            if driver:
                driver.quit()


def main():
    print("🏛️ 의정부시 정책 문서 자동 다운로더")
    print("=" * 60)
    print("🔧 단순화된 링크 추출 방식")
    print("📋 모든 goFile 링크를 직접 처리")
    print()

    show_browser = input("브라우저 창을 표시하시겠습니까? (y/n, 기본값: y): ").lower().strip()
    show_browser = show_browser != "n"

    download_dir = input("다운로드 폴더명 (기본값: uijeongbu_policies): ").strip()
    if not download_dir:
        download_dir = "uijeongbu_policies"

    test_mode = input("테스트 모드로 실행하시겠습니까? (10개 파일만, y/n): ").lower().strip()
    max_files = 10 if test_mode == "y" else None

    print(f"\n🚀 다운로드를 시작합니다...")
    if max_files:
        print(f"📊 테스트 모드: 최대 {max_files}개 파일")
    else:
        print("📊 전체 모드: 모든 goFile 링크 처리")
    print("🔍 page_source.html 파일이 생성되어 디버깅에 활용됩니다")
    print("-" * 60)

    try:
        downloader = UijeongbuPolicyDownloader(
            download_dir=download_dir, show_browser=show_browser, max_files=max_files
        )
        downloader.run()

        print(f"\n🎉 다운로드 완료!")
        print(f"📂 결과 확인: '{download_dir}' 폴더")
        print("📊 상세 결과는 생성된 보고서 파일을 확인하세요")

    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 중단되었습니다.")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")


if __name__ == "__main__":
    main()
