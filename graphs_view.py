#!/usr/bin/python
# -*- coding: utf-8 -*-

from PyQt5 import QtCore
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph
import serial
import threading
import time
import signal
from serial.tools import list_ports
import types
import multiprocessing
import queue
import re

Settings = QtCore.QSettings('alexlexx', 'graph_view')


def process_port(in_queue, out_queue, settings):
    try:
        with serial.Serial(**settings['serial']) as ser:
            is_string_parsing = settings['parsing_mode']
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            out_queue.put((0, time.time(), b''))
            state = types.SimpleNamespace(stop=False)

            def send_proc():
                try:
                    while 1:
                        data = in_queue.get()
                        # exit
                        if not data:
                            break
                        ser.write(data)
                finally:
                    state.stop = True

            send_thread = threading.Thread(target=send_proc)
            send_thread.start()

            r_state = 0
            # row mode
            if not is_string_parsing:
                while not state.stop:
                    packet = ser.read(100)
                    packet_time = time.time()
                    if packet:
                        out_queue.put((r_state, packet_time, packet))
                        r_state = 1
            # string parsing
            else:
                data = b''
                packet_time = time.time()
                while not state.stop:
                    symbol = ser.read(1)
                    # splitter detected
                    if symbol in b'\r\n':
                        if r_state != 1:
                            data = data.strip()
                            if data:
                                packet = (r_state, packet_time, data)
                                out_queue.put(packet)
                            data = b''
                        r_state = 1
                    # collecting data
                    else:
                        if r_state == 1:
                            packet_time = time.time()
                            r_state = 2
                        data += symbol
            send_thread.join()
    finally:
        out_queue.put(None)


