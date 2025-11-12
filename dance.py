import asyncio
import json
import random
import socket
import ssl
import time
import traceback
from enum import Enum
from urllib.parse import urlparse

import aiohttp
import websockets

from joydance.constants import ( 
    ACCEL_ACQUISITION_FREQ_HZ, ACCEL_ACQUISITION_LATENCY,
    ACCEL_MAX_RANGE, FRAME_DURATION, SHORTCUT_MAPPING,
    UBI_APP_ID, UBI_SKU_ID, WS_SUBPROTOCOLS, Command,
    WsSubprotocolVersion
)
from pycon.wiimote import Wiimote, WiimoteButton


class PairingState(Enum):
    IDLE = 0
    GETTING_TOKEN = 1
    PAIRING = 2
    CONNECTING = 3
    CONNECTED = 4
    DISCONNECTING = 5
    DISCONNECTED = 10
    ERROR_JOYCON = 101
    ERROR_CONNECTION = 102
    ERROR_INVALID_PAIRING_CODE = 103
    ERROR_PUNCH_PAIRING = 104
    ERROR_HOLE_PUNCHING = 105
    ERROR_CONSOLE_CONNECTION = 106


class WiimoteDance:
    def __init__(
            self,
            wiimote: Wiimote,
            protocol_version,
            pairing_code=None,
            host_ip_addr=None,
            console_ip_addr=None,
            accel_acquisition_freq_hz=ACCEL_ACQUISITION_FREQ_HZ,
            accel_acquisition_latency=ACCEL_ACQUISITION_LATENCY,
            accel_max_range=ACCEL_MAX_RANGE,
            on_state_changed=None
    ):
        self.wiimote = wiimote
        self.protocol_version = protocol_version
        self.pairing_code = pairing_code
        self.host_ip_addr = host_ip_addr
        self.console_ip_addr = console_ip_addr
        self.host_port = random.randrange(39000, 39999)
        self.tls_certificate = None
        self.accel_acquisition_freq_hz = accel_acquisition_freq_hz
        self.accel_acquisition_latency = accel_acquisition_latency
        self.accel_max_range = accel_max_range
        self.number_of_accels_sent = 0
        self.should_start_accelerometer = False
        self.is_input_allowed = False
        self.available_shortcuts = set()
        self.accel_data = []
        self.ws = None
        self.console_conn = None
        self.disconnected = False
        self.headers = {'Ubi-AppId': UBI_APP_ID, 'X-SkuId': UBI_SKU_ID}
        if on_state_changed:
            self.on_state_changed = on_state_changed

    # -------------------------------
    # Token / Pairing
    # -------------------------------
    async def get_access_token(self):
        headers = {
            'Authorization': 'UbiMobile_v1 t=TOKEN_FICTICIO',
            'Ubi-AppId': UBI_APP_ID,
            'User-Agent': 'UbiServices_SDK_Unity_Light_Mobile_2018.Release.16_ANDROID64_dynamic',
            'Ubi-RequestedPlatformType': 'ubimobile',
            'Content-Type': 'application/json',
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post('https://public-ubiservices.ubi.com/v1/profiles/sessions', json={}, ssl=False) as resp:
                if resp.status != 200:
                    await self.on_state_changed(PairingState.ERROR_CONNECTION)
                    raise Exception("No se pudo obtener token")
                data = await resp.json()
                self.headers['Authorization'] = 'Ubi_v1 ' + data['ticket']

    async def send_pairing_code(self):
        url = 'https://prod.just-dance.com/sessions/v1/pairing-info'
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(url, params={'code': self.pairing_code}, ssl=False) as resp:
                if resp.status != 200:
                    await self.on_state_changed(PairingState.ERROR_INVALID_PAIRING_CODE)
                    raise Exception("Código de emparejamiento inválido")
                data = await resp.json()
                self.pairing_url = data['pairingUrl'].replace('https://', 'wss://') + 'smartphone'
                self.tls_certificate = data.get('tlsCertificate')
                self.requires_punch_pairing = data.get('requiresPunchPairing', False)

    async def send_initiate_punch_pairing(self):
        url = 'https://prod.just-dance.com/sessions/v1/initiate-punch-pairing'
        payload = {
            'pairingCode': self.pairing_code,
            'mobileIP': self.host_ip_addr,
            'mobilePort': self.host_port,
        }
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(url, json=payload, ssl=False) as resp:
                text = await resp.text()
                if text != 'OK':
                    await self.on_state_changed(PairingState.ERROR_PUNCH_PAIRING)
                    raise Exception("No se pudo iniciar punch pairing")

    async def hole_punching(self):
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.settimeout(10)
            conn.bind(('0.0.0.0', self.host_port))
            conn.listen(5)
            console_conn, addr = conn.accept()
            self.console_conn = console_conn
            print(f'Connected with {addr[0]}:{addr[1]}')
        except Exception:
            await self.on_state_changed(PairingState.ERROR_HOLE_PUNCHING)
            raise

    # -------------------------------
    # Acelerómetro
    # -------------------------------
    async def collect_accelerometer_data(self):
        if not self.should_start_accelerometer:
            self.accel_data = []
            return
        try:
            accels = self.wiimote.get_accels()
            self.accel_data += accels
        except OSError:
            await self.disconnect()

    async def send_accelerometer_data(self, frames):
        if not self.should_start_accelerometer or frames < 3:
            return
        tmp_accel_data = []
        while self.accel_data:
            tmp_accel_data.append(self.accel_data.pop(0))
        while tmp_accel_data:
            batch = tmp_accel_data[:10]
            await self.send_message('JD_PhoneScoringData', {
                'accelData': batch,
                'timeStamp': self.number_of_accels_sent
            })
            self.number_of_accels_sent += len(batch)
            tmp_accel_data = tmp_accel_data[10:]

    # -------------------------------
    # Comandos y shortcuts
    # -------------------------------
    async def send_command(self):
        while True:
            if self.disconnected:
                return
            await asyncio.sleep(FRAME_DURATION)
            if not self.is_input_allowed and not self.should_start_accelerometer:
                continue
            cmd = None
            for event_type, status in self.wiimote.events():
                if status == 0:  # released
                    continue
                button = WiimoteButton(event_type)
                if self.should_start_accelerometer:
                    if button in [WiimoteButton.PLUS, WiimoteButton.MINUS]:
                        cmd = Command.PAUSE
                else:
                    if button in [WiimoteButton.A, WiimoteButton.RIGHT]:
                        cmd = Command.ACCEPT
                    elif button in [WiimoteButton.B, WiimoteButton.DOWN]:
                        cmd = Command.BACK
                    elif button in SHORTCUT_MAPPING:
                        for shortcut in SHORTCUT_MAPPING[button]:
                            if shortcut in self.available_shortcuts:
                                cmd = shortcut
                                break
            if cmd and self.is_input_allowed:
                data = {}
                if cmd == Command.PAUSE:
                    cls = 'JD_Pause_PhoneCommandData'
                elif type(cmd.value) == str:
                    cls = 'JD_Custom_PhoneCommandData'
                    data['identifier'] = cmd.value
                else:
                    cls = 'JD_Input_PhoneCommandData'
                    data['input'] = cmd.value
                await self.send_message(cls, data)

    # -------------------------------
    # WebSocket y mensajes
    # -------------------------------
    async def send_message(self, __class, data={}):
        msg = {'root': {'__class': __class}}
        if data:
            msg['root'].update(data)
        try:
            await self.ws.send(json.dumps(msg, separators=(',', ':')))
        except Exception:
            await self.disconnect()

    async def on_message(self, message):
        message = json.loads(message)
        __class = message['__class']
        if __class == 'JD_EnableAccelValuesSending_ConsoleCommandData':
            self.should_start_accelerometer = True
            self.number_of_accels_sent = 0
        elif __class == 'JD_DisableAccelValuesSending_ConsoleCommandData':
            self.should_start_accelerometer = False
        elif __class == 'InputSetup_ConsoleCommandData':
            self.is_input_allowed = (message.get('isEnabled', 0) == 1)
        elif __class == 'ShortcutSetup_ConsoleCommandData':
            self.is_input_allowed = (message.get('isEnabled', 0) == 1)
        elif __class == 'JD_PhoneUiShortcutData':
            shortcuts = set()
            for item in message.get('shortcuts', []):
                if item['__class'] == 'JD_PhoneAction_Shortcut':
                    try:
                        shortcuts.add(Command(item['shortcutType']))
                    except Exception:
                        pass
            self.available_shortcuts = shortcuts

    # -------------------------------
    # Tick y loop
    # -------------------------------
    async def tick(self):
        sleep_duration = FRAME_DURATION
        frames = 0
        while True:
            if self.disconnected:
                break
            if not self.should_start_accelerometer:
                frames = 0
                await asyncio.sleep(sleep_duration)
                continue
            last_time = time.time()
            frames = frames + 1 if frames < 3 else 1
            await asyncio.gather(
                self.collect_accelerometer_data(),
                self.send_accelerometer_data(frames)
            )
            dt = time.time() - last_time
            sleep_duration = FRAME_DURATION - (dt - sleep_duration)

    # -------------------------------
    # Conexión
    # -------------------------------
    async def connect_ws(self):
        ssl_ctx = None
        server_hostname = None
        if self.protocol_version != WsSubprotocolVersion.V1:
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            if self.tls_certificate:
                ssl_ctx.load_verify_locations(cadata=self.tls_certificate)
            if self.pairing_url.startswith(('192.168.', '10.')) and self.console_conn:
                server_hostname = self.console_conn.getpeername()[0]
            else:
                tmp = urlparse(self.pairing_url)
                server_hostname = tmp.hostname

        subprotocol = WS_SUBPROTOCOLS[self.protocol_version.value]
        async with websockets.connect(
            self.pairing_url,
            subprotocols=[subprotocol],
            sock=self.console_conn,
            ssl=ssl_ctx,
            ping_timeout=None,
            server_hostname=server_hostname
        ) as ws:
            self.ws = ws
            await asyncio.gather(
                self.send_hello(),
                self.tick(),
                self.send_command(),
            )

    async def send_hello(self):
        await self.send_message('JD_PhoneDataCmdHandshakeHello', {
            'accelAcquisitionFreqHz': float(self.accel_acquisition_freq_hz),
            'accelAcquisitionLatency': float(self.accel_acquisition_latency),
            'accelMaxRange': float(self.accel_max_range),
        })

    # -------------------------------
    # Pair completo
    # -------------------------------
    async def pair(self):
        try:
            if self.console_ip_addr:
                self.pairing_url = f'wss://{self.console_ip_addr}:8080/smartphone'
            else:
                await self.get_access_token()
                await self.send_pairing_code()
                if self.requires_punch_pairing:
                    await self.send_initiate_punch_pairing()
                    await self.hole_punching()
            await self.connect_ws()
        except Exception:
            traceback.print_exc()
            await self.disconnect()

    async def disconnect(self):
        self.disconnected = True
        self.wiimote.__del__()
        if self.ws:
            await self.ws.close()
