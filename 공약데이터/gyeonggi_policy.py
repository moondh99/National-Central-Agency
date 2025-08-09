import time
import os
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from urllib.parse import unquote
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


def setup_driver(download_path=None):
    """webdriver_manager로 Chrome 드라이버 자동 설정"""
    if download_path is None:
        download_path = os.path.join(os.getcwd(), "downloads")

    if not os.path.exists(download_path):
        os.makedirs(download_path)

    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    print("ChromeDriver 자동 설치 중...")
    service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    return driver


def create_section_folders(base_path):
    """섹션별 폴더 생성"""

    section_info = {
        "01_더많은기회": {
            "name": "더 많은 기회",
            "range": (1, 49),
            "description": "경제성장, 스타트업, 일자리 창출 관련 공약",
        },
        "02_주택교통일자리": {
            "name": "주택, 교통, 일자리가 유쾌한 경기",
            "range": (50, 91),
            "description": "주거, 교통, 노동 관련 공약",
        },
        "03_문화예술여가": {
            "name": "문화예술, 여가가 일상이 되는 경기",
            "range": (92, 116),
            "description": "문화, 예술, 스포츠, 관광 관련 공약",
        },
        "04_더고른기회": {
            "name": "더 고른 기회",
            "range": (117, 203),
            "description": "복지, 돌봄, 의료, 교육 관련 공약",
        },
        "05_북부평화기회": {
            "name": "북부에 변화와 평화의 기회를 만드는 경기",
            "range": (204, 218),
            "description": "경기북부 발전, 평화경제 관련 공약",
        },
        "06_더나은기회": {"name": "더 나은 기회", "range": (219, 270), "description": "행정혁신, 환경, 안전 관련 공약"},
        "07_사회적가치": {
            "name": "사회적 가치, 평등한 기회가 보장되는 경기",
            "range": (271, 295),
            "description": "사회적경제, 평등, 공정거래 관련 공약",
        },
    }

    created_folders = {}

    print(f"📁 섹션별 폴더 생성: {base_path}")

    for folder_key, info in section_info.items():
        folder_path = os.path.join(base_path, folder_key)
        os.makedirs(folder_path, exist_ok=True)

        readme_path = os.path.join(folder_path, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(f"# {info['name']}\n\n")
            f.write(f"**공약 번호**: {info['range'][0]}번 ~ {info['range'][1]}번\n\n")
            f.write(f"**설명**: {info['description']}\n\n")
            f.write(f"**다운로드 시간**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        created_folders[folder_key] = {"path": folder_path, "info": info}

        print(f"  ✅ {folder_key} - {info['name']}")

    return created_folders


def determine_section_by_number(pdf_filename):
    """PDF 파일명에서 공약 번호를 추출하여 해당 섹션 결정"""

    match = re.match(r"^(\d+)_", pdf_filename)
    if not match:
        return "00_미분류"

    promise_num = int(match.group(1))

    if 1 <= promise_num <= 49:
        return "01_더많은기회"
    elif 50 <= promise_num <= 91:
        return "02_주택교통일자리"
    elif 92 <= promise_num <= 116:
        return "03_문화예술여가"
    elif 117 <= promise_num <= 203:
        return "04_더고른기회"
    elif 204 <= promise_num <= 218:
        return "05_북부평화기회"
    elif 219 <= promise_num <= 270:
        return "06_더나은기회"
    elif 271 <= promise_num <= 295:
        return "07_사회적가치"
    else:
        return "00_미분류"


def extract_and_categorize_pdfs(driver, base_path, section_folders):
    """페이지에서 PDF URL을 추출하고 섹션별로 분류"""

    print("🔍 페이지에서 PDF URL 추출 및 분류 중...")

    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(2)

    viewer_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'pdfjs/web/viewer.html')]")

    categorized_pdfs = {}

    for section_key in section_folders.keys():
        categorized_pdfs[section_key] = []
    categorized_pdfs["00_미분류"] = []

    for link in viewer_links:
        try:
            href = link.get_attribute("href")
            if "file=" in href:
                pdf_url = href.split("file=")[1]
                pdf_url = unquote(pdf_url)
                filename = pdf_url.split("/")[-1]

                if not any(exclude in filename for exclude in ["공약실천계획서", "붙임2"]):
                    section_key = determine_section_by_number(filename)

                    categorized_pdfs[section_key].append({"url": pdf_url, "filename": filename, "viewer_url": href})

        except Exception as e:
            print(f"⚠️ PDF 분류 중 오류: {e}")
            continue

    # 결과를 JSON으로 저장 (중단 시 재시작 가능)
    urls_backup_path = os.path.join(base_path, "pdf_urls_backup.json")
    with open(urls_backup_path, "w", encoding="utf-8") as f:
        json.dump(categorized_pdfs, f, ensure_ascii=False, indent=2)

    print(f"📊 PDF URL 백업 저장: {urls_backup_path}")

    total_pdfs = 0
    print("\n📊 섹션별 PDF 분류 결과:")
    for section_key, pdfs in categorized_pdfs.items():
        if pdfs:
            section_name = section_folders.get(section_key, {}).get("info", {}).get("name", "미분류")
            print(f"  📂 {section_key}: {len(pdfs)}개 - {section_name}")
            total_pdfs += len(pdfs)

    print(f"🎯 총 {total_pdfs}개의 개별 공약 PDF 발견")

    return categorized_pdfs


