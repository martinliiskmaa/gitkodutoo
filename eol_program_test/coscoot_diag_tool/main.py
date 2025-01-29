import time
from configparser import ConfigParser
from struct import unpack
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow
from common.bmsinfo import BmsInfo
from common.data_handling import BmsReader
from common.helper import resize_bytes, logging_basic_config, utc_time_seconds, str2bool
from ccu_data import CCUData
from iot_data import IoTData
from vehicledata import VehicleData
from common.BatteryWindow import MyWindow as BatWindow, ui_attach_status, ui_pack_state
from common.mvar import LockableBoolean
from coscooter_diag_tool_gui import *
import sys
import threading
from PyQt5.QtCore import pyqtSignal
from common.settings import settings as settings_data
from pathlib import Path
from argparse import ArgumentParser
from multiprocessing import Queue, Value
from enum import Enum, auto
from queue import Empty
import logging
from copy import deepcopy

from scooter_data_handling import update_ccu, IotMessageHandler

logger = logging.getLogger('main')

import logging


def setup_settings(config_file=Path("config.conf")):
    settings = settings_data()
    settings.add_default("CAN", "driver", "can")
    settings.add_default("CAN", "bustype", "kvaser")
    settings.add_default("CAN", "bitrate", "250000")
    settings.add_default("CAN", "channel", "0")
    settings.add_default("CSV", "data_period", "1")

    settings.add_default("APP", "log_level", "ERROR")
    settings.add_default("APP", "dark_mode", "False")
    settings.add_default("APP", "selected_theme", "1")

    if config_file.exists():
        settings.read(config_file)

    return settings


class UiCommand(Enum):
    NOT_SET = auto()

    CLEAR_MARKED_ERROR_LEFT = auto()
    CLEAR_MARKED_ERROR_RIGHT = auto()

    CLEAR_PRIMARY_FAULTS_LEFT = auto()
    CLEAR_PRIMARY_FAULTS_RIGHT = auto()

    SWITCH_LEFT = auto()
    SWITCH_RIGHT = auto()

    CONF_CAN = auto()
    CONF_IOT = auto()
    OPEN_BAT = auto()
    RESET_CCU = auto()
    ASI_ON = auto()
    ASI_OFF = auto()
    BUZZER_1 = auto()
    CAN_TALK = auto()


    RESET_IOT = auto()
    TURN_OFF = auto()


def set_attach_state(label, bms):
    label.setText(ui_attach_status(bms))


def set_pack_state(label, bms):
    label.setText(ui_pack_state(bms))


