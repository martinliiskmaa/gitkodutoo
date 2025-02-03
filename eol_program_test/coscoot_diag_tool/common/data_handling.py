from struct import unpack

from can import Message

from .helper import conv, resize_bytes, utc_time_seconds, time_in_ms, TransmitBufferFull
from .bmsinfo import BmsInfo
from .usbinfo import USB_Info

import logging

from .settings import settings as settings_data
from .pycan import PyCan
from pathlib import Path
from time import sleep
import math
import requests
import crcmod.predefined

logger = logging.getLogger('bms-data')
logger.setLevel("ERROR")

PACK_REG_1 = 0xc0
PACK_REG_2 = 0xc1
PACK_REG_3 = 0xc2
PACK_REG_4 = 0xc3
CELL_REG_4 = 0xd4
PACK_INFO = 0xff


def log_debug(bms, msg: str, log_level=logger.debug):
    # log_level(f"Slot {bms.slot_no:02} ({bms.bms_id}) {msg}")
    log_level(msg)
    pass


def unpack_c0(data):
    data = resize_bytes(data, 8)
    return unpack(">BBBBI", data)


def update_c0(bms: BmsInfo, data):
    # pack_soc (cm_bike_coscooter.c line 2432)
    bms.pack_state, bms.attach_status, bms.error_flags, bms.pack_soc, bms.bms_id_int = unpack_c0(data)
    bms.bms_id = f"{bms.bms_id_int:08x}"

    log_debug(bms, f"bms_id: {bms.bms_id}")
    log_debug(bms, f"pack_soc: {bms.pack_soc}")
    log_debug(bms, f"pack_state: {bms.pack_state}")
    log_debug(bms, f"attach_status: {bms.attach_status}")
    log_debug(bms, f"error_flags: {bms.error_flags}")


def update_cb(usb: USB_Info, data):
    data = resize_bytes(data, 8)
    usb.role_control, usb.cc_status, usb.power_status, usb.extended_status, usb.message_header, usb.i2c_state, usb.vbus_voltage = unpack(
        ">BBBBBBH", data)
    log_debug(usb, f"role_control: {usb.role_control}")
    log_debug(usb, f"cc_status: {usb.cc_status}")
    log_debug(usb, f"power_status: {usb.power_status}")
    log_debug(usb, f"extended_status: {usb.extended_status}")
    log_debug(usb, f"message_header: {usb.message_header}")
    log_debug(usb, f"i2c_state: {usb.i2c_state}")
    log_debug(usb, f"vbus_voltage: {usb.vbus_voltage}")
    # Message Header
    usb.cable_plug = (usb.message_header >> 4) & 0x1
    usb.data_role = (usb.message_header >> 3) & 0x1
    usb.usb_spec = (usb.message_header >> 1) & 0x3
    usb.power_role = usb.message_header & 0x1
    
    # Role Control
    usb.rc_cc1 = usb.role_control & 0x3
    usb.rc_cc2 = (usb.role_control >> 2) & 0x3
    usb.rp_value = (usb.role_control >> 4) & 0x3
    usb.drp = (usb.role_control >> 6) & 0x1
    

    # CC Status
    usb.Looking4Connection = (usb.cc_status >> 5) & 0x1
    usb.ConnectResult = (usb.cc_status >> 4) & 0x1
    usb.cc2_state = (usb.cc_status >> 2) & 0x3
    usb.cc1_state = usb.cc_status & 0x3

    # Power Status
    usb.vbus_sink = usb.power_status & 0x1
    usb.vconn_present = (usb.power_status >> 1) & 0x1
    usb.vbus_present = (usb.power_status >> 2) & 0x1
    usb.vbus_detect = (usb.power_status >> 3) & 0x1
    usb.vbus_source = (usb.power_status >> 4) & 0x1
    usb.high_volt = (usb.power_status >> 5) & 0x1
    usb.tcpc_init = (usb.power_status >> 6) & 0x1
    usb.debug_acc = (usb.power_status >> 7) & 0x1

    # Extended Status
    usb.vsafe = usb.extended_status & 0x1