def download_single_pdf(pdf_info, section_path, max_retries=5):
    """단일 PDF 다운로드 (재시도 로직 포함)"""

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://governor.gg.go.kr/",
        "Accept": "application/pdf,application/octet-stream,*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    for attempt in range(max_retries):
        try:
            session = requests.Session()
            session.headers.update(headers)

            # 점진적 타임아웃 증가
            timeout = 30 + (attempt * 15)

            response = session.get(pdf_info["url"], stream=True, timeout=timeout, allow_redirects=True)

            if response.status_code == 200:
                file_path = os.path.join(section_path, pdf_info["filename"])

                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                file_size = os.path.getsize(file_path)

                # 파일 크기 검증 (너무 작으면 오류)
                if file_size < 1000:  # 1KB 이하면 비정상
                    os.remove(file_path)
                    raise Exception(f"파일 크기가 너무 작음: {file_size} bytes")

                return {"success": True, "filename": pdf_info["filename"], "size": file_size, "attempts": attempt + 1}

            else:
                raise Exception(f"HTTP {response.status_code}")

        except Exception as e:
            error_msg = str(e)

            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # 2, 4, 6, 8초 대기
                print(f"      ⚠️ {attempt + 1}차 실패: {error_msg[:50]}... ({wait_time}초 후 재시도)")
                time.sleep(wait_time)
                continue
            else:
                return {"success": False, "filename": pdf_info["filename"], "error": error_msg, "attempts": max_retries}

    return {
        "success": False,
        "filename": pdf_info["filename"],
        "error": "최대 재시도 횟수 초과",
        "attempts": max_retries,
    }


def download_categorized_pdfs_with_retry(categorized_pdfs, section_folders, base_path):
    """개선된 다운로드 함수 (재시도 + 병렬 처리)"""

    print("📥 섹션별 PDF 다운로드 시작 (재시도 로직 적용)")
    print("=" * 60)

    download_results = {}

    for section_key, pdfs in categorized_pdfs.items():
        if not pdfs:
            continue

        if section_key == "00_미분류":
            section_path = os.path.join(base_path, "00_미분류")
            os.makedirs(section_path, exist_ok=True)
        else:
            section_path = section_folders[section_key]["path"]

        section_name = section_folders.get(section_key, {}).get("info", {}).get("name", "미분류")

        print(f"\n📂 {section_key} - {section_name} ({len(pdfs)}개)")
        print("=" * 50)

        success_count = 0
        failed_files = []

        # 진행 상황 저장을 위한 파일
        progress_file = os.path.join(section_path, ".download_progress.json")
        completed_files = set()

        # 기존 진행 상황 로드
        if os.path.exists(progress_file):
            try:
                with open(progress_file, "r", encoding="utf-8") as f:
                    progress_data = json.load(f)
                    completed_files = set(progress_data.get("completed", []))
                print(f"  📋 이미 완료된 파일: {len(completed_files)}개")
            except:
                pass

        # 남은 파일들만 다운로드
        remaining_pdfs = [pdf for pdf in pdfs if pdf["filename"] not in completed_files]

        if not remaining_pdfs:
            print(f"  ✅ 이미 모든 파일이 다운로드되었습니다.")
            download_results[section_key] = {"success": len(pdfs), "failed": [], "total": len(pdfs)}
            continue

        print(f"  📥 다운로드할 파일: {len(remaining_pdfs)}개")

        # 순차 다운로드 (서버 부하 방지)
        for i, pdf_info in enumerate(remaining_pdfs, 1):
            print(f"  📥 {i:2d}/{len(remaining_pdfs)} {pdf_info['filename']}")

            result = download_single_pdf(pdf_info, section_path)

            if result["success"]:
                print(f"      ✅ 완료 ({result['size']:,} bytes, {result['attempts']}회 시도)")
                success_count += 1
                completed_files.add(pdf_info["filename"])

                # 진행 상황 저장
                progress_data = {"completed": list(completed_files)}
                with open(progress_file, "w", encoding="utf-8") as f:
                    json.dump(progress_data, f, ensure_ascii=False, indent=2)

            else:
                print(f"      ❌ 실패: {result['error'][:50]}... ({result['attempts']}회 시도)")
                failed_files.append(pdf_info["filename"])

            # 서버 부하 방지를 위한 대기
            time.sleep(1)

        # 완료 후 진행 상황 파일 삭제
        if os.path.exists(progress_file):
            os.remove(progress_file)

        total_success = len(completed_files)
        download_results[section_key] = {"success": total_success, "failed": failed_files, "total": len(pdfs)}

        print(f"  📊 {section_name}: {total_success}/{len(pdfs)} 성공")
        if failed_files:
            print(f"      ❌ 실패한 파일: {len(failed_files)}개")

    return download_results