class MyWindow(QMainWindow):
    update_left_signal = pyqtSignal([BmsInfo])
    update_right_signal = pyqtSignal([BmsInfo])
    update_ccu_signal = pyqtSignal([CCUData])
    update_iot_signal = pyqtSignal([IoTData])
    display_vehicle_signal = pyqtSignal([VehicleData])

    update_fw_msg_signal = pyqtSignal([str, int])

    def __init__(self, settings, config_file_name):
        # super().__init__()
        super(MyWindow, self).__init__()
        self.settings = settings
        self.config_file_name = config_file_name

        self.fullscreen_mode = self.settings.get('APP', 'fullscreen_mode', True, str2bool)

        self.timesync_enabled = self.settings.get("BMS", "timesync", True, str2bool)
        self.show_untested_features = self.settings.get("APP", "show_untested_features", function=str2bool)

        self.update_left_signal.connect(self.on_update_left)  # noqa
        self.update_right_signal.connect(self.on_update_right)  # noqa
        self.update_ccu_signal.connect(self.on_update_ccu)  # noqa
        self.update_iot_signal.connect(self.on_update_iot)  # noqa
        self.display_vehicle_signal.connect(self.display_vehicle_data)  # noqa

        self.from_ui_queue = Queue()
        self.bms_read_regs = []
        self.reset_read_regs()

                

        self.ui = Ui_coscooterDiagnosticsTool()
        self.ui.setupUi(self)
        self.ui.button_clear_primary_faults_left.clicked.connect(self.clear_primary_faults_left)
        self.ui.button_clear_primary_faults_right.clicked.connect(self.clear_primary_faults_right)
        self.ui.button_open_battery_door.clicked.connect(self.open_battery_door)
        self.ui.button_configure_ccu_canbus.clicked.connect(self.configure_ccu_canbus)
        self.ui.button_configure_ccu_iot_uart.clicked.connect(self.configure_ccu_iot_uart)
        self.ui.button_buzzer_on_1sec.clicked.connect(self.buzzer_on_1sec)
        self.ui.button_reset_ccu.clicked.connect(self.reset_ccu_command)
        self.ui.button_ccu_asi_lights_on.clicked.connect(self.ccu_asi_lights_on)
        self.ui.button_ccu_asi_lights_off.clicked.connect(self.ccu_asi_lights_off)
        self.ui.button_switch_to_left.clicked.connect(self.switch_to_left)
        self.ui.button_switch_to_right.clicked.connect(self.switch_to_right)
        self.ui.button_clear_marked_error_left.clicked.connect(self.clear_marked_error_left)
        self.ui.button_clear_marked_error_right.clicked.connect(self.clear_marked_error_right)
        self.ui.button_listen_and_talk.clicked.connect(self.toggle_listen_and_talk)
        self.ui.button_iot_reset.clicked.connect(self.iot_command_reset)
        self.ui.button_iot_turn_off.clicked.connect(self.iot_command_turn_off)
        self.ui.pushButton_theme.clicked.connect(self.theme)
        self.ui.pushButton_leftbat.clicked.connect(self.open_left_bat)
        self.ui.pushButton_rightbat.clicked.connect(self.open_right_bat)
        self.ui.pushButton_modelselect.clicked.connect(self.scoot_model)
        self.ui.button_restart.clicked.connect(restart)

    

        self.ui.display_soc_left.setDigitCount(6)
        self.ui.display_voltage_left.setDigitCount(6)
        self.ui.display_current_left.setDigitCount(6)
        self.ui.display_min_cell_voltage_left.setDigitCount(6)
        self.ui.display_max_cell_voltage_left.setDigitCount(6)
        self.ui.display_fet_temperature_left.setDigitCount(6)
        self.ui.display_precharge_result_left.setDigitCount(6)
        self.ui.display_soc_right.setDigitCount(6)
        self.ui.display_voltage_right.setDigitCount(6)
        self.ui.display_current_right.setDigitCount(6)
        self.ui.display_min_cell_voltage_right.setDigitCount(6)
        self.ui.display_max_cell_voltage_right.setDigitCount(6)
        self.ui.display_fet_temperature_right.setDigitCount(6)
        self.ui.display_precharge_result_right.setDigitCount(6)

        self.ui.comboBoxErrorList.addItem("Requested off", 1)
        self.ui.comboBoxErrorList.addItem("Precharge error", 3)
        self.ui.comboBoxErrorList.addItem("Undervoltage error", 4)
        self.ui.comboBoxErrorList.addItem("Overvoltage error", 5)
        self.ui.comboBoxErrorList.addItem("Overcurrent error", 6)
        self.data_process_state = True
        self.ui.textBrowserLogWindow.setText("Welcome Hero!")

        self.bms_register_poll_counter = 0

        self.setWindowIcon(QIcon('icon.png'))

        self.bms_reader = BmsReader(self.settings)
        self.vehicle_data = VehicleData()
        self.iot_msg_handler = IotMessageHandler()
        # ---------------------------------------------------------
        self.left_bat_window = BatWindow(self.settings, False)
        self.right_bat_window = BatWindow(self.settings, False)

        self.bms_info_left = BmsInfo(2)
        self.bms_info_right = BmsInfo(1)
        self.ccu_info = CCUData()
        self.iot_info = IoTData()
        self.testRunning = LockableBoolean()
        self.testRunning.set()
        self.windowThread = threading.Thread(target=self.windowThreadRun)
        self.windowThread.start()

        self.ui_bms_info_left = self.bms_info_left
        self.ui_bms_info_right = self.bms_info_right
        self.ui_ccu_info = self.ccu_info
        self.ui_iot_info = self.iot_info
        self.ui_vehicle_data = self.vehicle_data


    def item_visibility(item, show):
        if show:
            item.show()
        else:
            item.hide()

    def scoot_model(self):
        config = ConfigParser()
        config.read(self.config_file_name)
        model = self.ui.comboBoxModelList.currentText()
        if model == "Gen 1":

            self.ui.left_bat_frame.show()

        elif model == "Äike 11":

            self.ui.left_bat_frame.hide()

        elif model == "Äike T":

            self.ui.left_bat_frame.hide()

        # with open(self.config_file_name, 'w') as f:
        #     config.write(f)
        pass



    def on_clear_log(self):
        self.ui.textBrowserLogWindow.clear()

    def on_append_log(self, msg):
        self.ui.textBrowserLogWindow.append(msg)

    def update_bms_left(self, bms):
        self.update_left_signal.emit(deepcopy(bms))  # noqa

    def update_bms_right(self, bms):
        self.update_right_signal.emit(deepcopy(bms))  # noqa

    def update_ccu(self, ccu):
        self.update_ccu_signal.emit(deepcopy(ccu))  # noqa

    def update_iot(self, iot):
        self.update_iot_signal.emit(deepcopy(iot))  # noqa

    def update_vehicle_data(self, data):
        self.display_vehicle_signal.emit(deepcopy(data))  # noqa

    def open_left_bat(self):

        # if self.left_bat_window.fullscreen_mode:
        #     self.left_bat_window.showMaximized()
        # else:
        self.left_bat_window.show()

        self.left_bat_window.window_open = True

    def open_right_bat(self):
        # if self.right_bat_window.fullscreen_mode:
        #     self.right_bat_window.showMaximized()
        # else:
        self.right_bat_window.show()

        self.right_bat_window.window_open = True

    def clear_marked_error_left(self):
        print("clear_marked_error_left", self.ui.comboBoxErrorList.currentText())
        self.to_worker((UiCommand.CLEAR_MARKED_ERROR_LEFT, self.ui.comboBoxErrorList.currentData()))

    def clear_marked_error_right(self):
        print("clear_marked_error_right", self.ui.comboBoxErrorList.currentText())
        self.to_worker((UiCommand.CLEAR_MARKED_ERROR_RIGHT, self.ui.comboBoxErrorList.currentData()))

    def clear_primary_faults_left(self):
        print("clear_primary_faults_left")
        self.to_worker((UiCommand.CLEAR_PRIMARY_FAULTS_LEFT, ""))

    def clear_primary_faults_right(self):
        print("clear_primary_faults_right")
        self.to_worker((UiCommand.CLEAR_PRIMARY_FAULTS_RIGHT, ""))

    def switch_to_left(self):
        print("switch_to_left")
        self.to_worker((UiCommand.SWITCH_LEFT, ""))

    def switch_to_right(self):
        print("switch_to_right")
        self.to_worker((UiCommand.SWITCH_RIGHT, ""))

    def configure_ccu_canbus(self):
        print("configure CCU CAN channel with 250 kbaud")
        self.to_worker((UiCommand.CONF_CAN, ""))

    def configure_ccu_iot_uart(self):
        print("configure CCU IoT UART channel")
        self.to_worker((UiCommand.CONF_IOT, ""))

    def open_battery_door(self):
        print("open_battery_door")
        self.to_worker((UiCommand.OPEN_BAT, ""))

    def reset_ccu_command(self):
        print("reset_ccu_command")
        self.to_worker((UiCommand.RESET_CCU, ""))

    def ccu_asi_lights_on(self):
        print("ccu_asi_lights_on")

        self.to_worker((UiCommand.ASI_ON, ""))


    def ccu_asi_lights_off(self):
        print("ccu_asi_lights_off")

        self.to_worker((UiCommand.ASI_OFF, ""))


    def buzzer_on_1sec(self):
        print("buzzer_on_1sec")
        self.to_worker((UiCommand.BUZZER_1, ""))

    def toggle_listen_and_talk(self):

        self.to_worker((UiCommand.CAN_TALK, ""))
        if self.ui_vehicle_data.receive_only:
            self.ui.button_listen_and_talk.setText("Receive Only")
        else:
            self.ui.button_listen_and_talk.setText("Normal")

    def iot_command_reset(self):
        print("iot_command_reset")

        self.to_worker((UiCommand.RESET_IOT, ""))

    def iot_command_turn_off(self):
        print("iot_command_turn_off")
        self.to_worker((UiCommand.TURN_OFF, ""))

    def append_bat_error(self, bat_msg, msg):
        self.on_append_log(f"{bat_msg} {msg}!")

    def analyze_bat_errors(self, bms, bat_msg):
        error_flags_left = self.bms_info_left.error_flags
        if error_flags_left != "":
            if error_flags_left & 0x01:
                self.append_bat_error(bat_msg, "Initial config error")

            if error_flags_left & 0x02:
                self.append_bat_error(bat_msg, "Requested off error")

            if error_flags_left & 0x04:
                self.append_bat_error(bat_msg, "Primary error present")

            if error_flags_left & 0x08:
                self.append_bat_error(bat_msg, "Precharge error")

            if error_flags_left & 0x10:
                self.append_bat_error(bat_msg, "Undervoltage error")

            if error_flags_left & 0x20:
                self.append_bat_error(bat_msg, "Overvoltage error")

            if error_flags_left & 0x40:
                self.append_bat_error(bat_msg, "Overcurrent error")

            if error_flags_left & 0x80:
                self.append_bat_error(bat_msg, "Overtemperature error")

            if error_flags_left == 0:
                self.append_bat_error(bat_msg, "No error flags")
                
        error_flags_right = self.bms_info_right.error_flags
        if error_flags_right != "":
            if error_flags_right & 0x01:
                self.append_bat_error(bat_msg, "Initial config error")

            if error_flags_right & 0x02:
                self.append_bat_error(bat_msg, "Requested off error")

            if error_flags_right & 0x04:
                self.append_bat_error(bat_msg, "Primary error present")

            if error_flags_right & 0x08:
                self.append_bat_error(bat_msg, "Precharge error")

            if error_flags_right & 0x10:
                self.append_bat_error(bat_msg, "Undervoltage error")

            if error_flags_right & 0x20:
                self.append_bat_error(bat_msg, "Overvoltage error")

            if error_flags_right & 0x40:
                self.append_bat_error(bat_msg, "Overcurrent error")

            if error_flags_right & 0x80:
                self.append_bat_error(bat_msg, "Overtemperature error")

            if error_flags_right == 0:
                self.append_bat_error(bat_msg, "No error flags")

        bq_sys_stat_left = self.bms_info_left.bq_sys_stat

        if bq_sys_stat_left != "":
            bq_sys_stat_left &= 0x3F
            if bq_sys_stat_left & 0x01:
                self.append_bat_error(f"{bat_msg}[Primary]", "Overcurrent detected")

            if bq_sys_stat_left & 0x02:
                self.append_bat_error(f"{bat_msg}[Primary]", "Short circuit detected")

            if bq_sys_stat_left & 0x04:
                self.append_bat_error(f"{bat_msg}[Primary]", "Cell overvoltage detected")

            if bq_sys_stat_left & 0x08:
                self.append_bat_error(f"{bat_msg}[Primary]", "Cell undervoltage detected")

            if bq_sys_stat_left & 0x10:
                self.append_bat_error(f"{bat_msg}[Primary]", "Alert pin external override detected")

            if bq_sys_stat_left & 0x20:
                self.append_bat_error(f"{bat_msg}[Primary]", "Internal chip fault detected")

            if bq_sys_stat_left == 0:
                self.append_bat_error(f"{bat_msg}[Primary]", "No Errors")
                
        bq_sys_stat_right = self.bms_info_right.bq_sys_stat

        if bq_sys_stat_right != "":
            bq_sys_stat_right &= 0x3F
            if bq_sys_stat_right & 0x01:
                self.append_bat_error(f"{bat_msg}[Primary]", "Overcurrent detected")

            if bq_sys_stat_right & 0x02:
                self.append_bat_error(f"{bat_msg}[Primary]", "Short circuit detected")

            if bq_sys_stat_right & 0x04:
                self.append_bat_error(f"{bat_msg}[Primary]", "Cell overvoltage detected")

            if bq_sys_stat_right & 0x08:
                self.append_bat_error(f"{bat_msg}[Primary]", "Cell undervoltage detected")

            if bq_sys_stat_right & 0x10:
                self.append_bat_error(f"{bat_msg}[Primary]", "Alert pin external override detected")

            if bq_sys_stat_right & 0x20:
                self.append_bat_error(f"{bat_msg}[Primary]", "Internal chip fault detected")

            if bq_sys_stat_right == 0:
                self.append_bat_error(f"{bat_msg}[Primary]", "No Errors")

    def update_error_log(self):
        self.on_clear_log()

        self.analyze_bat_errors(self.ui_bms_info_left, "[Left battery]")
        self.analyze_bat_errors(self.ui_bms_info_right, "[Right battery]")

        if self.ui_vehicle_data.unattached_battery_one_id != 0:
            self.on_append_log(f"Unattached battery detected! ID: {self.ui_vehicle_data.unattached_battery_one_id:08X}")

        if self.ui_vehicle_data.unattached_battery_two_id != 0:
            self.on_append_log(f"Unattached battery detected! ID: {self.ui_vehicle_data.unattached_battery_two_id:08X}")

    def reset_read_regs(self):
        # read pack info and pcb/fw types
        self.bms_read_regs = [0xff, 0xfc]

    def display_vehicle_data(self, vehicle_data: VehicleData):

        self.ui_vehicle_data = vehicle_data
        can_status = "N/A"
        if not vehicle_data.last_data_bms_left.is_timeout() or not vehicle_data.last_data_bms_right.is_timeout() or not vehicle_data.last_data_ccu.is_timeout():
            if vehicle_data.receive_only:
                can_status = "Active, Receive only"
            else:
                can_status = "Active"
        else:
            if vehicle_data.receive_only:
                can_status = "Inactive, Receive only"
            else:
                can_status = "Inactive"

        self.ui.label_can_status.setText(can_status)
        self.update_error_log()

    def to_worker(self, command):
        self.from_ui_queue.put(command)

    def on_update_left(self, bms: BmsInfo):
        self.ui_bms_info_left = bms

        # UI update left bat
        if self.left_bat_window is not None:
            if self.left_bat_window.window_open:
                self.left_bat_window.display_bms_data(bms)

        # Battery ID
        self.ui.label_battery_id_left.setText(bms.ui_bms_id())

        # Battery state
        set_pack_state(self.ui.label_battery_state_left, bms)

        # Attach Status
        set_attach_state(self.ui.label_attach_status_left, bms)

        self.ui.label_fw_version_left.setText(bms.ui_bms_sw_version())

        # Error state
        self.ui.label_bms_error_state_left.setNum(bms.ui_error_flags())

        # Primary fault
        self.ui.label_bms_prim_faults_left.setNum(bms.ui_error_bq_flags() & 0x7F)

        # State of charge
        self.ui.display_soc_left.display(bms.pack_soc)

        # Pack voltage
        self.ui.display_voltage_left.display(bms.voltage)
        # Pack current
        self.ui.display_current_left.display(bms.current)
        # MIN cell voltage
        self.ui.display_min_cell_voltage_left.display(bms.cell_voltage_lowest)
        # MAX cell voltage
        self.ui.display_max_cell_voltage_left.display(bms.cell_voltage_highest)
        # FET temp
        self.ui.display_fet_temperature_left.display(bms.fet_temp)
        # Precharge result
        self.ui.display_precharge_result_left.display(bms.precharge_result)

        # self.update_error_log()

    def on_update_right(self, bms: BmsInfo):
        self.ui_bms_info_right = bms
        # UI update right bat
        if self.right_bat_window is not None:
            if self.right_bat_window.window_open:
                self.right_bat_window.display_bms_data(bms)
        # Battery ID
        self.ui.label_battery_id_right.setText(bms.ui_bms_id())

        # Battery state
        set_pack_state(self.ui.label_battery_state_right, bms)

        # Attach Status
        set_attach_state(self.ui.label_attach_status_right, bms)

        # FW Version
        self.ui.label_fw_version_right.setText(bms.ui_bms_sw_version())

        # Error state
        self.ui.label_bms_error_state_right.setNum(bms.ui_error_flags())

        # Primary fault
        self.ui.label_bms_prim_faults_right.setNum(bms.ui_error_bq_flags() & 0x7F)

        # State of charge
        self.ui.display_soc_right.display(bms.pack_soc)

        # Pack voltage
        self.ui.display_voltage_right.display(bms.voltage)
        # Pack current
        self.ui.display_current_right.display(bms.current)
        # MIN cell voltage
        self.ui.display_min_cell_voltage_right.display(bms.cell_voltage_lowest)
        # MAX cell voltage
        self.ui.display_max_cell_voltage_right.display(bms.cell_voltage_highest)
        # FET temp
        self.ui.display_fet_temperature_right.display(bms.fet_temp)
        # Precharge result
        self.ui.display_precharge_result_right.display(bms.precharge_result)

        # self.update_error_log()

    def on_update_ccu(self, ccu: CCUData):
        self.ui_ccu_info = ccu
        # UI Update
        # FW Version
        if ccu.ccu_fw_version is not None:
            self.ui.label_ccu_fw_version.setText(str(ccu.ccu_fw_version))
        else:
            self.ui.label_ccu_fw_version.setText("N/A")

        # Comms Config
        if ccu.ccu_comms_config_state is not None:
            self.ui.label_ccu_comms_config.setNum(ccu.ccu_comms_config_state)
        else:
            self.ui.label_ccu_comms_config.setText("N/A")

        # ASI Status
        if ccu.ccu_asi_status == 0:
            self.ui.label_asi_status.setText("OFF")
        elif ccu.ccu_asi_status == 1:
            self.ui.label_asi_status.setText("ON")
        else:
            self.ui.label_asi_status.setText("N/A")

        # Lights Status

        if ccu.ccu_lights_status == 0:
            self.ui.label_ccu_lights_status.setText("OFF")
        elif ccu.ccu_lights_status == 1:
            self.ui.label_ccu_lights_status.setText("ON")
        else:
            self.ui.label_ccu_lights_status.setText("N/A")

        # self.update_error_log()

    def on_update_iot(self, iot: IoTData):
        self.ui_iot_info = iot
        # UI Update
        # IoT ID
        nrf_id = "N/A"
        if iot.iot_nrf_id is not None:
            nrf_id = f"{iot.iot_nrf_id:016x}"
        self.ui.label_iot_nrfid.setText(nrf_id)

        # FW Version
        iot_fw = "N/A"
        if iot.iot_nrf_fw_type is not None or iot.iot_nrf_fw_version is not None:
            iot_fw = f"{iot.iot_nrf_fw_type}.{iot.iot_nrf_fw_version}"
        self.ui.label_iot_fw_version.setText(iot_fw)

        # Network Status
        net_signal = "N/A"
        if iot.iot_net_status is not None:
            net_text = "Connecting"

            if iot.iot_net_status == 0:
                net_text = "UNKNOWN"
            elif iot.iot_net_status == 1:
                net_text = "NETWORK Connected"
            elif iot.iot_net_status == 2:
                net_text = "PDP ACTIVATED"
            elif iot.iot_net_status == 3:
                net_text = "TCP Connected"
            elif iot.iot_net_status == 4:
                net_text = "MQTT Connected"
            elif iot.iot_net_status == 5:
                net_text = "MQTT Subscribed"

            net_signal = f"{iot.iot_net_status} ({net_text})"
        self.ui.label_iot_net_status.setText(net_signal)

        # Signal Strength
        net_signal = "N/A"
        if iot.iot_net_signal_strength is not None:
            net_type_text = "3G"
            if iot.iot_net_type == 1 or iot.iot_net_type == 2:
                net_type_text = "2G"
            elif iot.iot_net_type == 0:
                net_type_text = "No tower"
            net_signal = f"{iot.iot_net_signal_strength} ({net_type_text})"
        self.ui.label_iot_net_signal_strength.setText(net_signal)

        # Battery Voltage

        bat_voltage = "N/A"
        if iot.iot_bat_voltage is not None:
            bat_voltage = f"{iot.iot_bat_voltage} V"
        self.ui.label_iot_bat_voltage.setText(bat_voltage)

        # Battery Temp
        bat_temp = "N/A"
        if iot.iot_bat_temperature is not None:
            bat_temp = f"{iot.iot_bat_temperature} °C"
        self.ui.label_iot_bat_temp.setText(bat_temp)

        # Battery Charger
        charger_text = "N/A"
        if iot.iot_bat_charger is not None:
            charger_text = ""
            if iot.iot_bat_charger == 0:
                charger_text = "Ready"
            elif iot.iot_bat_charger == 1:
                charger_text = "Charging"
            elif iot.iot_bat_charger == 2:
                charger_text = "Done"
            elif iot.iot_bat_charger == 3:
                charger_text = "Fault"
            charger_text = f"{iot.iot_bat_charger} ({charger_text})"

        self.ui.label_iot_bat_charger.setText(charger_text)

        # Module Vin
        module_vin = "N/A"
        if iot.iot_module_vin is not None:
            module_vin = f"{iot.iot_module_vin} V"
        self.ui.label_iot_module_vin.setText(module_vin)

        # GNSS fix
        gps_fix_text = "N/A"
        if iot.iot_gps_fix_state is not None:
            gps_fix_text = ""
            if iot.iot_gps_fix_state == 0:
                gps_fix_text = "No fix"
            elif iot.iot_gps_fix_state == 1:
                gps_fix_text = "no fix"
            elif iot.iot_gps_fix_state == 2:
                gps_fix_text = "2D fix"
            elif iot.iot_gps_fix_state == 3:
                gps_fix_text = "3D fix"
            elif iot.iot_gps_fix_state == 4:
                gps_fix_text = "BLE Beacon fix"
            gps_fix_text = f"{iot.iot_gps_fix_state} ({gps_fix_text})"

        self.ui.label_iot_gps_fix_state.setText(gps_fix_text)

        # GNSS used sats
        gps_sats = "N/A"
        if iot.iot_gps_used_sats is not None:
            gps_sats = f"{iot.iot_gps_used_sats}"
        self.ui.label_iot_gps_used_sats.setText(gps_sats)

        # GNSS max cno
        gps_max_cno = "N/A"
        if iot.iot_gps_max_cno is not None:
            gps_max_cno = f"{iot.iot_gps_max_cno}"
        self.ui.label_iot_gps_max_cno.setText(gps_max_cno)

        self.update_error_log()

    def send_receive_frames(self, id_to_ask, timeout_ms):

        if id_to_ask and not self.vehicle_data.receive_only:
            msg = []
            if id_to_ask == 0xd101:
                msg = self.iot_msg_handler.get_next_message(self.iot_info.iot_nrf_id)

            try:
                # print(f"[CAN SEND] id: {id_to_ask:04x} bms {hexlify(bytes(msg))}")
                self.bms_reader.can_bus.send_data(id_to_ask, msg)
            except Exception as e:
                print(f"Could not TX to ask for data! {e}")
        wait_end = utc_time_seconds()+timeout_ms/1000
        # print(f"wait_end {wait_end}| now {utc_time_seconds()}")

        while utc_time_seconds() < wait_end:
            try:
                timeout = (wait_end-utc_time_seconds())*1000
                bms_message = self.bms_reader.can_bus.read_data(timeout)
                if bms_message is not None and len(bms_message.data) and not bms_message.is_error_frame:

                    msg_id = bms_message.arbitration_id
                    # print(f"[CAN RECV] id: {msg_id:04x} bms {hexlify(bms_message.data)}")
                    data = resize_bytes(bms_message.data, 8)

                    if msg_id == 0x40f or msg_id == 0x401:
                        self.vehicle_data.last_data_ccu.update()
                        update_ccu(msg_id, bms_message.data, self.ccu_info)
                        self.update_ccu(self.ccu_info)

                    elif msg_id == 0xc0:
                        self.vehicle_data.last_data_other.update()

                        _, bat_id = unpack(">II", data)

                        if self.vehicle_data.unattached_battery_one_id == 0:
                            self.vehicle_data.unattached_battery_one_id = bat_id
                        else:
                            if self.vehicle_data.unattached_battery_one_id != bat_id:
                                self.vehicle_data.unattached_battery_two_id = bat_id

                    elif msg_id == 0xda01:
                        self.vehicle_data.last_data_iot.update()
                        self.iot_msg_handler.update_iot(msg_id, bms_message.dlc, bms_message.data, self.iot_info)
                        self.update_iot(self.iot_info)
                        # print(f"[CAN RECV] id: {msg_id:04x} bms {hexlify(bms_message.data)}")
                        break

                    elif msg_id & 0x100:
                        self.bms_reader.update_reg(msg_id, bms_message.data, 0, self.bms_info_right)
                        self.vehicle_data.last_data_bms_right.update()
                        self.update_bms_right(self.bms_info_right)

                    elif msg_id & 0x200:
                        self.bms_reader.update_reg(msg_id, bms_message.data, 0, self.bms_info_left)
                        self.vehicle_data.last_data_bms_left.update()
                        self.update_bms_left(self.bms_info_left)

                    if id_to_ask and not self.vehicle_data.receive_only:
                        if msg_id == id_to_ask:
                            break
                    # else:
                    #     print(f"No RX ID match from CAN {msg_id:04x}")
            except Exception as e:

                print(f"Nothing received from CAN ({e})")
                time.sleep(1)



    def poll_vehicle_data(self):
        id_to_ask_for_data = 0
        timeout_ms = 50

        if not self.vehicle_data.receive_only:
            read_regs = []
            self.left_bat_window.set_read_regs(self.bms_info_left)
            for reg in self.left_bat_window.bms_read_regs:
                read_regs.append(0x200 | reg)

            self.right_bat_window.set_read_regs(self.bms_info_right)
            for reg in self.right_bat_window.bms_read_regs:
                read_regs.append(0x100 | reg)

            read_regs.extend([0x40f, 0x401, 0xd101])
            # print(read_regs)
            # read_regs = [0x1ff, 0x2ff, 0x1c2, 0x2c2, 0x40f, 0x401, 0xd101]
            if self.bms_register_poll_counter >= len(read_regs):
                self.bms_register_poll_counter = 0

            id_to_ask_for_data = read_regs[self.bms_register_poll_counter]

            if id_to_ask_for_data == 0xd101:
                timeout_ms = 2000

            self.bms_register_poll_counter += 1
        else:
            self.bms_register_poll_counter = 0

        self.send_receive_frames(id_to_ask_for_data, timeout_ms)

        # check for data timeout
        if self.vehicle_data.last_data_other.is_timeout():
            self.vehicle_data.unattached_battery_one_id = 0
            self.vehicle_data.unattached_battery_two_id = 0
            self.update_vehicle_data(self.vehicle_data)

        if self.vehicle_data.last_data_bms_left.is_timeout():
            self.bms_info_left = BmsInfo(2)
            self.update_bms_left(self.bms_info_left)

        if self.vehicle_data.last_data_bms_right.is_timeout():
            self.bms_info_right = BmsInfo(1)
            self.update_bms_right(self.bms_info_right)

        if self.vehicle_data.last_data_ccu.is_timeout():
            self.ccu_info = CCUData()
            self.update_ccu(self.ccu_info)

        if self.vehicle_data.last_data_iot.is_timeout():
            self.iot_msg_handler.reset()
            self.iot_info = IoTData()
            self.update_iot(self.iot_info)


        self.update_vehicle_data(self.vehicle_data)

    def windowThreadRun(self):
        time.sleep(1)

        self.bms_reader.open_can()
        while self.testRunning.get():

            data_cmd = UiCommand.NOT_SET
            try:
                data = self.from_ui_queue.get(False)
                data_cmd = data[0]
                if data_cmd == UiCommand.CLEAR_MARKED_ERROR_LEFT:
                    self.bms_reader.send_message_to_can(0x02e0, [0x02, data[1]])

                elif data_cmd == UiCommand.CLEAR_MARKED_ERROR_RIGHT:
                    self.bms_reader.send_message_to_can(0x01e0, [0x02, data[1]])

                elif data_cmd == UiCommand.CLEAR_PRIMARY_FAULTS_LEFT:
                    self.bms_reader.send_message_to_can(0x02e0, [0x03, 0x74])

                elif data_cmd == UiCommand.CLEAR_PRIMARY_FAULTS_RIGHT:
                    self.bms_reader.send_message_to_can(0x01e0, [0x03, 0x74])

                elif data_cmd == UiCommand.SWITCH_LEFT:
                    self.bms_reader.send_message_to_can(0x02e0, [0x05, 0x01])

                elif data_cmd == UiCommand.SWITCH_RIGHT:
                    self.bms_reader.send_message_to_can(0x01e0, [0x05, 0x01])

                elif data_cmd == UiCommand.CONF_CAN:
                    self.bms_reader.send_message_to_can(0xcc11, [0x04, 0x01, 0x03, 0x03, 0xd0, 0x90])

                elif data_cmd == UiCommand.CONF_IOT:
                    self.bms_reader.send_message_to_can(0xcc01, [0x01, 0x00, 0x01, 0x01, 0xc2, 0x00])

                elif data_cmd == UiCommand.OPEN_BAT:
                    self.bms_reader.send_message_to_can(0x04f1, [0xff, 0x01, 0xff, 0xff])

                elif data_cmd == UiCommand.RESET_CCU:
                    self.ccu_info = CCUData()
                    self.bms_reader.send_message_to_can(0x04f1, [0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x01])

                elif data_cmd == UiCommand.ASI_ON:
                    self.bms_reader.send_message_to_can(0x04f1, [0xff, 0xff, 0x01, 0x01])

                elif data_cmd == UiCommand.ASI_OFF:
                    self.bms_reader.send_message_to_can(0x04f1, [0xff, 0xff, 0x00, 0x00])

                elif data_cmd == UiCommand.BUZZER_1:
                    self.bms_reader.send_message_to_can(0x04f1, [0xff, 0xff, 0xff, 0xff, 0x01, 0x32, 0x33])

                elif data_cmd == UiCommand.RESET_IOT:
                    self.iot_info = IoTData()
                    self.bms_reader.send_message_to_can(0xd101, [0xcc, 0x01, 0x00, 0x00, 0x00, 0x64])

                elif data_cmd == UiCommand.TURN_OFF:
                    self.iot_info = IoTData()
                    self.bms_reader.send_message_to_can(0xd101, [0xcc, 0x02, 0x00, 0x00, 0x13, 0x88])

                elif data_cmd == UiCommand.CAN_TALK:
                    self.vehicle_data.receive_only = not self.vehicle_data.receive_only
                    if self.vehicle_data.receive_only:
                        print("RX only")
                    else:
                        print("RX and TX")

            except Empty as e:
                pass
            except Exception as e:
                logger.error(f"from_ui_queue cmd: {data_cmd} | error: {e}")
                pass
            self.poll_vehicle_data()
            # time.sleep(0.1)

        self.bms_reader.close_can()

    # [START closeEvent]
    def closeEvent(self, event):
        # do stuff
        print("close application requested")

        self.testRunning.clear()
        self.windowThread.join(timeout=5)

        print("Thread finished")

        if self.left_bat_window.window_open:
            self.left_bat_window.close()

        if self.right_bat_window.window_open:
            self.right_bat_window.close()

        event.accept()  # let the window close

        # [END closeEvent]
    def theme(self):
        try:
            config = ConfigParser()
            config.read(self.config_file_name)
            theme = self.ui.comboBoxThemeList.currentText()
            import qdarktheme
            if theme == "Dark":
                config.set('APP', 'selected_theme', theme)
                self.setStyleSheet(qdarktheme.load_stylesheet())

            elif theme == "Light":
                config.set('APP', 'selected_theme', theme)
                self.setStyleSheet(qdarktheme.load_stylesheet("light"))
            else:
                config.set('APP', 'selected_theme', theme)
                with open(self.config_file_name, 'w') as f:
                    config.write(f)
                pass

                restart()


            with open(self.config_file_name, 'w') as f:
                config.write(f)
            pass
        except Exception as e:
            print({e})


