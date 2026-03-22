"""
Transmitter (the controller board)
"""
import utime
import struct
from machine import Pin, SPI, ADC
from ssd1306 import SSD1306_I2C
from nrf24l01 import NRF24L01
from machine import SoftI2C


# ---------------------------------------------------------------------------
# Radio configuration — must match the transmitter exactly
# ---------------------------------------------------------------------------
RADIO_CHANNEL  = 90
PAYLOAD_SIZE   = 5
PIPE_ADDRESS   = b"\xe1\xf0\xf0\xf0\xf0"

# GPIO pins on the pico
PIN_MISO = 4
PIN_SCK = 6
PIN_MOSI = 7
PIN_CS = 14
PIN_CE = 17

# Button switches
# SW1 = Pin(11, Pin.IN, Pin.PULL_DOWN)
# SW2 = Pin(10, Pin.IN, Pin.PULL_DOWN)

# Screen
OLED_SDA = Pin(20, Pin.OUT)
OLED_SCL = Pin(21, Pin.OUT)

i2c = SoftI2C(sda=OLED_SDA, scl=OLED_SCL)
oled = SSD1306_I2C(128, 64, i2c)  
oled.rotate(180) 

# ADC channels (joystick)
LEFT_H = ADC(Pin(26))
LEFT_V = ADC(Pin(27))
RIGHT_H = ADC(Pin(28))

# joystick switch
SW1 = Pin(12, Pin.IN, Pin.PULL_DOWN)
SW2 = Pin(18, Pin.IN, Pin.PULL_DOWN)

# status
STATUS_LED = Pin(3, Pin.OUT)

# ---------------------------------------------------------------------------
# Radio initialisation
# ---------------------------------------------------------------------------
def init_radio():
    spi = SPI(0,
              baudrate=4_000_000,
              polarity=0,
              phase=0,
              sck=Pin(PIN_SCK),
              mosi=Pin(PIN_MOSI),
              miso=Pin(PIN_MISO))

    nrf = NRF24L01(spi, cs=Pin(PIN_CS), ce=Pin(PIN_CE),
                   payload_size=PAYLOAD_SIZE)

    nrf.set_channel(RADIO_CHANNEL)
    nrf.open_tx_pipe(PIPE_ADDRESS)
    nrf.stop_listening()
    return nrf

# Packet builder

def build_packet(oled, buggy, bridge, sw1, sw2):
    actuator = 0
    if sw1:
        actuator = 1
    elif sw2:
        actuator = -1

    oled.fill(0)
    oled.text("Buggy:  {}".format(buggy >> 8),  0,  0)
    oled.text("Bridge: {}".format(bridge >> 8), 0, 12)
    oled.text("Act: {}".format(actuator),        0, 24)
    oled.text("SW1:{} SW2:{}".format(sw1, sw2), 0, 36)
    oled.show()

    return struct.pack("<HHb", buggy, bridge, actuator)

TX_INTERVAL_MS = 20

def main():
    print("Hack-A-Bot transmitter starting...")
    nrf = init_radio()
    STATUS_LED.value(1)
    utime.sleep_ms(100)
    STATUS_LED.value(0)

    last_tx = utime.ticks_ms()

    while True:
        now = utime.ticks_ms()
        if utime.ticks_diff(now, last_tx) < TX_INTERVAL_MS:
            continue
        last_tx = now

        buggy  = RIGHT_H.read_u16()   # left = backward, right = forward
        bridge = 65535 - LEFT_H.read_u16()        
        s1 = SW1.value()
        s2 = SW2.value()

        payload = build_packet(oled, buggy, bridge, s1, s2)

        try:
            nrf.send(payload)
            STATUS_LED.toggle()
        except OSError:
            # Radio NAK or not ready — safe to ignore for one cycle
            pass

        utime.sleep_ms(1)

main()