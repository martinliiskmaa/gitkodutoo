#!/usr/bin/env python
import json
from pprint import pprint
from time import time, sleep
from argparse import ArgumentParser
from binascii import hexlify
from copy import deepcopy
from datetime import datetime, timezone
from math import floor
from pathlib import Path
from queue import Empty
from struct import pack

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow
from can import CanError
from requests import get


from .balancing_dialog_ui import Ui_balancing_dialog
from .battery_diag_tool_gui import *
from common import data_handling
import sys

import threading
from PyQt5.QtCore import pyqtSignal

from .bms_id_dialog_ui import Ui_bmsid_update_dialog
from .bmsinfo import BmsInfo

from .usbinfo import USB_Info

from .confirm_dialog_ui import Ui_confirm_dialog
from .digipot_dialog_ui import Ui_digipot_dialog
from .helper import logging_basic_config, utc_time_seconds, str2bool
from .mvar import LockableBoolean
import logging

from multiprocessing import Queue, Value

from .sensors_dialog_ui import Ui_sensors_dialog
from .settings import settings as settings_data

from enum import Enum, auto

from .update_dialog import Ui_fw_update_dialog
from .usbc_dialog_ui import Ui_usbc_dialog
from .voltage_dialog_ui import Ui_voltage_dialog

stylesheet_display_none = 'background-color:None; border-width: 1px;'
stylesheet_display_red = 'background-color:#F65AAE; border-color:red; border-width: 4px;'
stylesheet_display_yellow = 'background-color:#F6F05A; border-color:yellow; border-width: 4px;'
stylesheet_display_blue = 'background-color:#5A60F6; border-color:blue; border-width: 4px;'
stylesheet_display_error = stylesheet_display_red
stylesheet_display_warn = stylesheet_display_yellow

BATTERY_DATA_TIMEOUT = 3


logger = logging.getLogger('main')


class UiCommand(Enum):
    NOT_SET = auto()
    BMS_TO_SHIPPING = auto()
    CLEAR_PRIMARY_FAULTS = auto()
    ATTACH_FOLDY_BMS = auto()
    TIMESYNC = auto()
    BALANCING_PATTERN = auto()
    FW_UPDATE = auto()
    WRITE_BMSID = auto()
    MASTER_COMMAND = auto()
    POLL_REG = auto()


def is_feature_supported(v1, v2, fw_ver):
    return fw_ver == v1 or fw_ver >= v2


def is_semver_new(cur, new):
    res = False
    if cur != new:
        new_ver = int(new / 100) * 100
        new_ver_ = new % 100
        cur_ver = int(cur / 100) * 100
        cur_ver_ = cur % 100
        if cur_ver_ == 0:
            res = new_ver > cur_ver
            # logger.info(f"is_semver_new_0(cur: {cur} new: {new}) : {res} = {new_ver} > {cur_ver}")
        elif new_ver_ == 0:
            cur_ver = int(cur / 100) * 100
            res = new_ver > cur_ver or new_ver == cur_ver
            # logger.info(f"is_semver_new_1(cur: {cur} new: {new}) : {res} = {new_ver} > {cur_ver} or {new_ver} == {cur_ver}")
        else:
            res = new >= cur
            # logger.info(f"is_semver_new_2(cur: {cur} new: {new}): {res} = {new} >= {cur}")
    return res


def calc_cell_percent(bms, cell):
    res = 0
    cell_voltage = bms.cell_voltages[cell]
    if cell_voltage != "" and bms.cell_voltage_highest != "" and bms.cell_voltage_lowest != "":
        # lowest = bms.cell_voltage_lowest
        lowest = 3250
        if bms.cell_voltage_lowest < lowest:
            lowest = bms.cell_voltage_lowest

        highest = 4000
        if bms.cell_voltage_highest > highest:
            highest = bms.cell_voltage_highest

        res = (cell_voltage - lowest) / (highest - lowest) * 100

    return res


def calc_avg_temperature(bms):
    if bms.bms_id_int == 0:
        return 0

    temperatures = [bms.pack_left_temp, bms.pack_right_temp, bms.pack_center_temp]

    if bms.hw_type == 1 or bms.hw_type == 2:
        temperatures.append(bms.temp_ts_1)
        temperatures.append(bms.temp_ts_2)
        temperatures.append(bms.temp_ts_3)

    temperatures.sort()

    temperatures.pop(0)
    temperatures.pop(-1)

    avg_temp = temperatures[0]
    arr_len = len(temperatures)
    if arr_len > 1:
        avg_temp = sum(temperatures) / arr_len
    return avg_temp


def ui_pack_state(bms: BmsInfo):
    state_text = "N/A"
    if bms.pack_state == 0:
        state_text = "0 (ALL OFF)"
    elif bms.pack_state == 2:
        state_text = "2 (Precharging)"
    elif bms.pack_state == 3:
        state_text = "3 (Discharging)"
    elif bms.pack_state == 4:
        state_text = "4 (Slow charging)"
    elif bms.pack_state == 5:
        state_text = "5 (Normal charging)"
    return state_text


def ui_attach_status(bms: BmsInfo):
    attach_status_text = "N/A"
    if bms.attach_status == 255:
        attach_status_text = "0 (Detached)"
    elif bms.attach_status == 1:
        attach_status_text = "1 (Vehicle slot 1)"
    elif bms.attach_status == 2:
        attach_status_text = "2 (Vehicle slot 2)"
    elif bms.attach_status == 3:
        attach_status_text = "3 (Foldy)"
    elif bms.attach_status == 6:
        attach_status_text = "6 (Charger)"
    return attach_status_text




class ValueChanged:
    def __init__(self):

        self.value = None
        self.prev = None

    def update(self, new_value):
        self.prev = self.value
        self.value = new_value

    def is_changed(self) -> bool:
        return self.prev != self.value

    def is_changed_update(self, new_value) -> bool:
        self.update(new_value)

        return self.is_changed()

    def diff(self):
        try:
            if self.value is not None and self.prev is not None:
                return self.value-self.prev
        except Exception:
            pass
        return 0


class CsvDataLogging:
    def __init__(self, config: settings_data):
        self.enabled = config.get('CSV', 'enabled', False, str2bool)
        self.data_period = config.get('CSV', 'data_period', 1, int)

        # self.output_file_path: Path = None
        self.output_file = None

        self.prev_bms_id = 0
        self.next_data_time = 0

    def update(self, data: BmsInfo):
        if data.bms_id_int != self.prev_bms_id:
            # create new file
            self.reset(data)

            self.prev_bms_id = data.bms_id_int

        if data.bms_id_int:
            # append to file
            time_now = time()
            if floor(time_now) != floor(self.next_data_time):
                # logger.debug(f"Log to file time_now {time_now} {self.next_data_time}")
                data.timestamp = utc_time_seconds()
                self.output_file.write(data.to_csv_test())
                self.output_file.write("\n")
                self.output_file.flush()

                self.next_data_time = floor(time_now)

    def reset(self, data: BmsInfo):
        if self.output_file is not None:
            self.output_file.close()

        if data.bms_id_int != 0:
            csv_folder = Path("csv") / f"{data.bms_id}"
            if not csv_folder.exists():
                csv_folder.mkdir(parents=True)
            time_now = datetime.utcnow()
            date_str = time_now.strftime("%Y%m%d_%H%M%S")
            output_file_path = csv_folder / f"{date_str}_{data.bms_id}.csv"

            self.output_file = open(output_file_path, "a+")

    def __del__(self):
        if self.output_file is not None:
            self.output_file.close()


def item_visibility(item, show):
    if show:
        item.show()
    else:
        item.hide()


def setup_settings(config_file=Path("config.conf")):
    settings = settings_data()
    settings.add_default("CAN", "driver", "can")
    settings.add_default("CAN", "bustype", "kvaser")
    settings.add_default("CAN", "bitrate", "250000")
    settings.add_default("CAN", "channel", "0")
    settings.add_default("FIRMWARE", "DIR", "firmware")
    settings.add_default("FIRMWARE", "storage",
                              "https://storage.googleapis.com/46e5307363aa417e00bb26a6d999c142cbab1aeb/COSCOOTER")

    settings.add_default("BMS", "timesync", "True")
    settings.add_default("BMS", "version", "80056")

    settings.add_default("APP", "show_untested_features", "False")
    settings.add_default("APP", "polls_per_sec", "5")
    settings.add_default("CSV", "enabled", "True")
    settings.add_default("CSV", "data_period", "1")

    settings.add_default("APP", "log_level", "INFO")

    settings.add_default("APP", "dark_mode", "False")

    if config_file.exists():
        settings.read(config_file)

    return settings