class ParametersFrame(QtWidgets.QFrame):
    parameter_changed = QtCore.pyqtSignal(str)

    class ParameterFrame(QtWidgets.QFrame):
        value_changed = QtCore.pyqtSignal(str)
        state_changed = QtCore.pyqtSignal()

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.radio_button_select = QtWidgets.QRadioButton(self)
            self.line_edit_template = QtWidgets.QLineEdit(self)
            self.line_edit_template.setText(
                'set,/controller/heading_pid/p,{}')
            self.line_edit_template.textChanged.connect(self.on_state_changed)

            self.double_spin_box_min = QtWidgets.QDoubleSpinBox(self)
            self.double_spin_box_min.setMinimum(-10000000)
            self.double_spin_box_min.setMaximum(10000000)
            self.double_spin_box_min.setValue(0)
            self.double_spin_box_min.setDecimals(4)
            self.double_spin_box_min.valueChanged.connect(
                self.on_state_changed)

            self.double_spin_box_max = QtWidgets.QDoubleSpinBox(self)
            self.double_spin_box_max.setMinimum(-10000000)
            self.double_spin_box_max.setMaximum(10000000)
            self.double_spin_box_max.setValue(1000)
            self.double_spin_box_max.setDecimals(4)
            self.double_spin_box_max.valueChanged.connect(
                self.on_state_changed)

            self.double_spin_box_value = QtWidgets.QDoubleSpinBox(self)
            self.double_spin_box_value.setMinimum(
                self.double_spin_box_min.value())
            self.double_spin_box_value.setMaximum(
                self.double_spin_box_max.value())
            self.double_spin_box_value.setValue(0)
            self.double_spin_box_value.setSingleStep(0.01)
            self.double_spin_box_value.setDecimals(4)
            self.double_spin_box_min.valueChanged.connect(
                self.double_spin_box_value.setMinimum)
            self.double_spin_box_max.valueChanged.connect(
                self.double_spin_box_value.setMaximum)
            self.double_spin_box_value.valueChanged.connect(
                self.on_value_changed)
            self.double_spin_box_value.valueChanged.connect(
                self.on_state_changed)

            self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            self.slider.setMinimum(0)
            self.slider.setMaximum(100)
            self.slider.valueChanged.connect(self.on_slider_value_changed)
            self.slider.valueChanged.connect(self.on_state_changed)
            self.slider.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.MinimumExpanding,
                QtWidgets.QSizePolicy.Policy.Preferred)

            self.check_box_enable = QtWidgets.QCheckBox("Enable")
            self.check_box_enable.toggled.connect(self.on_state_changed)

            self.h_box_layout = QtWidgets.QHBoxLayout(self)
            self.h_box_layout.addWidget(self.radio_button_select)
            self.h_box_layout.addWidget(self.line_edit_template)
            self.h_box_layout.addWidget(self.double_spin_box_min)
            self.h_box_layout.addWidget(self.double_spin_box_value)
            self.h_box_layout.addWidget(self.slider)
            self.h_box_layout.addWidget(self.double_spin_box_max)
            self.h_box_layout.addWidget(self.check_box_enable)

        def get_state(self):
            return {
                'template': self.line_edit_template.text(),
                'min': self.double_spin_box_min.value(),
                'max': self.double_spin_box_max.value(),
                'value': self.double_spin_box_value.value(),
                'enable': self.check_box_enable.isChecked()}

        def set_state(self, state):
            prev_block = self.blockSignals(True)
            self.line_edit_template.setText(state['template'])
            self.double_spin_box_min.setValue(state['min'])
            self.double_spin_box_max.setValue(state['max'])
            self.double_spin_box_value.setValue(state['value'])
            self.check_box_enable.setChecked(state['enable'])
            self.on_value_changed(state['value'])
            self.blockSignals(prev_block)

        def on_state_changed(self):
            self.state_changed.emit()

        def send_value(self, value):
            if self.check_box_enable.isChecked() and self.line_edit_template.text():
                text = self.line_edit_template.text()
                param = text.format(value)
                self.value_changed.emit(param)

        def on_value_changed(self, value):
            prev_block = self.slider.blockSignals(True)

            try:
                norm_value = (
                    (value - self.double_spin_box_value.minimum()) /
                    (self.double_spin_box_value.maximum() - self.double_spin_box_value.minimum()))

                slider_value = (
                    norm_value * (self.slider.maximum() - self.slider.minimum()) +
                    self.slider.minimum())

                self.slider.setValue(int(slider_value))
                self.send_value(value)
            except ZeroDivisionError:
                pass
            self.slider.blockSignals(prev_block)

        def on_slider_value_changed(self, value):
            prev_block = self.double_spin_box_value.blockSignals(True)
            try:
                norm_value = (
                    (value - self.slider.minimum()) /
                    (self.slider.maximum() - self.slider.minimum()))

                spin_box_value = (
                    norm_value * (self.double_spin_box_value.maximum() - self.double_spin_box_value.minimum()) +
                    self.double_spin_box_value.minimum())

                self.double_spin_box_value.setValue(spin_box_value)
                self.send_value(spin_box_value)
            except ZeroDivisionError:
                pass
            self.double_spin_box_value.blockSignals(prev_block)

    KEYS = {
        'Up': QtCore.Qt.Key_Up,
        'Down': QtCore.Qt.Key_Down,
        'Left': QtCore.Qt.Key_Left,
        'Right': QtCore.Qt.Key_Right,
        'Space': QtCore.Qt.Key_Space}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.button_group = QtWidgets.QButtonGroup()
        self.v_box_layout = QtWidgets.QVBoxLayout(self)
        self.h_box_layout = QtWidgets.QHBoxLayout()
        self.v_box_layout.addLayout(self.h_box_layout)

        self.table_widget = QtWidgets.QTableWidget(0, 3, self)
        self.table_widget.setHorizontalHeaderItem(
            0, QtWidgets.QTableWidgetItem('cmd'))
        self.table_widget.setHorizontalHeaderItem(
            1, QtWidgets.QTableWidgetItem('key'))
        self.table_widget.setHorizontalHeaderItem(
            2, QtWidgets.QTableWidgetItem('enable'))
        self.add_key_parameter_action = QtWidgets.QAction("Add")
        self.remove_key_parameter_action = QtWidgets.QAction("Remove")
        self.table_widget.addAction(self.add_key_parameter_action)
        self.table_widget.addAction(self.remove_key_parameter_action)
        self.table_widget.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.ActionsContextMenu)
        self.table_widget.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection)
        self.add_key_parameter_action.triggered.connect(
            self.on_add_key_parameter)
        self.remove_key_parameter_action.triggered.connect(
            self.on_remove_key_parameter)
        self.table_widget.itemChanged.connect(self.on_key_parameter_changed)
        key_parameters = Settings.value("key_parameters")
        self.key_row = {}
        if key_parameters:
            for desc in key_parameters:
                self.add_key_parameter(
                    desc['cmd'], desc['key'], desc['enable'])
        self.table_widget.resizeColumnsToContents()
        self.v_box_layout.addWidget(self.table_widget)

        self.button_add_parameter = QtWidgets.QPushButton('Add')
        self.button_add_parameter.clicked.connect(self.add_parameter)

        self.button_remove_parameter = QtWidgets.QPushButton('Remove')
        self.button_remove_parameter.clicked.connect(self.on_remove_parameter)

        self.check_box_key_map = QtWidgets.QCheckBox('Show key map')
        self.check_box_key_map.toggled.connect(
            self.on_check_box_key_map_changed)
        value = Settings.value('key_map_visible')
        self.check_box_key_map.setChecked(
            int(value) if value is not None else 0)
        self.on_check_box_key_map_changed(self.check_box_key_map.isChecked())

        self.h_box_layout.addWidget(self.button_add_parameter)
        self.h_box_layout.addWidget(self.button_remove_parameter)
        self.h_box_layout.addWidget(self.check_box_key_map)

        self.h_box_layout.addSpacerItem(QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Expanding))

        self.spacer = QtWidgets.QSpacerItem(
            0, 0, vPolicy=QtWidgets.QSizePolicy.Expanding)
        self.v_box_layout.addSpacerItem(self.spacer)

        parameters = Settings.value("parameters")
        if parameters is not None:
            for state in parameters:
                self.create_parameter().set_state(state)

    def on_keyboard_pressed(self, key):
        row = self.key_row.get(key)
        if row is not None:
            cmd = self.table_widget.item(row, 0).text()
            enable = self.table_widget.item(row, 2).checkState()
            if enable:
                self.parameter_changed.emit(cmd)

    def on_add_key_parameter(self):
        self.add_key_parameter("xxx", '0', False)

    def add_key_parameter(self, cmd, key, checked):
        row = self.table_widget.rowCount()
        self.table_widget.setRowCount(row + 1)

        item = QtWidgets.QTableWidgetItem(cmd)
        item.setFlags(
            QtCore.Qt.ItemFlag.ItemIsSelectable |
            QtCore.Qt.ItemFlag.ItemIsEditable |
            QtCore.Qt.ItemFlag.ItemIsEnabled)
        self.table_widget.setItem(row, 0, item)

        item = QtWidgets.QTableWidgetItem(key)
        item.setFlags(
            QtCore.Qt.ItemFlag.ItemIsSelectable |
            QtCore.Qt.ItemFlag.ItemIsEditable |
            QtCore.Qt.ItemFlag.ItemIsEnabled)

        combo_box = QtWidgets.QComboBox()
        combo_box.currentIndexChanged.connect(self.on_key_parameter_changed)
        for text, value in self.KEYS.items():
            combo_box.addItem(text, value)
        combo_box.setCurrentIndex(combo_box.findData(key))
        self.table_widget.setCellWidget(row, 1, combo_box)

        item = QtWidgets.QTableWidgetItem()
        item.setCheckState(checked)
        item.setFlags(
            QtCore.Qt.ItemFlag.ItemIsSelectable |
            QtCore.Qt.ItemFlag.ItemIsUserCheckable |
            QtCore.Qt.ItemFlag.ItemIsEnabled)
        self.table_widget.setItem(row, 2, item)
        self.on_key_parameter_changed()

    def on_remove_key_parameter(self):
        self.table_widget.removeRow(self.table_widget.currentRow())
        self.on_key_parameter_changed()

    def on_key_parameter_changed(self):
        rows_desc = []
        self.key_row = {}
        for row in range(self.table_widget.rowCount()):
            cmd_item = self.table_widget.item(row, 0)
            key_item = self.table_widget.cellWidget(row, 1)
            enable_item = self.table_widget.item(row, 2)
            if cmd_item and key_item and enable_item:
                desc = {
                    'cmd': cmd_item.text(),
                    'key': key_item.currentData(),
                    'enable': enable_item.checkState()}
                self.key_row[key_item.currentData()] = row
                rows_desc.append(desc)
        Settings.setValue("key_parameters", rows_desc)

    def on_check_box_key_map_changed(self, value):
        Settings.setValue("key_map_visible", int(value))
        self.table_widget.setVisible(value)

    def create_parameter(self):
        param = self.ParameterFrame()
        self.button_group.addButton(param.radio_button_select)
        index = self.v_box_layout.indexOf(self.spacer)
        self.v_box_layout.insertWidget(index, param)

        if self.button_group.checkedButton() is None:
            param.radio_button_select.setChecked(True)
        param.value_changed.connect(self.on_parameter_value_changed)
        param.state_changed.connect(self.on_parameter_state_changed)
        return param

    def add_parameter(self):
        self.create_parameter()
        self.on_parameter_state_changed()

    def on_remove_parameter(self):
        btn = self.button_group.checkedButton()
        if btn:
            param_frame = btn.parent()
            self.v_box_layout.removeWidget(param_frame)
            del param_frame
        self.on_parameter_state_changed()

    def on_parameter_value_changed(self, value):
        self.parameter_changed.emit(value)

    def on_parameter_state_changed(self):
        state = []
        for i in range(self.v_box_layout.count()):
            param = self.v_box_layout.itemAt(i)
            if isinstance(param, QtWidgets.QWidgetItem):
                param = param.widget()
                if isinstance(param, self.ParameterFrame):
                    state.append(param.get_state())
        Settings.setValue("parameters", state)