def restart():
    import sys
    print("argv was",sys.argv)
    print("sys.executable was", sys.executable)
    print("restart now")

    import os
    os.execv(sys.executable, ['python'] + sys.argv)

def main():
    logging_basic_config()
    app = QtWidgets.QApplication([])

    app.setStyleSheet("")  # Fixes the font size.
    parser = ArgumentParser(description='Coscooter Diagnostics Tool')
    parser.add_argument('--config', type=str, help='Configuration file', default="config.conf")
    args = parser.parse_args()
    config_file_name = Path(args.config)
    settings = setup_settings(config_file_name)
    config = ConfigParser()
    config.read(config_file_name)
    application = MyWindow(settings, config_file_name)
    

    if application.fullscreen_mode:
        application.showMaximized()
    else:
        application.show()

    try:
        import qdarktheme

        if config.get('APP', 'selected_theme'):
            try:
                if config.get('APP', 'selected_theme') == "Dark":
                    app.setStyleSheet(qdarktheme.load_stylesheet())
                elif config.get('APP', 'selected_theme') == "Light":
                    app.setStyleSheet(qdarktheme.load_stylesheet("light"))

            except Exception:
                print(f"Failed to import dark theme module")
                pass
    except ImportError as e:
        print(f"OMG!!! {e}")
        pass
    except Exception as e:
        print(f"Another problem!!! {e}")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
    
