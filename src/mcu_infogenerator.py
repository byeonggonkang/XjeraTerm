from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QTextEdit
from can.interfaces.vector.exceptions import VectorInitializationError
import can
import CAN_Contents
import Configration_Code
import time

class MCUinfomationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MCU Information")
        self.setGeometry(100, 100, 550, 230)
        self.parent = parent
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        self.text_box = QTextEdit(self)
        self.refresh_button = QPushButton("REFRESH", self)
        self.refresh_button.clicked.connect(self.refresh_info)
        # 스타일 시트 추가
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #000000;
            }
            QPushButton:hover {
                background-color: #CCCCCC;
                color: #000000;
            }
        """)
        
        layout.addWidget(self.text_box)
        layout.addWidget(self.refresh_button)
        
        self.refresh_info()

    def refresh_info(self):
        mcu_info = get_mcu_information(self)
        self.text_box.setPlainText(
        f"canch: {self.parent.canch_entry_value}   "
        f"bustype: {self.parent.bustype_entry_value}\n"
        f"Software Version Number: {mcu_info['software_version']}\n"
        f"HardWare Version Number: {mcu_info['hardware_version']}\n"
        f"Part Number: {mcu_info['part_number']}\n"
        f"Config Code: {mcu_info['config_code']}\n"
        f"Vin Number: {mcu_info['Vin_Number']}"
        )
        
    def showEvent(self, event):
        super().showEvent(event)
        if self.parent:  # 550,230
            parent_pos = self.parent.pos()
            parent_size = self.parent.size()
            self.move(parent_pos.x() - 550, parent_pos.y())

def get_mcu_information(dialog):
    # mcu_version = get_mcu_version()
    software_version = get_version_from_can(dialog, "Software Version Number")
    hardware_version = get_version_from_can(dialog, "HardWare Version Number")
    part_number = get_version_from_can(dialog, "Part Number")
    config_code = get_version_from_can(dialog, "Config Code")
    Vin_Number = get_version_from_can(dialog, "Vin Number")

    return {
        # 'mcu_version': mcu_version,
        'software_version': software_version,
        'hardware_version': hardware_version,
        'part_number': part_number,
        'config_code': config_code,
        'Vin_Number': Vin_Number
    }

def get_version_from_can(dialog, version_type):
    can_ch = int(dialog.parent.canch_entry_value) - 1
    can_bustype = dialog.parent.bustype_entry_value
    print(can_ch, can_bustype)

    try:
        bus = can.interface.Bus(channel=can_ch, bustype=can_bustype, app_name='CANoe', bitrate=500000)
    except VectorInitializationError:
        return "Check CAN communication."
    
    if version_type == "Software Version Number":
        message = can.Message(arbitration_id=CAN_Contents.diag_req_id, data=CAN_Contents.diagSwVerread, is_extended_id=False)
    elif version_type == "HardWare Version Number":
        message = can.Message(arbitration_id=CAN_Contents.diag_req_id, data=CAN_Contents.diagHwVerread, is_extended_id=False)
    elif version_type == "Part Number":
        message = can.Message(arbitration_id=CAN_Contents.diag_req_id, data=CAN_Contents.diagpartnumread, is_extended_id=False)
    elif version_type == "Config Code":
        message = can.Message(arbitration_id=CAN_Contents.diag_req_id, data=CAN_Contents.diagconfigread, is_extended_id=False)
    elif version_type == "Vin Number":
        message = can.Message(arbitration_id=CAN_Contents.diag_req_id, data=CAN_Contents.diagVinread, is_extended_id=False)
    
    bus.send(message)
    print(f"DEBUG: Sent message: {message}")

    start_time = time.time()
    timeout = 2.0  # Increase timeout to 1 second
    response_data = ""
    total_length = 0
    expected_sn = 1
    while time.time() - start_time < timeout:
        msg = bus.recv(timeout=2)
        if msg:
            if msg.arbitration_id == CAN_Contents.diag_res_id:
                print(f"Received message: {msg}")
                if (msg.data[0] >> 4) == 0x1 or msg.data[0] == 0x10:  # FF frame
                    total_length = ((msg.data[0] & 0x0F) << 8) + msg.data[1]
                    response_data = msg.data[2:].hex()
                    print(f"FF Frame detected. Total length: {total_length}, Data: {response_data}")
                    # CTS frame 처리
                    cts_message = can.Message(arbitration_id=CAN_Contents.diag_req_id, data=[0x30, 0x00, 0x00], is_extended_id=False)
                    bus.send(cts_message)
                    print(f"CTS Frame sent: {cts_message}")
                elif (msg.data[0] >> 4) == 0x2 or (0x21 <= msg.data[0] <= 0x25):  # CF frame
                    sn = msg.data[0] & 0x0F
                    if sn == expected_sn:
                        response_data += msg.data[1:].hex()
                        print(f"CF Frame detected. Data: {response_data}")
                        expected_sn = (expected_sn + 1) % 16
                    else:
                        print(f"CF Frame sequence number mismatch. Expected: {expected_sn}, Received: {sn}")
                        break
                else:
                    response_data = msg.data.hex()
                    print(f"Single Frame detected. Data: {response_data}")
                    total_length = len(response_data) // 2  # Update total_length for single frame
                if total_length > 0 and len(response_data) >= total_length * 2:
                    break
        else:
            continue
    if response_data:
        # 앞의 3바이트 제거
        response_data = response_data[6:]
        print(f'version_type: {version_type}')
        print(f"DEBUG: Processed response data: {response_data}")
        if version_type == "Config Code":
            # 뒤의 12개의 바이트가 0이면 무시
            if response_data[-12:] == '0' * 12:
                response_data = response_data[:-12]
            print(f"DEBUG: Trimmed response data: {response_data}")
            for model, codes in Configration_Code.Configration_Code.items():
                for config_name, config_code in codes.items():
                    config_code_hex = config_code.hex()
                    if config_code_hex[-12:] == '0' * 12:
                        print(f'@@config_code_hex[-12:] == 0 * 12')
                        config_code_hex = config_code_hex[:-12]
                        if not len(config_code_hex) == 64:
                            config_code_hex = config_code_hex.ljust(64, '0')
                    if response_data == config_code_hex:
                        print(f"@@response_data == config_code_hex")
                        print(f"DEBUG: Padded config code: {config_code_hex}")
                        print(f"DEBUG: Comparing with config code: {model}-{config_name}, {config_code_hex}")
                        print(f"Codematched: {model} - {config_name}")
                        bus.shutdown()
                        return f"{model} - {config_name}"
                    else:
                        print(f'@@else')
                        print(f'config_code_hex \n{type(config_code_hex)} \n{config_code_hex} \nresponse_data \n{type(response_data)} \n{response_data}')
                        print(f"Code not matched. {response_data}")
            bus.shutdown()
            return response_data
            
        if version_type == "Vin Number":
            print(f"Response Data (Hex): {response_data}")
            return response_data
        ascii_data = hex_to_ASCII(response_data)
        print(f"Response Data (ASCII): {ascii_data}")
        bus.shutdown()
        return ascii_data
    print("Timeout reached, stopping reception.")
    bus.shutdown()
    return "No response received from CAN bus."

def hex_to_ASCII(hex_data):
    bytes_object = bytes.fromhex(hex_data)
    ascii_data = bytes_object.decode("utf-8", errors="replace")
    ascii_data = ''.join(char for char in ascii_data if char.isprintable())
    return ascii_data.strip()