class SettingFrame(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()
        self.combo_box_port_path = QtWidgets.QComboBox()
        self.combo_box_port_path.setToolTip("Path to the COM port file")
        for desc in list_ports.comports():
            self.combo_box_port_path.addItem(desc.device)
        port_path = Settings.value("port_path")
        dev_id = self.combo_box_port_path.findText(
            port_path if port_path is not None else "/dev/ttyACM0")

        self.combo_box_port_path.setCurrentIndex(0 if dev_id == -1 else dev_id)
        self.combo_box_port_path.setEditable(True)
        self.combo_box_port_path.currentTextChanged.connect(
            self.on_port_changed)

        self.push_button_open = QtWidgets.QPushButton("Open")
        self.push_button_open.setToolTip(
            "Open/Close the COM port for reading/writing.")
        self.combo_box_speed = QtWidgets.QComboBox()
        self.combo_box_speed.setToolTip("List of standard COM port speeds")
        for speed in serial.Serial.BAUDRATES:
            self.combo_box_speed.addItem(str(speed), speed)

        speed = Settings.value("port_speed")
        speed = int(speed) if speed is not None else 115200
        self.combo_box_speed.setCurrentIndex(
            self.combo_box_speed.findData(speed))
        self.combo_box_speed.currentIndexChanged.connect(self.on_speed_changed)

        self.group_box_line_parsing = QtWidgets.QGroupBox(self)
        self.group_box_line_parsing.setTitle('Line parsing')
        self.group_box_line_parsing.setToolTip(
            "Enable string parsing mode to display graphs")
        self.group_box_line_parsing.setCheckable(True)
        self.group_box_line_parsing.toggled.connect(
            self.on_string_parsing_changed)
        string_parsing = Settings.value("string_parsing")
        string_parsing = int(
            string_parsing) if string_parsing is not None else 1
        self.group_box_line_parsing.setChecked(string_parsing)

        self.spin_box_max_points = QtWidgets.QSpinBox()
        self.spin_box_max_points.setMaximum(2147483647)
        max_points = Settings.value('max_points')
        self.spin_box_max_points.setValue(
            int(max_points) if max_points is not None else 10000)
        self.spin_box_max_points.setToolTip(
            "Maximum number of points displayed on graphs.")
        self.spin_box_max_points.valueChanged.connect(
            self.on_max_points_changes)

        self.spin_box_max_points.setSizePolicy(
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Fixed)

        v_box_layout = QtWidgets.QVBoxLayout(self)
        h_box_layout = QtWidgets.QHBoxLayout()
        v_box_layout.addLayout(h_box_layout)

        self.push_button_clear = QtWidgets.QPushButton("Clear")
        self.push_button_clear.setToolTip(
            "Delete all data displayed on the graphs.")

        self.push_button_pause = QtWidgets.QPushButton("Pause")
        self.push_button_pause.setToolTip(
            "Suspend updating data on the graphs "
            "(data is not lost, it accumulates in the background).")

        self.check_box_xy_mode = QtWidgets.QCheckBox("XY plot")
        self.check_box_xy_mode.setToolTip(
            "XY mode replaces the time-based display with a "
            "dot display (data for the dots: "
            "x - the first element of the row, y - the second element).")

        self.check_box_show_only_cmd_response = QtWidgets.QCheckBox(
            "Only response")
        self.check_box_show_only_cmd_response.setToolTip(
            "Display only responses to commands "
            "(everything that starts with RE and ER) in the console.")
        self.check_box_show_only_cmd_response.toggled.connect(
            self.on_show_only_cmd_response_changes)
        value = Settings.value('only_cmd_response')
        self.check_box_show_only_cmd_response.setChecked(
            int(value) if value is not None else 0)

        group_box_v_box_layout = QtWidgets.QVBoxLayout(
            self.group_box_line_parsing)
        h_box_layout_graphs = QtWidgets.QHBoxLayout()
        group_box_v_box_layout.addLayout(h_box_layout_graphs)

        v_box_layout.addWidget(self.group_box_line_parsing)
        v_box_layout.addSpacerItem(QtWidgets.QSpacerItem(
            0, 0, vPolicy=QtWidgets.QSizePolicy.Expanding))

        h_box_layout_graphs.addWidget(QtWidgets.QLabel("Max points:"))
        h_box_layout_graphs.addWidget(self.spin_box_max_points)
        h_box_layout_graphs.addWidget(self.push_button_clear)
        h_box_layout_graphs.addWidget(self.push_button_pause)
        h_box_layout_graphs.addWidget(self.check_box_xy_mode)
        h_box_layout_graphs.addWidget(self.check_box_show_only_cmd_response)
        h_box_layout_graphs.addSpacerItem(QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Expanding))

        h_box_layout_graphs_2 = QtWidgets.QHBoxLayout()
        group_box_v_box_layout.addLayout(h_box_layout_graphs_2)
        self.check_box_re = QtWidgets.QCheckBox("RE")
        self.check_box_re.setToolTip(
            "Allows the use of regular expressions (Python's re.match) "
            "for extracting graph data from a line.\n"
            "For example, to extract data from the line 'x:232 q:123.3',\n"
            "you need to use this regex: 'x:(\d+)\s+q:(\d+)'.\n\n"
            "Also allows specifying a \"time\" parameter for displaying data on the horizontal axis:\n"
            "For example, to extract the time parameter and data from the given line: 'x:456 y:789 z:234 time:123',\n"
            "you need to use this expression: 'x:(\d+)\s+y:(\d+)\s+z:(\d+)\s+time:(?P<time>\d+)'.")
        self.line_edit_re = QtWidgets.QLineEdit(self)
        self.line_edit_re.setEnabled(False)
        h_box_layout_graphs_2.addWidget(self.check_box_re)
        h_box_layout_graphs_2.addWidget(self.line_edit_re)
        self.check_box_re.toggled.connect(self.on_check_box_re_changed)
        self.line_edit_re.textChanged.connect(self.on_line_edit_re_changed)

        use_re = Settings.value('use_re')
        self.check_box_re.setChecked(int(use_re) if use_re is not None else 0)

        _re = Settings.value('re')
        self.line_edit_re.setText(
            _re if _re is not None else r'(?P<time>[-+]?\d*\.*\d+)\s+([-+]?\d*\.*\d+)\s+([-+]?\d*\.*\d+)\s+([-+]?\d*\.*\d+)')

        self.combo_box_port_path.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed)

        self.combo_box_speed.setSizePolicy(
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Fixed)

        h_box_layout.addWidget(self.combo_box_port_path)
        h_box_layout.addWidget(self.push_button_open)
        h_box_layout.addWidget(self.combo_box_speed)

    def on_check_box_re_changed(self, value):
        Settings.setValue('use_re', int(value))
        self.line_edit_re.setEnabled(value)

    def on_line_edit_re_changed(self, text):
        Settings.setValue('re', text)

    def on_max_points_changes(self, value):
        Settings.setValue('max_points', value)

    def on_show_only_cmd_response_changes(self, value):
        Settings.setValue('only_cmd_response', int(value))

    def on_port_changed(self, port_path):
        Settings.setValue('port_path', port_path)

    def on_speed_changed(self, index):
        speed = self.combo_box_speed.itemData(index)
        Settings.setValue("port_speed", speed)

    def on_string_parsing_changed(self, value):
        Settings.setValue("string_parsing", int(value))


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


