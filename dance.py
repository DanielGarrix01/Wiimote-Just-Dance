import asyncio
import json
import random
import socket
import ssl
import time
import traceback
from enum import Enum

import aiohttp
from aiohttp import web
import websockets

from joydance.constants import (
    ACCEL_ACQUISITION_FREQ_HZ, ACCEL_ACQUISITION_LATENCY,
    ACCEL_MAX_RANGE, FRAME_DURATION, SHORTCUT_MAPPING,
    UBI_APP_ID, UBI_SKU_ID, WS_SUBPROTOCOLS, Command,
    WsSubprotocolVersion, WiimoteButton)
from pycon.wiimote import Wiimote


class State(Enum):
    DISCONNECTED = 0
    IDLE = 1
    PENDING = 2
    CONNECTED = 3
    DANCING = 4


class WiimoteDance:
    def __init__(self, wiimote, protocol_version, pairing_id=None, pairing_code=None, on_state_changed=None):
        self.wiimote = wiimote
        self.protocol_version = protocol_version
        self.pairing_id = pairing_id or str(random.randint(0, 0xFFFFFFFF))
        self.pairing_code = pairing_code
        self.state = State.IDLE
        self.ws = None
        self.ws_url = None
        self.last_phone_accel_sent_at = 0
        
        if on_state_changed:
            self.on_state_changed = on_state_changed
        else:
            self.on_state_changed = self._default_state_changed

    async def _default_state_changed(self, state):
        print(f"[Estado] {state.name}")

    def change_state(self, state):
        if state == self.state:
            return
        self.state = state
        asyncio.create_task(self.on_state_changed(state))

    async def pair(self):
        self.change_state(State.PENDING)

        if self.protocol_version == WsSubprotocolVersion.V2:
            await self.pair_with_code()
        else:
            await self.pair_v1()

    async def pair_with_code(self):
        """Emparejamiento V2 con código (JD 2018+)"""
        url = f'https://jmcs-controller-api.just-dance.com/pair/{self.pairing_code}'
        headers = {
            'X-SkuId': UBI_SKU_ID,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        print(f'Error al emparejar: {resp.status}')
                        self.change_state(State.IDLE)
                        return

                    result = await resp.json()
                    self.ws_url = result['jdcsUrl']
        except Exception as e:
            print(f'Error de emparejamiento: {e}')
            self.change_state(State.IDLE)
            return

        await self.connect()

    async def pair_v1(self):
        """Emparejamiento V1 directo por IP (JD 2016-2019)"""
        if not self.pairing_id:
            print('Error: Se requiere una IP para emparejamiento V1')
            self.change_state(State.IDLE)
            return

        # Enviando descubrimiento UDP a {self.pairing_id}:6000...
        print(f'Enviando descubrimiento UDP a {self.pairing_id}:6000...')
        udp_success = await self.udp_discovery(self.pairing_id)
        
        if udp_success:
            print('Descubrimiento UDP exitoso')
        else:
            print('Advertencia: No hubo respuesta UDP, intentando de todas formas...')
        
        # Pequeña espera para que Just Dance procese el descubrimiento
        await asyncio.sleep(1)

        print(f'Intentando descubrimiento HTTP en {self.pairing_id}...')
        discovered = await self.http_discovery(self.pairing_id)
        
        if not discovered:
            print('Advertencia: No se pudo hacer descubrimiento HTTP, intentando WebSocket directo...')
        
        ports_to_try = [8080, 50000, 50001]
        paths_to_try = ['', '/ws', '/websocket', '/controller', '/phone']
        
        for port in ports_to_try:
            for path in paths_to_try:
                test_url = f'ws://{self.pairing_id}:{port}{path}'
                print(f'Probando {test_url}...')
                self.ws_url = test_url
                
                try:
                    await self.connect()
                    print(f'Conexion exitosa en {test_url}')
                    return
                except websockets.exceptions.InvalidStatusCode as e:
                    print(f'  Puerto {port}{path} - HTTP {e.status_code}')
                except Exception as e:
                    error_msg = str(e)[:80]
                    print(f'  Puerto {port}{path} - {type(e).__name__}: {error_msg}')
                    continue
        
        print('Error: No se pudo conectar en ninguna combinacion de puerto/path')
        self.change_state(State.IDLE)

    async def udp_discovery(self, ip):
        """Envía mensaje de descubrimiento UDP al puerto 6000"""
        try:
            loop = asyncio.get_event_loop()
            
            # Crear socket UDP
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(2.0)
            
            # Mensaje de descubrimiento (puede variar según el protocolo)
            discovery_messages = [
                b'DISCOVER',
                b'JDCONTROLLER',
                json.dumps({
                    'type': 'discover',
                    'deviceId': self.pairing_id
                }).encode('utf-8'),
                json.dumps({
                    'msg': 'discover'
                }).encode('utf-8')
            ]
            
            for message in discovery_messages:
                try:
                    # Enviar mensaje de descubrimiento
                    sock.sendto(message, (ip, 6000))
                    print(f'  Enviado UDP: {message[:50]}')
                    
                    # Intentar recibir respuesta
                    sock.settimeout(1.0)
                    try:
                        data, addr = sock.recvfrom(1024)
                        print(f'  Respuesta UDP de {addr}: {data[:100]}')
                        sock.close()
                        return True
                    except socket.timeout:
                        continue
                except Exception as e:
                    print(f'  Error UDP con mensaje {message[:20]}: {type(e).__name__}')
                    continue
            
            sock.close()
            return False
            
        except Exception as e:
            print(f'Error en descubrimiento UDP: {e}')
            return False

    async def http_discovery(self, ip):
        """Intenta descubrimiento HTTP antes del WebSocket"""
        endpoints = [
            f'http://{ip}:8080/',
            f'http://{ip}:8080/discovery',
            f'http://{ip}:8080/connect',
            f'http://{ip}:8080/api',
        ]
        
        try:
            async with aiohttp.ClientSession() as session:
                for endpoint in endpoints:
                    try:
                        async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=2)) as resp:
                            print(f'  HTTP {endpoint} - Status {resp.status}')
                            if resp.status in [200, 201, 204]:
                                text = await resp.text()
                                print(f'  Respuesta: {text[:100]}')
                                return True
                    except Exception as e:
                        print(f'  HTTP {endpoint} - {type(e).__name__}')
                        continue
        except Exception as e:
            print(f'Error en descubrimiento HTTP: {e}')
        
        return False

    async def connect(self):
        """Conecta al servidor WebSocket de Just Dance"""
        if not self.ws_url:
            print('Error: No hay URL de WebSocket')
            return

        try:
            ssl_context = None
            if self.ws_url.startswith('wss://'):
                ssl_context = ssl.create_default_context()

            subprotocol = 'v2' if self.protocol_version == WsSubprotocolVersion.V2 else 'v1'
            
            self.ws = await asyncio.wait_for(
                websockets.connect(
                    self.ws_url,
                    subprotocols=[subprotocol],
                    ssl=ssl_context,
                    ping_interval=None  # Desactivar ping automático
                ),
                timeout=3.0  # Timeout de 3 segundos
            )

            self.change_state(State.CONNECTED)
            print(f'Conectado exitosamente a {self.ws_url}')

            await asyncio.gather(
                self.send_ping(),
                self.send_command(),
                self.receive_message()
            )

        except asyncio.TimeoutError:
            print(f'Timeout al conectar')
            self.change_state(State.IDLE)
            raise
        except Exception as e:
            print(f'Error de conexión: {type(e).__name__}: {e}')
            self.change_state(State.IDLE)
            raise

    async def send_ping(self):
        """Envía pings periódicos para mantener la conexión"""
        while self.ws and not self.ws.closed:
            try:
                await self.ws.ping()
                await asyncio.sleep(10)
            except Exception as e:
                print(f'Error al enviar ping: {e}')
                break

    async def send_command(self):
        """Envía comandos del Wiimote a Just Dance"""
        while self.ws and not self.ws.closed:
            try:
                events = self.wiimote.events()
                
                for event_type, status in events:
                    if status == 0:
                        continue

                    command = SHORTCUT_MAPPING.get(event_type)
                    if command:
                        await self._send_json({'command': command.value})
                        print(f'[CMD] {command.name}')

                now = time.time()
                if now - self.last_phone_accel_sent_at >= ACCEL_ACQUISITION_LATENCY:
                    accels = self.wiimote.get_accels()
                    await self._send_json({
                        'phoneAccel': {
                            'data': accels
                        }
                    })
                    self.last_phone_accel_sent_at = now

                await asyncio.sleep(FRAME_DURATION)

            except Exception as e:
                print(f'Error al enviar comando: {e}')
                traceback.print_exc()
                break

    async def receive_message(self):
        """Recibe mensajes del servidor"""
        while self.ws and not self.ws.closed:
            try:
                message = await self.ws.recv()
                data = json.loads(message)

                if 'msg_id' in data:
                    msg_id = data['msg_id']
                    
                    if msg_id == 5:
                        self.change_state(State.DANCING)
                        print('[INFO] Juego iniciado')
                    
                    elif msg_id == 6:
                        self.change_state(State.CONNECTED)
                        print('[INFO] Juego pausado')
                    
                    elif msg_id == 7:
                        self.change_state(State.CONNECTED)
                        print('[INFO] Juego terminado')

            except websockets.exceptions.ConnectionClosed:
                print('[INFO] Conexión cerrada')
                break
            except Exception as e:
                print(f'Error al recibir mensaje: {e}')
                break

        self.change_state(State.DISCONNECTED)

    async def _send_json(self, data):
        """Envía datos JSON al servidor"""
        if self.ws and not self.ws.closed:
            await self.ws.send(json.dumps(data))


