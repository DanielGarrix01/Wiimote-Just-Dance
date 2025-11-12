import hid
import time
from threading import Thread
from typing import Callable, List, Tuple, Optional

WIIMOTE_VENDOR_ID = 0x057E
WIIMOTE_PRODUCT_IDS = [0x0306, 0x0307]

class Wiimote:
    _REPORT_SIZE = 22
    _UPDATE_PERIOD = 0.01

    def __init__(self, vendor_id=WIIMOTE_VENDOR_ID, product_id=WIIMOTE_PRODUCT_IDS[0], serial: Optional[str]=None):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.serial = serial
        self._input_report = bytes(self._REPORT_SIZE)
        self._input_hooks: List[Callable[[dict], None]] = []

        self._device = hid.device()
        self._device.open(vendor_id, product_id, serial)
        self._running = True

        Thread(target=self._update_loop, daemon=True).start()

    def _read_report(self):
        try:
            data = self._device.read(self._REPORT_SIZE)
            if data:
                self._input_report = bytes(data)
        except OSError:
            self._running = False

    def _update_loop(self):
        while self._running:
            self._read_report()
            status = self.get_status()
            for hook in self._input_hooks:
                hook(status)
            time.sleep(self._UPDATE_PERIOD)

    def get_button_a(self):  return self._input_report[2] & 0x08 > 0
    def get_button_b(self):  return self._input_report[2] & 0x04 > 0
    def get_button_1(self):  return self._input_report[2] & 0x02 > 0
    def get_button_2(self):  return self._input_report[2] & 0x01 > 0
    def get_button_plus(self):  return self._input_report[3] & 0x10 > 0
    def get_button_minus(self): return self._input_report[3] & 0x01 > 0
    def get_up(self):     return self._input_report[2] & 0x10 > 0
    def get_down(self):   return self._input_report[2] & 0x20 > 0
    def get_left(self):   return self._input_report[2] & 0x40 > 0
    def get_right(self):  return self._input_report[2] & 0x80 > 0

    def get_accel(self) -> Tuple[int, int, int]:
        x = self._input_report[4]
        y = self._input_report[5]
        z = self._input_report[6]
        return (x, y, z)

    def get_status(self) -> dict:
        return {
            "buttons": {
                "A": self.get_button_a(),
                "B": self.get_button_b(),
                "+": self.get_button_plus(),
                "-": self.get_button_minus(),
                "1": self.get_button_1(),
                "2": self.get_button_2(),
                "up": self.get_up(),
                "down": self.get_down(),
                "left": self.get_left(),
                "right": self.get_right(),
            },
            "accel": self.get_accel()
        }

    def register_update_hook(self, callback: Callable[[dict], None]):
        self._input_hooks.append(callback)
        return callback

    def close(self):
        self._running = False
        self._device.close()
