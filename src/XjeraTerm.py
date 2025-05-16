import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QVBoxLayout, QHBoxLayout, QWidget, QTextEdit, QLineEdit, QLabel, QSplitter, QFontDialog, QDialog, QFormLayout, QComboBox, QPushButton, QCheckBox, QGridLayout, QFileDialog, QMessageBox, QLCDNumber
from PySide6.QtGui import QFont, QIntValidator, QIcon, QFontDatabase, QAction, QTextCursor
from PySide6.QtCore import Qt, QThread, Signal, QTimer
import os
import serial
import serial.tools.list_ports
import re
from datetime import datetime
import subprocess
import updatemanager
import requests
import gittoken
import ctypes  # Windows API를 사용하기 위해 추가 # v2.0.4
from MCULOGDetectCanTrigger import MCULOGDetectCanTriggerDialog
import logging
from AlertFunc import AlertSettingsDialog
from mcu_infogenerator import MCUinfomationDialog
from ANSI_Escapecode import appendFormattedText
import webbrowser

# 디버그 로그 설정
log_file_path = os.path.join(os.getenv('TEMP'), 'XjeraTerm_debug.log')
logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

__version__ = updatemanager.CURRENT_VERSION

def resource_path(relative_path):
    """PyInstaller에서 리소스 경로를 찾는 함수"""
    try:
        # PyInstaller가 빌드한 실행 파일 내부에서 리소스를 찾음
        base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    except Exception as e:
        logging.error(f"Error in resource_path: {e}")
        # 개발 환경에서는 상대 경로로 파일을 찾음
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

class SerialReaderThread(QThread):
    
    data_received = Signal(str)
    disconnected = Signal()  # 연결 끊김 감지용 시그널 추가가

    def __init__(self, serialPort, processedData):
        super().__init__()
        self.serialPort = serialPort
        self.processedData = processedData  # processedData 인스턴스 변수 추가

    def run(self):
        while self.serialPort.is_open:
            try:
                if self.serialPort.in_waiting > 0:
                    try:
                        data = self.serialPort.read(self.serialPort.in_waiting).decode('utf-8', errors='ignore')
                        self.data_received.emit(data)
                        self.processedData.append(data.strip())  # 처리된 데이터를 리스트에 추가
                        if len(self.processedData) > 5:  # 리스트 길이 제한
                            self.processedData.pop(0)
                    except UnicodeDecodeError as e:
                        logging.error(f"UnicodeDecodeError in SerialReaderThread: {e}")
                        pass  # 디코딩 오류가 발생하면 해당 데이터를 무시하고 계속 진행
            except serial.SerialException as e:
                logging.error(f"SerialException in SerialReaderThread: {e}")
                self.serialPort.close()
                self.data_received.emit(f'Error: {e}')
                self.disconnected.emit()  # 연결 끊김 시그널 전송
                break
                

class FilteredDataWindow(QMainWindow):
    def __init__(self, filteredRxData, parent):
        super().__init__(parent)
        self.setWindowTitle('Filtered Rx Data')
        self.setGeometry(100, 100, 800, 600)
        self.filteredRxData = filteredRxData
        self.parent = parent
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        layout.addWidget(self.filteredRxData)
        centralWidget = QWidget()
        centralWidget.setLayout(layout)
        self.setCentralWidget(centralWidget)

    def closeEvent(self, event):
        try:
            self.parent.leftLayout.addWidget(self.filteredRxData)
        except Exception as e:
            logging.error(f"Error in FilteredDataWindow closeEvent: {e}")
        event.accept()