routes = web.RouteTableDef()

@routes.get('/')
async def index(request):
    return web.FileResponse('./static/index.html')

@routes.post('/start')
async def start_dance(request):
    """Inicia el emparejamiento con Just Dance"""
    try:
        data = await request.json()
        method = data.get('method')
        value = data.get('value', '')

        print(f'\n[INICIO] Método: {method}, Valor: {value}')

        if method == 'code':
            protocol_version = WsSubprotocolVersion.V2
            pairing_code = value
            pairing_id = None
        elif method == 'old':
            protocol_version = WsSubprotocolVersion.V1
            pairing_code = None
            pairing_id = value
        else:
            return web.json_response({'error': 'Método desconocido'}, status=400)

        try:
            wiimote = Wiimote()
            print('Wiimote conectado')
        except Exception as e:
            print(f'Error al conectar Wiimote: {e}')
            return web.json_response({'error': f'Error al conectar Wiimote: {e}'}, status=500)

        dancer = WiimoteDance(
            wiimote=wiimote,
            protocol_version=protocol_version,
            pairing_code=pairing_code,
            pairing_id=pairing_id
        )

        asyncio.create_task(dancer.pair())

        return web.json_response({'status': 'ok'})

    except Exception as e:
        print(f'Error: {e}')
        traceback.print_exc()
        return web.json_response({'error': str(e)}, status=500)


def get_local_ip():
    """Obtiene la IP local de la PC"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'


async def main():
    print('=== Wiimote Just Dance Server ===')
    
    local_ip = get_local_ip()
    port = 8000
    
    app = web.Application()
    app.add_routes(routes)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f'\nServidor iniciado')
    print(f'  Abre en tu navegador: http://{local_ip}:{port}')
    print(f'  O usa: http://localhost:{port}')
    print(f'\nPresiona Ctrl+C para detener\n')
    
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print('\n\nDeteniendo servidor...')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Servidor detenido')