class MainWindow(QtWidgets.QMainWindow):
    max_len = 10000
    timeout = 0.5
    GRAPH_WIDTH = 2
    COLOURS = [
        QtGui.QColor(QtCore.Qt.white),
        QtGui.QColor(QtCore.Qt.red),
        QtGui.QColor(QtCore.Qt.darkRed),
        QtGui.QColor(QtCore.Qt.green),
        QtGui.QColor(QtCore.Qt.lightGray),
        QtGui.QColor(QtCore.Qt.blue),
        QtGui.QColor(QtCore.Qt.cyan),
        QtGui.QColor(QtCore.Qt.magenta),
        QtGui.QColor(QtCore.Qt.yellow),
        QtGui.QColor(QtCore.Qt.darkRed),
        QtGui.QColor(QtCore.Qt.darkGreen),
        QtGui.QColor(QtCore.Qt.darkBlue),
        QtGui.QColor(QtCore.Qt.darkCyan),
        QtGui.QColor(QtCore.Qt.darkMagenta),
        QtGui.QColor(QtCore.Qt.darkYellow)]

    UPDATE_RATE = 80  # ms
    NEW_LINE_SIGNAL = QtCore.pyqtSignal(object)
    CONTROL_KEYS_SIGNAL = QtCore.pyqtSignal(int)
    CONTROL_KEYS = [
        QtCore.Qt.Key_Up,
        QtCore.Qt.Key_Down,
        QtCore.Qt.Key_Left,
        QtCore.Qt.Key_Right,
        QtCore.Qt.Key_Space]

    SHOW_POINTS = False

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Graph View")
        self.points = {}

        self.plot_graph = pyqtgraph.PlotWidget(self)
        self.plot_graph.installEventFilter(self)
        self.setCentralWidget(self.plot_graph)
        self.plot_graph.setLabel("left", "value")
        self.plot_graph.setLabel("bottom", "time")
        self.plot_graph.setTitle("test curve")
        self.plot_graph.showGrid(x=True, y=True)
        self.legend = self.plot_graph.addLegend()

        self.parameters_frame = ParametersFrame()
        self.CONTROL_KEYS_SIGNAL.connect(
            self.parameters_frame.on_keyboard_pressed)
        self.parameters_dock_widget = QtWidgets.QDockWidget(
            "Parameters", self)
        self.parameters_dock_widget.setObjectName("parameters_dock_widget")
        self.parameters_dock_widget.setFeatures(
            QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.parameters_dock_widget.setAllowedAreas(
            QtCore.Qt.AllDockWidgetAreas)

        self.scroll_parameters_frame = QtWidgets.QScrollArea()
        self.scroll_parameters_frame.setWidget(self.parameters_frame)
        self.scroll_parameters_frame.setWidgetResizable(True)

        self.parameters_dock_widget.setWidget(self.scroll_parameters_frame)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea,
                           self.parameters_dock_widget)

        self.settings_frame = SettingFrame()
        self.settings_dock_widget = QtWidgets.QDockWidget(
            "Port settings", self)
        self.settings_dock_widget.setObjectName("settings_dock_widget")
        self.settings_dock_widget.setFeatures(
            QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.settings_dock_widget.setAllowedAreas(
            QtCore.Qt.AllDockWidgetAreas)
        self.settings_dock_widget.setWidget(self.settings_frame)
        self.addDockWidget(QtCore.Qt.TopDockWidgetArea,
                           self.settings_dock_widget)

        self.settings_frame.push_button_open.clicked.connect(self.on_open_port)
        self.settings_frame.push_button_clear.clicked.connect(
            self.on_clear_graphs)
        self.settings_frame.push_button_pause.clicked.connect(self.pause)
        self.settings_frame.check_box_xy_mode.toggled.connect(
            self.xy_mode_changed)
        self.curves = {}
        self.results = {}

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.setWindowState(QtCore.Qt.WindowMaximized)

        self.console_frame = ConsoleFrame()
        self.NEW_LINE_SIGNAL.connect(self.console_frame.on_new_line)
        self.console_dock_widget = QtWidgets.QDockWidget("Console", self)
        self.console_dock_widget.setObjectName("console_dock_widget")
        self.console_dock_widget.setFeatures(
            QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable)

        self.console_dock_widget.setAllowedAreas(
            QtCore.Qt.AllDockWidgetAreas)
        self.console_dock_widget.setWidget(self.console_frame)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea,
                           self.console_dock_widget)
        self.parameters_frame.parameter_changed.connect(
            self.console_frame.send_line)

        self.file_menu = self.menuBar().addMenu("&View")

        self.show_settings = QtWidgets.QAction("Settings")
        self.show_settings.setCheckable(True)
        self.file_menu.addAction(self.show_settings)
        self.show_settings.toggled.connect(
            self.on_visible_settings_changed)

        self.show_console = QtWidgets.QAction("Console")
        self.show_console.setCheckable(True)
        self.file_menu.addAction(self.show_console)
        self.show_console.toggled.connect(
            self.on_visible_console_changed)

        self.show_parameters = QtWidgets.QAction("Parameters")
        self.show_parameters.setCheckable(True)
        self.file_menu.addAction(self.show_parameters)
        self.show_parameters.toggled.connect(
            self.on_visible_parameters_changed)

        self.help_menu = self.menuBar().addMenu("&Help")
        self.action_about = QtWidgets.QAction("About")
        self.help_menu.addAction(self.action_about)
        self.action_about.triggered.connect(self.on_help)

        window_state = Settings.value("window_state")
        if window_state:
            self.restoreState(window_state)

        window_geometry = Settings.value("window_geometry")

        if window_geometry:
            self.restoreGeometry(window_geometry)

        settings_visible = Settings.value('settings_visible')
        self.show_settings.setChecked(
            int(settings_visible) if settings_visible is not None else 1)

        console_visible = Settings.value('console_visible')
        self.show_console.setChecked(
            int(console_visible) if console_visible is not None else 1)

        parameters_visible = Settings.value('parameters_visible')
        self.show_parameters.setChecked(
            int(parameters_visible) if parameters_visible is not None else 0)
        self.on_visible_parameters_changed(self.show_parameters.isChecked())

        self.process_port = None
        self.in_queue = None
        self.out_queue = None

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.KeyPress:
            if event.key() in self.CONTROL_KEYS:
                self.CONTROL_KEYS_SIGNAL.emit(event.key())
        return False

    def on_visible_settings_changed(self, checked):
        Settings.setValue('settings_visible', int(checked))
        self.settings_dock_widget.setVisible(int(checked))

    def on_visible_console_changed(self, checked):
        Settings.setValue('console_visible', int(checked))
        self.console_dock_widget.setVisible(int(checked))

    def on_visible_parameters_changed(self, checked):
        Settings.setValue('parameters_visible', int(checked))
        self.parameters_dock_widget.setVisible(int(checked))

    def on_clear_graphs(self):
        self.clear(False)

    def on_help(self):
        QtWidgets.QMessageBox.about(
            self,
            "Help",
            "Purpose of the application:\nThe application reads data from the COM port, "
            "parses each line as a set of floats separated by spaces/tabs, "
            "and then displays the data on graphs. \n"
            "The timestamp used is the moment when the data is read from the port.\n\n"
            "This is my attempt to fight against the stupid implementation of  "
            "Serial Monitor and Serial Plotter in the Arduino IDE.\n\n"
            "Author:\n"
            "Alexey Kalmykov\n"
            "alexlexx1@gmail.com")

    def on_open_port(self):
        if not self.process_port:
            try:
                if self.settings_frame.check_box_re.isChecked():
                    try:
                        _re = self.settings_frame.line_edit_re.text().encode()
                        self.line_pattern = re.compile(_re)
                        self.time_index = self.line_pattern.groupindex.get(
                            "time")
                    except re.error as e:
                        QtWidgets.QMessageBox.warning(
                            self, "Warning: can't compile regexp", str(e))
                        return
                else:
                    self.line_pattern = None

                path = self.settings_frame.combo_box_port_path.currentText()
                baudrate = self.settings_frame.combo_box_speed.currentData()
                in_queue = multiprocessing.Queue()
                out_queue = multiprocessing.Queue()
                settings = {
                    'serial': {
                        'port': path,
                        'baudrate': baudrate,
                        'timeout': self.timeout},
                    'parsing_mode': self.settings_frame.group_box_line_parsing.isChecked()}
                proc = multiprocessing.Process(
                    target=process_port,
                    args=(in_queue, out_queue, settings))
                proc.start()
                res = out_queue.get()

                # finished process
                if not res:
                    proc.join()
                    return

                self.process_port = proc
                self.in_queue = in_queue
                self.out_queue = out_queue

                self.timer.start(self.UPDATE_RATE)
                self.settings_frame.push_button_pause.setText("Pause")
                self.clear()
                self.settings_frame.push_button_open.setText("close")
                self.settings_frame.combo_box_port_path.setEnabled(False)
                self.settings_frame.combo_box_speed.setEnabled(False)
                self.console_frame.set_cmd_queue(self.in_queue)
            except serial.serialutil.SerialException as e:
                QtWidgets.QMessageBox.warning(
                    self, "Warning", str(e))
        else:
            self.in_queue.put(None)
            self.process_port.join()
            self.process_port = None
            self.in_queue = None
            self.out_queue = None

            self.settings_frame.push_button_open.setText("open")
            self.settings_frame.combo_box_port_path.setEnabled(True)
            self.settings_frame.combo_box_speed.setEnabled(True)
            self.console_frame.set_cmd_queue(None)

    def clear(self, remove_items=True):
        self.results = {}
        self.points = {}

        if remove_items:
            self.plot_graph.clear()
            self.curves = {}
        else:
            for _id, desc in self.curves.items():
                desc['time'] = []
                desc['val'] = []
                desc['curve'].setData([], [])
                if self.SHOW_POINTS:
                    desc['scatter'].setData([], [])

    def pause(self):
        if self.timer.isActive():
            self.timer.stop()
            self.settings_frame.push_button_pause.setText("Play")
        else:
            self.timer.start(self.UPDATE_RATE)
            self.settings_frame.push_button_pause.setText("Pause")

    def xy_mode_changed(self, state):
        if state:
            self.plot_graph.setAspectLocked(lock=True)
            self.clear()
            self.plot_graph.setLabel("left", "Y")
            self.plot_graph.setLabel("bottom", "X")
        else:
            self.plot_graph.setAspectLocked(lock=False)
            self.clear()
            self.plot_graph.setLabel("left", "value")
            self.plot_graph.setLabel("bottom", "time")

    def get(self):
        results = {}
        if self.out_queue:
            # reading data from queue
            try:
                while 1:
                    packet = self.out_queue.get(False)
                    if packet is None:
                        break

                    full_line, packet_time, line = packet
                    # row data
                    if not self.settings_frame.group_box_line_parsing.isChecked():
                        self.NEW_LINE_SIGNAL.emit(line)
                    # splitted data
                    else:
                        if not self.settings_frame.check_box_show_only_cmd_response.isChecked() or\
                                line[:2] in [b'RE', b'ER']:
                            self.NEW_LINE_SIGNAL.emit(line + b'\n')
                        if full_line:
                            if self.line_pattern:
                                match = self.line_pattern.match(line)
                                data = None
                                if match:
                                    data = match.groups()
                                    if self.time_index is not None:
                                        packet_time = float(
                                            match.group(self.time_index))
                            else:
                                data = line.split()

                            if data:
                                try:
                                    data = [float(d) for d in data]
                                    for index, value in enumerate(data):
                                        store = results.setdefault(
                                            index, [[], []])
                                        store[0].append(packet_time)
                                        store[1].append(value)
                                except ValueError as e:
                                    print(f'error:{e} line:{line}')
            except queue.Empty:
                pass
        return results

    def update(self):
        res = self.get()

        if not res:
            return
        max_len = self.settings_frame.spin_box_max_points.value()

        # draw graphs
        if not self.settings_frame.check_box_xy_mode.isChecked():
            for index, data in res.items():
                _time, val = data
                desc = self.curves.setdefault(index, {})
                desc.setdefault('time', []).extend(_time)
                desc.setdefault('val', []).extend(val)
                desc['time'] = desc['time'][-max_len:]
                desc['val'] = desc['val'][-max_len:]

                if 'curve' not in desc:
                    curve = pyqtgraph.PlotCurveItem()
                    pen = pyqtgraph.mkPen(
                        self.COLOURS[index % len(self.COLOURS)],
                        width=self.GRAPH_WIDTH)
                    curve.setPen(pen)
                    self.legend.addItem(
                        curve,
                        f"{index}")
                    self.plot_graph.addItem(curve)
                    desc['curve'] = curve

                    if self.SHOW_POINTS:
                        scatter = pyqtgraph.ScatterPlotItem()
                        scatter.setPen(pen)
                        self.legend.addItem(
                            scatter,
                            f"{index}")
                        self.plot_graph.addItem(scatter)
                        desc['scatter'] = scatter

                desc['curve'].setData(desc['time'], desc['val'])
                if self.SHOW_POINTS:
                    desc['scatter'].setData(desc['time'], desc['val'])
        # draw points
        else:
            # use first and second value as x, y coordinates
            if 0 in res and 1 in res:
                # first points pair
                index = 0
                desc = self.points.setdefault(0, {'x': [], 'y': []})
                desc['x'].extend(res[0][1])
                desc['y'].extend(res[1][1])
                desc['x'] = desc['x'][-max_len:]
                desc['y'] = desc['y'][-max_len:]

                # creating of scatter
                scatter = desc.get("scatter")
                if scatter is None:
                    scatter = pyqtgraph.ScatterPlotItem()
                    pen = pyqtgraph.mkPen(
                        self.COLOURS[index % len(self.COLOURS)],
                        width=self.GRAPH_WIDTH)
                    scatter.setPen(pen)
                    self.legend.addItem(
                        scatter,
                        f"{index}")

                    self.plot_graph.addItem(scatter)
                    desc['scatter'] = scatter
                # update points in scatter
                scatter.setData(desc['x'], desc['y'])

    def closeEvent(self, event):
        Settings.setValue("window_state", self.saveState())
        Settings.setValue("window_geometry", self.saveGeometry())
        event.accept()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QtWidgets.QApplication([])
    main = MainWindow()
    main.show()
    app.exec()
