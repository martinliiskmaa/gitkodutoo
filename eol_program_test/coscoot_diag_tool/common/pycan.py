from can import interface, Message, CanError
from .settings import settings as settings_data
from .helper import str2bool, TransmitBufferFull


class PyCan:
    def __init__(self, config: settings_data):
        self.bustype = config.get("CAN", "bustype", "socketcan")
        self.channel = config.get("CAN", "channel", "can0")
        self.bitrate = config.get("CAN", "bitrate", 250000, int)
        self.bus: interface.Bus = None
        self.no_clear_buf = not config.get("CAN", "clear_buf", True, str2bool)
        self.can_status = 0

    def init_can(self):
        self.close()
        if self.bus is not None:
            print("RESETTING CAN")

        self.bus = interface.Bus(bustype=self.bustype, channel=self.channel, bitrate=self.bitrate)

    def send_data(self, msg_type, msg, is_extended_id=False, update_can_status=True):
        if msg_type > 0xFF:
            is_extended_id=True
        msg = Message(arbitration_id=msg_type,
                          data=msg,
                          is_extended_id=is_extended_id)
        # self.bus.Message(msg_type, [], False)
        try:
            self.bus.send(msg)
            if update_can_status:
                self.can_status = 1
            # print("Message sent on {}".format(self.bus.channel_info))
        except CanError as e:
            # print(f"Message NOT sent: {e}")
            error_str = str(e)
            if error_str.find("[Errno 105]") < 0 and error_str.find("Transmit buffer overflow") < 0 and error_str.find("[Error Code 105]") < 0 :  # Is not [Errno 105] No buffer space available
                if update_can_status:
                    self.can_status = 0
                raise
            raise TransmitBufferFull("Buffer full") from e

    def close(self):
        if self.bus is not None:
            self.bus.shutdown()

    def is_initialized(self):
        return self.bus is not None

    def can_bus_on(self):
        # self.ch1.busOn()
        pass

    def can_bus_off(self):
        # self.ch1.busOff()
        pass

    def read_data(self, timeout_in_ms=0):
        try:
            return self.bus.recv(timeout_in_ms/1000)
        except CanError:
            self.can_status = 0
            # print("Message NOT received, canerror")
            raise

    def clear_buf(self):
        if self.no_clear_buf:
            return

        while 1:
            try:
                bms_data = self.read_data(0)
                if bms_data is None:
                    return

            except Exception as e:
                print("clear buf exception: ", e)
                return

    def __enter__(self):
        self.init_can()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
