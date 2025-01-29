from hashlib import sha1
from math import trunc
from struct import unpack

from common.helper import resize_bytes
from ccu_data import CCUData
from iot_data import IoTData


class IotMessageHandler:
    def __init__(self):
        self.authentication_requested = 0
        self.counter = 0
        self.iot_auth_state = False

    def reset(self):
        self.__init__()

    def get_next_message(self, nrf_id):

        if nrf_id is None and self.counter == 2:
            self.counter = 0

        if self.iot_auth_state is False and self.counter > 3:
            self.counter = 0
        elif self.iot_auth_state is True and self.counter == 2:
            self.counter += 1

        if self.counter > 10:
            self.counter = 0

        msg = []
        if self.counter == 0:
            msg = [0xfe, 0x0d]
        elif self.counter == 1:
            msg = [0xfe, 0x09]
        elif self.counter == 2:
            # Authenticate
            # IOT_DIAG_DEFAULT_PW {0x63,0x6f,0x6d,0x6f,0x31,0x32,0x33,0x34} // como1234
            iot_password = [0x63, 0x6f, 0x6d, 0x6f, 0x31, 0x32, 0x33, 0x34]
            # nrf_id_local = [0x25, 0xc7, 0x97, 0x25, 0x12, 0x5d, 0x94, 0x60]
            # hash_test_in = [0x63, 0x6f, 0x6d, 0x6f, 0x31, 0x32, 0x33, 0x34, 0x25, 0xc7, 0x97, 0x25, 0x12, 0x5d, 0x94, 0x60]
            # hash_in = bytes(hash_test_in)
            nrf_id_in_bytes = bytes.fromhex(f"{nrf_id:016x}")
            hash_in = bytes(iot_password) + nrf_id_in_bytes
            # hash_in = bytes.fromhex('63 6f 6d 6f 31 32 33 34 25 c7 97 25 12 5d 94 60')
            hash_out = [0] * 8
            m = sha1()
            m.update(hash_in)
            mem_out = m.digest()
            print("memout", mem_out)
            for i in range(8):
                hash_out[i] = mem_out[i]
            # hash_out = [0xee, 0x0d, 0x86, 0xdd, 0x78, 0x07, 0x82, 0x9e] # ee 0d 86 dd 78 07 82 9e , for 25c79725125d9460
            msg = hash_out
            self.authentication_requested = 1
        elif self.counter == 3:
            msg = [0x00, 0xc3, 0x02]
        elif self.counter == 4:
            msg = [0x00, 0xc2, 0x01]
        elif self.counter == 5:
            msg = [0x00, 0xc2, 0x02]
        elif self.counter == 6:
            msg = [0x00, 0xc5, 0x00]
        elif self.counter == 7:
            msg = [0x00, 0xc5, 0x01]
        elif self.counter == 8:
            msg = [0x00, 0xc4, 0x05]
        elif self.counter == 9:
            msg = [0x00, 0xc4, 0x01]
        elif self.counter == 10:
            msg = [0x00, 0xc4, 0x04]

        # print(f"counter {self.counter} | authentication_requested {self.authentication_requested} | iot_auth_state {self.iot_auth_state} | nrf_id {nrf_id}")

        self.counter += 1
        return msg

    def update_da01(self, iot: IoTData, dlc, data):
        if dlc == 8:
            iot.iot_nrf_id = unpack(">Q", data)[0]
            # print(f"iot_nrf_id: {iot.iot_nrf_id}")
        elif dlc == 5:
            iot.iot_nrf_fw_type = (data[0] << 8) + data[1]
            iot.iot_nrf_fw_version = (data[2] << 16) + (data[3] << 8) + data[4]
        elif dlc == 7:
            self.iot_auth_state = True

            reg_id = (data[0] << 8) + data[1]
            reg_data_int = (data[3] << 24) + (data[4] << 16) + \
                           (data[5] << 8) + data[6]
            if reg_id == 0x00c3:
                if data[2] == 2:
                    signal_strength = trunc(reg_data_int / 10000)
                    net_status = trunc((reg_data_int - signal_strength * 10000) / 100)
                    net_type = reg_data_int - signal_strength * 10000 - net_status * 100
                    iot.iot_net_signal_strength = signal_strength
                    iot.iot_net_status = net_status
                    iot.iot_net_type = net_type
            elif reg_id == 0x00c2:
                if data[2] == 1:
                    iot.iot_bat_voltage = reg_data_int / 100
                elif data[2] == 2:
                    iot.iot_bat_temperature = reg_data_int
            elif reg_id == 0x00c4:
                if data[2] == 1:
                    iot.iot_gps_used_sats = reg_data_int
                elif data[2] == 4:
                    iot.iot_gps_max_cno = reg_data_int
                elif data[2] == 5:
                    iot.iot_gps_fix_state = reg_data_int
            elif reg_id == 0x00c5:
                if data[2] == 0:
                    charger_state = 0x03 & (reg_data_int >> 28)
                    iot.iot_bat_charger = charger_state
                elif data[2] == 1:
                    iot.iot_module_vin = reg_data_int

    def update_iot(self, reg_id, dlc, data, iot: IoTData):
        if reg_id == 0xda01:
            self.update_da01(iot, dlc, data)


# CCU Update

def update_0f(ccu: CCUData, data):
    data = resize_bytes(data, 4)
    ccu.ccu_fw_version = data[0] * 1000000 + \
                         data[1] * 10000 + \
                         data[2] * 100 + \
                         data[3]


def update_401(ccu: CCUData, data):
    data = resize_bytes(data, 4)
    ccu.ccu_comms_config_state, ccu.ccu_asi_status, ccu.ccu_lights_status = unpack(">hBB", data)


def update_ccu(reg_id, data, ccu: CCUData):
    if reg_id == 0x40f:
        update_0f(ccu, data)
    elif reg_id == 0x401:
        update_401(ccu, data)


