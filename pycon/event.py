# event.py
from .wrappers import PythonicWiimote

class ButtonEventWiimote(PythonicWiimote):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._events_buffer = []
        self._previous = {btn: 0 for btn in ['a','b','plus','minus','up','down','left','right']}

    def joycon_button_event(self, button, state):
        self._events_buffer.append((button, state))

    def events(self):
        while self._events_buffer:
            yield self._events_buffer.pop(0)

    def _update_buttons(self):
        for btn in self._previous.keys():
            val = getattr(self, btn)
            if val != self._previous[btn]:
                self._previous[btn] = val
                self.joycon_button_event(btn, val)

    def register_update_hook(self, callback):
        super().register_update_hook(lambda status: self._update_buttons())
