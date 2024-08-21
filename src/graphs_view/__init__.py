#!/usr/bin/python
# -*- coding: utf-8 -*-

import multiprocessing
import queue
import re
import types
import time
import threading
import signal
import socket
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph
import serial
from .settings import Settings
from .console_frame import ConsoleFrame
from .settings_frame import SettingFrame
from .parameters_frame import ParametersFrame

# SERIAL PORT READER
def process_port_serial(in_queue, out_queue, settings):
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

# PROCESS PORT UDP


def process_port_udp(in_queue, out_queue, settings):
    try:
        # Setup UDP socket
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind((
            settings['udp']['bind_ip'],
            settings['udp']['bind_port']))
        udp_socket.settimeout(settings['udp']['timeout'])

        # If sending data, set up destination IP and port
        dest_ip = settings['udp']['dest_ip']
        dest_port = settings['udp']['dest_port']

        is_string_parsing = settings['parsing_mode']
        out_queue.put((0, time.time(), b''))
        state = types.SimpleNamespace(stop=False)

        def send_proc():
            try:
                while 1:
                    data = in_queue.get()
                    # exit
                    if not data:
                        break
                    udp_socket.sendto(data, (dest_ip, dest_port))
            finally:
                state.stop = True

        send_thread = threading.Thread(target=send_proc)
        send_thread.start()

        r_state = 0
        # row mode
        if not is_string_parsing:
            while not state.stop:
                packet, __addr = udp_socket.recvfrom(1024)
                packet_time = time.time()
                if packet:
                    out_queue.put((r_state, packet_time, packet))
                    r_state = 1
        # string parsing
        else:
            data = b''
            packet_time = time.time()
            while not state.stop:
                try:
                    packet, __addr = udp_socket.recvfrom(1024)
                    for symbol in packet:
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
                except TimeoutError:
                    pass
        send_thread.join()
    finally:
        out_queue.put(None)
        udp_socket.close()


class GraphsView(QtWidgets.QMainWindow):
    TIMEOUT = 0.5
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
            "Settings", self)
        self.settings_dock_widget.setObjectName("settings_dock_widget")
        self.settings_dock_widget.setFeatures(
            QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.settings_dock_widget.setAllowedAreas(
            QtCore.Qt.AllDockWidgetAreas)
        self.settings_dock_widget.setWidget(self.settings_frame)
        self.addDockWidget(QtCore.Qt.TopDockWidgetArea,
                           self.settings_dock_widget)

        self.settings_frame.push_button_open.clicked.connect(
            self.on_open_port_serial)
        self.settings_frame.push_button_open_udp.clicked.connect(
            self.on_open_port_udp)
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

    def on_open_port_serial(self):
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
                        'timeout': self.TIMEOUT},
                    'parsing_mode': self.settings_frame.group_box_line_parsing.isChecked()}
                proc = multiprocessing.Process(
                    target=process_port_serial,
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

    def on_open_port_udp(self):
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
                    'udp': {
                        'timeout':self.TIMEOUT,
                        'bind_ip': self.settings_frame.line_edit_udp_bind_ip.text(),
                        'bind_port': int(self.settings_frame.line_edit_udp_bind_port.text()),
                        'dest_ip': self.settings_frame.line_edit_udp_dest_ip.text(),
                        'dest_port': int(self.settings_frame.line_edit_udp_dest_port.text())},

                    'parsing_mode': self.settings_frame.group_box_line_parsing.isChecked()}
                proc = multiprocessing.Process(
                    target=process_port_udp,
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
                self.settings_frame.push_button_open_udp.setText("close")
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

            self.settings_frame.push_button_open_udp.setText("Open UDP")
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


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QtWidgets.QApplication([])
    graphs_view = GraphsView()
    graphs_view.show()
    app.exec()
