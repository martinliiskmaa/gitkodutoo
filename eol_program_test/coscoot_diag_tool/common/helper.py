from math import floor
from time import time
from datetime import datetime
from sys import platform
import logging


end_of_time = 2**64
epoch = datetime(1970, 1, 1, 0, 0, 0)

msg_can_error = "CAN-bus error"
msg_can_error_or_no_bat = "No batteries or CAN-bus error"

is_linux = False
if platform.startswith('linux'):
    is_linux = True


def utc_time_seconds(timetag=None):
    if timetag is None:
        timetag = datetime.utcnow()
    return (timetag - epoch).total_seconds()


def str2bool(v):
    return str(v).lower() in ["yes", "true", "t", "1"]


def conv(data, index, count=1):
    res_value = 0
    for i in range(0, count):
        res_value = res_value << 8 | data[index + i]
    return res_value


def time_in_ms():
    return int(time() * 1000)


def get_slot_mask(i):
    if i < 16:
        return 1 << (31 - i) | 1 << i
    else:
        return (1 << (31 - (i-16)) | 1 << (i-16)) << 32


def get_slots_mask(slot_count):
    mask = 0
    for i in range(slot_count):
        mask |= get_slot_mask(i)
    return mask


def to_signed(n, byte_count=1):
    return int.from_bytes(n.to_bytes(byte_count, 'little'), 'little', signed=True)


def resize_bytes(data: bytes, length: int) -> bytes:
    data_len = len(data)
    temp = []
    if data_len == length:
        return data
    elif data_len < length:
        temp = list(data)
        for x in range(data_len, length):
            temp.append(0)
    elif data_len > length:
        temp = []
        for x in range(length):
            temp.append(data[x])

    return bytes(temp)


class Error(Exception):
    """Base class for other exceptions"""
    pass


class Timeout(Error):
    """Raised when a timeout occurs"""
    pass


class InvalidMessage(Error):
    """Raised when a InvalidMessage occurs"""
    pass


class FirmwareUpdateError(Error):
    """Raised when a InvalidMessage occurs"""
    pass


class FoundNewDevice(Error):
    """Raised when a InvalidMessage occurs"""
    pass


class TransmitBufferFull(Error):
    """Raised when a InvalidMessage occurs"""
    pass


def logging_basic_config():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(name)s | %(levelname)s | %(message)s')


def calculate_xor_checksum(data: bytes, length: int):
    checksum = 0
    for i in range(0, length):
        checksum ^= data[i]
    return checksum
