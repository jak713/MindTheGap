"""
Hack-A-Bot Buggy Receiver
"""
import utime
import struct
from machine import Pin, SPI, PWM
from nrf24l01 import NRF24L01

# ---------------------------------------------------------------------------
# Radio configuration — must match transmitter
# ---------------------------------------------------------------------------
RADIO_CHANNEL = 90
PAYLOAD_SIZE  = 5          # "<HHb" = 2+2+1
PIPE_ADDRESS  = b"\xe1\xf0\xf0\xf0\xf0"

PIN_MISO = 12
PIN_SCK  = 14
PIN_MOSI = 15
PIN_CSN  = 20
PIN_CE   = 21

# ---------------------------------------------------------------------------
# DCMotor class
# ---------------------------------------------------------------------------
MAX_POWER = 65535

class DCMotor:
    def __init__(self, pin1, pin2, enable_pin, min_duty=15000, max_duty=65535):
        self.pin1       = pin1
        self.pin2       = pin2
        self.enable_pin = enable_pin
        self.min_duty   = min_duty
        self.max_duty   = max_duty

    def forward(self, speed):
        self.enable_pin.duty_u16(self._duty(speed))
        self.pin1.value(1)
        self.pin2.value(0)

    def backwards(self, speed):
        self.enable_pin.duty_u16(self._duty(speed))
        self.pin1.value(0)
        self.pin2.value(1)

    def stop(self):
        self.enable_pin.duty_u16(0)
        self.pin1.value(0)
        self.pin2.value(0)

    def brake(self):
        self.enable_pin.duty_u16(MAX_POWER)
        self.pin1.value(1)
        self.pin2.value(1)

    def _duty(self, speed):
        if speed <= 0 or speed > 100:
            return 0
        return int(self.min_duty + (self.max_duty - self.min_duty) * (speed / 100))

    def drive_raw(self, raw: int, speed_pct: int = 60):
        """
        Takes a raw 16-bit ADC value (0-65535), centre=32768.
        Drives forward/backward at speed_pct, stops in deadzone.
        """
        DEADZONE = 2000
        offset = raw - 32768
        if abs(offset) < DEADZONE:
            self.stop()
        elif offset > 0:
            self.forward(speed_pct)
        else:
            self.backwards(speed_pct)

class OnOffMotor:
    def __init__(self, pin1, pin2):
        self.pin1 = pin1
        self.pin2 = pin2

    def forward(self):
        self.pin1.value(1)
        self.pin2.value(0)

    def backwards(self):
        self.pin1.value(0)
        self.pin2.value(1)

    def stop(self):
        self.pin1.value(0)
        self.pin2.value(0)

    def drive_raw(self, raw: int):
        DEADZONE = 2000
        offset = raw - 32768
        if abs(offset) < DEADZONE:
            self.stop()
        elif offset > 0:
            self.forward()
        else:
            self.backwards()

# Bridge TT motor
bridge = OnOffMotor(Pin(11, Pin.OUT), Pin(12, Pin.OUT))
# ---------------------------------------------------------------------------
# Motor setup — fill in your GPIO pins below
# ---------------------------------------------------------------------------
PWM_FREQ = 1000

# Buggy drive motors (left and right)
drive_left  = DCMotor(Pin(0,  Pin.OUT),
                      Pin(1,  Pin.OUT),
                      PWM(Pin(2), freq=PWM_FREQ))

drive_right = DCMotor(Pin(3,  Pin.OUT),
                      Pin(4,  Pin.OUT),
                      PWM(Pin(5),freq=PWM_FREQ))

# Actuator motors (left and right lift) — TODO: fill correct pins
actuator_left  = OnOffMotor(Pin(6,  Pin.OUT),
                         Pin(7,  Pin.OUT))

actuator_right = OnOffMotor(Pin(8,  Pin.OUT),
                         Pin(9, Pin.OUT))

# Bridge TT motor
bridge = OnOffMotor(Pin(11, Pin.OUT),
                 Pin(12, Pin.OUT))

DRIVE_SPEED  = 60   # % for buggy
BRIDGE_SPEED = 40   # % for bridge motor
LIFT_SPEED   = 100  # % for actuators (full speed)

# ---------------------------------------------------------------------------
# Stop everything
# ---------------------------------------------------------------------------
def stop_all():
    drive_left.stop()
    drive_right.stop()
    actuator_left.stop()
    actuator_right.stop()
    bridge.stop()

# ---------------------------------------------------------------------------
# Radio init
# ---------------------------------------------------------------------------
def init_radio():
    spi = SPI(1,
              baudrate=4_000_000,
              polarity=0,
              phase=0,
              sck=Pin(PIN_SCK),
              mosi=Pin(PIN_MOSI),
              miso=Pin(PIN_MISO))

    nrf = NRF24L01(spi, cs=Pin(PIN_CSN), ce=Pin(PIN_CE),
                   payload_size=PAYLOAD_SIZE)
    nrf.set_channel(RADIO_CHANNEL)
    nrf.open_rx_pipe(1, PIPE_ADDRESS)
    nrf.start_listening()
    return nrf

# ---------------------------------------------------------------------------
# Packet decoder — matches transmitter "<HHb"
# ---------------------------------------------------------------------------
def decode_packet(buf):
    """Returns (buggy_raw, bridge_raw, actuator) from 5-byte buffer."""
    
    buggy_raw, bridge_raw, actuator = struct.unpack("<HHb", buf)
    return buggy_raw, bridge_raw, actuator
# ---------------------------------------------------------------------------
# Status LED
# ---------------------------------------------------------------------------
status_led = Pin(25, Pin.OUT)

    

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
TIMEOUT_MS = 500

def main():
    print("Buggy receiver starting...")
    nrf = init_radio()
    stop_all()
    print("Listening...")

    last_rx = utime.ticks_ms()

    while True:
        if nrf.any():
            buf = nrf.recv()
            last_rx = utime.ticks_ms()
            status_led.toggle()


            try:
                buggy_raw, bridge_raw, actuator = decode_packet(buf)
                print("buggy={} bridge={} act={}".format(buggy_raw >> 8, bridge_raw >> 8, actuator))
            except Exception as e:
                print("Bad packet:", e)
                continue

            # Buggy: both drive motors same direction
            print("  -> drive_raw({})".format(buggy_raw))
            drive_left.drive_raw(buggy_raw, DRIVE_SPEED)
            drive_right.drive_raw(buggy_raw, DRIVE_SPEED)

            # Bridge
            print("  -> bridge_raw({})".format(bridge_raw))
            bridge.drive_raw(bridge_raw)

            # Actuators
            print("  -> actuator={}".format(actuator))
            if actuator == 1:
                actuator_left.forward()
                actuator_right.forward()
            elif actuator == -1:
                actuator_left.backwards()
                actuator_right.backwards()
            else:
                actuator_left.stop()
                actuator_right.stop()

        else:
            if utime.ticks_diff(utime.ticks_ms(), last_rx) > TIMEOUT_MS:
                stop_all()
                status_led.value(0)

        utime.sleep_ms(5)

main()