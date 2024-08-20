#!/usr/bin/python
# -*- coding: utf-8 -*-

import signal
from PyQt5 import QtWidgets
from . import GraphsView

def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QtWidgets.QApplication([])
    graphs_view = GraphsView()
    graphs_view.show()
    app.exec()


if __name__ == "__main__":
    main()