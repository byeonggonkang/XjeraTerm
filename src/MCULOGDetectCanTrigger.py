from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QTextEdit, QHBoxLayout, QLabel
import threading
import time
import can
import CAN_Contents
import os
import sys

class MCULOGDetectCanTriggerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MCULOGDetectCanTrigger_Xjera")
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
        self.running = False
        self.current_thread = None
        self.parent = parent
        self.initUI()
        self.loadSettings()  # 설정 로드
        

    def initUI(self):
        layout = QVBoxLayout(self)

        # Console log area
        self.log_area = QTextEdit(self)
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)

        # Target string input
        form_layout = QFormLayout()
        # self.canch_entry = QLineEdit(self)
        # self.bustype_entry = QComboBox(self)
        # self.bustype_entry.addItems(["vector", "kvaser"])
        self.target_string_entry = QLineEdit(self)
        self.ConfigurationCode_entry = QLineEdit(self)
        self.VIN_entry = QLineEdit(self)
        
        # form_layout.addRow('CAN Channel:', self.canch_entry)
        # form_layout.addRow('Bus Type:', self.bustype_entry)
        form_layout.addRow('Target String:', self.target_string_entry)
        form_layout.addRow('ConfigurationCode', self.ConfigurationCode_entry)
        form_layout.addRow('VIN', self.VIN_entry)

        layout.addLayout(form_layout)

        button_layout = QHBoxLayout()
        self.monitor_button = QPushButton('Start Monitoring', self)
        self.monitor_button.clicked.connect(self.on_start_monitoring)
        button_layout.addWidget(self.monitor_button)

        self.stop_button = QPushButton('Stop Monitoring', self)
        self.stop_button.clicked.connect(self.on_stop)
        button_layout.addWidget(self.stop_button)

        layout.addLayout(button_layout)

        # Running status label
        self.status_label = QLabel('Status: Stopped', self)
        layout.addWidget(self.status_label)

    def loadSettings(self):
        try:
            settings_path = os.path.join(os.path.dirname(sys.executable), 'env_set.txt')
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as file:
                    settings = dict(line.strip().split('=', 1) for line in file)
                    self.target_string_entry.setText(settings.get('target_string_entry', ''))
                    self.ConfigurationCode_entry.setText(settings.get('ConfigurationCode_entry', ''))
                    self.VIN_entry.setText(settings.get('VIN_entry', ''))
                    print(f'Settings loaded: {settings_path}')
        except Exception as e:
            print(f"Error in loadSettings: {e}")

    def log(self, message):
        self.log_area.append(message)
        # print(message)

    def send_can_messages(self, messages):
        try:
            can_channel = int(self.parent.canch_entry_value) - 1
            bus = can.interface.Bus(channel=can_channel, bustype=self.parent.bustype_entry_value, app_name='CANoe', bitrate=500000, fd=False)
            print(can_channel, bus)
            for msg in messages:
                bus.send(msg)
                print(msg)
                time.sleep(0.01)
            print(f"Message sent successfully ch: {bus}")
        except can.CanError as e:
            print(f"CAN Error: {e}")
        except ValueError as e:
            print(f"Invalid channel number: {e}")
        finally:
            if 'bus' in locals():
                bus.shutdown()

    def send_vinwrite(self, data):
        # 첫 프레임 전송
        data = [int(data[i:i+2], 16) for i in range(0, len(data), 2)]
        print(data)
        print(type(data))
        first_frame_data = [0x10, len(data)+3, 0x2E, 0xf1, 0x90] + data[:3]
        first_frame = can.Message(arbitration_id=CAN_Contents.diag_req_id, data=first_frame_data, is_extended_id=False)
        self.send_can_messages([first_frame])
        time.sleep(0.03)

        # # FC.CTS 프레임 처리
        fc_cts_frame = can.Message(arbitration_id=CAN_Contents.diag_req_id, data=[0x30, 0x08, 0x14], is_extended_id=False)
        self.send_can_messages([fc_cts_frame])
        time.sleep(0.03)

        # 연속 프레임 전송
        remaining_data = data[3:]
        sequence_number = 1
        while remaining_data:
            chunk = remaining_data[:7]
            remaining_data = remaining_data[7:]
            consecutive_frame_data = [0x20 + sequence_number] + chunk
            consecutive_frame = can.Message(arbitration_id=CAN_Contents.diag_req_id, data=consecutive_frame_data, is_extended_id=False)
            self.send_can_messages([consecutive_frame])
            sequence_number = (sequence_number + 1) % 16
            time.sleep(0.1)
        return True

    def send_configwrite(self, data):
        # 첫 프레임 전송
        data = [int(data[i:i+2], 16) for i in range(0, len(data), 2)]
        print(data)
        print(type(data))
        first_frame_data = [0x10, len(data)+3, 0x2E, 0xd0, 0x09] + data[:3]
        first_frame = can.Message(arbitration_id=CAN_Contents.diag_req_id, data=first_frame_data, is_extended_id=False)
        self.send_can_messages([first_frame])
        time.sleep(0.03)
        
        # # FC.CTS 프레임 처리
        fc_cts_frame = can.Message(arbitration_id=CAN_Contents.diag_req_id, data=[0x30, 0x00, 0x00], is_extended_id=False)
        self.send_can_messages([fc_cts_frame])
        time.sleep(0.03)

        # 연속 프레임 전송
        remaining_data = data[3:]
        sequence_number = 1
        while remaining_data:
            chunk = remaining_data[:7]
            remaining_data = remaining_data[7:]
            consecutive_frame_data = [0x20 + sequence_number] + chunk
            consecutive_frame = can.Message(arbitration_id=CAN_Contents.diag_req_id, data=consecutive_frame_data, is_extended_id=False)
            self.send_can_messages([consecutive_frame])
            sequence_number = (sequence_number + 1) % 16
            time.sleep(0.1)
        return True

    def send_ExtdSession(self):
        messages = [
            can.Message(arbitration_id=CAN_Contents.diag_req_id, data=CAN_Contents.diagExtendedSession, is_extended_id=False)
        ]
        self.send_can_messages(messages)

    def send_keyReq(self):
        messages = [
            can.Message(arbitration_id=CAN_Contents.diag_req_id, data=CAN_Contents.diagkeyReq, is_extended_id=False)
        ]
        self.send_can_messages(messages)

    def send_keysend(self):
        messages = [
            can.Message(arbitration_id=CAN_Contents.diag_req_id, data=CAN_Contents.diagkeysend, is_extended_id=False)
        ]
        self.send_can_messages(messages)

    def send_vinread(self):
        messages = [
            can.Message(arbitration_id=CAN_Contents.diag_req_id, data=CAN_Contents.diagVinread, is_extended_id=False)
        ]
        self.send_can_messages(messages)

    def send_configread(self):
        messages = [
            can.Message(arbitration_id=CAN_Contents.diag_req_id, data=CAN_Contents.diagconfigread, is_extended_id=False)
        ]
        self.send_can_messages(messages)

    def send_partnumread(self):
        messages = [
            can.Message(arbitration_id=CAN_Contents.diag_req_id, data=CAN_Contents.diagpartnumread, is_extended_id=False)
        ]
        self.send_can_messages(messages)

    def send_t1npartnumread(self):
        messages = [
            can.Message(arbitration_id=CAN_Contents.diag_req_id, data=CAN_Contents.diagt1npartnumread, is_extended_id=False)
        ]
        self.send_can_messages(messages)

    def send_reset(self):
        messages = [
            can.Message(arbitration_id=CAN_Contents.diag_req_id, data=CAN_Contents.diagreset, is_extended_id=False)
        ]
        self.send_can_messages(messages)

    def on_stop(self):
        self.running = False
        self.status_label.setText('Status: Stopped')

    def monitor_comport(self, target_string):
        self.log("Monitoring started.\n")
        self.log(f'canch: {self.parent.canch_entry_value}\n')
        self.log(f'bustype: {self.parent.bustype_entry_value}\n')
        while self.running:
            try:
                processed_data = self.parent.getProcessedData()
                if processed_data:
                    processed_data_str = '\n'.join(processed_data)
                    lines = processed_data_str.split('\n')
                    print (lines)
                    for line in lines:
                        if line.strip():
                            # self.log(f"Received: {line.strip()}\n")
                            if target_string in line:
                                self.log(f"Target string '{target_string}' found in received data.\n")
                                self.send_ExtdSession()
                                time.sleep(0.2)
                                self.send_keyReq()
                                time.sleep(0.2)
                                self.send_keysend()
                                time.sleep(0.2)
                                self.send_configwrite(self.ConfigurationCode_entry.text())
                                time.sleep(0.2)
                                self.send_vinwrite(self.VIN_entry.text())
                                time.sleep(0.4)
                                self.send_vinread()
                                time.sleep(0.2)
                                self.send_configread()
                                time.sleep(0.2)
                                self.send_partnumread()
                                time.sleep(0.2)
                                self.send_t1npartnumread()
                                time.sleep(0.2)
                                self.send_reset()
                                time.sleep(0.2)
                                self.log("Sequence sent.\n")
                    if len(self.parent.processedData) > 5:  # 리스트 길이 제한
                        self.parent.processedData.pop(0)
                time.sleep(0.1)
            except Exception as e:
                self.log(f"Error: {e}")
                self.running = False
                self.status_label.setText('Status: Stopped')

    def on_start_monitoring(self):
        if self.running:
            self.on_stop()
            if self.current_thread is not None:
                self.current_thread.join()  # Ensure the thread has stopped before starting a new one
        self.running = True
        if self.parent and hasattr(self.parent, 'saveSettings'):
            self.parent.saveSettings()  # parent의 saveSettings 메서드 호출
        self.status_label.setText('Status: Running')
        self.current_thread = threading.Thread(target=self.monitor_comport, args=(self.target_string_entry.text(),))
        self.current_thread.daemon = True
        self.current_thread.start()

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent: ##530,230
            parent_pos = self.parent.pos()
            parent_size = self.parent.size()
            self.move(parent_pos.x() - 530, parent_pos.y())