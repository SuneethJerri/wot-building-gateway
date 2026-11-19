class Relay:
    """Relay on a GPIO pin. With mock=True it only keeps the state in memory."""

    def __init__(self, pin=17, mock=False):
        self.on = False
        self.out = None
        self.on_change = None  # called after every set(), e.g. to publish the new state over MQTT
        if not mock:
            from gpiozero import OutputDevice
            self.out = OutputDevice(pin)

    def set(self, value):
        self.on = bool(value)
        if self.out:
            self.out.value = self.on
        print("relay", "on" if self.on else "off", flush=True)
        if self.on_change:
            self.on_change()
