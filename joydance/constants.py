from enum import Enum, IntEnum

JOYDANCE_VERSION = '0.5.2'
UBI_APP_ID = '210da0fb-d6a5-4ed1-9808-01e86f0de7fb'
UBI_SKU_ID = 'jdcompanion-android'


class WsSubprotocolVersion(Enum):
    V1 = 'v1'
    V2 = 'v2'


WS_SUBPROTOCOLS = ['v1.phonescoring.jd.ubisoft.com', 'v2.phonescoring.jd.ubisoft.com']

FRAME_DURATION = 0.015
SEND_FREQ_MS = 0.05
ACCEL_ACQUISITION_FREQ_HZ = 200  # Hz
ACCEL_ACQUISITION_LATENCY = 0  # ms
ACCEL_MAX_RANGE = 8  # ±G

DEFAULT_CONFIG = {
    'pairing_method': 'default',
    'host_ip_addr': '',
    'console_ip_addr': '',
    'pairing_code': '',
}


class Command(Enum):
    UP = 3690595578
    RIGHT = 1099935642
    DOWN = 2467711647
    LEFT = 3652315484
    ACCEPT = 1084313942
    PAUSE = 'PAUSE'
    BACK = 'SHORTCUT_BACK'


class WiimoteButton(Enum):
    """Enum para los botones del Wiimote"""
    A = 'a'
    B = 'b'
    ONE = 'one'
    TWO = 'two'
    MINUS = 'minus'
    PLUS = 'plus'
    HOME = 'home'
    UP = 'up'
    DOWN = 'down'
    LEFT = 'left'
    RIGHT = 'right'


SHORTCUT_MAPPING = {
    'a': Command.ACCEPT,
    'b': Command.BACK,
    'plus': Command.PAUSE,
    'minus': Command.BACK,
    'one': Command.ACCEPT,
    'two': Command.BACK,
    'up': Command.UP,
    'down': Command.DOWN,
    'left': Command.LEFT,
    'right': Command.RIGHT,
}
