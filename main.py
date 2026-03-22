"""
Hack-A-Bot Controller Transmitter
===================================
Runs on the Hack-A-Bot Pi Pico controller board.
Reads joysticks, buttons, and encodes a 9-byte control packet
which is sent over nRF24L01+ to the buggy receiver.

Pin assignments taken directly from the Hack-A-Bot controller schematic:

  Radio  (SPI0):
    MISO  -> GPIO4  (pad 6)
    SCK   -> GPIO6  (pad 9)
    MOSI  -> GPIO7  (pad 10)
    CSN   -> GPIO14 (pad 19)
    CE    -> GPIO17 (pad 22)

  Buttons (active-high, pull-down in firmware):
    SW1      -> GPIO11 (pad 15)   -- bridge forward
    SW2      -> GPIO10 (pad 14)   -- bridge reverse
    Left_SW  -> GPIO12 (pad 16)   -- lift up
    Right_SW -> GPIO18 (pad 24)   -- lift down

  Joysticks (ADC):
    Left_H   -> GPIO26 / ADC0     -- unused in drive mix but sent in packet
    Left_V   -> GPIO27 / ADC1     -- forward / backward
    Right_H  -> GPIO28 / ADC2     -- left / right turn

  Status LED:
    STATUS   -> GPIO3  (pad 5)

Packet format (9 bytes, matches receiver decoder):
  Byte 0-1 : uint16  left_h
  Byte 2-3 : uint16  left_v
  Byte 4-5 : uint16  right_h
  Byte 6   : uint8   buttons  (bit0=SW1, bit1=SW2, bit2=Left_SW, bit3=Right_SW)
  Byte 7   : uint8   lift_btn (bit0=lift up / Left_SW, bit1=lift down / Right_SW)
  Byte 8   : uint8   bridge   (bit0=bridge fwd / SW1,  bit1=bridge rev / SW2)

Dependencies:
  nrf24l01.py from micropython-lib — copy to the Pico filesystem.
"""

import utime
import struct
from machine import Pin, SPI, ADC
from nrf24l01 import NRF24L01

# ---------------------------------------------------------------------------
# Radio configuration — must match the receiver exactly
# ---------------------------------------------------------------------------
RADIO_CHANNEL  = 90
PAYLOAD_SIZE   = 9
PIPE_ADDRESS   = b"\xe1\xf0\xf0\xf0\xf0"

# ---------------------------------------------------------------------------
# Radio pins (from the Hack-A-Bot controller schematic)
# ---------------------------------------------------------------------------
PIN_MISO = 4
PIN_SCK  = 6
PIN_MOSI = 7
PIN_CSN  = 14
PIN_CE   = 17

# ---------------------------------------------------------------------------
# Input pins
# ---------------------------------------------------------------------------
# Buttons: tied to 3V3 when pressed — configure with pull-downs
SW1      = Pin(11, Pin.IN, Pin.PULL_DOWN)   # bridge forward
SW2      = Pin(10, Pin.IN, Pin.PULL_DOWN)   # bridge reverse
LEFT_SW  = Pin(12, Pin.IN, Pin.PULL_DOWN)   # lift up
RIGHT_SW = Pin(18, Pin.IN, Pin.PULL_DOWN)   # lift down

# Joystick ADC channels
adc_left_h  = ADC(Pin(26))   # ADC0
adc_left_v  = ADC(Pin(27))   # ADC1
adc_right_h = ADC(Pin(28))   # ADC2

# Status LED
status_led = Pin(3, Pin.OUT)

# ---------------------------------------------------------------------------
# Radio init
# ---------------------------------------------------------------------------
def init_radio():
    spi = SPI(0,
              baudrate=4_000_000,
              polarity=0,
              phase=0,
              sck=Pin(PIN_SCK),
              mosi=Pin(PIN_MOSI),
              miso=Pin(PIN_MISO))

    nrf = NRF24L01(spi, cs=Pin(PIN_CSN), ce=Pin(PIN_CE),
                   payload_size=PAYLOAD_SIZE)

    nrf.set_channel(RADIO_CHANNEL)
    nrf.open_tx_pipe(PIPE_ADDRESS)
    nrf.stop_listening()   # TX mode
    return nrf

# ---------------------------------------------------------------------------
# Packet builder
# ---------------------------------------------------------------------------
def build_packet(left_h, left_v, right_h, sw1, sw2, left_sw, right_sw):
    """
    Pack joystick axes and buttons into a 9-byte payload.

    Axis values are raw 16-bit ADC reads (0–65535).
    Button values are 0 or 1.
    """
    buttons  = (sw1 & 1) | ((sw2 & 1) << 1) | ((left_sw & 1) << 2) | ((right_sw & 1) << 3)
    lift_btn = (left_sw & 1) | ((right_sw & 1) << 1)   # Left_SW=up, Right_SW=down
    bridge   = (sw1 & 1) | ((sw2 & 1) << 1)            # SW1=fwd,   SW2=rev

    return struct.pack("<HHHbbb", left_h, left_v, right_h, buttons, lift_btn, bridge)

# ---------------------------------------------------------------------------
# Main transmit loop
# ---------------------------------------------------------------------------
TX_INTERVAL_MS = 20   # send at ~50 Hz

def main():
    print("Hack-A-Bot transmitter starting...")
    nrf = init_radio()
    status_led.value(1)
    utime.sleep_ms(100)
    status_led.value(0)

    last_tx = utime.ticks_ms()

    while True:
        now = utime.ticks_ms()
        if utime.ticks_diff(now, last_tx) < TX_INTERVAL_MS:
            continue
        last_tx = now

        # Read joysticks
        lh = adc_left_h.read_u16()
        lv = adc_left_v.read_u16()
        rh = adc_right_h.read_u16()

        # Read buttons
        s1 = SW1.value()
        s2 = SW2.value()
        ls = LEFT_SW.value()
        rs = RIGHT_SW.value()

        payload = build_packet(lh, lv, rh, s1, s2, ls, rs)

        try:
            nrf.send(payload)
            status_led.toggle()
        except OSError:
            # Radio NAK or not ready — safe to ignore for one cycle
            pass

        utime.sleep_ms(1)


main()
