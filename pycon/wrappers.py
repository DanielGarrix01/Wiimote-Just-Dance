# wrappers.py
from .wiimote import Wiimote


class PythonicWiimote(Wiimote):
    """
    Wrapper pythonico para Wiimote.
    Esto:
      * convierte los getters de botones en propiedades
      * agrupa botones relacionados
      * devuelve acelerómetro como lista de tuplas
      * incluye soporte para Nunchuk (si está conectado)
    """

    # Botones principales
    a = property(Wiimote.get_button_a)
    b = property(Wiimote.get_button_b)
    plus = property(Wiimote.get_button_plus)
    minus = property(Wiimote.get_button_minus)
    home = property(Wiimote.get_button_home)
    one = property(Wiimote.get_button_one)
    two = property(Wiimote.get_button_two)

    up = property(Wiimote.get_button_up)
    down = property(Wiimote.get_button_down)
    left = property(Wiimote.get_button_left)
    right = property(Wiimote.get_button_right)

    disconnect = Wiimote.disconnect_device

    # Nunchuk si está conectado
    c = property(Wiimote.get_nunchuk_c)
    z = property(Wiimote.get_nunchuk_z)

    @property
    def stick_nunchuk(self):
        """
        Devuelve los valores del stick del nunchuk como tupla (horizontal, vertical)
        """
        if not self.has_nunchuk():
            return (0, 0)
        return (self.get_nunchuk_stick_horizontal(), self.get_nunchuk_stick_vertical())

    @property
    def accel(self):
        """
        Devuelve acelerómetro principal y nunchuk como lista de tuplas (x, y, z)
        Si el nunchuk no está conectado, solo devuelve el Wiimote
        """
        data = [(self.get_accel_x(), self.get_accel_y(), self.get_accel_z())]
        if self.has_nunchuk():
            data.append((
                self.get_nunchuk_accel_x(),
                self.get_nunchuk_accel_y(),
                self.get_nunchuk_accel_z()
            ))
        return data
