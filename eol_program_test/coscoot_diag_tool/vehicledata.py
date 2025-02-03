from common.helper import utc_time_seconds

IOT_DATA_TIMEOUT = 6
BATTERY_DATA_TIMEOUT = 3
CCU_DATA_TIMEOUT = 6


class TimeoutChecker:
    def __init__(self, timeout_sec):
        self.timeout = timeout_sec
        self.last_data = 0

    def is_timeout(self):
        return utc_time_seconds() - self.last_data > self.timeout

    def update(self):
        self.last_data = utc_time_seconds()


class VehicleData:
    def __init__(self):

        self.unattached_battery_one_id = 0
        self.unattached_battery_two_id = 0
        self.receive_only = False

        self.last_data_bms_left = TimeoutChecker(BATTERY_DATA_TIMEOUT)
        self.last_data_bms_right = TimeoutChecker(BATTERY_DATA_TIMEOUT)
        self.last_data_other = TimeoutChecker(BATTERY_DATA_TIMEOUT)
        self.last_data_ccu = TimeoutChecker(CCU_DATA_TIMEOUT)
        self.last_data_iot = TimeoutChecker(IOT_DATA_TIMEOUT)
