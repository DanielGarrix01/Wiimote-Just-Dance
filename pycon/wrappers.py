# wrappers.py
from .wiimote import Wiimote

class PythonicWiimote(Wiimote):
    """ Wrapper con propiedades tipo Python y acceso a acelerómetro """

    @property
    def a(self): return self.get_button_a()
    @property
    def b(self): return self.get_button_b()
    @property
    def plus(self): return self.get_button_plus()
    @property
    def minus(self): return self.get_button_minus()
    @property
    def up(self): return self.get_up()
    @property
    def down(self): return self.get_down()
    @property
    def left(self): return self.get_left()
    @property
    def right(self): return self.get_right()

    @property
    def accel(self): return self.get_accel()
