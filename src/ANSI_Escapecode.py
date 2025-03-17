import re
from PySide6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor

def appendFormattedText(rxData, text):
    try:
        cursor = rxData.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # 전체 텍스트에 대한 기본 색상 설정
        default_format = QTextCharFormat()
        default_format.setForeground(QColor('#40A4A4'))  # 기본 텍스트 색상
        cursor.mergeCharFormat(default_format)

        format = QTextCharFormat()
        segments = re.split(r'(\x1b\[[0-9;]*m)', text)
        for segment in segments:
            if segment.startswith('\x1b[') and segment.endswith('m'):
                codes = segment[2:-1].split(';')
                for code in codes:
                    print(f'code: {code}')
                    # if code == '0':  # 기본 상태 (초기화)
                    #     format.setForeground(QColor('#40A4A4'))
                    #     format.setFontWeight(QFont.Weight.Normal)
                    if code == '1':  # 굵게
                        format.setFontWeight(QFont.Weight.Bold)
                    elif code == '2':  # 흐리게
                        format.setForeground(QColor('#70A4A4'))  # 기본 색보다 약간 연한 색
                    elif code == '3':
                        format.setFontItalic(True)
                    elif code == '4':
                        format.setFontUnderline(True)
                    elif code == '5':
                        format.setFontWeight(QFont.Weight.DemiBold)
                    elif code == '6':
                        format.setFontWeight(QFont.Weight.DemiBold)
                    elif code == '7':
                        format.setFontStrikeOut(True)
                    elif code == '8':
                        format.setFontWeight(QFont.Weight.Light)
                    elif code == '9':
                        format.setFontStrikeOut(True)
                    elif code == '10':
                        format.setFont(QFont('default'))
                    elif code == '11':
                        format.setFont(QFont('default'))
                    elif code == '12':
                        format.setFont(QFont('default'))
                    elif code == '13':
                        format.setFont(QFont('default'))
                    elif code == '14':
                        format.setFont(QFont('default'))
                    elif code == '15':
                        format.setFont(QFont('default'))
                    elif code == '16':
                        format.setFont(QFont('default'))
                    elif code == '17':
                        format.setFont(QFont('default'))
                    elif code == '18':
                        format.setFont(QFont('default'))
                    elif code == '19':
                        format.setFont(QFont('default'))
                    elif code == '20':
                        format.setFont(QFont('default'))
                    elif code == '21':
                        format.setFontWeight(QFont.Weight.Bold)
                    elif code == '22':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '23':
                        format.setFontItalic(False)
                    elif code == '24':
                        format.setFontUnderline(False)
                    elif code == '25':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '26':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '27':
                        format.setFontStrikeOut(False)
                    elif code == '28':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '29':
                        format.setFontStrikeOut(False)
                    elif code == '31':
                        format.setForeground(QColor('red'))
                    elif code == '32':
                        format.setForeground(QColor('green'))
                    elif code == '33':
                        format.setForeground(QColor('yellow'))
                    elif code == '34':
                        format.setForeground(QColor('blue'))
                    elif code == '35':
                        format.setForeground(QColor('magenta'))
                    elif code == '36':
                        format.setForeground(QColor('cyan'))
                    elif code == '38':
                        format.setForeground(QColor('default'))
                    elif code == '39':
                        format.setForeground(QColor('default'))
                    elif code == '41':
                        format.setBackground(QColor('red'))
                    elif code == '42':
                        format.setBackground(QColor('green'))
                    elif code == '43':
                        format.setBackground(QColor('yellow'))
                    elif code == '44':
                        format.setBackground(QColor('blue'))
                    elif code == '45':
                        format.setBackground(QColor('magenta'))
                    elif code == '46':
                        format.setBackground(QColor('cyan'))
                    elif code == '48':
                        format.setBackground(QColor('default'))
                    elif code == '49':
                        format.setBackground(QColor('default'))
                    elif code == '50':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '51':
                        format.setFontWeight(QFont.Weight.Bold)
                    elif code == '52':
                        format.setFontWeight(QFont.Weight.DemiBold)
                    elif code == '53':
                        format.setFontWeight(QFont.Weight.Bold)
                    elif code == '54':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '55':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '56':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '57':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '58':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '59':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '60':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '61':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '62':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '63':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '64':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '65':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '66':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '67':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '68':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '69':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '70':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '71':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '72':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '73':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '74':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '75':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '76':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '77':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '78':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '79':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '80':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '81':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '82':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '83':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '84':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '85':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '86':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '87':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '88':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '89':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '90':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '91':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '92':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '93':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '94':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '95':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '96':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '97':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '98':
                        format.setFontWeight(QFont.Weight.Normal)
                    elif code == '99':
                        format.setFontWeight(QFont.Weight.Normal)
            else:
                cursor.insertText(segment, format)
    except Exception as e:
        print(f"Error in appendFormattedText: {e}")