import os
import sys
import requests
import subprocess
from PySide6.QtWidgets import QMessageBox  # PyQt6 -> PySide6
from packaging import version  # version 비교를 위한 모듈 추가

GITHUB_API_URL = "https://api.github.com/repos/byeonggonkang/XjeraTerm/releases/latest"
CURRENT_VERSION = "v5.0.4"

def check_for_updates():
    try:
        # GitHub에서 최신 릴리스 정보 가져오기
        response = requests.get(GITHUB_API_URL)
        response.raise_for_status()
        release_info = response.json()

        latest_version = release_info['tag_name']  # 최신 릴리스 태그 (예: v1.0.2)
        
        # 버전 비교 (v2.0.1과 v2.0.0이 올바르게 비교되도록)
        if version.parse(latest_version.lstrip('v')) > version.parse(CURRENT_VERSION.lstrip('v')):
            # 최신 EXE 파일 URL 가져오기
            for asset in release_info['assets']:
                if asset['name'].endswith(".exe"):
                    download_url = asset['browser_download_url']
                    prompt_update(latest_version, download_url)
                    return True
                else:
                    return False
    except Exception as e:
        print(f"Error checking for updates: {e}")

def prompt_update(latest_version, download_url):
    message = f"A new version {latest_version} is available. Do you want to update?"
    reply = QMessageBox.question(None, "Update Available", message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)  # PySide6 호환
    if reply == QMessageBox.StandardButton.Yes:  # PySide6 호환
        download_and_install_update(download_url, latest_version)  # latest_version 추가

def download_and_install_update(download_url, latest_version):
    try:
        # 태그 이름 기반으로 새 EXE 경로 설정
        exe_filename = "XjeraTermInstaller.exe"
        new_exe_path = os.path.join(os.path.dirname(sys.executable), exe_filename)

        # EXE 파일 다운로드
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        with open(new_exe_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        # 업데이트 완료 메시지 표시
        QMessageBox.information(
            None,
            "Installer Download Complete",
            f"downloaded successfully.\n"
            f"The new file will now be executed:\n{new_exe_path}",
        )

        # 새 EXE 파일 실행
        subprocess.Popen([new_exe_path], close_fds=True)

        # 현재 프로그램 종료
        sys.exit(0)

    except Exception as e:
        QMessageBox.critical(None, "Download Failed", f"An error occurred while downloading: {e}")