def update_c1(bms: BmsInfo, data):
    data = resize_bytes(data, 8)
    bms.fet_temp, bms.pack_left_temp, bms.pack_center_temp, bms.pack_right_temp, bms.voltage, bms.current = unpack(">bbbbHh", data)

    log_debug(bms, f"fet_temp: {bms.fet_temp}")
    log_debug(bms, f"pack_left_temp: {bms.pack_left_temp}")
    log_debug(bms, f"pack_center_temp: {bms.pack_center_temp}")
    log_debug(bms, f"pack_right_temp: {bms.pack_right_temp}")
    log_debug(bms, f"voltage: {bms.voltage}")
    log_debug(bms, f"current: {bms.current}")


def update_c2(bms: BmsInfo, data):
    data = resize_bytes(data, 8)
    bms.bq_sys_stat = conv(data, 7)
    log_debug(bms, f"bq_sys_stat: {bms.bq_sys_stat}")


def update_c3(bms: BmsInfo, data):
    data = resize_bytes(data, 8)
    bms.precharge_result, bms.cycle_count, bms.coulomb_soc, bms.available_capacity, bms.collected_regen = unpack(
        ">BHBhH", data)

    log_debug(bms, f"precharge_result: {bms.precharge_result}")
    log_debug(bms, f"cycle_count: {bms.cycle_count}")
    log_debug(bms, f"coulomb_soc: {bms.coulomb_soc}")
    log_debug(bms, f"available_capacity: {bms.available_capacity}")
    log_debug(bms, f"collected_regen: {bms.collected_regen}")


def update_c5(bms: BmsInfo, data):
    length = len(data)
    if 8 == length:
        bms.balance_state, bms.balance_pattern, bms.cap_sense_fill_time, bms.bms_unread_error_count, bms.bq_sys_stat = unpack(">BHHHB", data)
        log_debug(bms, f"bq_sys_stat: {bms.bq_sys_stat}")
        log_debug(bms, f"cap_sense_fill_time: {bms.cap_sense_fill_time}")
        log_debug(bms, f"bms_unread_error_count: {bms.bms_unread_error_count}")
    elif 7 == length:
        bms.balance_state, bms.balance_pattern, bms.cap_sense_fill_time, bms.bms_unread_error_count = unpack(">BHHH", data)
        log_debug(bms, f"cap_sense_fill_time: {bms.cap_sense_fill_time}")
        log_debug(bms, f"bms_unread_error_count: {bms.bms_unread_error_count}")
    elif 5 == length:
        bms.balance_state, bms.balance_pattern, bms.cap_sense_fill_time = unpack(">BHH", data)
        log_debug(bms, f"cap_sense_fill_time: {bms.cap_sense_fill_time}")
    else:
        data = resize_bytes(data, 4)
        bms.balance_state, bms.balance_pattern = unpack(">BH", data)

    log_debug(bms, f"balance_state: {bms.balance_state}")
    log_debug(bms, f"balance_pattern: {bms.balance_pattern}")


def update_c6(bms: BmsInfo, data):
    if len(data) == 6:
        bms.temp_ts_1, bms.temp_ts_2, bms.temp_ts_3, bms.pack_temp_4, bms.pack_temp_5, bms.pack_temp_6 = unpack(">bbbbbb", data)
        log_debug(bms, f"pack_temp_4: {bms.pack_temp_4}")
        log_debug(bms, f"pack_temp_5: {bms.pack_temp_5}")
        log_debug(bms, f"pack_temp_6: {bms.pack_temp_6}")
    else:
        data = resize_bytes(data, 4)
        bms.temp_ts_1, bms.temp_ts_2, bms.temp_ts_3, bms.temp_usb = unpack(">bbbb", data)
        log_debug(bms, f"temp_usb: {bms.temp_usb}")

    log_debug(bms, f"temp_ts_1: {bms.temp_ts_1}")
    log_debug(bms, f"temp_ts_2: {bms.temp_ts_2}")
    log_debug(bms, f"temp_ts_3: {bms.temp_ts_3}")


def update_ca(bms: BmsInfo, data):
    data = resize_bytes(data, 2)
    bms.attach_pin_voltage = unpack(">H", data)[0]

    log_debug(bms, f"attach_pin_voltage: {bms.attach_pin_voltage}")


