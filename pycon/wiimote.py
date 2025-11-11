from .wrappers import PythonicWiimote

class ButtonEventWiimote(PythonicWiimote):
    def __init__(self, *args, track_accel=True, **kwargs):
        super().__init__(*args, **kwargs)

        # Buffer de eventos (botón presionado o liberado)
        self._events_buffer = []

        # Si track_accel es True, se actualizarán datos del acelerómetro
        self._track_accel = track_accel

        # Guardar estado anterior para detectar cambios
        self._previous = self.status()

        # Registrar hook que se llama cada vez que el Wiimote se actualiza
        self.register_update_hook(self._update_hook)

    def _update_hook(self, status):
        # Detectar cambios en botones
        for button, pressed in status["buttons"].items():
            if self._previous["buttons"].get(button) != pressed:
                self._previous["buttons"][button] = pressed
                self._events_buffer.append((button, pressed))

        # Detectar cambios en acelerómetro si está activado
        if self._track_accel:
            self._previous["accel"] = status["accel"]

    def events(self):
        """Generador que devuelve eventos pendientes (botón, estado)"""
        while self._events_buffer:
            yield self._events_buffer.pop(0)

    @property
    def accel(self):
        """Devuelve acelerómetro actual"""
        return self.get_accel()
