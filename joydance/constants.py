from enum import Enum

JOYDANCE_VERSION = '0.5.2'
UBI_APP_ID = '210da0fb-d6a5-4ed1-9808-01e86f0de7fb'
UBI_SKU_ID = 'jdcompanion-android'


class WsSubprotocolVersion(Enum):
    V1 = 'v1'
    V2 = 'v2'


WS_SUBPROTOCOLS = {
    WsSubprotocolVersion.V1.value: 'v1.phonescoring.jd.ubisoft.com',
    WsSubprotocolVersion.V2.value: 'v2.phonescoring.jd.ubisoft.com',
}

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
    # Movimientos del juego
    UP = 3690595578
    RIGHT = 1099935642
    DOWN = 2467711647
    LEFT = 3652315484

    # Confirmar / retroceder
    ACCEPT = 'ACCEPT'
    BACK = 'BACK'

    # Pausa / opciones
    PAUSE = 'PAUSE'
    OPTIONS = 'OPTIONS'

    # Cambiar entre botones favoritos o bailar
    CHANGE_BUTTONS = 'CHANGE_BUTTONS'


class WiimoteButton(Enum):
    # Botones físicos del Wiimote
    A = 'a'
    B = 'b'
    PLUS = 'plus'
    MINUS = 'minus'
    ONE = '1'
    TWO = '2'
    UP = 'up'
    DOWN = 'down'
    LEFT = 'left'
    RIGHT = 'right'


# Asignación de botones del Wiimote a comandos de Just Dance
SHORTCUT_MAPPING = {
    WiimoteButton.A: [Command.ACCEPT],
    WiimoteButton.B: [Command.BACK],
    WiimoteButton.PLUS: [Command.PAUSE],
    WiimoteButton.MINUS: [Command.OPTIONS],
    WiimoteButton.ONE: [Command.CHANGE_BUTTONS],
    WiimoteButton.TWO: [Command.CHANGE_BUTTONS],
    WiimoteButton.UP: [Command.UP],
    WiimoteButton.DOWN: [Command.DOWN],
    WiimoteButton.LEFT: [Command.LEFT],
    WiimoteButton.RIGHT: [Command.RIGHT],
}
