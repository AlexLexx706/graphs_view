#!/usr/bin/python
# -*- coding: utf-8 -*-

from PyQt5 import QtWidgets
import serial
from serial.tools import list_ports
from .settings import Settings


class SettingFrame(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()

        # SERIAL PORT UI ELEMENTS -------------------------------------------------------------------
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

        # UDP SETTINGS UI ELEMENTS --------------------------------------------------------------------
        self.line_edit_udp_bind_ip = QtWidgets.QLineEdit("127.0.0.1")
        self.line_edit_udp_bind_ip.setToolTip("UDP Bind IP address")
        self.line_edit_udp_bind_port = QtWidgets.QLineEdit("5005")
        self.line_edit_udp_bind_port.setToolTip("UDP Bind Port")
        self.line_edit_udp_dest_ip = QtWidgets.QLineEdit("127.0.0.1")
        self.line_edit_udp_dest_ip.setToolTip("UDP Destination IP address")
        self.line_edit_udp_dest_port = QtWidgets.QLineEdit("5006")
        self.line_edit_udp_dest_port.setToolTip("UDP Destination Port")
        self.push_button_open_udp = QtWidgets.QPushButton("Open")
        self.push_button_open_udp.setToolTip("Open/Close the UDP connection.")

        # LINE PARSING UI ELEMMENTS -------------------------------------------------------------------
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

        # LAYOUT FOR SERIAL SETUP ---------------------------------------------------------------------
        v_box_layout = QtWidgets.QVBoxLayout(self)
        h_box_layout = QtWidgets.QHBoxLayout()
        v_box_layout.addLayout(h_box_layout)

        # LAYOUT FOR UDP SETUP ------------------------------------------------------------------------
        udp_layout = QtWidgets.QHBoxLayout()
        udp_layout.addWidget(QtWidgets.QLabel("UDP: Bind Port:"))
        udp_layout.addWidget(self.line_edit_udp_bind_port)
        udp_layout.addWidget(QtWidgets.QLabel("Dest IP:"))
        udp_layout.addWidget(self.line_edit_udp_dest_ip)
        udp_layout.addWidget(QtWidgets.QLabel("Dest Port:"))
        udp_layout.addWidget(self.line_edit_udp_dest_port)
        udp_layout.addWidget(self.push_button_open_udp)

        v_box_layout.addLayout(udp_layout)

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

        h_box_layout.addWidget(QtWidgets.QLabel("Serial:"))
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
