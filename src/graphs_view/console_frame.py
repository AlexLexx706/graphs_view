#!/usr/bin/python
# -*- coding: utf-8 -*-

from PyQt5 import QtCore
from PyQt5 import QtWidgets, QtCore, QtGui
from .settings import Settings


class ConsoleFrame(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()
        self.combo_box_cmd = QtWidgets.QComboBox()
        self.combo_box_cmd.setEditable(True)
        self.combo_box_cmd.setToolTip(
            "Enter a new command and press the Enter button to send "
            "(includes command history).")

        self.combo_box_line_ending = QtWidgets.QComboBox()
        self.combo_box_line_ending.addItem("No Line ending", b'')
        self.combo_box_line_ending.addItem("New Line", b'\n')
        self.combo_box_line_ending.addItem("Carriage Return", b'\r')
        self.combo_box_line_ending.addItem("Both NL & CR", b'\n\r')
        self.combo_box_line_ending.currentIndexChanged.connect(
            self.on_line_ending_changed)
        index = Settings.value("line_ending_index")
        self.combo_box_line_ending.setCurrentIndex(int(index) if index else 1)

        self.push_button_send = QtWidgets.QPushButton("Send")
        self.push_button_send.setToolTip("Send command to port.")
        self.cmd_queue = None
        self.combo_box_cmd.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed)

        self.push_button_send.setSizePolicy(
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Fixed)

        v_box_layout = QtWidgets.QVBoxLayout(self)
        h_box_layout = QtWidgets.QHBoxLayout()
        v_box_layout.addLayout(h_box_layout)

        h_box_layout.addWidget(self.combo_box_cmd)
        h_box_layout.addWidget(self.combo_box_line_ending)

        self.plain_text_editor = QtWidgets.QPlainTextEdit()
        self.plain_text_editor.setToolTip(
            "Displays incoming stream from the COM port.")
        self.plain_text_editor.setReadOnly(True)
        v_box_layout.addWidget(self.plain_text_editor)
        self.set_cmd_queue(None)

        self.clear_action = QtWidgets.QAction("Clear")
        self.plain_text_editor.addAction(self.clear_action)
        self.clear_action.triggered.connect(self.on_clear_history)
        self.plain_text_editor.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.ActionsContextMenu)
        self.combo_box_cmd.lineEdit().editingFinished.connect(self.on_line_changed)
        self.combo_box_cmd.currentIndexChanged.connect(
            self.on_currentIndexChanged)

        commands = Settings.value("commands")
        last_commands_index = Settings.value("last_commands_index")

        if commands is not None and last_commands_index is not None:
            last_block = self.combo_box_cmd.blockSignals(True)
            self.combo_box_cmd.addItems(commands)
            self.combo_box_cmd.setCurrentIndex(int(last_commands_index))
            self.combo_box_cmd.blockSignals(last_block)

        history = Settings.value("history")
        if history:
            self.plain_text_editor.setPlainText(history)

        self.remove_action = QtWidgets.QAction("Remove")
        self.combo_box_cmd.addAction(self.remove_action)
        self.remove_action.triggered.connect(self.on_remove_item)

        self.remove_all_action = QtWidgets.QAction("Remove All")
        self.combo_box_cmd.addAction(self.remove_all_action)
        self.remove_all_action.triggered.connect(self.on_remove_all_item)

        self.combo_box_cmd.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.ActionsContextMenu)

    def on_line_ending_changed(self, index):
        Settings.setValue("line_ending_index", index)

    def on_remove_all_item(self):
        if QtWidgets.QMessageBox.question(
            self,
            'Remove all commands',
            "Are you sure you want to remove all items?") ==\
                QtWidgets.QMessageBox.StandardButton.Yes:
            self.combo_box_cmd.clear()

    def on_remove_item(self):
        self.combo_box_cmd.removeItem(
            self.combo_box_cmd.currentIndex())

    def on_clear_history(self):
        self.plain_text_editor.clear()
        Settings.setValue("history", "")

    def set_cmd_queue(self, cmd_queue):
        self.cmd_queue = cmd_queue
        self.setEnabled(bool(self.cmd_queue))

    def on_line_changed(self):
        line = self.combo_box_cmd.currentText()
        self.send_line(line)

    def send_line(self, line):
        if self.cmd_queue:
            line_ending = self.combo_box_line_ending.itemData(
                self.combo_box_line_ending.currentIndex())

            cursor = QtGui.QTextCursor(self.plain_text_editor.document())
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            cursor.insertText(line + ("" if not line_ending else '\n'))
            self.plain_text_editor.moveCursor(
                QtGui.QTextCursor.MoveOperation.End)

            Settings.setValue("history", self.plain_text_editor.toPlainText())
            data = line.encode() + line_ending
            self.cmd_queue.put(data)

    def on_currentIndexChanged(self, index):
        Settings.setValue(
            "commands",
            [self.combo_box_cmd.itemText(index) for index in range(self.combo_box_cmd.count())])
        Settings.setValue("last_commands_index",
                          self.combo_box_cmd.currentIndex())

    def on_new_line(self, line):
        cursor = QtGui.QTextCursor(self.plain_text_editor.document())
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        cursor.insertText(line.decode())
        self.plain_text_editor.moveCursor(QtGui.QTextCursor.MoveOperation.End)
