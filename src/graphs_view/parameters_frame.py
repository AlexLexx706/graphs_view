#!/usr/bin/python
# -*- coding: utf-8 -*-

from PyQt5 import QtCore
from PyQt5 import QtWidgets, QtCore
from .settings import Settings


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
            self.double_spin_box_min.setMinimum(-1000000000)
            self.double_spin_box_min.setMaximum(1000000000)
            self.double_spin_box_min.setValue(0)
            self.double_spin_box_min.setDecimals(4)
            self.double_spin_box_min.valueChanged.connect(
                self.on_state_changed)

            self.double_spin_box_max = QtWidgets.QDoubleSpinBox(self)
            self.double_spin_box_max.setMinimum(-1000000000)
            self.double_spin_box_max.setMaximum(1000000000)
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
