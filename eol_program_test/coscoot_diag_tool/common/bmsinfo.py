import datetime
import logging
from math import floor

# import psutil

from .helper import utc_time_seconds
from .settings import settings

import random
# from uptime import uptime

# storage_path = get_config('CCS', 'disk_usage_path', "/")
# warn_cell_voltage_diff = get_config('WARNING', 'cell_voltage_diff', 89, int)
# warn_temperature_diff = get_config('WARNING', 'temperature_diff', 10, int)
warn_cell_voltage_diff = 89
warn_temperature_diff = 10


def to_ui(value, unit: str = "", divider: int = 1, rounding: int = 0):
    if value != "":
        if value < 0 < rounding:
            rounding -= 1
        val = round(value / divider, rounding)
        if rounding == 1:
            val = f"{val:.1f}"
        elif rounding == 2:
            val = f"{val:.2f}"
        return f"{val}{unit}"
    return ""

#
# def get_cpu_temp():
#     cpu_temp = 0
#     try:
#         temp_file = open("/sys/class/thermal/thermal_zone0/temp")
#         cpu_temp = temp_file.read()
#         temp_file.close()
#     except:
#         pass
#
#     return round(float(cpu_temp) / 1000, 2)
#
#
# def cpu_load():
#     return round(psutil.getloadavg()[2] / psutil.cpu_count() * 100)
#
#
# def get_uptime():
#     return uptime() / 3600 / 24


def battery_test_csv_headers():
    return "timestamp,cell_1_v,cell_2_v,cell_3_v,cell_4_v,cell_5_v,cell_6_v,cell_7_v,cell_8_v,cell_9_v,cell_10_v,cell_11_v,cell_12_v,pack_current,pack_center_temp,ambient_temp"


