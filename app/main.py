import sys
import os

# Ensure project imports work (dev и pyinstaller)
if getattr(sys, 'frozen', False):
    _base = sys._MEIPASS
else:
    _base = os.getcwd()
sys.path.insert(0, _base)

from PyQt6 import QtWidgets
from app.gui import PdfCheckerWindow


def main():
    app = QtWidgets.QApplication([])
    win = PdfCheckerWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