def display_temp(display, temp, warn_high, warn_low=None, warn_diff=None, avg_temp=None):
    stylesheet = stylesheet_display_none
    if temp != "":
        if temp >= warn_high:
            stylesheet = stylesheet_display_red
        elif warn_low is not None:
            if temp <= warn_low:
                stylesheet = stylesheet_display_blue
        elif warn_diff is not None:
            if abs(temp - avg_temp) >= warn_diff:
                stylesheet = stylesheet_display_yellow

    display.display(temp)
    display.setStyleSheet(stylesheet)


class MyWindow(QMainWindow):

    update_ui_signal = pyqtSignal([BmsInfo, USB_Info])
    update_fw_msg_signal = pyqtSignal([str, int])

    def __init__(self, settings, standalone=True):
        super(MyWindow, self).__init__()
        self.settings = settings
        self.standalone = standalone

        logger.setLevel(self.settings.get("APP", "log_level"))

        self.ui = Ui_BatteryDiagnosticsTool()
        self.ui.setupUi(self)

        self.timesync_enabled = self.settings.get("BMS", "timesync", True, str2bool)
        self.show_untested_features = self.settings.get("APP", "show_untested_features", function=str2bool)

        self.fullscreen_mode = self.settings.get('APP', 'fullscreen_mode', True, str2bool)
        
        self.temp_high = self.settings.get('APP', 'warning_temp_high', 44, int)
        self.temp_low = self.settings.get('APP', 'warning_temp_low', 4, int)
        self.temp_diff = self.settings.get('APP', 'warning_temp_diff', 7, int)
        self.fet_temp_high = self.settings.get('APP', 'warning_fet_temp_high', 65, int)
        self.usb_temp_high = self.settings.get('APP', 'warning_usb_temp_high', 65, int)

        self.ask_for_update = self.settings.get('APP', 'ask_for_update', False, str2bool)
        self.live_load_period = self.settings.get('APP', 'load_live_period', 600, float)

        self.aike_t_dev_live = Value('i', 0)
        self.beyonder_live = Value('i', 0)

        self.ui.checkbox_timesync.setChecked(self.timesync_enabled)

        self.update_ui_signal.connect(self.on_update_ui) # noqa
        self.update_fw_msg_signal.connect(self.on_update_fw_msg) # noqa

        self.ui.button_shipping_mode.clicked.connect(self.ui_put_bms_to_shipping)
        self.ui.button_clear_primary_faults.clicked.connect(self.ui_clear_primary_faults)

        self.ui.pushButton_requestoff.clicked.connect(self.ui_send_requestoff)

        self.ui.checkbox_attach.stateChanged.connect(self.ui_checkbox_changed)
        self.ui.checkbox_timesync.stateChanged.connect(self.ui_checkbox_changed)

        self.ui.display_soc.setDigitCount(6)
        self.ui.display_voltage.setDigitCount(6)
        self.ui.display_current.setDigitCount(6)
        self.ui.display_min_cell_voltage.setDigitCount(6)
        self.ui.display_max_cell_voltage.setDigitCount(6)

        #  stuff
        if not self.show_untested_features or not self.standalone:
            self.ui.pushButton_resetmcu.hide()
            self.ui.pushButton_balancing.hide()

        self.confirm_content = "N/A"

        self.data_process_state = True
        self.bms_reader = data_handling.BmsReader(self.settings)

        self.last_poll_time = 0

        self.setWindowIcon(QIcon('icon.png'))

        self.bms_register_poll_counter = 0
        self.bms_data_timeout = 0

        self.attach_foldy_bms = False

        self.last_rx_data = 0
        self.can_bus_timeout = True

        self.polls_per_sec = self.settings.get("APP", "polls_per_sec", 1, function=int )

        self.cell_progressbars = [self.ui.progressBar_0,
                                  self.ui.progressBar_1,
                                  self.ui.progressBar_2,
                                  self.ui.progressBar_3,
                                  self.ui.progressBar_4,
                                  self.ui.progressBar_5,
                                  self.ui.progressBar_6,
                                  self.ui.progressBar_7,
                                  self.ui.progressBar_8,
                                  self.ui.progressBar_9,
                                  self.ui.progressBar_10,
                                  self.ui.progressBar_11]

        self.prev_timesync = floor(time())
        self.prev_attach = 0

        self.prev_lowest_scale = 0
        self.prev_highest_scale = 0

        self.prev_bms_data = BmsInfo()
        self.prev_usb_data = USB_Info()

        self.cell_voltage_diff = ValueChanged()

        self.latest_fw_changed = ValueChanged()
        self.prev_avg_temp = 0

        # data in can thread
        self.next_poll_time = 0
        self.bms_register_poll_counter = 0
        self.prev_bms_data_can = BmsInfo()

        self.bms_info = BmsInfo(1)
        self.usb_info = USB_Info()

        self.bms_read_regs = []
        self.reset_read_regs()

        self.cell_format_stylesheets = {0: "", 1: "", 2: "", 3: "", 4: "", 5: "", 6: "", 7: "", 8: "", 9: "", 10: "", 11: ""}
        self.cell_voltages_stylesheets = {0: "", 1: "", 2: "", 3: "", 4: "", 5: "", 6: "", 7: "", 8: "", 9: "", 10: "", 11: ""}

        self.csv_logging = CsvDataLogging(self.settings)

        self.fw_update_dialog = QtWidgets.QDialog()
        self.fw_update_dialog_ui = Ui_fw_update_dialog()
        self.fw_update_dialog_ui.setupUi(self.fw_update_dialog)
        self.fw_update_dialog_ui.pushButton_updatefw.clicked.connect(self.ui_send_fwupdate)
        self.fw_update_dialog_ui.cb_options.clicked.connect(self.show_update_ui)
        self.ui.pushButton_updatefw_2.clicked.connect(self.show_update_ui)
        self.fw_update_dialog_ui.progressBar.hide()
        self.fw_update_dialog_ui.label_info.hide()
        self.fw_update_dialog_ui.lineEdit_fw_version.setText(self.settings.get("BMS", "version"))

        # BMS ID Popup
        self.bmsid_update_dialog = QtWidgets.QDialog()
        self.bmsid_update_dialog_ui = Ui_bmsid_update_dialog()
        self.bmsid_update_dialog_ui.setupUi(self.bmsid_update_dialog)
        self.ui.pushButton_bmsid.clicked.connect(self.show_bmsid_ui)
        self.bmsid_update_dialog_ui.pushButton_write_bms_id.clicked.connect(self.ui_bmsid_write)

        # Disable Sensors Popup
        self.sensors_dialog = QtWidgets.QDialog()
        self.sensors_dialog_ui = Ui_sensors_dialog()
        self.sensors_dialog_ui.setupUi(self.sensors_dialog)
        self.ui.pushButton_sensors.clicked.connect(self.show_sensors_ui)
        self.sensors_dialog_ui.pushButton_sensors_write.clicked.connect(self.ui_write_sensor_mask)
        self.sensors_dialog_ui.pushButton_sensors_read.clicked.connect(self.ui_read_sensor_mask)

        # Balancing Popup
        self.balancing_dialog = QtWidgets.QDialog()
        self.balancing_dialog_ui = Ui_balancing_dialog()
        self.balancing_dialog_ui.setupUi(self.balancing_dialog)
        self.ui.pushButton_balancing.clicked.connect(self.show_balancing_ui)
        self.balancing_dialog_ui.pushButton_send_pattern.clicked.connect(self.ui_send_balance_pattern)
        self.balancing_dialog_ui.pushButton_balancing_enable.clicked.connect(self.ui_send_balance_enable)
        self.balancing_dialog_ui.pushButton_balancing_disable.clicked.connect(self.ui_send_balance_disable)

        # Voltage Limits Popup
        self.voltage_dialog = QtWidgets.QDialog()
        self.voltage_dialog_ui = Ui_voltage_dialog()
        self.voltage_dialog_ui.setupUi(self.voltage_dialog)
        self.ui.pushButton_voltage.clicked.connect(self.show_voltage_ui)
        self.voltage_dialog_ui.pushButton_voltage_read.clicked.connect(self.ui_read_max_voltage)
        self.voltage_dialog_ui.pushButton_voltage_ov_write.clicked.connect(self.ui_write_max_voltage)
        self.voltage_dialog_ui.pushButton_voltage_uv_write.clicked.connect(self.ui_write_min_voltage)

        # Digipot Control Popup

        self.digipot_dialog = QtWidgets.QDialog()
        self.digipot_dialog_ui = Ui_digipot_dialog()
        self.digipot_dialog_ui.setupUi(self.digipot_dialog)
        self.ui.pushButton_digipot.clicked.connect(self.show_digipot_ui)
        self.digipot_dialog_ui.pushButton_digipot_read.clicked.connect(self.ui_digipot_read)
        self.digipot_dialog_ui.pushButton_digipot_write.clicked.connect(self.ui_digipot_write)

        self.from_ui_queue = Queue()

        # Confirm Dialog Popup

        self.confirm_dialog = QtWidgets.QDialog()
        self.confirm_dialog_ui = Ui_confirm_dialog()
        self.confirm_dialog_ui.setupUi(self.confirm_dialog)
        self.ui.pushButton_resetmcu.clicked.connect(self.mcu_reset_confirm)
        # self.confirm_content = "N/A"
        self.confirm_dialog_ui.pushButton_confirm_yes.clicked.connect(self.ui_confirm_yes)
        self.confirm_dialog_ui.pushButton_confirm_cancel.clicked.connect(self.confirm_dialog.close)

        # USB-C Debug Data Popup

        self.usbc_dialog = QtWidgets.QWidget()
        self.usbc_dialog_ui = Ui_usbc_dialog()
        self.usbc_dialog_ui.setupUi(self.usbc_dialog)
        self.ui.pushButton_usbc.clicked.connect(self.show_usbc_ui)
        self.display_usb_data(self.prev_usb_data, self.prev_bms_data)

        self.display_bms_data(self.prev_bms_data, True)

        if not self.standalone:
            self.ui.scrollArea.hide()
            self.ui.checkbox_timesync.hide()
            self.ui.pushButton_updatefw_2.hide()

            # can bus state
            self.ui.label_2.hide()
            self.ui.label_can_status.hide()

        self.update_checker_thread_running = LockableBoolean()
        self.update_checker_thread = threading.Thread(target=self.update_checker)

        self.testRunning = LockableBoolean()
        self.window_thread = threading.Thread(target=self.windowThreadRun)

        self.window_open = False

    def start(self):
        self.update_checker_thread_running.set()
        self.update_checker_thread.start()

        self.testRunning.set()
        self.window_thread.start()

    def show_update_ui(self):
        item_visibility(self.fw_update_dialog_ui.label_type, self.fw_update_dialog_ui.cb_options.isChecked())
        item_visibility(self.fw_update_dialog_ui.input_fwtype, self.fw_update_dialog_ui.cb_options.isChecked())

        self.fw_update_dialog_ui.label_info.setText("")
        self.fw_update_dialog.show()
        self.fw_update_dialog.activateWindow()

    def show_bmsid_ui(self):
        self.bmsid_update_dialog.show()
        self.bmsid_update_dialog.activateWindow()

    def show_sensors_ui(self):
        self.sensors_dialog.show()
        self.sensors_dialog.activateWindow()

    def show_balancing_ui(self):
        self.balancing_dialog.show()
        self.balancing_dialog.activateWindow()

    def show_voltage_ui(self):
        self.voltage_dialog.show()
        self.voltage_dialog.activateWindow()

    def show_digipot_ui(self):
        self.digipot_dialog.show()
        self.digipot_dialog.activateWindow()

    def show_usbc_ui(self):
        self.usbc_dialog.show()
        self.usbc_dialog.activateWindow()

    def reset_bms_info(self):
        self.bms_info = BmsInfo(1)

    def ui_show_hide_type(self, bms: BmsInfo):
        fw_ver = bms.bms_sw_version
        hw_type = bms.hw_type
        sw_profile = bms.sw_profile

        hw_type_txt = "Unknown"
        sw_profile_txt = "Unknown"
        hw_profile_text = ""
        # if bms.bms_id:
        if hw_type == 0:
            hw_type_txt = "Beyonder"

            if sw_profile == 0:
                sw_profile_txt = "Default"
        elif hw_type == 1:
            hw_type_txt = "Foldy"

            if sw_profile == 0:
                sw_profile_txt = "Default"
            elif sw_profile == 0xF:
                sw_profile_txt = "Prototype"
        elif hw_type == 2:
            hw_type_txt = "Aike 11"

            if sw_profile == 0:
                sw_profile_txt = "Default"
            elif sw_profile == 0xF:
                sw_profile_txt = "Prototype"

        hw_profile_text = f"HW: {hw_type_txt} (0x{hw_type:X}) SW: {sw_profile_txt} (0x{sw_profile:X})"
        self.ui.label_time_2.setText(hw_profile_text)

        is_capsense = False
        is_attach_pin = False
        is_usb_temp_sensor = False
        is_temp_sensors = False
        is_aike11_temp_sensors = False

        if hw_type == 1:
            # FOLDY
            self.ui.checkbox_attach.show()

            is_temp_sensors = True
            is_usb_temp_sensor = True
            is_capsense = True
        elif hw_type == 2:
            # AIKE11
            self.ui.checkbox_attach.show()

            is_temp_sensors = True
            is_capsense = True
            is_attach_pin = True
            is_aike11_temp_sensors = True
        elif hw_type == 0:
            # BEYONDER
            self.ui.checkbox_attach.hide()

            is_capsense = bms.pcb_version >= 230 or is_feature_supported(80000, 80052, fw_ver)

            is_attach_pin = is_feature_supported(80000, 80057, fw_ver)

        item_visibility(self.ui.lcd_attach_pin_voltage, is_attach_pin)
        item_visibility(self.ui.label_30, is_attach_pin)

        item_visibility(self.ui.lcd_capsense, is_capsense)
        item_visibility(self.ui.label_17, is_capsense)

        # usb temperature
        item_visibility(self.ui.lcd_temp_usb, is_usb_temp_sensor)
        item_visibility(self.ui.label_26, is_usb_temp_sensor)

        # bq temp sensors
        item_visibility(self.ui.lcd_ts1, is_temp_sensors)
        item_visibility(self.ui.lcd_ts2, is_temp_sensors)
        item_visibility(self.ui.lcd_ts3, is_temp_sensors)
        item_visibility(self.ui.label_20, is_temp_sensors)
        item_visibility(self.ui.label_22, is_temp_sensors)
        item_visibility(self.ui.label_24, is_temp_sensors)

        #aike11 temp sensors
        item_visibility(self.ui.label_33, is_aike11_temp_sensors)
        item_visibility(self.ui.label_34, is_aike11_temp_sensors)
        item_visibility(self.ui.label_36, is_aike11_temp_sensors)
        item_visibility(self.ui.lcd_temp4, is_aike11_temp_sensors)
        item_visibility(self.ui.lcd_temp5, is_aike11_temp_sensors)
        item_visibility(self.ui.lcd_temp6, is_aike11_temp_sensors)

        
        # Command buttons
        item_visibility(self.ui.pushButton_sensors, is_feature_supported(80000, 80056, fw_ver) and self.standalone)
        item_visibility(self.ui.pushButton_bmsid, bms.bms_id_int == 0xb16b00b5 and self.standalone)
        item_visibility(self.ui.pushButton_balancing, is_feature_supported(80000, 88800, fw_ver) and hw_type != 0 and self.standalone)
        item_visibility(self.ui.pushButton_voltage, is_feature_supported(80000, 88800, fw_ver) and hw_type != 0 and self.standalone)
        item_visibility(self.ui.pushButton_digipot, is_feature_supported(80000, 88800, fw_ver) and hw_type == 1 and self.standalone)
        item_visibility(self.ui.pushButton_usbc, is_feature_supported(80000, 88816, fw_ver) and hw_type == 1 and self.standalone)

        # Voltage control info
        item_visibility(self.ui.lcdOver, is_feature_supported(80000, 88800, fw_ver))
        item_visibility(self.ui.lcdUnder, is_feature_supported(80000, 88800, fw_ver))
        item_visibility(self.ui.label_27, is_feature_supported(80000, 88800, fw_ver))

        item_visibility(self.sensors_dialog_ui.checkBox_dis_4, hw_type != 0)
        item_visibility(self.sensors_dialog_ui.checkBox_dis_5, hw_type != 0)
        item_visibility(self.sensors_dialog_ui.checkBox_dis_6, hw_type != 0)

    def set_cells(self, bms, cell):
        # self.cell_lcd[cell].display(bms.cell_voltages[cell])

        # percent = calc_cell_percent(bms, cell)
        # # print(f"cell {cell} res: {percent}")
        bms_cell_voltage = bms.cell_voltages[cell]
        prev_bms_cell_voltage = self.prev_bms_data.cell_voltages[cell]
        if bms_cell_voltage == prev_bms_cell_voltage and bms.balance_pattern == self.prev_bms_data.balance_pattern and bms.overvoltage_limit != self.prev_bms_data.overvoltage_limit:
            return

        prgrss = self.cell_progressbars[cell]

        color = "#7bbd7b"

        cell_voltage = 0
        cell_format = "N/A"
        if bms_cell_voltage != "":
            cell_voltage = bms_cell_voltage
            cell_format = f"{cell + 1:02}: {cell_voltage}"

        overvoltage_limit = 4040
        if bms.overvoltage_limit != "" and bms.overvoltage_limit != 0:
            overvoltage_limit = bms.overvoltage_limit

        undervoltage_limit = 3000
        if bms.undervoltage_limit != "" and bms.undervoltage_limit != 0:
            undervoltage_limit = bms.undervoltage_limit

        if cell_voltage > overvoltage_limit or cell_voltage < undervoltage_limit:
            color = "#ff0000"

        box_style = "border: 2px solid grey"

        if bms.balance_pattern != "":
            if bms.balance_pattern & (1 << cell):
                box_style = "border: 5px solid blue"

        if bms_cell_voltage != prev_bms_cell_voltage:
            # print(f"cell {cell} cell_voltage {cell_voltage} prev_bms_cell_voltage: {prev_bms_cell_voltage}")
            self.cell_format_stylesheets[cell] = cell_format
            prgrss.setValue(cell_voltage)

            prgrss.setFormat(cell_format)

        stylesheet = (" QProgressBar { "
            f"{box_style}; border-radius: 0px; text-align: center; "
            "} QProgressBar::chunk {"
            f"background-color: {color};"
            "width: 1px;}")

        if stylesheet != self.cell_voltages_stylesheets[cell]:
            prgrss.setStyleSheet(stylesheet)
            self.cell_voltages_stylesheets[cell] = stylesheet

    def update_ui(self, value: BmsInfo, usb_value: USB_Info):
        self.update_ui_signal.emit(value, usb_value) # noqa

    def on_update_ui(self, value: BmsInfo, usb_value: USB_Info):
        try:
            self.display_bms_data(value, False)
            self.display_usb_data(usb_value, value)
        except Exception as e:
            logger.error(f"on_update_ui: {e}")
            pass

    def update_fw_msg(self, value: str, percent: int):
        self.update_fw_msg_signal.emit(value, percent) # noqa

    def on_update_fw_msg(self, value: str, percent: int):
        self.fw_update_dialog_ui.label_info.setText(value)

        if percent < 0:
            self.fw_update_dialog_ui.progressBar.hide()
        else:
            self.fw_update_dialog_ui.progressBar.setValue(percent)

        if percent == 0:
            self.fw_update_dialog_ui.progressBar.show()
            self.fw_update_dialog_ui.label_info.show()

        if percent == -1:
            self.fw_update_dialog_ui.label_info.hide()
            self.fw_update_dialog.close()

    def to_worker(self, command):
        self.from_ui_queue.put(command)

    def ui_put_bms_to_shipping(self):
        if is_feature_supported(80000, 80054, self.bms_info.bms_sw_version):
            if self.bms_info.cell_voltage_highest < 3700:
                self.to_worker((UiCommand.MASTER_COMMAND, 10, 0, 0x99))
            else:
                self.show_confirm_dialog("force_shipping_mode", "Force shipping mode?", f"Battery maximum cell voltage ({self.bms_info.cell_voltage_highest} mV) is not in storage range (below 3700 mV).\n\nForce shipping mode?")
        else:
            self.to_worker((UiCommand.BMS_TO_SHIPPING, "to shipping"))

    def put_bms_to_shipping(self):
        print("put_bms_to_shipping")
        self.bms_reader.send_message_to_can(0xf123, [0x03, 0x99])

    def ui_clear_primary_faults(self):
        self.to_worker((UiCommand.CLEAR_PRIMARY_FAULTS, "clear faults"))

    def ui_send_balance_pattern(self):
        try:
            balancing_pattern_txt = self.balancing_dialog_ui.lineEdit_balancing_pattern.text()
            balancing_pattern = int(balancing_pattern_txt.replace(" ", ""), 2)
            print(f"Sending balancing pattern ({balancing_pattern_txt}): {balancing_pattern}")
            self.to_worker((UiCommand.MASTER_COMMAND, 7, 1, balancing_pattern))
        except Exception:
            pass

    def show_confirm_dialog(self, handle: str, title: str, text: str):
        self.confirm_content = handle
        self.confirm_dialog_ui.label_confirm.setText(text)

        self.confirm_dialog.setWindowTitle(title)
        self.confirm_dialog.show()
        self.confirm_dialog.activateWindow()

    def mcu_reset_confirm(self):
        self.show_confirm_dialog("restart_bms", "Restart BMS?", "Are you really sure you want to restart BMS?")

    def ui_confirm_yes(self):
        if self.confirm_content == "restart_bms":
            self.to_worker((UiCommand.MASTER_COMMAND, 4, 0, 0x32))

        elif self.confirm_content == "force_shipping_mode":
            self.to_worker((UiCommand.MASTER_COMMAND, 10, 0, 0xF0))

        elif self.confirm_content == "new_fw_update":
            if self.prev_bms_data.is_reg_fc:
                cur_latest = 0
                if self.prev_bms_data.hw_type == 0:
                    cur_latest = self.beyonder_live.value
                elif self.prev_bms_data.hw_type == 1:
                    cur_latest = self.aike_t_dev_live.value
                elif self.prev_bms_data.hw_type == 2:
                    cur_latest = self.aike_t_dev_live.value

                self.fw_update_dialog_ui.lineEdit_fw_version.setText(f"{cur_latest}")
                self.fw_update_dialog_ui.input_fwtype.setText("")
                self.show_update_ui()

        self.confirm_dialog.close()
        self.confirm_content = None

    def ui_send_balance_enable(self):
        self.to_worker((UiCommand.MASTER_COMMAND, 7, 0, 1))

    def ui_send_balance_disable(self):
        self.to_worker((UiCommand.MASTER_COMMAND, 7, 0, 0))

    def ui_send_requestoff(self):
        if self.bms_info.error_flags & 2:
            self.to_worker((UiCommand.MASTER_COMMAND, 3, 0, 1))
        else:
            self.to_worker((UiCommand.MASTER_COMMAND, 2, 0, 1))

    def ui_send_fwupdate(self):
        try:
            fw_ver = int(self.fw_update_dialog_ui.lineEdit_fw_version.text())
            fw_type = self.fw_update_dialog_ui.input_fwtype.text()
            if self.fw_update_dialog_ui.cb_options.isChecked() and fw_type != "":
                self.to_worker((UiCommand.FW_UPDATE, fw_ver, int(fw_type, 16)))
            else:
                self.to_worker((UiCommand.FW_UPDATE, fw_ver, None))

        except Exception as e:
            logger.error(f"ui_send_fwupdate: {e}")
            pass

    def clear_primary_faults(self):
        print("clear_primary_faults")
        self.bms_reader.send_message_to_can(0xf123, [0x04, 0x01])

    def ui_checkbox_changed(self):
        self.to_worker((UiCommand.ATTACH_FOLDY_BMS, self.ui.checkbox_attach.isChecked()))
        self.to_worker((UiCommand.TIMESYNC, self.ui.checkbox_timesync.isChecked()))

    def ui_read_max_voltage(self):
        self.to_worker((UiCommand.POLL_REG, 0xc9))
        pass

    def ui_write_max_voltage(self):
        self.to_worker((UiCommand.MASTER_COMMAND, 8, 0, self.voltage_dialog_ui.spinBox.value()))
        pass

    def ui_write_min_voltage(self):
        self.to_worker((UiCommand.MASTER_COMMAND, 8, 5, self.voltage_dialog_ui.spinBox_undevoltage.value()))
        pass

    def ui_read_sensor_mask(self):
        print(f"ui_read_sensor_mask")
        self.to_worker((UiCommand.POLL_REG, 0xc8))
        pass

    def ui_digipot_read(self):
        self.to_worker((UiCommand.POLL_REG, 0xc9))
        pass

    def ui_digipot_write(self):
        self.to_worker((UiCommand.MASTER_COMMAND, 8, 2, self.digipot_dialog_ui.spinBox_digipot.value()))

        pass

    def ui_bmsid_write(self):
        try:
            bms_id = int(self.bmsid_update_dialog_ui.lineEdit_new_bmsid.text(), 16)
            print(f"ui_bmsid_write: {bms_id:08x}")
            self.to_worker((UiCommand.WRITE_BMSID, bms_id))
        except Exception as e:
            print(f"ui_bmsid_write: {e}")
            pass

    def ui_write_sensor_mask(self):
        mask = 0
        mask |= self.sensors_dialog_ui.checkBox_dis_1.isChecked()
        mask |= self.sensors_dialog_ui.checkBox_dis_2.isChecked() << 1
        mask |= self.sensors_dialog_ui.checkBox_dis_3.isChecked() << 2
        mask |= self.sensors_dialog_ui.checkBox_dis_4.isChecked() << 3
        mask |= self.sensors_dialog_ui.checkBox_dis_5.isChecked() << 4
        mask |= self.sensors_dialog_ui.checkBox_dis_6.isChecked() << 5
        print(f"ui_write_sensor_mask: {mask:08x}")
        self.to_worker((UiCommand.MASTER_COMMAND, 8, 1, mask))

    def display_usb_data(self, usb: USB_Info, bms:BmsInfo):
        prev_usb = self.prev_usb_data

        # Role Control
        if usb.role_control != prev_usb.role_control:
            self.usbc_dialog_ui.label_cc1.setNum(usb.rc_cc1)
            self.usbc_dialog_ui.label_cc2.setNum(usb.rc_cc2)
            self.usbc_dialog_ui.label_rp.setNum(usb.rp_value)
            self.usbc_dialog_ui.label_drp.setNum(usb.drp)

        # Message header
        if usb.message_header != prev_usb.message_header:
            self.usbc_dialog_ui.label_cable.setNum(usb.cable_plug)
            self.usbc_dialog_ui.label_role.setNum(usb.data_role)
            self.usbc_dialog_ui.label_usbpd.setNum(usb.usb_spec)
            self.usbc_dialog_ui.label_power.setNum(usb.power_role)

        # CC Status
        if usb.cc_status != prev_usb.cc_status:
            self.usbc_dialog_ui.label_l4c.setNum(usb.Looking4Connection)
            self.usbc_dialog_ui.label_connresult.setNum(usb.ConnectResult)
            self.usbc_dialog_ui.label_cc2state.setNum(usb.cc2_state)
            self.usbc_dialog_ui.label_cc1state.setNum(usb.cc1_state)
            
        # Power Status
        if usb.power_status != prev_usb.power_status:
            self.usbc_dialog_ui.label_vbussink.setNum(usb.vbus_sink)
            self.usbc_dialog_ui.label_vconnpresent.setNum(usb.vconn_present)
            self.usbc_dialog_ui.label_vbuspresent.setNum(usb.vbus_present)
            self.usbc_dialog_ui.label_vbusdetection.setNum(usb.vbus_detect)
            self.usbc_dialog_ui.label_vbussourcing.setNum(usb.vbus_source)
            self.usbc_dialog_ui.label_highvolt.setNum(usb.high_volt)
            self.usbc_dialog_ui.label_tcpcinit.setNum(usb.tcpc_init)
            self.usbc_dialog_ui.label_debugacc.setNum(usb.debug_acc)

        # Extended Status
        if usb.extended_status != prev_usb.extended_status:
            self.usbc_dialog_ui.label_vsafe.setNum(usb.vsafe)
        
        if usb.vbus_voltage != prev_usb.vbus_voltage:
            self.usbc_dialog_ui.lcd_vbus.display(usb.vbus_voltage)
        
        if usb.i2c_state != prev_usb.i2c_state:
            self.usbc_dialog_ui.label_i2c.setNum(usb.i2c_state)
            stylesheet = stylesheet_display_none
            try:
                if usb.i2c_state > 0:
                    stylesheet = stylesheet_display_red
            except Exception:
                pass
            self.usbc_dialog_ui.label_i2c.setStyleSheet(stylesheet)

        self.usbc_dialog_ui.label_vsafe_3.setText(f"Digipot: {bms.digipot_value}")

    def display_bms_data(self, bms: BmsInfo, is_changed=False):
        prev_bms = self.prev_bms_data
        is_fw_type_changed = bms.hw_type != prev_bms.hw_type or bms.sw_profile != prev_bms.sw_profile or bms.bms_sw_version != prev_bms.bms_sw_version or is_changed
        # logger.debug(f"prev hw {self.prev_bms_data.hw_type} sw {self.prev_bms_data.sw_profile} -> hw {bms.hw_type} sw {bms.sw_profile}")
        # print(f"is_fw_type_changed {is_fw_type_changed}")
        # if is_fw_type_changed:

        if bms.bms_sw_version != prev_bms.bms_sw_version:
            sw_ver_text = f"{bms.ui_bms_sw_version()}"
            self.ui.label_fw_version.setText(sw_ver_text)

        cur_latest = 0
        if bms.is_reg_fc:
            if bms.hw_type == 0:
                cur_latest = self.beyonder_live.value
            elif bms.hw_type == 1:
                cur_latest = self.aike_t_dev_live.value
            elif bms.hw_type == 2:
                cur_latest = self.aike_t_dev_live.value
        else:
            cur_latest = self.beyonder_live.value

        self.latest_fw_changed.update(cur_latest)

        if self.ask_for_update:
            if bms.bms_sw_version != prev_bms.bms_sw_version or self.latest_fw_changed.is_changed():

                if is_semver_new(bms.bms_sw_version, cur_latest) and bms.bms_id_int:
                    logger.info(f"new firmware available: {cur_latest}")
                    self.show_confirm_dialog("new_fw_update", "New firmware!", f"New firmware available: {cur_latest}\nWould you like to update?")

        if bms.bms_id_int != prev_bms.bms_id_int:
            self.ui.label_battery_id.setText(bms.ui_bms_id())
            if bms.bms_id_int:
                self.ui.label_time_2.show()
            else:
                self.ui.label_time_2.hide()
                self.confirm_dialog.close()

        if bms.pack_state != prev_bms.pack_state:
            self.ui.label_battery_state.setText(ui_pack_state(bms))

        if bms.can_bus != prev_bms.can_bus or is_changed:
            if bms.can_bus:
                self.ui.label_can_status.setText("Active")
            else:
                self.ui.label_can_status.setText("Inactive")

        if bms.error_flags != prev_bms.error_flags or bms.bq_sys_stat != prev_bms.bq_sys_stat:
            if bms.error_flags == "":
                bms_error_state_text = "N/A"
            else:
                bms_error_state_text = f"{bms.error_flags}"
                errors = []

                if bms.error_flags & 1:
                    errors.append("Initial config")

                if bms.error_flags & 2:
                    errors.append("REQUEST OFF")

                if bms.error_flags & 4:
                    errors.append("BQ STATUS")
                    if bms.bq_sys_stat == "":
                        errors.append(f"BQ: N/A")
                    else:
                        errors.append(f"BQ: {bms.bq_sys_stat}")

                        if bms.bq_sys_stat & 1:
                            errors.append("BQ1: Overcurrent")

                        if bms.bq_sys_stat & 2:
                            errors.append("BQ2: Short-circuit")

                        if bms.bq_sys_stat & 4:
                            errors.append("BQ4: Overvoltage")

                        if bms.bq_sys_stat & 8:
                            errors.append("BQ8: Undervoltage")

                if bms.error_flags & 8:
                    errors.append("PRECHARGE")

                if bms.error_flags & 16:
                    errors.append("Under Voltage")

                if bms.error_flags & 32:
                    errors.append("Over Voltage")

                if bms.error_flags & 64:
                    errors.append("Over Current")

                if bms.error_flags & 128:
                    errors.append("Over Temperature")

                if len(errors):
                    errors_text = "\n".join(errors)
                    bms_error_state_text += f" ({errors_text})"

            self.ui.label_bms_error_state.setText(bms_error_state_text)

        if bms.attach_status != prev_bms.attach_status:

            self.ui.label_attach_status.setText(ui_attach_status(bms))

        if bms.bms_unread_error_count != prev_bms.bms_unread_error_count:
            self.ui.lcd_errors.display(bms.bms_unread_error_count)

        if bms.available_capacity != prev_bms.available_capacity:
            self.ui.lcd_capacity.display(bms.available_capacity)

        if bms.pack_soc != prev_bms.pack_soc:
            self.ui.display_soc.display(bms.pack_soc)

        update_power = is_changed
        if bms.voltage != prev_bms.voltage:
            self.ui.display_voltage.display(f"{bms.voltage}")
            update_power = True

        if bms.current != prev_bms.current:
            self.ui.display_current.display(f"{bms.current}")
            update_power = True
        if update_power:
            display_value = ""
            try:
                power = (bms.voltage / 1000) * (bms.current / 1000)
                display_value = f"{power:.2f}"
            except Exception:
                pass
            self.ui.lcd_power.display(display_value)
        if bms.cell_voltage_lowest != prev_bms.cell_voltage_lowest:
            self.ui.display_min_cell_voltage.display(f"{bms.cell_voltage_lowest}")

        if bms.cell_voltage_highest != prev_bms.cell_voltage_highest:
            self.ui.display_max_cell_voltage.display(f"{bms.cell_voltage_highest}")

        if bms.cap_sense_fill_time != prev_bms.cap_sense_fill_time:
            if bms.cap_sense_fill_time == 0xDEAD:
                cap_sense_text = f"DEAD"
            else:
                cap_sense_text = f"{bms.cap_sense_fill_time}"
            self.ui.lcd_capsense.display(cap_sense_text)

        cell_diff_value = ""
        if bms.cell_voltage_highest != "" and bms.cell_voltage_lowest != "":
            cell_diff_value = bms.cell_voltage_highest - bms.cell_voltage_lowest

        if self.cell_voltage_diff.is_changed_update(cell_diff_value):
            stylesheet = stylesheet_display_none
            try:
                if abs(cell_diff_value) > 100:
                    stylesheet = stylesheet_display_error

                elif abs(cell_diff_value) > 45:
                    stylesheet = stylesheet_display_warn
            except Exception:
                pass

            self.ui.lcd_cell_diff.display(f"{cell_diff_value}")
            self.ui.lcd_cell_diff.setStyleSheet(stylesheet)

        if bms.cycle_count != prev_bms.cycle_count:
            cell_cycle_count = ""
            if bms.cycle_count != "":
                cell_cycle_count = f"{bms.cycle_count}"

            self.ui.lcd_cycle_count.display(cell_cycle_count)

        avg_temp = int(calc_avg_temperature(bms))
        avg_temp_change = avg_temp != self.prev_avg_temp

        if bms.fet_temp != prev_bms.fet_temp or avg_temp_change:
            display_temp(self.ui.display_fet_temperature, bms.fet_temp, self.fet_temp_high, self.temp_low, self.temp_diff, avg_temp)

        if bms.pack_left_temp != prev_bms.pack_left_temp or avg_temp_change:
            display_temp(self.ui.lcd_temp1, bms.pack_left_temp, self.temp_high, self.temp_low, self.temp_diff, avg_temp)
        if bms.pack_center_temp != prev_bms.pack_center_temp or avg_temp_change:
            display_temp(self.ui.lcd_temp2, bms.pack_center_temp, self.temp_high, self.temp_low, self.temp_diff, avg_temp)
        if bms.pack_right_temp != prev_bms.pack_right_temp or avg_temp_change:
            display_temp(self.ui.lcd_temp3, bms.pack_right_temp, self.temp_high, self.temp_low, self.temp_diff, avg_temp)

        if bms.hw_type == 1 or bms.hw_type == 2:
            if bms.temp_usb != prev_bms.temp_usb or avg_temp_change:
                display_temp(self.ui.lcd_temp_usb, bms.temp_usb, self.usb_temp_high)
            if bms.temp_ts_1 != prev_bms.temp_ts_1 or avg_temp_change:
                display_temp(self.ui.lcd_ts1, bms.temp_ts_1, self.temp_high, self.temp_low, self.temp_diff, avg_temp)
            if bms.temp_ts_2 != prev_bms.temp_ts_2 or avg_temp_change:
                display_temp(self.ui.lcd_ts2, bms.temp_ts_2, self.temp_high, self.temp_low, self.temp_diff, avg_temp)
            if bms.temp_ts_3 != prev_bms.temp_ts_3 or avg_temp_change:
                display_temp(self.ui.lcd_ts3, bms.temp_ts_3, self.temp_high, self.temp_low, self.temp_diff, avg_temp)

        if bms.hw_type == 2:
            if bms.pack_temp_4 != prev_bms.pack_temp_4 or avg_temp_change:
                display_temp(self.ui.lcd_temp4, bms.pack_temp_4, self.temp_high, self.temp_low, self.temp_diff,
                             avg_temp)
            if bms.pack_temp_5 != prev_bms.pack_temp_5 or avg_temp_change:
                display_temp(self.ui.lcd_temp5, bms.pack_temp_5, self.temp_high, self.temp_low, self.temp_diff,
                             avg_temp)
            if bms.pack_temp_6 != prev_bms.pack_temp_6 or avg_temp_change:
                display_temp(self.ui.lcd_temp6, bms.pack_temp_6, self.temp_high, self.temp_low, self.temp_diff,
                             avg_temp)

        self.prev_avg_temp = avg_temp
        # is_low_high_changed = False
        # lowest = self.prev_lowest_scale
        # highest = self.prev_highest_scale

        if bms.cell_voltage_highest != prev_bms.cell_voltage_highest or bms.cell_voltage_lowest != prev_bms.cell_voltage_lowest or bms.overvoltage_limit != prev_bms.overvoltage_limit or bms.undervoltage_limit != prev_bms.undervoltage_limit:

            lowest = 0
            highest = 4000
            uv_limit = 3000
            if bms.overvoltage_limit != "" and bms.overvoltage_limit != 0:
                highest = bms.overvoltage_limit

            if bms.undervoltage_limit != "" and bms.undervoltage_limit != 0:
                uv_limit = bms.undervoltage_limit

            if bms.cell_voltage_highest != "" and bms.cell_voltage_lowest != "":
                lowest = 3900

                if bms.cell_voltage_lowest < lowest:
                    lowest = 3700

                if bms.cell_voltage_lowest < lowest:
                    lowest = uv_limit

                if bms.cell_voltage_lowest < uv_limit:
                    lowest = uv_limit - 200

                if bms.cell_voltage_lowest < lowest:
                    lowest = 2000

                if bms.cell_voltage_lowest < lowest:
                    lowest = 1000

                if bms.cell_voltage_lowest < lowest:
                    lowest = 0

                if bms.cell_voltage_highest > highest:
                    highest = 4040

                if bms.cell_voltage_highest > highest:
                    highest = 4200

                if bms.cell_voltage_highest > highest:
                    highest = 4250

                if bms.cell_voltage_highest > highest:
                    highest = 4500

            is_low_high_changed = lowest != self.prev_lowest_scale or highest != self.prev_highest_scale

            if is_low_high_changed:
                self.ui.gridGroupBox.setTitle(f"Cells ({round(lowest/1000,2)} ... {round(highest/1000,2)})")

                for i in range(12):
                    progressbar = self.cell_progressbars[i]
                    progressbar.setMaximum(highest)
                    progressbar.setMinimum(lowest)

                self.prev_lowest_scale = lowest
                self.prev_highest_scale = highest

        for i in range(12):
            self.set_cells(bms, i)

        if bms.balance_state != prev_bms.balance_state:
            balance_text = "N/A"
            if bms.balance_state != "":
                if bms.balance_state == 1:
                    balance_text = "Enabled"
                else:
                    balance_text = "Disabled"

            self.balancing_dialog_ui.label_balancing.setText(balance_text)

        if bms.unix_time != prev_bms.unix_time:
            timetag_str = "N/A"
            try:
                time_obj = datetime.fromtimestamp(bms.unix_time, timezone.utc)
                timetag_str = f"{time_obj.strftime('%Y-%m-%d %H:%M:%S')} ({bms.time_diff:.3f})"
            except Exception:
                pass

            self.ui.label_time.setText(timetag_str)

        if is_fw_type_changed:
            self.ui_show_hide_type(bms)

        if bms.error_flags != prev_bms.error_flags and bms.error_flags != "":
            if bms.error_flags & 0x2:
                self.ui.pushButton_requestoff.setText("Request ON")
            else:
                self.ui.pushButton_requestoff.setText("Request OFF")

        if bms.attach_pin_voltage != prev_bms.attach_pin_voltage:
            attach_pin_voltage_txt = ""
            if bms.attach_pin_voltage != "":
                attach_pin_voltage_txt = f"{bms.attach_pin_voltage}"
            self.ui.lcd_attach_pin_voltage.display(attach_pin_voltage_txt)

        if bms.temp_sensor_mask != prev_bms.temp_sensor_mask or is_changed:
            if bms.temp_sensor_mask == "":
                self.sensors_dialog_ui.pushButton_sensors_write.hide()
            else:
                self.sensors_dialog_ui.checkBox_dis_1.setChecked((bms.temp_sensor_mask >> 0) & 0x1)
                self.sensors_dialog_ui.checkBox_dis_2.setChecked((bms.temp_sensor_mask >> 1) & 0x1)
                self.sensors_dialog_ui.checkBox_dis_3.setChecked((bms.temp_sensor_mask >> 2) & 0x1)
                self.sensors_dialog_ui.checkBox_dis_4.setChecked((bms.temp_sensor_mask >> 3) & 0x1)
                self.sensors_dialog_ui.checkBox_dis_5.setChecked((bms.temp_sensor_mask >> 4) & 0x1)
                self.sensors_dialog_ui.checkBox_dis_6.setChecked((bms.temp_sensor_mask >> 5) & 0x1)

                self.ui.lcd_temp1.setDisabled((bms.temp_sensor_mask >> 0) & 0x1)
                self.ui.lcd_temp2.setDisabled((bms.temp_sensor_mask >> 1) & 0x1)
                self.ui.lcd_temp3.setDisabled((bms.temp_sensor_mask >> 2) & 0x1)

                self.ui.label_21.setDisabled((bms.temp_sensor_mask >> 0) & 0x1)
                self.ui.label_23.setDisabled((bms.temp_sensor_mask >> 1) & 0x1)
                self.ui.label_25.setDisabled((bms.temp_sensor_mask >> 2) & 0x1)

                self.sensors_dialog_ui.pushButton_sensors_write.show()

        if bms.overvoltage_limit != prev_bms.overvoltage_limit or bms.undervoltage_limit != prev_bms.undervoltage_limit or is_changed:
            label_text_ov = "N/A"
            label_text_uv = "N/A"
            label_lcd_ov = ""
            label_lcd_uv = ""
            if bms.overvoltage_limit == "":
                self.voltage_dialog_ui.pushButton_voltage_ov_write.hide()
                self.voltage_dialog_ui.pushButton_voltage_uv_write.hide()
            else:
                self.voltage_dialog_ui.pushButton_voltage_ov_write.show()
                self.voltage_dialog_ui.pushButton_voltage_uv_write.show()

                label_text_ov = f"{bms.overvoltage_limit}"
                label_lcd_ov = bms.overvoltage_limit

                label_text_uv = f"{bms.undervoltage_limit}"
                label_lcd_uv = bms.undervoltage_limit

            if prev_bms.overvoltage_limit == "" and bms.overvoltage_limit != "":
                self.voltage_dialog_ui.spinBox.setValue(bms.overvoltage_limit)

            if prev_bms.undervoltage_limit == "" and bms.undervoltage_limit != "":
                self.voltage_dialog_ui.spinBox_undevoltage.setValue(bms.undervoltage_limit)

            self.voltage_dialog_ui.label_32.setText(label_text_ov)
            self.voltage_dialog_ui.label_40.setText(label_text_uv)
            self.ui.lcdUnder.display(label_lcd_uv)
            self.ui.lcdOver.display(label_lcd_ov)

            pass

        if bms.digipot_value != prev_bms.digipot_value or is_changed:
            label_text = "N/A"
            if bms.digipot_value == "":
                self.digipot_dialog_ui.pushButton_digipot_write.hide()
            else:
                self.digipot_dialog_ui.pushButton_digipot_write.show()
                label_text = f"{bms.digipot_value}"
                if prev_bms.digipot_value == "":
                    self.digipot_dialog_ui.spinBox_digipot.setValue(bms.digipot_value)

            self.digipot_dialog_ui.label_digipot_value.setText(label_text)

        # remember last state
        self.prev_bms_data = deepcopy(bms)

    def reset_read_regs(self):
        # read pack info and pcb/fw types
        self.bms_read_regs = [0xff, 0xfc]

    def set_read_regs(self, bms: BmsInfo):
        self.reset_read_regs()

        self.bms_read_regs.extend([0xc0, 0xc1, 0xc3, 0xc5, 0xd4])


        if is_feature_supported(80000, 80035, bms.bms_sw_version):
            # unix time registers
            self.bms_read_regs.append(0xfe)

        if is_feature_supported(80000, 80056, bms.bms_sw_version):
            self.bms_read_regs.append(0xc8)

        self.bms_read_regs.extend([0xd1, 0xd2, 0xd3])

        if is_feature_supported(80000, 80054, bms.bms_sw_version):
            self.bms_read_regs.append(0xc8)

        if bms.hw_type == 1:
            # foldy
            if is_feature_supported(80000, 88815, bms.bms_sw_version):
                # USB C debug data
                self.bms_read_regs.append(0xCB)
            self.bms_read_regs.append(0xc6)
            if is_feature_supported(80000, 80055, bms.bms_sw_version):
                self.bms_read_regs.append(0xc9)
                self.bms_read_regs.append(0xcc)
            pass
        elif bms.hw_type == 2:
            self.bms_read_regs.append(0xc6)
            self.bms_read_regs.append(0xc9)

        if bms.hw_type == 0 or bms.hw_type == 2:
            # beyonder
            if is_feature_supported(80000, 80052, bms.bms_sw_version):
                # attach pin register
                self.bms_read_regs.append(0xca)
            pass

        # add 0xC2 last
        self.bms_read_regs.append(0xc2)
        pass

    def send_poll_reg(self, reg_nr):
        try:
            tx_msg = []
            self.bms_reader.can_bus.send_data(reg_nr, tx_msg)

        except Exception as e:
            logger.error(f"Could not TX to ask for data! {e}")

    def update_battery_data(self):
        poll_reg_nr = 0
        time_now = utc_time_seconds()
        if self.next_poll_time <= time_now:

            if self.bms_info.bms_sw_version == 0:
                self.bms_register_poll_counter = 0

            if self.bms_register_poll_counter == 0:
                self.last_poll_time = time_now

            if self.bms_register_poll_counter == len(self.bms_read_regs)-1:
                self.next_poll_time = self.last_poll_time + 1 / self.polls_per_sec

        # print(f"len {len(self.bms_read_regs)} ctr: {self.bms_register_poll_counter}")

            poll_reg_nr = self.bms_read_regs[self.bms_register_poll_counter]

        received_some_data = 0

        # logger.debug(f"get_bms_info: ask {poll_reg_nr:02X}")
        #
        # while read_messages_count > 0:
        #     try:
        #         bms_message = can_bus.read_data(100)
        #         received_some_data = self.update_reg(bms_message.id, bms_message.data)
        #
        #     except Exception as e:
        #         logger.error(f"Nothing received from CAN:{e}")
        #
        #     read_messages_count = read_messages_count - 1

        start = utc_time_seconds()
        timeout_ms = 20
        if poll_reg_nr:
            # logger.info(f"get_bms_info: ask {poll_reg_nr:02X}")
            timeout_ms = 100
            self.send_poll_reg(poll_reg_nr)
        update_ui = False
        try:
            while utc_time_seconds() - start < timeout_ms / 1000:
                try:
                    # timeout_left = abs((timeout_ms / 1000 - (utc_time_seconds()-start))*1000)
                    response_time = utc_time_seconds() - start
                    bms_response = self.bms_reader.can_bus.read_data(timeout_ms)
                    # logger.debug(f"bms_response: {bms_response}")
                    # if bms_response is not None:
                    if bms_response is not None and not bms_response.is_error_frame and bms_response.arbitration_id and len(bms_response.data):
                        # logger.debug(bms_response)
                        self.last_rx_data = utc_time_seconds()
                        received_msg_id = bms_response.arbitration_id & 0xFF
                        # print(f"{received_msg_id}")
                        # received_msg_id = 0xCB
                        if received_msg_id == 0xCB:
                            data_handling.update_cb(self.usb_info, bms_response.data)
                            pass
                        else:
                            self.bms_reader.update_reg(bms_response.arbitration_id, bms_response.data, response_time, self.bms_info, self.usb_info)

                        if poll_reg_nr and poll_reg_nr & 0xFF == received_msg_id:

                            self.set_next_reg()

                            # if received_msg_id == 0xC1:
                            #     update_ui = True

                            if received_msg_id == 0xC2:
                                self.csv_logging.update(self.bms_info)
                                update_ui = True
                            break
                except CanError as e:
                    logger.error(f"Message NOT received, canerror! {e}")
                    sleep(1)
                except Exception as e:
                    logger.error(f"Could not RX asked data! {e}")
            # detech data timeout
            if utc_time_seconds() - start >= timeout_ms / 1000:
                self.set_next_reg()
        except Exception as e:
            logger.error(f"Could not TX to ask for data! {e}")

        if self.bms_info.bms_id_int == 0:
            self.csv_logging.update(self.bms_info)

        self.can_bus_timeout = utc_time_seconds() - self.last_rx_data > BATTERY_DATA_TIMEOUT
        self.bms_info.can_bus = not self.can_bus_timeout

        if self.can_bus_timeout:
            self.reset_bms_info()
            self.reset_read_regs()
            self.next_poll_time = 0
            update_ui = True

        if self.bms_info.bms_sw_version != self.prev_bms_data_can.bms_sw_version or self.bms_info.hw_type != self.prev_bms_data_can.hw_type:
            self.set_read_regs(self.bms_info)
            self.next_poll_time = 0

        if update_ui:
            self.update_ui(deepcopy(self.bms_info), deepcopy(self.usb_info))

        # Protect FETs and SCP from overtemp
        # if self.bms_info.fet_temp != "":
        #     if self.bms_info.fet_temp > 50:
        #         print("FET overtemp, putting BMS to shipping mode!")
        #         self.put_bms_to_shipping()

        self.prev_bms_data_can = deepcopy(self.bms_info)

    def set_next_reg(self):
        if self.bms_info.bms_sw_version == 0 or self.bms_register_poll_counter >= len(
                self.bms_read_regs) - 1:
            self.bms_register_poll_counter = 0
        else:
            self.bms_register_poll_counter = self.bms_register_poll_counter + 1

    def send_timesync(self, utc_time):

        try:
            since_last = utc_time-self.prev_timesync
            if since_last > 0.98:
                timestamp = 0
                milliseconds = 0
                if self.timesync_enabled:
                    floor_time_now = floor(utc_time)
                    sec_from_zero = utc_time - floor_time_now
                    sw_ver = self.bms_info.bms_sw_version
                    # logger.debug(f"timesync: sec_from_zero {sec_from_zero} since_last {since_last}")
                    if sw_ver >= 80052 or sw_ver == 80000 or abs(sec_from_zero-round(sec_from_zero)) < 0.03:
                        timestamp = floor_time_now
                        milliseconds = floor(sec_from_zero*1000)

                        # logger.debug(f"timesync: {timestamp}.{milliseconds:03}")

                foldy_enable_output = 0
                if self.attach_foldy_bms:
                    foldy_enable_output = 1

                msg = pack(">iHBB", timestamp, milliseconds, 0, foldy_enable_output)
                # logger.debug(f"timesync msg: {binascii.hexlify(msg)}")

                if timestamp or not self.timesync_enabled:
                    self.prev_timesync = utc_time

                self.bms_reader.send_message_to_can(0xF000, msg)
                logger.debug(f"timesync msg: {hexlify(msg)}")
        except Exception as e:
            logger.debug(f"failed to send timesync: {e}")
            raise

    def send_master_command(self, main_code, sub, data):
        msg = pack(">IBBH", self.bms_info.bms_id_int, main_code, sub, data)
        self.bms_reader.send_message_to_can(0xfb01, msg)

    def windowThreadRun(self):
        # sleep(1)
        self.bms_reader.open_can()
        while self.testRunning.get():
            # logger.debug(f"looping")
            time_now = utc_time_seconds()

            if not self.can_bus_timeout and (self.attach_foldy_bms or self.timesync_enabled):
                self.send_timesync(time_now)

            data_cmd = UiCommand.NOT_SET
            try:
                data = self.from_ui_queue.get(False)
                data_cmd = data[0]
                if data_cmd == UiCommand.BMS_TO_SHIPPING:
                    self.put_bms_to_shipping()
                elif data_cmd == UiCommand.CLEAR_PRIMARY_FAULTS:
                    self.clear_primary_faults()
                elif data_cmd == UiCommand.ATTACH_FOLDY_BMS:
                    self.attach_foldy_bms = data[1]
                elif data_cmd == UiCommand.TIMESYNC:
                    self.timesync_enabled = data[1]
                elif data_cmd == UiCommand.BALANCING_PATTERN:
                    msg = pack(">BH", 6, data[1])
                    self.bms_reader.send_message_to_can(0xf123, msg)

                elif data_cmd == UiCommand.FW_UPDATE:
                    # do update
                    fw_version = data[1]


                    # use_temporary_attach = self.bms_info.attach_status == 0

                    use_temporary_attach = False

                    new_id = 0x20

                    # if self.bms_info.fw_type == 0 or self.bms_info.fw_type == 1:
                    logger.debug(f"updat_fw attach_status = {self.bms_info.attach_status}")
                    if self.bms_info.attach_status != 0xFF:
                        # new_id = self.bms_info.attach_status | 0xD0
                        if self.bms_info.fw_type == 0:
                            self.bms_reader.tx_identifier = 0xF000 | ((self.bms_info.attach_status | 0xD0) << 4) | 0xD
                        else:
                            self.bms_reader.tx_identifier = 0xFD0D
                        self.bms_reader.rx_identifier = 0xF000 | ((self.bms_info.attach_status | 0xD0) << 4) | 0xA
                    # elif self.bms_info.fw_type == 1:
                    else:

                        self.bms_reader.tx_identifier = 0xF000 | (new_id << 4) | 0xD
                        self.bms_reader.rx_identifier = 0xF000 | (new_id << 4) | 0xA
                        use_temporary_attach = True

                    try:

                        if use_temporary_attach:
                            msg = pack(">IBBH", self.bms_info.bms_id_int, 1, 1, new_id)
                            logger.debug(f"send_new_aid {new_id:x}")
                            self.bms_reader.can_bus.send_data(0xFB01, msg, True)

                        selected_fw_type = self.bms_info.fw_type
                        if data[2] is not None:
                            selected_fw_type = data[2]

                        logger.info(f"do fw update: {fw_version} fw_type: {selected_fw_type:02x}")
                        self.update_fw_msg("Starting", 0)
                        self.bms_reader.fw_update(fw_version, self.update_fw_msg, selected_fw_type)
                        self.update_fw_msg("Done", 100)
                        sleep(2)
                        self.update_fw_msg("", -1)
                    except Exception as e:
                        self.update_fw_msg(f"Failed: {e}", -2)
                        logger.error(f"UiCommand.FW_UPDATE error: {e}")
                    pass

                    if use_temporary_attach:
                        msg = pack(">IBBH", self.bms_info.bms_id_int, 1, 2, 0)
                        logger.debug(f"send_new_aid {new_id:x}")
                        self.bms_reader.can_bus.send_data(0xFB01, msg, True)

                elif data_cmd == UiCommand.POLL_REG:
                    logger.debug(f"poll_reg: {data[1]:02x}")
                    self.send_poll_reg(data[1])
                    pass

                elif data_cmd == UiCommand.MASTER_COMMAND:
                    print_msg = f"MASTER_COMMAND | {data[1]} | {data[2]} | {data[3]}"
                    pprint(data)
                    print(print_msg)
                    logger.debug(print_msg)
                    self.send_master_command(data[1], data[2], data[3])

                elif data_cmd == UiCommand.WRITE_BMSID:
                    # logger.debug(f"ui_bmsid_write: {data[1]:08x}")
                    msg = pack(">BL", 0xf, data[1])
                    print(f"Sending BMS ID: {data[1]:08x}")
                    self.bms_reader.send_message_to_can(0xf123, msg)
                    pass

            except Empty as e:
                pass
            except Exception as e:
                logger.error(f"from_ui_queue cmd: {data_cmd} | error: {e}")
                pass

            # logger.debug(f"attach: {self.attach_foldy_bms}")
            self.update_battery_data()

            # if self.bms_register_poll_counter >= len(self.bms_read_regs)-1:
            #     self.csv_logging.update(self.bms_info)
            # if self.bms_info.bms_sw_version == 0 or self.bms_register_poll_counter >= len(self.bms_read_regs):

            # if self.bms_register_poll_counter < len(self.bms_read_regs):
            #
            # if utc_time_seconds() - time_now < 0.1 and self.bms_register_poll_counter >= len(self.bms_read_regs):
            #
            #     # sync loop with milliseconds == 0
            #     time_now = utc_time_seconds()
            #     ms_stamp = time_now - floor(time_now)
            #     time_to_sleep = (ceil(ms_stamp * self.polls_per_sec) / self.polls_per_sec) - ms_stamp
            #     # logger.info(f"ms_stamp: {ms_stamp} to sleep: {time_to_sleep}")
            #     sleep(time_to_sleep)

        self.bms_reader.close_can()

    def update_checker(self):
        is_running = self.update_checker_thread_running
        logger.info(f"Started update_checker thread")

        bucket_url = "https://storage.googleapis.com/46e5307363aa417e00bb26a6d999c142cbab1aeb/COSCOOTER"
        fleet_url = "https://europe-west1-comodule-fleet.cloudfunctions.net/latest-firmware?apiKey=5Z9dZzrSvMeZr7gQ9IU1376h"
        next_check = time()+3
        while is_running.get():
            sleep(0.3)
            tt = time()
            if next_check < tt:
                next_check = tt + self.live_load_period
                rand_get = round(tt)

                # check for new BMS version
                bms_fw_version_url = f"{fleet_url}&random={rand_get}"
                logger.info(f"Read live BMS version from: {bms_fw_version_url}")
                try:
                    r = get(bms_fw_version_url, allow_redirects=True, timeout=5)
                    if r.status_code != 200:
                        raise Exception("invalid response")
                    buf = r.content.decode("UTF-8")
                    json_data = json.loads(buf)
                    bms_ver = int(json_data['bmsVer'])
                    logger.info(f"Current live BMS sw version: {bms_ver}")
                    self.beyonder_live.value = bms_ver
                except Exception as e:
                    logger.error(f"Failed to GET live BMS sw version, because: {e}")
                    pass

                try:
                    package_conf_file = "aike_t_dev"
                    ccs_version_url = f"{bucket_url}/{package_conf_file}?random={rand_get}"
                    logger.info(f"Read live aike_t battery version from: {ccs_version_url}")
                    r = get(ccs_version_url, allow_redirects=True, timeout=5)
                    if r.status_code != 200:
                        raise Exception("invalid response")
                    online_version = int(r.content.decode("UTF-8"))
                    logger.info(f"Current live CCS version: {online_version}")
                    self.aike_t_dev_live.value = online_version

                except Exception as e:
                    logger.error(f"Failed to GET live AIKE T bms version, because: {e}")
                    pass

    # [START closeEvent]
    def closeEvent(self, event):
        # do stuff
        print("close application requested")

        if self.testRunning.get():
            self.testRunning.clear()

            self.window_thread.join(timeout=5)

        if self.update_checker_thread_running.get():
            self.update_checker_thread_running.clear()
            self.update_checker_thread.join(timeout=5)

        print("Thread finished")

        self.fw_update_dialog.close()
        self.bmsid_update_dialog.close()
        self.sensors_dialog.close()
        self.balancing_dialog.close()
        self.voltage_dialog.close()
        self.digipot_dialog.close()
        self.confirm_dialog.close()
        self.usbc_dialog.close()

        self.window_open = False

        event.accept()  # let the window close

        # [END closeEvent]