# [START class BmsInfo]
class BmsInfo:
    """
        payload format: CSV
        # timestamp - seconds since unix epoch
            self.cpu_load,
            self.cpu_temp,
            self.mem_usage,
            self.storage_usage,
        # connected_bat - how many batteries currently connected
        # charging_bat - how many batteries currently charging
        # slot_no - slot no of current BMS
        bms_id
        pack_state
        attach_status
        error_flags
        pack_soc
        fet_temp
        pack_left_temp
        pack_center_temp
        pack_right_temp
        voltage
        current
        bq_sys_stat
        precharge_result
        cycle_count
        coulomb_soc
        available_capacity
        collected_regen
        cell_voltage_avg
        cell_voltage_lowest
        cell_voltage_highest
        min_cell_no
        max_cell_no
    """

    # [START __init__]
    def __init__(self, slot_no=""):
        # timestamp - seconds since unix epoch
        self.timestamp = utc_time_seconds()
        # connected_bat - how many batteries currently connected
        self.connected_bat = ""
        # charging_bat - how many batteries currently charging
        self.charging_bat = ""
        # slot_no - slot no of current BMS
        self.slot_no = slot_no
        self.bms_id = ""
        self.bms_id_int = 0
        self.pack_state = ""
        self.attach_status = ""
        self.error_flags = ""
        # battery State Of Charge
        self.pack_soc = ""
        self.fet_temp = ""
        self.pack_left_temp = ""
        self.pack_center_temp = ""
        self.pack_right_temp = ""
        self.voltage = ""
        self.current = ""
        self.bq_sys_stat = ""
        self.precharge_result = ""
        self.cycle_count = ""
        self.coulomb_soc = ""
        self.available_capacity = ""
        self.collected_regen = ""
        self.cell_voltages = {0: "", 1: "", 2: "", 3: "", 4: "", 5: "", 6: "", 7: "", 8: "", 9: "", 10: "", 11: ""}
        self.cell_voltage_avg = ""
        self.cell_voltage_lowest = ""
        self.cell_voltage_highest = ""
        self.min_cell_no = ""
        self.max_cell_no = ""
        self.balance_state = ""
        self.balance_pattern = ""
        self.cap_sense_fill_time = ""

        self.temp_ts_1 = ""
        self.temp_ts_2 = ""
        self.temp_ts_3 = ""
        self.temp_usb = ""

        self.pack_temp_4 = ""
        self.pack_temp_5 = ""
        self.pack_temp_6 = ""

        self.attach_pin_voltage = ""

        self.unix_time = ""
        self.time_diff = ""

        self.bms_sw_version = 0
        self.sw_upgrade_text = ""
        self.relay_board = ""
        self.can_bus = ""
        self.ambient_temp = ""
        self.up_time = ""
        self.cpu_usage = ""
        self.cpu_temp = ""
        self.mem_usage = ""
        self.storage_usage = ""
        self.can_problem = False

        self.is_slow_charging = False

        self.flash_write_count = 0
        self.bms_unread_error_count = 0

        self.production_date = ""
        self.production_message = ""
        self.is_reg_fc = False
        self.pcb_version = 0
        self.fw_type = 0
        self.hw_type = 0
        self.sw_profile = 0

        self.temp_sensor_mask = ""
        self.overvoltage_limit = ""
        self.undervoltage_limit = ""
        self.digipot_value = ""

    # [END __init__]

    # def update_stats(self):
    #     self.up_time = get_uptime()
    #     self.cpu_usage = cpu_load()
    #     self.cpu_temp = get_cpu_temp()
    #     self.mem_usage = round(psutil.virtual_memory().used * 100 / psutil.virtual_memory().total, 1)
    #     self.storage_usage = round(psutil.disk_usage(storage_path).percent, 1)

    # [START to_csv]
    def to_csv(self):
        v = self.cell_voltages
        ambient = ""
        if self.ambient_temp != "":
            ambient = f"{self.ambient_temp:.1f}"
        return f"{floor(self.timestamp)};{self.cpu_usage};{self.cpu_temp:.1f};{self.mem_usage:.1f};{self.storage_usage:.1f};{self.connected_bat};{self.charging_bat};{self.slot_no + 1};{self.up_time:.3f};{self.relay_board};{self.can_bus};{ambient};{self.bms_id};{self.pack_state};{self.attach_status};{self.error_flags};{self.pack_soc};{self.fet_temp};{self.pack_left_temp};{self.pack_center_temp};{self.pack_right_temp};{self.voltage};{self.current};{self.bq_sys_stat};{self.cycle_count};{self.coulomb_soc};{self.available_capacity};{v[0]};{v[1]};{v[2]};{v[3]};{v[4]};{v[5]};{v[6]};{v[7]};{v[8]};{v[9]};{v[10]};{v[11]};{self.balance_pattern};{self.cap_sense_fill_time}"

    # [END to_csv]

    def to_csv_test(self):
        v = self.cell_voltages
        ambient = ""
        if self.ambient_temp != "":
            ambient = f"{self.ambient_temp:.1f}"

        return f"{self.timestamp:.3f};{ambient};{self.pack_state};{self.attach_status};{self.error_flags};{self.pack_soc};{self.voltage};{self.current};{self.bq_sys_stat};{self.cycle_count};{self.coulomb_soc};{self.available_capacity};{v[0]};{v[1]};{v[2]};{v[3]};{v[4]};{v[5]};{v[6]};{v[7]};{v[8]};{v[9]};{v[10]};{v[11]};{self.balance_pattern};{self.cap_sense_fill_time};{self.fet_temp};{self.pack_left_temp};{self.pack_center_temp};{self.pack_right_temp};{self.temp_ts_1};{self.temp_ts_2};{self.temp_ts_3};{self.temp_usb}"

    def to_battery_test_csv(self, start_time=0):
        v = self.cell_voltages
        ambient = f"{self.ambient_temp:.1f}" if self.ambient_temp != "" else ""
        return f"{self.timestamp-start_time:.3f},{v[0]/1000:.3f},{v[1]/1000:.3f},{v[2]/1000:.3f},{v[3]/1000:.3f},{v[4]/1000:.3f},{v[5]/1000:.3f},{v[6]/1000:.3f},{v[7]/1000:.3f},{v[8]/1000:.3f},{v[9]/1000:.3f},{v[10]/1000:.3f},{v[11]/1000:.3f},{self.current/1000:.3f},{self.pack_center_temp},{ambient}"

    def is_connected(self):
        return self.pack_state != ""

    def set_disconnected(self):
        self.pack_state = ""

    def is_charging(self):
        if self.pack_state != "":
            return self.pack_state == 4 or self.pack_state == 5 or self.is_slow_charge()
        return False

    def is_attached(self):
        if self.attach_status != "":
            return self.attach_status == 6 or self.pack_state == 3 or 0x20 <= self.attach_status <= 0x4F
        return False

    def is_battery_full(self, soc=95):
        return self.pack_state == 0 and self.ui_soc_int() > soc

    def is_slow_charge(self):
        return self.is_slow_charging

    def is_reg_c1(self):
        return self.current != ""

    def is_reg_c3(self):
        return self.precharge_result != ""

    def is_reg_c4(self):
        return self.cell_voltage_avg != ""

    def lowest_temp(self):
        return min(self.pack_center_temp, self.pack_left_temp, self.pack_right_temp)

    def highest_temp(self):
        return max(self.pack_center_temp, self.pack_left_temp, self.pack_right_temp)

    def current_int(self):
        return self.current if self.current != "" else 0

    def ui_current(self):
        return to_ui(self.current, "A", 1000, 2)

    def ui_voltage(self):
        return to_ui(self.voltage, "V", 1000, 2)

    def ui_temperature_lowest(self):
        if self.is_reg_c1():
            return to_ui(self.lowest_temp(), "°C")
        return ""

    def ui_temperature_highest(self):
        if self.is_reg_c1():
            return to_ui(self.highest_temp(), "°C")
        return ""

    def ui_cell_voltage_lowest(self):
        if self.is_connected():
            return to_ui(self.cell_voltage_lowest, "V", 1000, 2)
        return ""

    def ui_cell_voltage_highest(self):
        if self.is_connected():
            return to_ui(self.cell_voltage_highest, "V", 1000, 2)
        return ""

    def ui_bms_sw_version(self):
        return "N/A" if self.bms_sw_version == 0 else f"{self.bms_sw_version}"


    def ui_bms_id(self):
        return "N/A" if self.bms_id == "" else self.bms_id.upper()

    def ui_soc_int(self):
        return 0 if self.pack_soc == "" else self.pack_soc

    def ui_error_flags(self):
        return 0 if self.error_flags == "" else self.error_flags

    def ui_error_bq_flags(self):
        return 0 if self.bq_sys_stat == "" else self.bq_sys_stat

    def is_errors(self):
        return self.ui_error_flags() != 0

    def ui_warn_cell_voltage_diff(self):
        if self.is_reg_c4():
            return warn_cell_voltage_diff < abs(
                self.cell_voltage_highest - self.cell_voltage_lowest) and self.ui_soc_int() > 10
        return False

    def ui_warn_temperature_diff(self):
        if self.is_reg_c1():
            return warn_temperature_diff < abs(self.highest_temp() - self.lowest_temp())
        return False

    def is_updatable(self, version: int, custom_address: bool = False):
        if version == 0 or self.bms_sw_version == "":
            return False
        if self.is_slow_charging:
            return False
        ret_val = (self.bms_sw_version != version
                   and ((self.is_connected() and custom_address)
                        or
                        (self.is_attached()
                            and
                            (((self.is_charging() or self.pack_state == 3) and self.ui_soc_int() < 70)
                                or (self.is_battery_full() and not self.is_charging())
                                or (version >= 80027))))) # allows updating when all batteries connected simultaneously
        # if ret_val:
        #     logging.debug(f"slot {self.slot_no} is_updatable - connected: {self.is_connected()} custom check: {custom_address} attached: {self.is_attached()} charging: {self.is_charging()} pack_state: {self.pack_state} soc: {self.ui_soc_int()} is_full: {self.is_battery_full()} version_to: {version})")

        return ret_val

    def calculate_cells(self):
        if self.cell_voltages[0] != "" and self.cell_voltages[4] != "" and self.cell_voltages[8] != "":
            avg = 0
            min_v = 0xFFFF
            max_v = 0
            min_c = 0
            max_c = 0

            for i, v in self.cell_voltages.items():
                avg += v
                if v < min_v:
                    min_v = v
                    min_c = i+1

                if v > max_v:
                    max_v = v
                    max_c = i+1

            self.cell_voltage_avg = round(avg/12)
            self.cell_voltage_lowest = min_v
            self.cell_voltage_highest = max_v
            self.min_cell_no = min_c
            self.max_cell_no = max_c

    def ui_balance_pattern(self):
        return 0 if self.balance_pattern == "" else self.balance_pattern

    def ui_moisture_count(self):
        return 0 if self.cap_sense_fill_time == "" else (self.cap_sense_fill_time * 0.01)

