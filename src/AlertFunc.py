from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QComboBox, QHBoxLayout, QPushButton, QMessageBox, QTextEdit
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6 import QtCore
from PyQt6.QtCore import QThread
import threading
import os
import sys

class AlertSettingsDialog(QDialog):
    alertTriggered = QtCore.pyqtSignal(str)  # 팝업 발생 트리거 시그널 추가

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Alert Settings")
        self.setGeometry(100, 100, 530, 230)
        # 스타일 시트 추가
        self.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #000000;
            }
            QPushButton:hover {
                background-color: #CCCCCC;
                color: #000000;
            }
        """)
        self.alertstatus = False
        self.alert_current_thread = None
        self.parent = parent
        self.alertSound = QSoundEffect()
        self.alertSound.setSource(QtCore.QUrl.fromLocalFile("alert.wav"))
        self.stop_event = threading.Event()
        # self.popup_shown = False
        self.initUI()
        self.loadSettings()  # 설정 로드

    def initUI(self):
        layout = QVBoxLayout(self)

        self.log_area = QTextEdit(self)
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)

        self.alertTextLabel = QLabel("Alert Text:")
        self.alertTextInput = QLineEdit(self)
        layout.addWidget(self.alertTextLabel)
        layout.addWidget(self.alertTextInput)

        self.alertTypeLabel = QLabel("Alert Type:")
        self.alertTypeComboBox = QComboBox()
        self.alertTypeComboBox.addItems(["Popup", "Beep", "Popup + Beep"])
        layout.addWidget(self.alertTypeLabel)
        layout.addWidget(self.alertTypeComboBox)

        button_layout = QHBoxLayout()
        self.enableButton = QPushButton('Start Monitoring', self)
        self.enableButton.clicked.connect(self.on_start)

        self.disableButton = QPushButton('Stop Monitoring', self)
        self.disableButton.clicked.connect(self.on_stop)

        button_layout.addWidget(self.enableButton)
        button_layout.addWidget(self.disableButton)

        layout.addLayout(button_layout)

        self.status_label = QLabel('Status: Stopped', self)
        layout.addWidget(self.status_label)

    def loadSettings(self):
        try:
            settings_path = os.path.join(os.path.dirname(sys.executable), 'env_set.txt')
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as file:
                    settings = dict(line.strip().split('=', 1) for line in file)
                    self.alertTextInput.setText(settings.get('alertTextInput', ''))
                    self.alertTypeComboBox.setCurrentText(settings.get('alertTypeComboBox', 'Popup'))
        except Exception as e:
            print(f"Error in loadSettings: {e}")

    def log(self, message):
        self.log_area.append(message)
        print(message)

    def on_stop(self):
        self.alertstatus = False
        self.status_label.setText('Status: Stopped')
        # self.popup_shown = False
        if self.alert_current_thread is not None:
            self.stop_event.set()
            self.alert_current_thread.join()

    def monitor_comport(self, target_string, alertType):
        self.log("Monitoring for Alert Text Start!!\n")
        while self.alertstatus and not self.stop_event.is_set():
            try:
                processed_data = self.parent.getProcessedData()
                if processed_data:
                    processed_data_str = '\n'.join(processed_data)
                    lines = processed_data_str.split('\n')
                    print(lines)
                    for line in lines:
                        if line.strip():
                            if target_string in line:
                                self.log(f"Target string '{target_string}' found in received data.\n")
                                self.triggerAlert(alertType)
                                self.alertstatus = False
                                self.status_label.setText('Status: Stopped')
                                return  # triggerAlert 호출 후 for 루프 중단
                    if len(self.parent.processedData) > 5:  # 리스트 길이 제한
                        self.parent.processedData.pop(0)
                QThread.msleep(100)
            except Exception as e:
                self.log(f"Error in monitor_Str: {e}")
                self.alertstatus = False
                self.status_label.setText('Status: Stopped')

    def on_start(self):
        if self.alertstatus:
            self.on_stop()
            if self.alert_current_thread is not None:
                self.alert_current_thread.join()
        self.alertstatus = True
        self.status_label.setText('Status: Monitoring')
        self.stop_event.clear()
        if self.parent and hasattr(self.parent, 'saveSettings'):
            self.parent.saveSettings()  # parent의 saveSettings 메서드 호출
        self.alert_current_thread = threading.Thread(target=self.monitor_comport, args=(self.alertTextInput.text(), self.alertTypeComboBox.currentText()))
        self.alert_current_thread.daemon = True
        self.alert_current_thread.start()

    def triggerAlert(self, alertType):
        if not self.alertstatus:
            return
        if "Popup" in alertType :
            self.alertTriggered.emit(self.alertTextInput.text())  # 팝업 발생 트리거 시그널 발행
            # self.popup_shown = True
            QtCore.QMetaObject.invokeMethod(self, "showPopup", QtCore.Qt.ConnectionType.QueuedConnection)  # 메인 스레드에서 팝업 호출
        if "Beep" in alertType :
            # self.popup_shown = True
            self.alertSound.play()

    @QtCore.pyqtSlot()
    def showPopup(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Alert")
        msg_box.setText(f"Alert Text '{self.alertTextInput.text()}' detected!")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        # msg_box.buttonClicked.connect(self.resetPopupFlag)
        msg_box.exec()
        if self.parent:
            print(f"Parent exists: {self.parent}")
            if hasattr(self.parent, 'processedData'):
                print(f"Before clearing: {self.parent.processedData}")  # 리스트 비우기 전 상태 출력
                self.parent.processedData.clear()  # 팝업 표시 후 리스트 비우기
                print(f"After clearing: {self.parent.processedData}")  # 리스트 비운 후 상태 출력
            else:
                print("Parent does not have attribute 'processedData'")
        else:
            print("Parent is None")

    # def resetPopupFlag(self):
        # self.popup_shown = False  # 팝업 종료 시 플래그 초기화
        # print(self.popup_shown)

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent: ##530,230
            parent_pos = self.parent.pos()
            parent_size = self.parent.size()
            self.move(parent_pos.x() - 530, parent_pos.y())