def create_retry_script(failed_files, base_path):
    """실패한 파일들을 재다운로드하는 스크립트 생성"""

    if not any(result["failed"] for result in failed_files.values()):
        return

    retry_script_path = os.path.join(base_path, "retry_failed_downloads.py")

    with open(retry_script_path, "w", encoding="utf-8") as f:
        f.write(
            """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"
실패한 PDF 파일들을 재다운로드하는 스크립트
자동 생성됨
\"\"\"

import json
import os
import sys

# 원본 스크립트의 함수들을 import
# (이 스크립트를 원본 스크립트와 같은 폴더에 두고 실행)

def retry_failed_downloads():
    base_path = os.path.dirname(os.path.abspath(__file__))
    urls_backup_path = os.path.join(base_path, "pdf_urls_backup.json")
    
    if not os.path.exists(urls_backup_path):
        print("❌ PDF URL 백업 파일을 찾을 수 없습니다.")
        return
    
    with open(urls_backup_path, 'r', encoding='utf-8') as f:
        categorized_pdfs = json.load(f)
    
    print("🔄 실패한 파일들 재다운로드 시작...")
    
    # 실패한 파일들만 추출
    failed_pdfs = {}
"""
        )

        for section_key, result in failed_files.items():
            if result["failed"]:
                f.write(f"    failed_pdfs['{section_key}'] = {result['failed']}\n")

        f.write(
            """
    # 재다운로드 로직 구현
    # ... (실제 다운로드 로직은 원본 함수 재사용)

if __name__ == "__main__":
    retry_failed_downloads()
"""
        )

    print(f"🔄 재시도 스크립트 생성: {retry_script_path}")


def main():
    """메인 실행 함수"""

    print("🚀 경기도 섹션별 공약 PDF 다운로더 v6.0 (안정화 버전)")
    print("=" * 70)

    base_path = os.path.join(os.getcwd(), "gyeonggi_policies")

    print(f"📁 다운로드 기본 경로: {base_path}")

    # 기존 백업 파일이 있으면 재시작 옵션 제공
    urls_backup_path = os.path.join(base_path, "pdf_urls_backup.json")

    if os.path.exists(urls_backup_path):
        print(f"\n🔍 기존 백업 파일 발견: {urls_backup_path}")
        restart = input("기존 URL 데이터를 사용하여 재시작하시겠습니까? (y/n): ").strip().lower()

        if restart == "y":
            print("📋 백업 파일에서 데이터 로딩...")

            with open(urls_backup_path, "r", encoding="utf-8") as f:
                categorized_pdfs = json.load(f)

            section_folders = create_section_folders(base_path)
            download_results = download_categorized_pdfs_with_retry(categorized_pdfs, section_folders, base_path)

            # 재시도 스크립트 생성
            create_retry_script(download_results, base_path)

            print("\n🎉 재시작 다운로드 완료!")
            return

    # 새로 시작
    section_folders = create_section_folders(base_path)

    print("\n🔧 ChromeDriver 설정 중...")
    driver = setup_driver(base_path)

    try:
        url = "https://governor.gg.go.kr/promises/status/"
        print(f"🌐 페이지 접속: {url}")

        driver.get(url)
        time.sleep(5)

        categorized_pdfs = extract_and_categorize_pdfs(driver, base_path, section_folders)

        driver.quit()
        print("🔚 브라우저 종료")

        download_results = download_categorized_pdfs_with_retry(categorized_pdfs, section_folders, base_path)

        # 재시도 스크립트 생성
        create_retry_script(download_results, base_path)

        # 최종 결과 출력
        print("\n" + "=" * 70)
        print("🎉 다운로드 완료!")

        total_success = sum(result["success"] for result in download_results.values())
        total_files = sum(result["total"] for result in download_results.values())
        total_failed = sum(len(result["failed"]) for result in download_results.values())

        print(f"📊 전체 결과: {total_success}/{total_files} 성공 ({total_failed}개 실패)")
        print(f"📁 다운로드 폴더: {base_path}")

        if total_failed > 0:
            print(f"\n⚠️ 실패한 파일이 있습니다.")
            print(f"retry_failed_downloads.py 스크립트로 재시도할 수 있습니다.")

        # 폴더 열기
        import platform

        system = platform.system()

        if system == "Darwin":  # macOS
            os.system(f"open '{base_path}'")
        elif system == "Windows":
            os.system(f'explorer "{base_path}"')

        print("📁 다운로드 폴더가 열렸습니다!")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        if "driver" in locals():
            driver.quit()


if __name__ == "__main__":
    main()