# [END class BmsInfo]


app_start = round(datetime.datetime.utcnow().timestamp())

#
# def insert_test_data(value: BmsInfo):
#     global app_start
#
#     app_end = round(datetime.datetime.utcnow().timestamp())
#     app_time = app_end - app_start
#
#     slot_count = get_config('CCS', 'slots', 32, int) - 1
#     # app_time = value.slot_no / slot_count * 100
#     if app_time > 100:
#         app_time = 100
#
#     if (value.slot_no == 19 and random.randint(0,
#                                                5) == 1) or value.slot_no == slot_count or value.slot_no == slot_count - 1:
#         raise Exception("no device")
#
#     value.attach_status = 6
#     # value.bms_id = "aad96788"
#     value.bms_id = "rand_%i" % value.slot_no
#     value.bms_sw_version = 80030
#     value.pack_soc = app_time
#
#     value.error_flags = 0x32
#
#     value.pack_state = 5  # normal charge
#     if value.slot_no < 3:
#         value.pack_state = 4  # slow charge
#
#     if value.slot_no == 15:
#         value.pack_right_temp *= 2
#
#     if value.slot_no == 17:
#         value.cell_voltage_highest *= 2
#
#     if 1 < value.slot_no < 6:
#         value.pack_soc = 96
#         value.pack_state = 0  # not charging
#
#     if 8 == value.slot_no :
#         value.pack_soc = 35
#         value.pack_state = 0  # not charging
#
#     if value.pack_soc > 95:
#         value.pack_state = 0  # not charging
#
#     if value.slot_no == 7:
#         value.bms_sw_version = 80030
#
#     if value.slot_no == 5:
#         return
#
#     value.cell_voltage_lowest = random.randint(3500, 4000)
#     value.cell_voltage_avg = random.randint(3500, 4000)
#     value.cell_voltage_highest = random.randint(3500, 4000)
#     value.current = random.randint(-100, 20000)
#     value.voltage = random.randint(42000, 48000)
#     value.pack_left_temp = random.randint(15, 30)
#     value.pack_right_temp = random.randint(15, 30)
#     value.pack_center_temp = random.randint(15, 30)
#     value.fet_temp = random.randint(15, 30)
#     value.cycle_count = value.slot_no
#
#     value.min_cell_no = random.randint(0, 12)
#     value.max_cell_no = random.randint(0, 12)
#
#     if value.slot_no == slot_count and app_time == 100:
#         app_start = round(datetime.datetime.utcnow().timestamp())
#
#     if random.randint(0, 100) == 1:
#         value.error_flags = 1 << random.randint(0, 7)
#     return
#     if random.randint(0, 1):
#         value.bq_sys_stat = 1 << random.randint(0, 7)
#     # if value.slot_no == 14:
#     #     value.error_flags = 0x3F
#     if value.slot_no == 11:
#         value.error_flags = 4
#         value.bq_sys_stat = 0xF
#     if value.slot_no == 0:
#         value.bq_sys_stat = 1
#     if value.slot_no == 8:
#         value.bq_sys_stat = 2
#     if value.slot_no == 16:
#         value.bq_sys_stat = 4
#     if value.slot_no == 24:
#         value.bq_sys_stat = 8
