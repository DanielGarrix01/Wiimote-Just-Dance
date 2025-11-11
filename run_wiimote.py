from pycon.event import ButtonEventWiimote
import time

def main():
    # Inicializar Wiimote con seguimiento de acelerómetro
    wm = ButtonEventWiimote(track_accel=True)

    # Función para manejar eventos de botones
    def handle_events():
        for button, pressed in wm.events():
            if pressed:
                print(f"Botón {button} presionado")
            else:
                print(f"Botón {button} liberado")

    try:
        print("Wiimote listo. Presiona botones o mueve el control...")
        while True:
            # Manejar eventos de botones
            handle_events()

            # Leer acelerómetro
            accel_x, accel_y, accel_z = wm.accel
            print(f"Acelerómetro: x={accel_x}, y={accel_y}, z={accel_z}")

            # Esperar un poco para no saturar la consola
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("Cerrando Wiimote...")
        wm.close()

if __name__ == "__main__":
    main()
