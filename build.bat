pyinstaller --windowed --onefile --name "XjeraTerm" --hidden-import=can.interfaces.vector --hidden-import=can.interfaces.kvaser --add-data "XjeraTerm.ico;." --add-data "src/alert.wav;." --icon=XjeraTerm.ico src/XjeraTerm.py

pause