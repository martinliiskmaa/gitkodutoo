class USB_Info:
    def __init__(self):
        # self.state = None

        # Message Header
        self.message_header = None
        self.cable_plug = None
        self.data_role = None
        self.usb_spec = None
        self.power_role = None

        # Role Control
        self.role_control = None
        self.rc_cc1 = None
        self.rc_cc2 = None
        self.rp_value = None
        self.drp = None

        # CC Status
        self.cc_status = None
        self.Looking4Connection = None
        self.ConnectResult = None
        self.cc2_state = None
        self.cc1_state = None

        # Power Status
        self.power_status = None
        self.vbus_sink = None
        self.vconn_present = None
        self.vbus_present = None
        self.vbus_detect = None
        self.vbus_source = None
        self.high_volt = None
        self.tcpc_init = None
        self.debug_acc = None

        # Extended Status
        self.extended_status = None
        self.vsafe = None
        
        self.i2c_state = None
        self.vbus_voltage = None