def update_c8(bms: BmsInfo, data):
    data = resize_bytes(data, 1)
    bms.temp_sensor_mask = unpack(">B", data)[0]

    log_debug(bms, f"temp_sensor_mask: {bms.temp_sensor_mask}")


def update_c9(bms: BmsInfo, data):
    data = resize_bytes(data, 4)
    bms.overvoltage_limit, bms.undervoltage_limit = unpack(">HH", data)

    log_debug(bms, f"overvoltage_limit: {bms.overvoltage_limit}")
    log_debug(bms, f"undervoltage_limit: {bms.undervoltage_limit}")


def update_cc(bms: BmsInfo, data):
    data = resize_bytes(data, 2)
    bms.digipot_value = unpack(">H", data)[0]

    log_debug(bms, f"digipot_value: {bms.digipot_value}")


def update_d4(bms: BmsInfo, data):
    data = resize_bytes(data, 8)
    bms.cell_voltage_avg, bms.cell_voltage_lowest, bms.cell_voltage_highest, bms.min_cell_no, bms.max_cell_no = unpack(">HHHBB", data)

    log_debug(bms, f"cell_voltage_avg: {bms.cell_voltage_avg}")
    log_debug(bms, f"cell_voltage_lowest: {bms.cell_voltage_lowest}")
    log_debug(bms, f"cell_voltage_highest: {bms.cell_voltage_highest}")
    log_debug(bms, f"min_cell_no: {bms.min_cell_no}")
    log_debug(bms, f"max_cell_no: {bms.max_cell_no}")


def update_ff(bms: BmsInfo, data):
    # (cm_bike_coscooter.c line 2445)
    data = resize_bytes(data, 4)
    bms.bms_sw_version = data[0] * 1000000 + \
                          data[1] * 10000 + \
                          data[2] * 100 + \
                          data[3]

    log_debug(bms, f"bms_sw_version: {bms.bms_sw_version}")


def update_fe(bms: BmsInfo, data, response_time):
    # pack_soc (cm_bike_coscooter.c line 2432)
    seconds, milliseconds = unpack(">IH", data)
    bms.unix_time = seconds + milliseconds / 1000
    bms.time_diff = -((utc_time_seconds()-bms.unix_time)-response_time/2)

    log_debug(bms, f"unix_time: {bms.unix_time} ({bms.time_diff:.3f})")


def update_fc(bms: BmsInfo, data):
    length = len(data)
    data = resize_bytes(data, 3)
    bms.pcb_version, bms.fw_type = unpack(">HB", data)
    log_debug(bms, f"pcb_version: {bms.pcb_version}")
    log_debug(bms, f"fw_type: {bms.fw_type}")
    bms.hw_type = bms.fw_type >> 4
    bms.sw_profile = bms.fw_type & 0xF
    if length == 2:
        # beyonder
        bms.hw_type = 0
        bms.sw_profile = 0
    bms.is_reg_fc = True
    log_debug(bms, f"hw_type: {bms.hw_type}")
    log_debug(bms, f"sw_profile: {bms.sw_profile}")
    pass


def update_d_cell(bms: BmsInfo, data, off=0):
    r0, r1, r2, r3 = unpack(">HHHH", data)
    v = bms.cell_voltages
    v[0+off] = r0
    v[1+off] = r1
    v[2+off] = r2
    v[3+off] = r3
    log_debug(bms, f"cell_{off+1}_voltage: {r0}")
    log_debug(bms, f"cell_{off+2}_voltage: {r1}")
    log_debug(bms, f"cell_{off+3}_voltage: {r2}")
    log_debug(bms, f"cell_{off+4}_voltage: {r3}")


def standard_check(sent, received):
    return sent[2] == received[2] and sent[3] == received[3]


def non_standard_check(sent, received):
    return 0x30 == received[0]


