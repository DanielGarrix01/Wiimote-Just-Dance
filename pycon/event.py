from .wiimote import Wiimote  # tu clase Wiimote.py


class ButtonEventWiimote(Wiimote):
    """
    Wrapper para Wiimote que detecta cambios de estado de los botones
    y mantiene un buffer de eventos. Funciona de forma similar a
    ButtonEventJoyCon.
    """
    def __init__(self, *args, track_buttons=False, **kwargs):
        super().__init__(*args, **kwargs)

        self._events_buffer = []
        self._event_handlers = {}
        self._event_track_buttons = track_buttons

        # Estados previos de todos los botones
        self._previous_a = 0
        self._previous_b = 0
        self._previous_up = 0
        self._previous_down = 0
        self._previous_left = 0
        self._previous_right = 0
        self._previous_minus = 0
        self._previous_plus = 0
        self._previous_1 = 0
        self._previous_2 = 0

        # Hook para actualizar eventos cada vez que cambia el estado del Wiimote
        self.register_update_hook(self._event_tracking_update_hook)

    def wiimote_button_event(self, button, state):
        """Añade un evento al buffer"""
        self._events_buffer.append((button, state))

    def events(self):
        """Generador de eventos"""
        while self._events_buffer:
            yield self._events_buffer.pop(0)

    def _event_tracking_update_hook(self, _wiimote=None):
        """Se ejecuta cada vez que hay actualización de estado"""
        if self._event_track_buttons:
            # Lista de botones y estados
            mapping = {
                "a": self.a,
                "b": self.b,
                "up": self.up,
                "down": self.down,
                "left": self.left,
                "right": self.right,
                "minus": self.minus,
                "plus": self.plus,
                "1": self.button_1,
                "2": self.button_2,
            }

            # Compara con el estado previo y añade al buffer si cambia
            for btn_name, pressed in mapping.items():
                prev_attr = f"_previous_{btn_name}" if btn_name not in ["1", "2"] else f"_previous_{btn_name}"
                prev_state = getattr(self, prev_attr)
                if prev_state != pressed:
                    setattr(self, prev_attr, pressed)
                    self.wiimote_button_event(btn_name, pressed)