class MainWindow(QMainWindow):
    MAX_LINES = 80000  # 최대 라인 수 제한 ## v5.0.2 #v5.0.4
    REMOVE_LINES = 10000  # 제거할 라인 수 ## v5.0.2
    filteredRxDatacount_value = 0  # v5.0.3 특정 스트링 카운트 추가

    def __init__(self):
        super().__init__()
        logging.debug("Initializing MainWindow")
        self.filteredData = []  # filteredData 속성 추가
        self.processedData = []  # 처리된 데이터를 저장할 리스트
        icon_path = resource_path('XjeraTerm.ico')
        self.setWindowIcon(QIcon(icon_path))
        self.checkFirstRun()  # 첫 실행 여부 확인 및 업데이트 팝업 표시 # v2.0.5
        self.initUI()
        self.MCULOGDetectCanTriggerDialog = MCULOGDetectCanTriggerDialog(self)  # 인스턴스 초기화
        self.alertSettingsDialog = AlertSettingsDialog(self)  # 인스턴스 초기화
        self.MCUInformationDialog = None  # 인스턴스 초기화 제거
        self.canch_entry_value = None  # CAN Channel
        self.bustype_entry_value = None  # CAN Bus Type
        self.loadSettings()  # loadSettings를 initUI 이후에 호출
        self.connectSerialPort()
        self.buffer = ""  # 데이터 누적 버퍼
        self.userScrolled = False  # 사용자 스크롤 상태를 추적하는 플래그
        self.userScrolled_filter = False  # 사용자 스크롤 상태를 추적하는 플래그 #v4.0.3 
        self.txHistory = []  # 이전 입력 메시지 저장 리스트 #4.0.5 #1
        self.txHistoryIndex = -1  # 현재 선택된 히스토리 위치 (-1은 새 입력 상태) #4.0.5 #1
        self.rxData.verticalScrollBar().valueChanged.connect(self.handleScroll)
        self.filteredRxData.verticalScrollBar().valueChanged.connect(self.handleScroll_filter)  # 스크롤 이벤트 연결 #v4.0.3 
        self.check_updates_on_startup()  # 시작시 업데이트 확인
        ## git 정보 설정
        self.github_token = gittoken.token
        self.github_repo = gittoken.repo
        self.installEventFilter(self)  # 이벤트 필터 설치 #v2.0.3
        self.txInput.focusInEvent = self.setEnglishInputMode  # txInput에 포커스가 갈 때 입력 모드 변경 #v2.0.4

        
    def checkFirstRun(self): # v2.0.5 ~
        settings_path = os.path.join(os.path.dirname(sys.executable), 'env_set.txt')
        first_run = True
        
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r') as file:
                    settings = {}
                    for line in file:
                        key, value = line.strip().split('=', 1)
                        settings[key] = value
                        print(f'{key}={value}')
                    first_run = settings.get('Version') != updatemanager.CURRENT_VERSION
                    print(f'first_run {first_run}')
            except Exception as e:
                logging.error(f"Error in checkFirstRun: {e}")
                print(f"Error reading settings file: {e}")
                first_run = True
        
        if first_run:
            self.showVersionInfo() # ~ v2.0.5

    def check_updates_on_startup(self):
        try:
            QTimer.singleShot(1000, updatemanager.check_for_updates)  # 1초 후 업데이트 확인
        except Exception as e:
            logging.error(f"Error in check_updates_on_startup: {e}")

    def check_updates_on_manual(self):
        try:
            update_available = updatemanager.check_for_updates()
            if not update_available:
                QMessageBox.information(self, "업데이트 확인", "현 버전이 최신버전입니다.")
        except Exception as e:
            logging.error(f"Error in check_updates_on_manual: {e}")
    
    def showReportDialog(self):
        try:
            """Report Dialog 생성"""
            dialog = QDialog(self)
            dialog.setWindowTitle("Report an Issue")

            layout = QVBoxLayout(dialog)

            # Input 필드 추가
            issueTitleLabel = QLabel("Issue Title:")
            self.issueTitleInput = QLineEdit()
            layout.addWidget(issueTitleLabel)
            layout.addWidget(self.issueTitleInput)

            issueBodyLabel = QLabel("Issue Description:")
            self.issueBodyInput = QTextEdit()
            layout.addWidget(issueBodyLabel)
            layout.addWidget(self.issueBodyInput)

            # 버튼 추가
            buttonLayout = QHBoxLayout()
            sendButton = QPushButton("Send")
            sendButton.clicked.connect(lambda: self.sendGitHubIssue(dialog))
            cancelButton = QPushButton("Cancel")
            cancelButton.clicked.connect(dialog.reject)
            buttonLayout.addWidget(sendButton)
            buttonLayout.addWidget(cancelButton)

            layout.addLayout(buttonLayout)
            dialog.setLayout(layout)
            dialog.exec()
        except Exception as e:
            logging.error(f"Error in showReportDialog: {e}")

    def sendGitHubIssue(self, dialog):
        """GitHub Issue 전송"""
        issue_title = self.issueTitleInput.text()
        issue_body = self.issueBodyInput.toPlainText()

        if not issue_title.strip() or not issue_body.strip():
            QMessageBox.warning(self, "Warning", "Please fill in both the title and description.")
            return

        # GitHub Issue 생성 API 호출
        try:
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            data = {
                "title": issue_title,
                "body": issue_body
            }
            url = f"https://api.github.com/repos/{self.github_repo}/issues"
            response = requests.post(url, headers=headers, json=data)

            if response.status_code == 201:
                QMessageBox.information(self, "Success", "Your issue has been submitted!")
                dialog.accept()
            else:
                QMessageBox.critical(self, "Error", f"Failed to submit the issue.\n{response.json().get('message', 'Unknown error')}")
        except Exception as e:
            logging.error(f"Error in sendGitHubIssue: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred: {e}")

    def initUI(self):
        try:
            self.setWindowTitle(f'X-jera Term {__version__}')
            self.setGeometry(0, 0, 1300, 1000)  # 창 크기를 1300x1000으로 설정
            self.move(QApplication.primaryScreen().availableGeometry().topRight() - self.rect().topRight())  # 창을 화면 오른쪽으로 이동

            # 메뉴 바 생성
            menubar = self.menuBar()

            # 메뉴 생성
            menu = menubar.addMenu('Menu')
            settings = menubar.addMenu('Settings')
            info = menubar.addMenu('Info')
            reportmenu = menubar.addMenu('Report!!')
            reportAction = QAction('Report an Issue & Suggestion', self)
            reportAction.triggered.connect(self.showReportDialog)
            reportmenu.addAction(reportAction)
                      
            # 추가 기능 메뉴
            AdditionalFeaturesmenu = menubar.addMenu('실험실')
            
            updatecheck = menubar.addAction('Check for Updates')

            # # 추가 기능 액션 생성
            mcuinformation = QAction('MCU Information', self)
            mcuinformation.triggered.connect(self.showMCUInformationDialog)
            AdditionalFeaturesmenu.addAction(mcuinformation)

            MCULOGDetectCanTriggerAction = QAction('MCU LOG Detect CAN Trigger', self)
            MCULOGDetectCanTriggerAction.triggered.connect(self.showMCULOGDetectCanTriggerDialog)

            AdditionalFeaturesmenu.addAction(MCULOGDetectCanTriggerAction)

            alertSettingsAction = QAction('Alert Settings', self)
            alertSettingsAction.triggered.connect(self.showAlertSettingsDialog)
            AdditionalFeaturesmenu.addAction(alertSettingsAction)

            # 메뉴에 대한 액션 생성
            reconnectAction = QAction('Reconnect COM Port', self)
            reconnectAction.triggered.connect(self.reconnectSerialPort)
            loggingAction = QAction('Snap Log Export', self)
            loggingAction.triggered.connect(self.saveLog)
            viewLogsAction = QAction('View Log Directory', self)
            viewLogsAction.triggered.connect(self.viewLogDirectory)
            exitAction = QAction('Exit', self)
            exitAction.triggered.connect(self.close)
            # Filtered Rx Data Export 메뉴 추가
            exportFilteredDataAction = QAction('Export Filtered Rx Data', self)
            exportFilteredDataAction.triggered.connect(self.exportFilteredData)

            menu.addAction(reconnectAction)
            menu.addAction(loggingAction)
            menu.addAction(viewLogsAction)
            menu.addAction(exportFilteredDataAction)
            menu.addAction(exitAction)

            # 글꼴 액션 생성
            fontAction = QAction('Rxdata Font', self)
            fontAction.triggered.connect(self.showFontDialog)
            settings.addAction(fontAction)
            
            ## v4.0.4 소장님 컴퓨터 시스템폰트 작아짐 이슈 개선
            sysfontAction = QAction('System Font', self)
            sysfontAction.triggered.connect(self.showSystemFontDialog)
            settings.addAction(sysfontAction)

            # 환경설정 액션 생성
            preferencesAction = QAction('SerialSettings', self)
            preferencesAction.triggered.connect(self.showPreferencesDialog)
            settings.addAction(preferencesAction)

            cansettingsAction = QAction('CAN Settings', self)
            cansettingsAction.triggered.connect(self.showCANSettingsDialog)
            settings.addAction(cansettingsAction)

            # 로그 설정 액션 생성
            logSettingsAction = QAction('Log Settings', self)
            logSettingsAction.triggered.connect(self.showLogSettingsDialog)
            settings.addAction(logSettingsAction)

            # 테마 변경 액션 생성
            themeMenu = QMenu('Theme', self)
            lightThemeAction = QAction('Light', self)
            lightThemeAction.triggered.connect(lambda: self.setTheme('light'))
            darkThemeAction = QAction('Dark', self)
            darkThemeAction.triggered.connect(lambda: self.setTheme('dark'))
            grayThemeAction = QAction('Gray', self)
            grayThemeAction.triggered.connect(lambda: self.setTheme('gray'))
            themeMenu.addAction(lightThemeAction)
            themeMenu.addAction(darkThemeAction)
            themeMenu.addAction(grayThemeAction)
            settings.addMenu(themeMenu)

            # Info 메뉴에 대한 액션 생성
            versionInfoAction = QAction('Version Info', self)
            versionInfoAction.triggered.connect(self.showVersionInfo)
            info.addAction(versionInfoAction)

            #v4.0.3 #2
            visitGitHubAction = QAction('Visit GitHub', self)
            visitGitHubAction.triggered.connect(self.visitGitHub)
            info.addAction(visitGitHubAction)
            
            #v5.0.2
            viewSystemlog = QAction('View System Log', self)
            viewSystemlog.triggered.connect(self.viewSystemLog)
            info.addAction(viewSystemlog)
            
            updatecheck.triggered.connect(self.check_updates_on_manual)

            # 메인 레이아웃 생성
            mainLayout = QHBoxLayout()

            # 왼쪽 레이아웃 생성
            self.leftLayout = QVBoxLayout()

            # 필터 개수 입력 영역 추가
            filterCountLayout = QHBoxLayout()
            filterCountLabel = QLabel('Number of Filters:')
            self.filterCountInput = QLineEdit(self)
            self.filterCountInput.setText('3')
            self.filterCountInput.setValidator(QIntValidator(3, 30, self))
            self.filterCountInput.textChanged.connect(self.updateFilterInputs)
            filterCountLayout.addWidget(filterCountLabel)
            filterCountLayout.addWidget(self.filterCountInput)
            self.leftLayout.addLayout(filterCountLayout)

            self.filterInputs = []
            self.filterInputLayouts = []

            # 기본 3개의 필터 입력 영역 생성
            for i in range(3):
                filterLayout = QHBoxLayout()
                filterLabel = QLabel(f'Filter Input {i+1}:')
                filterInput = QLineEdit(self)
                filterInput.setPlaceholderText(f'Enter filter text {i+1}')
                filterCheckBox = QCheckBox(self)
                filterCheckBox.setChecked(True)
                self.filterInputs.append((filterInput, filterCheckBox))
                filterLayout.addWidget(filterLabel)
                filterLayout.addWidget(filterInput)
                filterLayout.addWidget(filterCheckBox)
                self.filterInputLayouts.append(filterLayout)
                self.leftLayout.addLayout(filterLayout)

            filteredRxDataLayout = QHBoxLayout()
            filteredRxDataLabel = QLabel('Filtered Rx Data:')
            self.showFilteredDataButton = QPushButton('Open in new window', self)
            self.showFilteredDataButton.clicked.connect(self.showFilteredDataWindow)
            self.clearFilteredDataButton = QPushButton('Clear', self)
            self.clearFilteredDataButton.setFixedSize(50, 25)
            self.clearFilteredDataButton.clicked.connect(self.clearFilteredData)
            filteredRxDataLayout.addWidget(filteredRxDataLabel)
            filteredRxDataLayout.addWidget(self.showFilteredDataButton)
            filteredRxDataLayout.addWidget(self.clearFilteredDataButton)
            filteredRxDataLayout.addStretch()
            self.leftLayout.addLayout(filteredRxDataLayout)
            
            filteredRxDatacountLayout = QHBoxLayout()
            filteredRxDatacountLabel = QLabel('Count Characters:')
            self.filteredRxDatacountString = QTextEdit(self)
            self.filteredRxDatacountString.setMaximumHeight(30)
            self.filteredRxDatacountString.setPlaceholderText("카운트할 문자열을 입력하세요")
            self.filteredRxDatacount = QLCDNumber(self)
            self.filteredRxDatacount.setDigitCount(10)
            self.filteredRxDatacount.setStyleSheet("color: black; background: white;")
            filteredRxDatacountLayout.addWidget(filteredRxDatacountLabel)
            filteredRxDatacountLayout.addWidget(self.filteredRxDatacountString)
            filteredRxDatacountLayout.addWidget(self.filteredRxDatacount)
            # self.leftLayout.addLayout(filteredRxDatacountLayout)
             
            self.filteredRxData = QTextEdit(self)
            self.filteredRxData.setReadOnly(True)
            self.leftLayout.addLayout(filteredRxDataLayout)
            self.leftLayout.addWidget(self.filteredRxData)
            self.filteredRxData.keyPressEvent = self.handleKeyPress  # RxData 영역에서 키 입력 처리 # v2.0.3
            for filterInput, filterCheckBox in self.filterInputs:
                filterInput.textChanged.connect(self.applyFilters)
                filterCheckBox.stateChanged.connect(self.applyFilters)

            # 오른쪽 레이아웃 생성
            rightLayout = QVBoxLayout()
            self.rxData = QTextEdit(self)
            self.rxData.setReadOnly(True)
            # self.rxData.mousePressEvent = self.focusTxInput  # RxData 영역 클릭 시 커서 이동 # v2.0.3 # v3.0.0 CtrlC 복사 기능 안되어 롤백
            self.rxData.keyPressEvent = self.handleKeyPress  # RxData 영역에서 키 입력 처리 # v2.0.3
            rxDataLayout = QHBoxLayout()
            rxDataLabel = QLabel('Rx Data:')
            self.connectionStatusLabel = QLabel('', self)  # 연결 상태 레이블 추가
            self.clearRxDataButton = QPushButton('Clear', self)
            self.clearRxDataButton.setFixedSize(50, 25)
            self.clearRxDataButton.clicked.connect(self.clearRxData)
            rxDataLayout.addWidget(rxDataLabel)
            rxDataLayout.addWidget(self.connectionStatusLabel)  # 연결 상태 레이블 추가
            rxDataLayout.addLayout(filteredRxDatacountLayout)
            rxDataLayout.addWidget(self.clearRxDataButton)
            rightLayout.addLayout(rxDataLayout)
            rightLayout.addWidget(self.rxData)

            # TxInput Favorite 추가
            txFavoriteLayout = QGridLayout()
            self.txFavoriteInputs = []
            for i in range(6):
                favoriteInput = QLineEdit(self)
                favoriteInput.setPlaceholderText(f'Tx Favorite Data {i+1}')
                sendButton = QPushButton('Send', self)
                sendButton.clicked.connect(lambda _, fi=favoriteInput: self.sendFavoriteData(fi))
                self.txFavoriteInputs.append(favoriteInput)
                txFavoriteLayout.addWidget(favoriteInput, i // 3, (i % 3) * 2)
                txFavoriteLayout.addWidget(sendButton, i // 3, (i % 3) * 2 + 1)
            rightLayout.addLayout(txFavoriteLayout)

            # Tx 입력 박스 추가
            self.txInput = QLineEdit(self)
            self.txInput.setPlaceholderText('Enter text to send')
            self.txInput.returnPressed.connect(self.sendTxData)
            rightLayout.addWidget(self.txInput)

            # 크기 조정을 허용하는 스플리터 생성
            splitter = QSplitter(Qt.Orientation.Horizontal)
            leftWidget = QWidget()
            leftWidget.setLayout(self.leftLayout)
            rightWidget = QWidget()
            rightWidget.setLayout(rightLayout)
            splitter.addWidget(leftWidget)
            splitter.addWidget(rightWidget)
            splitter.setSizes([410, 890])  # 초기 크기를 3:7 비율로 설정
            splitter.setStyleSheet("""
                QSplitter::handle {
                    background-color: gray;
                    width: 5px;
                    border: 1px solid black;
                }
            """)  # 스플리터 스타일 설정

            # 스플리터를 메인 레이아웃에 추가
            mainLayout.addWidget(splitter)

            # 메인 레이아웃을 중앙 위젯에 설정
            centralWidget = QWidget()
            centralWidget.setLayout(mainLayout)
            self.setCentralWidget(centralWidget)

            # 로그 설정 기본값
            self.defaultLogFileName = "Y-%m-%d%p%H_%M_%S.teralog"
            self.defaultLogFolderPath = os.path.expanduser("~")
            self.snapLogFileName = "snap_Y-%m-%d%p%H_%M_%S.teralog"
            self.snapLogFolderPath = os.path.expanduser("~")
            self.autoLogging = False
            self.fontFamily = "Arial"
            self.fontSize = 14
            self.systemFontFamily = "Arial"
            self.systemFontSize = 10

            self.currentTheme = 'light'  # 기본 테마 설정
            self.applyTheme()

            # 창 크기 및 위치 변경 이벤트 연결
            self.resizeEvent = self.saveWindowSettings
            self.moveEvent = self.saveWindowSettings
        except Exception as e:
            logging.error(f"Error in initUI: {e}")

    ### v4.0.5 #1 handleKeyPress 함수 변경
    
    # def handleKeyPress(self, event):  # v2.0.3
    #     try:
    #         if (event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter):
    #             self.txInput.setFocus()
    #             self.rxData.verticalScrollBar().setValue(self.rxData.verticalScrollBar().maximum())
    #         else:
    #             QTextEdit.keyPressEvent(self.rxData, event)  # 기존 keyPressEvent 호출
    #     except Exception as e:
    #         logging.error(f"Error in handleKeyPress: {e}")
            
    def handleKeyPress(self, event):  # v4.0.5 #1
        """방향키(↑, ↓)로 TxInput의 입력 히스토리를 탐색"""
        if self.txInput.hasFocus():  # Tx 입력 박스에서만 동작
            print("focusedtxInput")
            
            if event.key() == Qt.Key.Key_Up:  # 위 방향키 ↑
                if self.txHistory and self.txHistoryIndex < len(self.txHistory) - 1:
                    if self.txHistoryIndex == -1:  # 새 입력이면 마지막 히스토리 선택
                        self.txHistoryIndex = len(self.txHistory) - 1
                    else:
                        self.txHistoryIndex -= 1
                    self.txInput.setText(self.txHistory[self.txHistoryIndex])
                return

            elif event.key() == Qt.Key.Key_Down:  # 아래 방향키 ↓
                if self.txHistory and self.txHistoryIndex >= 0:
                    self.txHistoryIndex += 1
                    if self.txHistoryIndex >= len(self.txHistory):  # 마지막 이후면 빈 입력
                        self.txHistoryIndex = -1
                        self.txInput.clear()
                    else:
                        self.txInput.setText(self.txHistory[self.txHistoryIndex])
                return
        
            elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                self.sendTxData()
                return
            
            super(QLineEdit, self.txInput).keyPressEvent(event)  # 기본 동작 유지
            return
            
                        
        if self.rxData.hasFocus():
            print("focusedrxData")
            try:
                if (event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter):
                    self.txInput.setFocus()
                    self.rxData.verticalScrollBar().setValue(self.rxData.verticalScrollBar().maximum())
                else:
                    QTextEdit.keyPressEvent(self.rxData, event)
            except Exception as e:
                logging.error(f"Error in handleKeyPress: {e}")
        if self.filteredRxData.hasFocus():
            print("focusedfilteredRxData")
            try:
                if (event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter):
                    self.txInput.setFocus()
                    self.rxData.verticalScrollBar().setValue(self.rxData.verticalScrollBar().maximum())
                else:
                    QTextEdit.keyPressEvent(self.filteredRxData, event)
            except Exception as e:
                logging.error(f"Error in handleKeyPress: {e}")
                
    ###

    # def focusTxInput(self, event):  # v2.0.3
    #     try:
    #         self.txInput.setFocus()
    #         QTextEdit.mousePressEvent(self.rxData, event)  # 기존 mousePressEvent 호출
    #     except Exception as e:
    #         logging.error(f"Error in focusTxInput: {e}")

    def setEnglishInputMode(self, event): # v2.0.4
        """txInput에 포커스가 갈 때 입력 모드를 영어로 변경"""
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            ctypes.windll.user32.PostMessageW(hwnd, 0x0050, 0, 0x0409)  # 0x0409는 영어(미국) 키보드 레이아웃
            QLineEdit.focusInEvent(self.txInput, event)  # 기존 focusInEvent 호출
        except Exception as e:
            logging.error(f"Error in setEnglishInputMode: {e}")

    def updateFilterInputs(self):
        try:
            filterCount = int(self.filterCountInput.text())
            if filterCount < 1:
                raise ValueError("Number of Filters must be at least 1.")
        except ValueError:
            self.filterCountInput.setText('1')
            filterCount = 1

        currentCount = len(self.filterInputs)
        currentFilterValues = [(filterInput.text(), filterCheckBox.isChecked()) for filterInput, filterCheckBox in self.filterInputs]

        if filterCount > currentCount:
            for i in range(currentCount, filterCount):
                filterLayout = QHBoxLayout()
                filterLabel = QLabel(f'Filter Input {i+1}:')
                filterInput = QLineEdit(self)
                filterInput.setPlaceholderText(f'Enter filter text {i+1}')
                filterCheckBox = QCheckBox(self)
                filterCheckBox.setChecked(True)
                self.filterInputs.append((filterInput, filterCheckBox))
                filterLayout.addWidget(filterLabel)
                filterLayout.addWidget(filterInput)
                filterLayout.addWidget(filterCheckBox)
                self.filterInputLayouts.append(filterLayout)
                self.leftLayout.insertLayout(self.leftLayout.count() - 2, filterLayout)
                filterInput.textChanged.connect(self.applyFilters)
                filterCheckBox.stateChanged.connect(self.applyFilters)
        elif filterCount < currentCount:
            for i in range(currentCount - 1, filterCount - 1, -1):
                filterLayout = self.filterInputLayouts.pop()
                self.filterInputs.pop()
                self.leftLayout.removeItem(filterLayout)
                for j in reversed(range(filterLayout.count())):
                    widget = filterLayout.itemAt(j).widget()
                    if widget is not None:
                        widget.deleteLater()
                self.leftLayout.update()

        # Restore filter values from env_set.txt
        settings_path = os.path.join(os.path.dirname(sys.executable), 'env_set.txt')
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as file:
                settings = dict(line.strip().split('=', 1) for line in file)
                filter_inputs = settings.get('filter_inputs', [])
                if filter_inputs:
                    filter_inputs = eval(filter_inputs)
                for i, (filterInput, filterCheckBox) in enumerate(self.filterInputs):
                    if i < len(filter_inputs):
                        filterInput.setText(filter_inputs[i][0])
                        filterCheckBox.setChecked(filter_inputs[i][1])
                    else:
                        filterInput.setText('')
                        filterCheckBox.setChecked(True)
        else:
            for filterInput, filterCheckBox in self.filterInputs:
                filterInput.setText('')
                filterCheckBox.setChecked(True)

    def sendTxData(self):
        try:
            if (self.serialPort and self.serialPort.is_open):
                enterData = '\r\n' # v3.0.0 Enter키 입력 추가
                txData = self.txInput.text() + '\r\n'
                self.serialPort.write(enterData.encode('utf-8')) # v3.0.0 Enter키 입력 추가
                self.serialPort.write(txData.encode('utf-8'))
                self.txInput.clear()
                self.rxData.verticalScrollBar().setValue(self.rxData.verticalScrollBar().maximum()) # v2.0.3 Enter키 입력시 스크롤바 최하단으로 이동
                # self.saveSettings()
                if txData: #v4.0.5 #1
                    self.txHistory.append(txData)
                    self.txHistoryIndex = -1
                    
        except Exception as e:
            logging.error(f"Error in sendTxData: {e}")

    def sendFavoriteData(self, favoriteInput):
        try:
            if (self.serialPort and self.serialPort.is_open):
                enterData = '\r\n' # v3.0.0 Enter키 입력 추가
                txData = favoriteInput.text() + '\r\n'
                self.serialPort.write(enterData.encode('utf-8')) # v3.0.0 Enter키 입력 추가
                self.serialPort.write(txData.encode('utf-8'))
                self.saveSettings()
                logging.debug(f"Favorite data Saved: {txData}")
        except Exception as e:
            logging.error(f"Error in sendFavoriteData: {e}")

    def showFontDialog(self):
        current_font = self.rxData.font()
        font, ok = QFontDialog.getFont(current_font, self)
        if ok:
            self.rxData.setFont(font)
            self.filteredRxData.setFont(font)
            self.txInput.setFont(font)
            self.saveSettings()
            logging.debug(f"Font Saved: {self.fontFamily}, {self.fontSize}")
            
    def showSystemFontDialog(self): # v4.0.4
        current_font = QApplication.font()
        font, ok = QFontDialog.getFont(current_font, self)
        if ok:
            QApplication.setFont(font)
            self.updateFontForWidgets(self, font)
            self.saveSettings()
            logging.debug(f"System Font Saved: {self.systemFontFamily}, {self.systemFontSize}")
            self.updateFontForWidgets(self, font)

    def updateFontForWidgets(self, widget, font): # v4.0.4
        """재귀적으로 UI 위젯의 폰트를 변경 (RxData 제외)"""
        if widget == self.rxData:  # RxData는 폰트 변경 제외
            return
        
        widget.setFont(font)  
        for child in widget.findChildren(QWidget):
            if child != self.rxData:  # RxData는 변경하지 않음
                child.setFont(font)

    def showPreferencesDialog(self):
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle('Preferences')
            layout = QFormLayout(dialog)
            dialog.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제

            ports = [port.device for port in serial.tools.list_ports.comports()]
            self.portComboBox = QComboBox()
            self.portComboBox.addItems(ports)
            self.portComboBox.setCurrentText(self.port)
            self.portComboBox.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            
            # Portlist 버튼 추가
            portListButton = QPushButton('Portlist')
            portListButton.clicked.connect(self.showPortList)
            portListButton.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            portListLayout = QHBoxLayout()
            portListLayout.addWidget(self.portComboBox)
            portListLayout.addWidget(portListButton)
            layout.addRow('Port:', portListLayout)

            self.baudRateComboBox = QComboBox()
            self.baudRateComboBox.addItems(['9600', '19200', '38400', '57600', '115200'])
            self.baudRateComboBox.setCurrentText(self.baudRate)
            self.baudRateComboBox.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            layout.addRow('Baud Rate:', self.baudRateComboBox)

            self.dataBitsComboBox = QComboBox()
            self.dataBitsComboBox.addItems(['5', '6', '7', '8'])
            self.dataBitsComboBox.setCurrentText(self.dataBits)  # 기본값을 env_set.txt에서 설정
            self.dataBitsComboBox.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            layout.addRow('Data Bits:', self.dataBitsComboBox)

            self.parityComboBox = QComboBox()
            self.parityComboBox.addItems(['None', 'Even', 'Odd', 'Mark', 'Space'])
            self.parityComboBox.setCurrentText(self.parity)
            self.parityComboBox.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            layout.addRow('Parity:', self.parityComboBox)

            self.stopBitsComboBox = QComboBox()
            self.stopBitsComboBox.addItems(['1', '1.5', '2'])
            self.stopBitsComboBox.setCurrentText(self.stopBits)
            self.stopBitsComboBox.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            layout.addRow('Stop Bits:', self.stopBitsComboBox)

            buttonBox = QHBoxLayout()
            okButton = QPushButton('OK')
            okButton.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            cancelButton = QPushButton('Cancel')
            cancelButton.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            buttonBox.addWidget(okButton)
            buttonBox.addWidget(cancelButton)
            layout.addRow(buttonBox)

            okButton.clicked.connect(lambda: self.savePreferences(dialog))
            cancelButton.clicked.connect(dialog.reject)

            dialog.setLayout(layout)
            dialog.exec()
        except Exception as e:
            logging.error(f"Error in showPreferencesDialog: {e}")

    def showPortList(self):
        try:
            ports = serial.tools.list_ports.comports()
            portList = "\n".join([f"{port.device} - {port.description}" for port in ports])
            QMessageBox.information(self, "Port List", portList)
        except Exception as e:
            logging.error(f"Error in showPortList: {e}")

    def savePreferences(self, dialog):
        try:
            self.port = self.portComboBox.currentText()
            self.baudRate = self.baudRateComboBox.currentText()
            self.dataBits = self.dataBitsComboBox.currentText()
            self.parity = self.parityComboBox.currentText()
            self.stopBits = self.stopBitsComboBox.currentText()
            self.saveSettings()
            logging.debug(f'Preferences Saved. port : {self.port}, baudRate : {self.baudRate}, dataBits : {self.dataBits}, parity : {self.parity}, stopBits : {self.stopBits}')
            dialog.accept()
        except Exception as e:
            logging.error(f"Error in savePreferences: {e}")

    def showCANSettingsDialog(self):
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle('CAN Settings')
            layout = QFormLayout(dialog)
            dialog.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제

            self.canch_entry = QLineEdit(self)
            self.canch_entry.setPlaceholderText('Enter CAN Channel')
            self.canch_entry.setText(self.canch_entry_value if self.canch_entry_value else '1')
            layout.addRow('CAN Channel:', self.canch_entry)

            self.bustype_entry = QComboBox(self)
            self.bustype_entry.addItems(['vector', 'kvaser'])
            self.bustype_entry.setCurrentText(self.bustype_entry_value if self.bustype_entry_value else 'vector')
            layout.addRow('CAN Bus Type:', self.bustype_entry)

            buttonBox = QHBoxLayout()
            okButton = QPushButton('OK')
            okButton.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            cancelButton = QPushButton('Cancel')
            cancelButton.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            buttonBox.addWidget(okButton)
            buttonBox.addWidget(cancelButton)
            layout.addRow(buttonBox)

            okButton.clicked.connect(lambda: self.saveCANSettings(dialog))  # saveCANSettings 호출
            cancelButton.clicked.connect(dialog.reject)

            dialog.setLayout(layout)
            dialog.exec()
        except Exception as e:
            logging.error(f"Error in showCANSettingsDialog: {e}")

    def saveCANSettings(self, dialog):
        try:
            self.canch_entry_value = self.canch_entry.text()
            self.bustype_entry_value = self.bustype_entry.currentText()
            self.saveSettings()
            logging.debug(f'CAN Setting Saved. canch_entry_value : {self.canch_entry_value}, bustype_entry_value : {self.bustype_entry_value}')
            dialog.accept()
        except Exception as e:
            logging.error(f"Error in saveCANSettings: {e}")

    def showLogSettingsDialog(self):
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle('Log Settings')
            layout = QFormLayout(dialog)
            dialog.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제

            self.defaultLogFileNameInput = QLineEdit(self.defaultLogFileName)
            self.defaultLogFileNameInput.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            layout.addRow('Default Log File Name:', self.defaultLogFileNameInput)

            defaultLogFolderPathLayout = QHBoxLayout()
            self.defaultLogFolderPathInput = QLineEdit(self.defaultLogFolderPath)
            self.defaultLogFolderPathInput.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            defaultLogFolderPathBrowseButton = QPushButton('Browse')
            defaultLogFolderPathBrowseButton.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            defaultLogFolderPathBrowseButton.clicked.connect(self.browseDefaultLogFolderPath)
            defaultLogFolderPathLayout.addWidget(self.defaultLogFolderPathInput)
            defaultLogFolderPathLayout.addWidget(defaultLogFolderPathBrowseButton)
            layout.addRow('Default Log Folder Path:', defaultLogFolderPathLayout)

            self.snapLogFileNameInput = QLineEdit(self.snapLogFileName)
            self.snapLogFileNameInput.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            layout.addRow('Snap Log File Name:', self.snapLogFileNameInput)

            snapLogFolderPathLayout = QHBoxLayout()
            self.snapLogFolderPathInput = QLineEdit(self.snapLogFolderPath)
            self.snapLogFolderPathInput.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            snapLogFolderPathBrowseButton = QPushButton('Browse')
            snapLogFolderPathBrowseButton.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            snapLogFolderPathBrowseButton.clicked.connect(self.browseSnapLogFolderPath)
            snapLogFolderPathLayout.addWidget(self.snapLogFolderPathInput)
            snapLogFolderPathLayout.addWidget(snapLogFolderPathBrowseButton)
            layout.addRow('Snap Log Folder Path:', snapLogFolderPathLayout)

            self.autoLoggingCheckBox = QCheckBox('Start Auto Logging')
            self.autoLoggingCheckBox.setChecked(self.autoLogging)
            self.autoLoggingCheckBox.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            layout.addRow(self.autoLoggingCheckBox)

            buttonBox = QHBoxLayout()
            okButton = QPushButton('OK')
            okButton.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            cancelButton = QPushButton('Cancel')
            cancelButton.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            buttonBox.addWidget(okButton)
            buttonBox.addWidget(cancelButton)
            layout.addRow(buttonBox)

            okButton.clicked.connect(lambda: self.saveLogSettings(dialog))
            cancelButton.clicked.connect(dialog.reject)

            dialog.setLayout(layout)
            dialog.exec()
        except Exception as e:
            logging.error(f"Error in showLogSettingsDialog: {e}")

    def browseDefaultLogFolderPath(self):
        try:
            folder = QFileDialog.getExistingDirectory(self, 'Select Default Log Folder Path', self.defaultLogFolderPath)
            if folder:
                self.defaultLogFolderPathInput.setText(folder)
        except Exception as e:
            logging.error(f"Error in browseDefaultLogFolderPath: {e}")

    def browseSnapLogFolderPath(self):
        try:
            folder = QFileDialog.getExistingDirectory(self, 'Select Snap Log Folder Path', self.snapLogFolderPath)
            if folder:
                self.snapLogFolderPathInput.setText(folder)
        except Exception as e:
            logging.error(f"Error in browseSnapLogFolderPath: {e}")

    def saveLogSettings(self, dialog):
        try:
            self.defaultLogFileName = self.defaultLogFileNameInput.text()
            self.defaultLogFolderPath = os.path.expandvars(self.defaultLogFolderPathInput.text())
            self.snapLogFileName = self.snapLogFileNameInput.text()
            self.snapLogFolderPath = os.path.expandvars(self.snapLogFolderPathInput.text())
            
            # 디렉토리 생성
            os.makedirs(self.defaultLogFolderPath, exist_ok=True)
            os.makedirs(self.snapLogFolderPath, exist_ok=True)
            
            self.autoLogging = self.autoLoggingCheckBox.isChecked()
            self.saveSettings()
            logging.debug(f'Log Settings Saved. defaultLogFileName : {self.defaultLogFileName}, defaultLogFolderPath : {self.defaultLogFolderPath}, snapLogFileName : {self.snapLogFileName}, snapLogFolderPath : {self.snapLogFolderPath}, autoLogging : {self.autoLogging}')
            dialog.accept()
        except Exception as e:
            logging.error(f"Error in saveLogSettings: {e}")

    def saveSettings(self):
        logging.debug("Saving settings...")
        try:
            settings = {
                'Version': updatemanager.CURRENT_VERSION, #v2.0.5
                'port': self.port,
                'baud_rate': self.baudRate,
                'data_bits': self.dataBits,
                'parity': self.parity,
                'stop_bits': self.stopBits,
                'default_log_file_name': self.defaultLogFileName,
                'default_log_folder_path': self.defaultLogFolderPath,
                'snap_log_file_name': self.snapLogFileName,
                'snap_log_folder_path': self.snapLogFolderPath,
                'auto_logging': self.autoLogging,
                'font_family': self.fontFamily,
                'font_size': self.fontSize,
                'systemfont_family': self.systemFontFamily, #v4.0.4
                'systemfont_size': self.systemFontSize, #v4.0.4
                'tx_favorite_1': self.txFavoriteInputs[0].text(),
                'tx_favorite_2': self.txFavoriteInputs[1].text(),
                'tx_favorite_3': self.txFavoriteInputs[2].text(),
                'tx_favorite_4': self.txFavoriteInputs[3].text(),
                'tx_favorite_5': self.txFavoriteInputs[4].text(),
                'tx_favorite_6': self.txFavoriteInputs[5].text(),
                'window_width': self.width(),
                'window_height': self.height(),
                'window_x': self.x(),
                'window_y': self.y(),
                'theme': self.currentTheme,
                'filter_count': self.filterCountInput.text(),
                'filter_inputs': [(filterInput.text(), filterCheckBox.isChecked()) for filterInput, filterCheckBox in self.filterInputs],
                'canch_entry': self.canch_entry_value,
                'bustype_entry': self.bustype_entry_value,
                'target_string_entry': self.MCULOGDetectCanTriggerDialog.target_string_entry.text(),
                'ConfigurationCode_entry': self.MCULOGDetectCanTriggerDialog.ConfigurationCode_entry.text(),
                'VIN_entry': self.MCULOGDetectCanTriggerDialog.VIN_entry.text(),
                'alertTextInput': self.alertSettingsDialog.alertTextInput.text(),
                'alertTypeComboBox': self.alertSettingsDialog.alertTypeComboBox.currentText(),
                'filteredRxDatacountString': self.filteredRxDatacountString.toPlainText()
            }
            with open(os.path.join(os.path.dirname(sys.executable), 'env_set.txt'), 'w') as file:
                for key, value in settings.items():
                    file.write(f'{key}={value}\n')
        except Exception as e:
            logging.error(f"Error in saveSettings: {e}")

    def loadSettings(self):
        logging.debug("Loading settings...")
        try:
            settings_path = os.path.join(os.path.dirname(sys.executable), 'env_set.txt')
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as file:
                    print(settings_path)
                    settings = dict(line.strip().split('=', 1) for line in file)
                    self.port = settings.get('port', 'COM1')
                    self.baudRate = settings.get('baud_rate', '115200')
                    self.dataBits = settings.get('data_bits', '8')
                    self.parity = settings.get('parity', 'None')
                    self.stopBits = settings.get('stop_bits', '1')
                    self.defaultLogFileName = settings.get('default_log_file_name', '%Y-%m-%d%p%H_%M_%S.teralog')
                    self.defaultLogFolderPath = os.path.expandvars(settings.get('default_log_folder_path', os.path.expanduser("~")))
                    self.snapLogFileName = settings.get('snap_log_file_name', 'snap_%Y-%m-%d%p%H_%M_%S.teralog')
                    self.snapLogFolderPath = os.path.expandvars(settings.get('snap_log_folder_path', os.path.expanduser("~")))
                    self.autoLogging = settings.get('auto_logging', 'False') == 'True'
                    self.fontFamily = settings.get('font_family', 'Arial')
                    self.fontSize = int(settings.get('font_size', '14'))
                    self.systemFontFamily = settings.get('systemfont_family', 'Arial') #v4.0.4
                    self.systemFontSize = int(settings.get('systemfont_size', '10')) #v4.0.4
                    self.txFavoriteInputs[0].setText(settings.get('tx_favorite_1', ''))
                    self.txFavoriteInputs[1].setText(settings.get('tx_favorite_2', ''))
                    self.txFavoriteInputs[2].setText(settings.get('tx_favorite_3', ''))
                    self.txFavoriteInputs[3].setText(settings.get('tx_favorite_4', ''))
                    self.txFavoriteInputs[4].setText(settings.get('tx_favorite_5', ''))
                    self.txFavoriteInputs[5].setText(settings.get('tx_favorite_6', ''))
                    self.resize(int(settings.get('window_width', '1300')), int(settings.get('window_height', '1000')))
                    self.move(int(settings.get('window_x', '0')), int(settings.get('window_y', '0')))
                    self.currentTheme = settings.get('theme', 'light')
                    self.filterCountInput.setText(settings.get('filter_count', '3'))
                    self.canch_entry_value = settings.get('canch_entry', '1')
                    self.bustype_entry_value = settings.get('bustype_entry', 'vector')
                    self.MCULOGDetectCanTriggerDialog.target_string_entry.setText(settings.get('target_string_entry', ''))
                    self.MCULOGDetectCanTriggerDialog.ConfigurationCode_entry.setText(settings.get('ConfigurationCode_entry', ''))
                    self.MCULOGDetectCanTriggerDialog.VIN_entry.setText(settings.get('VIN_entry', ''))
                    self.alertSettingsDialog.alertTextInput.setText(settings.get('alertTextInput', ''))
                    self.alertSettingsDialog.alertTypeComboBox.setCurrentText(settings.get('alertTypeComboBox', 'Popup'))
                    self.filteredRxDatacountString.setPlainText(settings.get('filteredRxDatacountString', ''))
                    filter_inputs = settings.get('filter_inputs', [])
                    if filter_inputs:
                        filter_inputs = eval(filter_inputs)
                    self.updateFilterInputs()
                    for i, (filterInput, filterCheckBox) in enumerate(self.filterInputs):
                        if i < len(filter_inputs):
                            filterInput.setText(filter_inputs[i][0])
                            filterCheckBox.setChecked(filter_inputs[i][1])
                        else:
                            filterInput.setText('')
                            filterCheckBox.setChecked(True)
                    self.applyFilters()  # 필터 적용
            else:
                self.port = 'COM1'
                self.baudRate = '115200'
                self.dataBits = '8'
                self.parity = 'None'
                self.stopBits = '1'
                self.defaultLogFileName = '%Y-%m-%d%p%H_%M_%S.teralog'
                self.defaultLogFolderPath = os.path.expanduser("~")
                self.snapLogFileName = 'snap_%Y-%m-%d%p%H_%M_%S.teralog'
                self.snapLogFolderPath = os.path.expanduser("~")
                self.autoLogging = False
                self.fontFamily = 'Arial'
                self.fontSize = 14
                self.systemFontFamily = 'Arial'
                self.systemFontSize = 10
                self.currentTheme = 'light'
                self.filterCountInput.setText('3')
                self.canch_entry.setText('1')
                self.bustype_entry.setCurrentText('vector')
                self.MCULOGDetectCanTriggerDialog.target_string_entry.setText('')
                self.MCULOGDetectCanTriggerDialog.ConfigurationCode_entry.setText('')
                self.MCULOGDetectCanTriggerDialog.VIN_entry.setText('')
                self.alertSettingsDialog.alertTextInput.setText('')
                self.alertSettingsDialog.alertTypeComboBox.setCurrentText('Popup')
                self.filteredRxDatacountString.setPlainText('')

                for filterInput, filterCheckBox in self.filterInputs:
                    filterInput.setText('')
                    filterCheckBox.setChecked(True)

            self.rxData.setFont(QFont(self.fontFamily, self.fontSize))
            QApplication.setFont(QFont(self.systemFontFamily, self.systemFontSize)) #v4.0.4
            self.applyTheme()
        except Exception as e:
            logging.error(f"Error in loadSettings: {e}")

    def connectSerialPort(self):
        try:
            logging.debug(f"Connecting to serial port: {self.port} at {self.baudRate} baud")
            self.serialPort = serial.Serial(
                port=self.port,
                baudrate=int(self.baudRate),
                bytesize=int(self.dataBits),
                parity=self.parity[0],  # 첫 글자만 사용
                stopbits=float(self.stopBits),
                timeout=1
            )
            self.serialPort.flush()
            self.serialReaderThread = SerialReaderThread(self.serialPort, self.processedData)  # processedData 전달
            logging.info(f"Serial port connected: {self.port} at {self.baudRate} baud")
            self.serialReaderThread.data_received.connect(self.updateRxData)
            self.serialReaderThread.disconnected.connect(self.handleSerialDisconnect)  # disconnected 시그널 연결 #v5.0.5
            self.serialReaderThread.start()
            if self.autoLogging:
                self.startAutoLogging()
            self.showConnectionStatus(f'{self.port} CONNECTED.')
        except serial.SerialException as e:
            logging.error(f"Serial connection error: {e}")
            self.rxData.append(f'⚠️ Error: {e}') #v5.0.5
            self.rxData.append(f'⚠️ Please click "Reconnect COM Port" in the menu to reconnect.') #v5.0.5
        except Exception as e:
            logging.error(f"⚠️ Error in connectSerialPort: {e}") #v5.0.5
#v5.0.5
    def handleSerialDisconnect(self):
        logging.warning("Serial port disconnected. Attempting to reconnect...")
        self.showConnectionStatus(f"{self.port} DISCONNECTED. Reconnecting...")
        self.rxData.append("⚠️ Serial port disconnected. Retrying connection...")
        QTimer.singleShot(3000, self.reconnectSerialPort)  # 3초 후 재연결 시도
#v5.0.5

    def showConnectionStatus(self, message):
        try:
            self.connectionStatusLabel.setText(message)
            self.connectionStatusLabel.setStyleSheet("color: red; font-weight: bold;")
            QTimer.singleShot(10000, lambda: self.connectionStatusLabel.setText(''))
        except Exception as e:
            logging.error(f"Error in showConnectionStatus: {e}")

    def reconnectSerialPort(self):
        try:
            if hasattr(self, 'serialPort') and self.serialPort.is_open:
                self.serialPort.close()
            self.connectSerialPort()
        except AttributeError:
            self.connectSerialPort()
        except Exception as e:
            logging.error(f"Error in reconnectSerialPort: {e}")

    def startAutoLogging(self):
        try:
            logFileName = self.defaultLogFileName
            if '%' in logFileName:
                logFileName = datetime.now().strftime(logFileName)
            self.autoLogFilePath = os.path.join(self.defaultLogFolderPath, logFileName)
            os.makedirs(os.path.dirname(self.autoLogFilePath), exist_ok=True)  # 디렉토리 생성
            print(self.autoLogFilePath)
            self.autoLogFile = open(self.autoLogFilePath, 'w')
            self.autoLogBuffer = ""  # 자동 로깅을 위한 버퍼
        except Exception as e:
            logging.error(f"Error in startAutoLogging: {e}")

    def applyFilters(self):
        try:
            self.filteredRxData.clear()
            batch_size = 100  # 한 번에 처리할 데이터 양
            for i in range(0, len(self.filteredData), batch_size):
                batch = self.filteredData[i:i + batch_size]
                for line in batch:
                    if any(
                    re.search(re.escape(filterInput.text()), line) and filterCheckBox.isChecked() for filterInput, filterCheckBox in self.filterInputs if filterInput.text() and filterCheckBox.isChecked()):
                        self.filteredRxData.append(line)
                QApplication.processEvents()  # UI 업데이트를 위해 이벤트 처리
            self.saveSettings()
            logging.debug("Filters applied.")
        except Exception as e:
            logging.error(f"Error in applyFilters: {e}")

    ## mcu데이터 줄바꿈 \r\n 이지만 간혹 \n만 나오는경우있음. \r\n을 \n 으로 변경하여 줄바꿈을 통일 및 \n을 기준으로 데이터 나누기
    def updateRxData(self, data):
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            self.buffer += data  # 기존 버퍼에 새로운 데이터 추가
            self.buffer = self.buffer.replace('\n\r', '\n')  # Windows 스타일 줄바꿈을 통일
            lines = self.buffer.split('\n')  # \n을 기준으로 데이터 나누기
            # formatted_text = "" ##V5.0.2 #1 rxData GUI멈춤이슈 개선 코드
            # filtered_text = "" ##V5.0.2 #1 rxData GUI멈춤이슈 개선 코드
            # self.rxData.setUpdatesEnabled(False)  # UI 업데이트 중지 (속도 향상) ##V5.0.2 #1 rxData GUI멈춤이슈 개선 코드
            for line in lines[:-1]:
                if line.strip():
                    # formatted_line = f'[{timestamp}] {line.strip()}\n' ##V5.0.2 #1 rxData GUI멈춤이슈 개선 코드
                    # formatted_text += formatted_line ##V5.0.2 #1 rxData GUI멈춤이슈 개선 코드
                    appendFormattedText(self.rxData, f'[{timestamp}] {line.strip()}\n')
                    # print(line)
                    # self.filteredData.append(formatted_line)  # 리스트에 추가 ##V5.0.2 #1 rxData GUI멈춤이슈 개선 코드
                    self.filteredData.append(f'[{timestamp}] {line.strip()}')  # 리스트에 추가 ##RxData중복출력으로 인해 회귀
                    if any(re.search(re.escape(filterInput.text()), line) and filterCheckBox.isChecked() for filterInput, filterCheckBox in self.filterInputs if filterInput.text() and filterCheckBox.isChecked()):
                        appendFormattedText(self.filteredRxData, f'[{timestamp}] {line.strip()}\n') ##RxData중복출력으로 인해 회귀
                        # filtered_text += formatted_line ##V5.0.2 #1 rxData GUI멈춤이슈 개선 코드
                        # filteredRxDatacountString이 감지되면 카운트 증가
                        
                    text = self.filteredRxDatacountString.toPlainText().strip()  # 앞뒤 공백 제거
                    if text and text in line:  # 빈 문자열이 아닐 때만 비교
                        self.filteredRxDatacount_value += 1
                        self.filteredRxDatacount.display(self.filteredRxDatacount_value)  # QLCDNumber 업데이트
                        self.saveSettings()
                    if text == '':
                        self.filteredRxDatacount_value = 0
                        self.filteredRxDatacount.display(self.filteredRxDatacount_value)
                        self.saveSettings()
                        
            # if formatted_text:
            #     appendFormattedText(self.rxData, formatted_text) ##V5.0.2 #1 rxData GUI멈춤이슈 개선 코드
            # if filtered_text:
            #     appendFormattedText(self.filteredRxData, filtered_text) ##V5.0.2 #1 rxData GUI멈춤이슈 개선 코드
                                
            # # self.rxData.setUpdatesEnabled(True)  # UI 업데이트 재개 (속도 향상) ##V5.0.2 #1 rxData GUI멈춤이슈 개선 코드
            # if formatted_text or filtered_text: ##V5.0.2 #1 rxData GUI멈춤이슈 개선 코드
            #     QApplication.processEvents()  # UI 이벤트 강제처리 ##V5.0.2 #1 rxData GUI멈춤이슈 개선 코드
            
            if not self.userScrolled_filter: #v4.0.3 
                self.filteredRxData.verticalScrollBar().setValue(self.filteredRxData.verticalScrollBar().maximum()) #v4.0.3 
            
            self.buffer = lines[-1]  # 미완성 줄은 다시 버퍼에 저장
            # 자동 스크롤 제어
            if not self.userScrolled:
                self.rxData.verticalScrollBar().setValue(self.rxData.verticalScrollBar().maximum())
            # 자동 로깅
            if self.autoLogging:
                self.autoLogBuffer += data
                self.autoLogBuffer = self.autoLogBuffer.replace('\n\r', '\n') # Windows 스타일 줄바꿈을 통일
                logLines = self.autoLogBuffer.split('\n') # \n을 기준으로 데이터 나누기
                for logLine in logLines[:-1]:
                    logLine = re.sub(r'\x1b\[[0-9;]*m', '', logLine)
                    self.autoLogFile.write(f'[{timestamp}] {logLine.strip()}\n')
                self.autoLogBuffer = logLines[-1]
                self.autoLogFile.flush()
                
            # 최대 줄 수 제한 ##v5.0.2 #1 rxData GUI멈춤이슈 개선 코드
            if self.rxData.document().blockCount() > self.MAX_LINES:
                print(self.rxData.document().blockCount())
                self.removeOldLines(self.rxData)
                logging.info("Removed old lines.for rxData")
            if self.filteredRxData.document().blockCount() > self.MAX_LINES:
                self.removeOldLines(self.filteredRxData)
                logging.info("Removed old lines.for filteredRxData")

        except Exception as e:
            logging.error(f"Error in updateRxData: {e}")

    def getProcessedData(self):
        try:
            return self.processedData.copy()  # 데이터를 복사하여 반환
        except Exception as e:
            logging.error(f"Error in getProcessedData: {e}")

    def handleScroll(self, value):
        try:
            max_value = self.rxData.verticalScrollBar().maximum()
            if value < max_value:
                # print(f'right{self.userScrolled}')#v4.0.3 
                self.userScrolled = True
            else:
                self.userScrolled = False
                # print(f'right{self.userScrolled}')#v4.0.3 
        except Exception as e:
            logging.error(f"Error in handleScroll: {e}")

    def showFilteredDataWindow(self):
        try:
            self.filteredDataWindow = FilteredDataWindow(self.filteredRxData, self)
            self.filteredDataWindow.show()
        except Exception as e:
            logging.error(f"Error in showFilteredDataWindow: {e}")

#v4.0.3 Filtered Data Window 스크롤 이벤트 추가
    def handleScroll_filter(self, value):
        try:
            max_value = self.filteredRxData.verticalScrollBar().maximum()
            if value < max_value:
                # print(f'filter{self.userScrolled_filter}')
                self.userScrolled_filter = True
            else:
                # print(f'filter{self.userScrolled_filter}')
                self.userScrolled_filter = False
        except Exception as e:
            logging.error(f"Error in handleScroll: {e}")

    # 최대 줄 수 제한 ##v5.0.2 #1 rxData GUI멈춤이슈 개선 코드
    def removeOldLines(self, textEdit):
        cursor = textEdit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        for _ in range(self.REMOVE_LINES):
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.deleteChar()  # Remove the newline character
            
    def saveLog(self):
        try:
            filePath, _ = QFileDialog.getSaveFileName(self, "Save Rx Data", "", "Text Files (*.txt);;All Files (*)")
            if filePath:
                with open(filePath, 'w') as file:
                    file.write(self.rxData.toPlainText())
                QMessageBox.information(self, "Success", "Rx Data has been saved successfully.")
        except Exception as e:
            logging.error(f"Error in saveLog: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred while saving the data: {e}")

    def viewLogDirectory(self):
        try:
            log_dir = os.path.realpath(self.defaultLogFolderPath)
            if os.path.isdir(log_dir):
                if sys.platform == 'win32':
                    os.startfile(log_dir)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', log_dir])
                else:
                    subprocess.Popen(['xdg-open', log_dir])
        except Exception as e:
            logging.error(f"Error in viewLogDirectory: {e}")
            
    def viewSystemLog(self):
        try:
            if os.path.exists(log_file_path):
                if sys.platform == 'win32':
                    os.startfile(log_file_path)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', log_file_path])
                else:
                    subprocess.Popen(['xdg-open', log_file_path])
            else:
                QMessageBox.warning(self, "Warning", "Log file does not exist.")
        except Exception as e:
            logging.error(f"Error in viewSystemLog: {e}")


    def saveWindowSettings(self, event):
        try:
            self.saveSettings()
            logging.debug("Window settings saved.")
        except Exception as e:
            logging.error(f"Error in saveWindowSettings: {e}")
        event.accept()

    def closeEvent(self, event):
        try:
            if self.autoLogging and hasattr(self, 'autoLogFile'):
                self.autoLogFile.close()
            self.saveSettings()
            logging.debug("closeEvent Saved settings")
            if hasattr(self, 'serialPort') and self.serialPort.is_open:
                self.serialPort.close()
            QApplication.quit()  # 명시적으로 QApplication 종료
        except Exception as e:
            logging.error(f"Error in closeEvent: {e}")
        event.accept()

    def clearRxData(self):
        try:
            self.rxData.clear()
        except Exception as e:
            logging.error(f"Error in clearRxData: {e}")

    def clearFilteredData(self):
        try:
            self.filteredRxData.clear()
        except Exception as e:
            logging.error(f"Error in clearFilteredData: {e}")

    def setTheme(self, theme):
        self.currentTheme = theme
        self.applyTheme()
        self.saveSettings()
        logging.debug(f'Saved Theme {theme}')

    def applyTheme(self):
        try:
            if self.currentTheme == 'dark':
                self.setStyleSheet("""
                    QMainWindow {
                        background-color: #000000;
                        color: #ffffff;
                    }
                    QMainWindow::title {
                        background-color: #000000;
                        color: #ffffff;
                    }
                    QLineEdit, QLabel {
                        background-color: #000000;
                        color: #ffffff;
                    }
                    QTextEdit{
                        background-color: #1A1A1A;
                        color: #ffffff;
                    }
                    QPushButton, QComboBox {
                        background-color: #2F2F2F;
                        color: #ffffff;
                    }
                    QMenuBar {
                        background-color: #F3F3F3;
                        color: #000000;
                    }
                    QMenu, QAction {
                        background-color: #1F1F1F;
                        color: #ffffff;
                    }
                    QMenu::item:selected {
                        background-color: #3F3F3F;
                    }
                    QSplitter::handle {
                        background-color: #888888;
                        width: 10px;
                        border: 1px solid #ffffff;
                    }
                    QSplitter::handle:horizontal {
                        height: 100%;
                    }
                    QSplitter::handle:vertical {
                        width: 100%;
                    }
                """)
            elif self.currentTheme == 'gray': # v2.0.5
                self.setStyleSheet("""
                    QMainWindow {
                        background-color: #525252;
                        color: #ffffff;
                    }
                    QMainWindow::title {
                        background-color: #525252;
                        color: #ffffff;
                    }
                    QTextEdit, QLineEdit, QLabel {
                        background-color: #525252;
                        color: #ffffff;
                    }
                    QPushButton, QComboBox {
                        background-color: #3D3D3D;
                        color: #ffffff;
                    }
                    QMenuBar {
                        background-color: #D3D3D3;
                        color: #000000;
                    }
                    QMenu, QAction {
                        background-color: #3D3D3D;
                        color: #ffffff;
                    }
                    QMenu::item:selected {
                        background-color: #5D5D5D;
                    }
                    QSplitter::handle {
                        background-color: #696969;
                        width: 10px;
                        border: 1px solid #000000;
                    }
                    QSplitter::handle:horizontal {
                        height: 100%;
                    }
                    QSplitter::handle:vertical {
                        width: 100%;
                    }
                """)
            else:
                self.setStyleSheet("")
        except Exception as e:
            logging.error(f"Error in applyTheme: {e}")

    def showVersionInfo(self):
        try:
            version_info_lines = [
                f"X-jera Term Version: {__version__}\n\n\n",
                "v5.0.5:\n\n  #1_Comport 순단 될 시 기존 Comport Reconnect 기능 추가\n\n",
                "v5.0.4:\n\n  #1_특정문자 카운트 기능 최대치 증가\n 특정문자열카운트 입력칸 비울시 Count 초기화 기능 추가\n 특정문자열 1회이상 카운트 될 시 LastMemory 저장 \n\n",
                "v5.0.3:\n\n  #1_특정문자 카운트 기능 추가\n  #2_RxData중복 bug fix\n  #3_GUI엔진변경 상업적사용가능 모듈(PySide6)\n\n",
                "v5.0.2:\n\n  #1_장기방치시 rxData GUI멈춤이슈 개선 코드 추가\n\n",
                "v5.0.1:\n\n  #1_UpdateCheck메뉴 추가\n  #2_설치프로그램적용배포\n\n",
                "v5.0.0:\n\n  #1_GUI엔진 업그레이드(PyQt5->PyQt6)\n  #2_Filtered Rx Data Export 메뉴 추가\n  #3_AnsiCode 전체색변경으로 변경 \n  #4_키핸들링 로직변경\n\n",
                "v4.0.4:\n\n  #1_시스템 폰트 설정메뉴 추가                                                   .\n\n",
                "v4.0.3:\n\n  #1_Filtered Data Window 스크롤 이벤트 추가\n  #2_Info > visitGitHub추가\n\n",
                "v4.0.2:\n\n  Filtered Rxdata Ansi 적용 및 로그에서 ansi 코드 제거후 저장 \n 스크롤 사이드 이슈 fix \n 테마변경 하위메뉴로 변경 \n\n",
                "v4.0.1:\n\n  ModelSelect 삭제 ANSI Escape코드 적용 코드 추가 \n\n",
                "v4.0.0:\n\n  KGM 로그 호환 추가 \n Settings - Prefrences - ModelSelect 에서 Chery or KGM 선택 \n KGM로그는 HTML 코드로 색상 표시 기능이있음 \n\n",
                "v3.0.0:\n\n  TxData 입력시 Enter키 선 입력 추가\n debuglog 추가 \n 실험실 추가\n -MCU Information, LOG DETECT RESET(초기화이슈검증용), AlertSet(특정 로그 확인시 알람)  \nCtrl + C로 복사 기능 Fix (v2.0.3 Focus 설정 일부 롤백)\n\n",
                "v2.0.5:\n\n  Toggle Theme 에 Gray 테마 추가_사용자요청사항\n\n",
                "v2.0.4:\n\n  사용자편의 증가를 위한 Txinputbox Language Set_report.Ryan\n\n",
                "v2.0.3:\n\n  사용자편의 증가를 위한 Focus 설정 추가 _report.Ryan\n\n",
                "v2.0.1:\n\n  Issue & Suggest 메뉴 추가 \n\n",
                "v2.0.0:\n\n  필터 내 [ ] 와 같은 특수문자 처리 추가\n- 대량 데이터 처리시 버그 수정\n- OnlineUpdate 추가\n\n",
                "v1.0.0:\n\n  XjeraTerm 구현\n- 필터 Tx Favorite 추가\n\n"
            ]

            version_info = "".join(version_info_lines)
            current_version_info = version_info_lines[1]

            msg_box = QMessageBox(self)
            msg_box.setStyleSheet("background-color: #FFFFFF; color: #000000;")  # 다크 모드 해제
            msg_box.setWindowTitle(f"Version Info__{__version__}")
            msg_box.setText(current_version_info)
            msg_box.setDetailedText(version_info)  # 세부 정보 추가
            msg_box.setStyleSheet("QLabel{min-width: 500px; font-size: 20px; font-weight: bold;}")  # 폰트 크기 및 굵기 조절
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)

            msg_box.exec()
        except Exception as e:
            logging.error(f"Error in showVersionInfo: {e}")

    def exportFilteredData(self):
        try:
            filePath, _ = QFileDialog.getSaveFileName(self, "Save Filtered Rx Data", "", "Text Files (*.txt);;All Files (*)")
            if filePath:
                with open(filePath, 'w') as file:
                    file.write(self.filteredRxData.toPlainText())
                QMessageBox.information(self, "Success", "Filtered Rx Data has been exported successfully.")
        except Exception as e:
            logging.error(f"Error in exportFilteredData: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred while exporting the data: {e}")

    # v3.0.0 포커스 이동으로 Ctrl C 복사 기능 제한되어 롤백
    # def eventFilter(self, source, event): # v2.0.3 
    #     try:
    #         if event.type() == QtCore.QEvent.WindowActivate:
    #             self.txInput.setFocus()  # 창이 활성화될 때 txInput에 포커스 설정
    #     except Exception as e:
    #         logging.error(f"Error in eventFilter: {e}")
    #     return super().eventFilter(source, event)

    def showMCULOGDetectCanTriggerDialog(self):
        try:
            print(self.canch_entry_value)
            print(self.bustype_entry_value)
            logging.debug("Opening MCULOGDetectCanTriggerDialog")
            self.MCULOGDetectCanTriggerDialog = MCULOGDetectCanTriggerDialog(self)
            self.MCULOGDetectCanTriggerDialog.show()
            if not hasattr(self, 'canch_entry_value') or not hasattr(self, 'bustype_entry_value'):
                raise RuntimeError("CAN settings are not initialized.")
        except Exception as e:
            logging.error(f"Error in showMCULOGDetectCanTriggerDialog: {e}")

    def showAlertSettingsDialog(self):
        try:
            logging.debug("Opening AlertSettingsDialog")
            self.alertSettingsDialog = AlertSettingsDialog(self)
            self.alertSettingsDialog.show()
        except Exception as e:
            logging.error(f"Error in showAlertSettingsDialog: {e}")

    def showMCUInformationDialog(self):
        try:
            print(self.canch_entry_value)
            print(self.bustype_entry_value)
            logging.debug("Opening MCUInformationDialog")
            if self.MCUInformationDialog is None:
                self.MCUInformationDialog = MCUinfomationDialog(self)  # 다이얼로그를 한 번만 생성
            if not hasattr(self, 'canch_entry_value') or not hasattr(self, 'bustype_entry_value'):
                raise RuntimeError("CAN settings are not initialized.")
            self.MCUInformationDialog.show()
        except Exception as e:
            logging.error(f"Error in showMCUInformationDialog: {e}")

#v4.0.3 #2
    def visitGitHub(self):
        try:
            webbrowser.open('https://github.com/byeonggonkang/XjeraTerm')
        except Exception as e:
            logging.error(f"Error in visitGitHub: {e}")

            
if __name__ == '__main__':
    try:
        logging.debug("Starting application")
        
        ##v4.0.4 소장님 컴퓨터 시스템 폰트 작아지는 문제 해결
        
        app = QApplication(sys.argv)
        # Qt의 고해상도 DPI 설정
        app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        
                # 기본 폰트 설정
        default_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
        default_font.setPointSize(12)  # 원하는 크기로 조절
        app.setFont(default_font)
        
        mainWindow = MainWindow()
        mainWindow.show()
        sys.exit(app.exec())
    except Exception as e:
        logging.critical(f"Critical error: {e}")
        app.quit()  # 명시적으로 QApplication 종료