class BmsReader:
    def __init__(self, config: settings_data):
        logger.setLevel(config.get('CAN', 'log_level', "ERROR"))

        self.can_bus = PyCan(config)

        self.fw_directory = config.get('FIRMWARE', 'DIR', "fw_directory", Path)
        self.can_timeout = config.get('CAN', 'timeout', 20, int)
        self.can_retry = config.get('CAN', 'retry', 1, int)

        self.fw_path = Path()
        self.cs_file_path = Path()
        self.selected_fw_version: int = 0

        self.storage_url = config.get('FIRMWARE', 'storage', "")

        self.tx_identifier = 0xFD0D
        self.rx_identifier = 0xFD6A

        self.timeout = 200

    def set_fw_filename(self, fw_version, fw_type=0):
        fw_type_txt = ""
        if fw_type != 0:
            fw_type_txt = f"_{fw_type:02X}"

        fw_file_name = f"COMO_bms_fw_{fw_version}{fw_type_txt}.bin"
        cs_file_name = f"COMO_bms_cs_{fw_version}{fw_type_txt}.txt"

        self.fw_path = self.fw_directory / fw_file_name
        self.cs_file_path = self.fw_directory / cs_file_name
        self.selected_fw_version = fw_version

    def download_fw_files(self, fw_version, fw_type=0):
        logger.info(f"fw to download: {fw_version} type: '{fw_type}'")

        self.set_fw_filename(fw_version, fw_type)

        if self.fw_path.exists() and self.cs_file_path.exists():
            return

        try:
            fw_type_txt = ""
            if fw_type != 0:
                fw_type_txt = f"_{fw_type:02X}"
            print(f"{self.fw_path}")
            if self.fw_path.exists():
                logger.warning("Firmware file already exists, skipping download")
            else:
                fw_url = f"{self.storage_url}/COMO_bms_fw_{fw_version}{fw_type_txt}.bin"
                logger.info(f"Downloading from: {fw_url}")
                r = requests.get(fw_url, allow_redirects=True)
                if r.status_code != 200:
                    raise Exception("Firmware binary download failed")

                with open(self.fw_path, 'wb') as f:
                    f.write(r.content)

            if self.cs_file_path.exists():
                logger.warning("Checksum file already exists, skipping download")
            else:
                cs_url = f"{self.storage_url}/COMO_bms_cs_{fw_version}{fw_type_txt}.txt"
                logger.info(f"Downloading from: {cs_url}")
                r = requests.get(cs_url, allow_redirects=True)
                if r.status_code != 200:
                    raise Exception("Firmware checksum download failed")

                with open(self.cs_file_path, 'wb') as f:
                    f.write(r.content)
        except Exception as e:
            logger.error(f"Failed to download files: {e}")
            raise

    def open_can(self):
        self.can_bus.init_can()
        self.can_bus.can_bus_on()

    def close_can(self):
        self.can_bus.can_bus_off()

    def update_reg(self, reg_id, data, response_time, bms: BmsInfo, usb: USB_Info = None):
        logger.debug(f"update_reg: {reg_id:04x}")
        reg_nr = reg_id & 0xFF
        if reg_nr == 0xc0:
            update_c0(bms, data)

        elif reg_nr == 0xc1:
            update_c1(bms, data)

        elif reg_nr == 0xc3:
            update_c3(bms, data)

        elif reg_nr == 0xc5:
            update_c5(bms, data)

        elif reg_nr == 0xc6:
            update_c6(bms, data)

        elif reg_nr == 0xd4:
            update_d4(bms, data)

        elif reg_nr == 0xff:
            update_ff(bms, data)

        elif reg_nr == 0xfe:
            update_fe(bms, data, response_time)

        elif reg_nr == 0xfc:
            update_fc(bms, data)

        elif reg_nr == 0xc2:
            update_c2(bms, data)

        elif reg_nr == 0xd1:
            update_d_cell(bms, data)
            bms.calculate_cells()
        elif reg_nr == 0xd2:
            update_d_cell(bms, data, 4)
            bms.calculate_cells()
        elif reg_nr == 0xd3:
            update_d_cell(bms, data, 8)
            bms.calculate_cells()
            log_debug(bms, f"cell_voltage_avg: {bms.cell_voltage_avg}")
            log_debug(bms, f"cell_voltage_lowest: {bms.cell_voltage_lowest}")
            log_debug(bms, f"cell_voltage_highest: {bms.cell_voltage_highest}")
            log_debug(bms, f"min_cell_no: {bms.min_cell_no}")
            log_debug(bms, f"max_cell_no: {bms.max_cell_no}")

        elif reg_nr == 0xca:
            update_ca(bms, data)
        elif reg_nr == 0xcc:
            update_cc(bms, data)
        elif reg_nr == 0xc8:
            update_c8(bms, data)
        elif reg_nr == 0xc9:
            update_c9(bms, data)
        elif reg_nr == 0xCB:
            if usb is not None:
                update_cb(usb, data)
            # print(f"update {data}")
        else:
            logger.warning(f"unknown register received: {reg_id:04x}")

    def send_message_to_can(self, msg_id, msg):
        # print("msg sent: ", binascii.hexlify(bytearray(msg)))
        try:
            self.can_bus.send_data(msg_id, msg)
        except Exception:
            print("could not send data")

    # [START read_bms_v2]
    def read_bms_v2(self, aid, retry=1, data=None, data_cmp_fnc=None, timeout=None, mask=0xff, is_extended_id=False, rx_aid=None):
        if data is None:
            data = []
        if timeout is None:
            timeout = self.timeout
        timeout_end = time_in_ms() + timeout
        if rx_aid is None:
            rx_aid = aid
        i = 0
        while i < retry:
            try:
                logger.debug(f"read_bms_v2 send: {aid:x}, try: {i+1}, timeout: {timeout}ms")
                self.can_bus.send_data(aid, data, is_extended_id, False)
                while 1:
                    timeout = timeout_end - time_in_ms()
                    if timeout < 0:
                        raise Exception("timeout")

                    logger.debug(f"read_bms_v2 read: {rx_aid:x} timeout: {timeout}ms")
                    msg: Message = self.can_bus.read_data(timeout)
                    if msg is not None and len(msg.data) and not msg.is_error_frame:
                        correct = 0

                        if msg.arbitration_id & mask == rx_aid & mask:
                            if data_cmp_fnc is not None:
                                if data_cmp_fnc(data, msg.data):
                                    correct = 1
                            else:
                                correct = 1

                            if correct:
                                logger.debug(f"msg - id: {msg.arbitration_id:x} data: {msg.data} dlc: {msg.dlc}")
                                return msg
                        if not correct:
                            logger.debug(f"read_bms_v2 disc: {msg.arbitration_id:x} data: {msg.data} dlc: {msg.dlc}")
                            pass

            except TransmitBufferFull:
                logger.debug(f"read_bms_v2 TransmitBufferFull")

                if timeout_end - time_in_ms() < 0:
                    raise Exception("timeout")
                pass
            except Exception as e:
                logger.debug(f"read_bms_v2 read: {rx_aid:x} try: {i+1} error: {e}")
                i += 1
                timeout_end = time_in_ms() + timeout
        raise Exception("retry count exceeded")
    # [END read_bms_v2]

    def send_command(self, msg, index=7, count=1, timeout=1000):
        reply = self.read_bms_v2(self.tx_identifier, 1, msg, standard_check, timeout, 0xFFFF, True, self.rx_identifier)
        return conv(reply.data, index, count)

    def send_fw_block(self, data, delay):
        try_count = 0
        while True:
            try:
                try_count += 1
                self.can_bus.send_data(self.tx_identifier, data, True)
                break
            except TransmitBufferFull as e:
                logger.error(f"send_fw_block, {e}")
                sleep(0.005)
                if try_count > 100:
                    raise

        sleep(delay)

    def fw_update(self, fw_version, ui_txt, fw_type=0):
        ui_txt(f"Downloading", 0)
        self.download_fw_files(fw_version, fw_type)

        with open(self.fw_path, "rb") as f:
            fw = f.read()

        # read checksum
        with open(self.cs_file_path, "r") as cs:
            total_checksum = cs.readlines()

        self.can_bus.can_bus_on()

        timeout = 10000

        msg = [0x03, 0xfd, 0x12, 0x02]

        # Get packet size
        packet_size = self.send_command(msg, 6, 2, timeout=timeout)
        logger.debug(f"packet_size: {packet_size}")
        if not (64 <= packet_size <= 1024):
            raise Exception("Received invalid packet size")

        total_packet_no = math.ceil(len(fw) / packet_size)
        logger.debug(f"total packet number: {total_packet_no}")

        ui_txt(f"Erasing", 3)
        # Erase fw update area
        msg = [0x07, 0xfd, 0x11, 0x05, 0x01, 0x02, 0x03, 0x04]
        erase_response = self.send_command(msg, timeout=timeout)
        logger.debug(f"erase response: {erase_response}")
        if erase_response != 77:
            raise Exception("Failed to erase FW update area")

        # Write update checksum
        logger.debug(f"total_checksum: {total_checksum}")
        msg = [0x07, 0xfd, 0x05, 0x05, int(total_checksum[0][:2], 16), int(total_checksum[0][2:4], 16),
               int(total_checksum[0][4:6], 16), int(total_checksum[0][-2:], 16)]

        checksum_write_response = self.send_command(msg, timeout=timeout)
        logger.debug(f"checksum write response {checksum_write_response}")
        if checksum_write_response != 77:
            raise Exception("Failed to set write checksum")

        # Write update status
        msg = [0x07, 0xfd, 0x04, 0x05, 0xD0, 0xD1, 0xD2, 0xD3]
        status_write_response = self.send_command(msg, timeout=timeout)
        logger.debug(f"status write response {status_write_response}")
        if status_write_response != 77:
            raise Exception("Failed to write update status")

        # Set total block count for the update
        total_packet_no_low = (total_packet_no >> 8) & 0xff
        total_packet_no_high = total_packet_no & 0xff
        msg = [0x07, 0xfd, 0x13, 0x05, 0x00, 0x00, total_packet_no_low, total_packet_no_high]
        block_response = self.send_command(msg, timeout=timeout)
        logger.debug(f"block count set response {block_response}")
        if status_write_response != 77:
            raise Exception("Failed to set total block count")

        ui_txt(f"Ready?", 6)
        # Ask if BMS is prepared
        msg = [0x03, 0xfd, 0x10, 0x02]
        ready_response = self.send_command(msg, timeout=timeout)
        logger.debug(f"ready response {ready_response}")
        if ready_response != 77:
            raise Exception("BMS is not prepared")

        # Send consecutive frames
        for package in range(1, total_packet_no + 1):
            percent = 10 + (package / (total_packet_no + 1))*80
            ui_txt(f"Sending block: {package} / {total_packet_no + 1}", int(percent))
            package_content = fw[(package - 1) * packet_size:package * packet_size]
            # Set block number
            msg = [0x07, 0xfd, 0x14, 0x05, 0x00, 0x00, (package >> 8) & 0xff, package & 0xff]

            block_no_response = self.send_command(msg, timeout=timeout)
            logger.debug(f"block number response {block_no_response}")
            if block_no_response != 77:
                raise Exception("Failed to set block number")

            # Calculate and set block checksum
            crc32_func = crcmod.predefined.mkCrcFun('crc-32-mpeg')

            package_content_hex = package_content.hex()

            data_prep_for_checksum = str(package_content_hex)
            # logger.debug(f"{package} {len(package_content)} {data_prep_for_checksum}")
            data_prep_for_checksum = data_prep_for_checksum.ljust(packet_size * 2, 'f')
            packet_checksum = crc32_func(bytearray.fromhex(data_prep_for_checksum))
            logger.debug(f"packet checksum: {packet_checksum:x}")

            msg = [0x07, 0xfd, 0x15, 0x05, int(packet_checksum >> 24 & 0xFF), int((packet_checksum >> 16) & 0xFF),
                   int((packet_checksum >> 8) & 0xFF), (packet_checksum & 0xFF)]

            block_cs_response = self.send_command(msg, timeout=timeout)
            logger.debug(f"block cs response {block_cs_response}")
            if block_cs_response != 77:
                raise Exception("Failed to set block checksum")

            # Send start command
            msg = [0x07, 0xfd, 0x16, 0x05, 0x01, 0x02, 0x03, 0x04]
            block_start_response = self.send_command(msg, timeout=timeout)
            logger.debug(f"block start response {block_start_response}")
            if block_start_response != 77:
                raise Exception("Failed to set block start")

            # If all successes, then start sending data over ISO TP
            # if block_no_response == 77 and block_cs_response == 77 and block_start_response == 77:
            bytes_sent = 0
            # Send first frame, check if it should be single or multi-frame block
            next_packet_size = len(package_content)

            # print(package, len(package_content), ' ', package_content_hex)

            # Send first frame, check if it should be single or multi-frame block
            if next_packet_size <= 6:
                logger.debug("end of file")
            else:
                # (next_packet_size >> 8) & 0xff, next_packet_size & 0xff
                msg = [0x10 | ((next_packet_size >> 8) & 0x0F), next_packet_size & 0xFF,
                       int(package_content_hex[:2], 16),
                       int(package_content_hex[2:4], 16),
                       int(package_content_hex[4:6], 16),
                       int(package_content_hex[6:8], 16),
                       int(package_content_hex[8:10], 16),
                       int(package_content_hex[10:12], 16)]
                # print(msg)
                reply = self.read_bms_v2(self.tx_identifier, 1, msg, non_standard_check, timeout, 0xFFFF, True, self.rx_identifier)
                reply_data = reply.data
                test = conv(reply_data, 0)
                logger.debug(f"Test: {test}")

                # ISO TP FC flags: 0 = Continue To Send, 1 = Wait, 2 = Overflow/abort
                iso_tp_fc_flag = 2
                iso_tp_block_size = 0
                iso_tp_separation_time = 0

                if test == 0x30:
                    iso_tp_fc_flag = test & 0x0F
                    iso_tp_block_size = conv(reply_data, 1)
                    iso_tp_separation_time = conv(reply_data, 2) & 0x7F
                    logger.debug(f"iso tp - fc_flag: {iso_tp_fc_flag} block_size: {iso_tp_block_size} sep time: {iso_tp_separation_time}")

                if iso_tp_fc_flag == 0 and iso_tp_block_size != 0 and iso_tp_separation_time != 0:
                    seq_msg_id = 1
                    j = 0

                    bytes_to_send = package_content_hex
                    desired_block_size = (math.ceil((len(bytes_to_send) - 12) / 14) + 1) * 14
                    frame_count = math.ceil(desired_block_size / 14)
                    logger.debug(f"bytes to process: {desired_block_size} frame count: {frame_count}")
                    bytes_to_send = bytes_to_send.ljust(desired_block_size, '0')
                    # print(bytes_to_send)

                    for i in range(frame_count):
                        if i == 0:
                            j = j + 12
                        else:
                            msg = [0x20 | (seq_msg_id & 0x0F), int(bytes_to_send[j:j + 2], 16),
                                   int(bytes_to_send[j + 2:j + 4], 16),
                                   int(bytes_to_send[j + 4:j + 6], 16),
                                   int(bytes_to_send[j + 6:j + 8], 16),
                                   int(bytes_to_send[j + 8:j + 10], 16),
                                   int(bytes_to_send[j + 10:j + 12], 16),
                                   int(bytes_to_send[j + 12:j + 14], 16)]
                            # print("msg to send: ", binascii.hexlify(bytearray(msg)))
                            self.send_fw_block(msg, 0.0001 * iso_tp_separation_time)

                            j = j + 14
                            seq_msg_id += 1
                            if seq_msg_id > 15:
                                seq_msg_id = 0

                # Validate block
                msg = [0x07, 0xfd, 0x17, 0x05, 0x01, 0x02, 0x03, 0x04]
                block_valid_response = self.send_command(msg, timeout=timeout)
                if block_valid_response != 77:
                    raise Exception("Failed write block")

        ui_txt(f"Validating", 95)
        # Validate firmware image
        msg = [0x07, 0xfd, 0x18, 0x05, 0x01, 0x02, 0x03, 0x04]
        update_valid_response = self.send_command(msg, timeout=timeout)
        if update_valid_response != 77:
            raise Exception("Failed to validate firmware image")
