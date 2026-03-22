"""
Hack-A-Bot Buggy Receiver
=========================
Runs on the buggy's Raspberry Pi Pico (RP2040).
Receives control packets from the Hack-A-Bot Pi Pico controller over nRF24L01+
and drives 5 motors via H-bridge drivers (L298N / TB6612 etc.).

Radio wiring (SPI1 — valid RP2040 pin assignments):
  MISO  -> GPIO12  (SPI1 RX)
  SCK   -> GPIO14  (SPI1 SCK)
  MOSI  -> GPIO15  (SPI1 TX)   -- NOTE: GPIO15 is SPI1 TX, not used by motors
  CSN   -> GPIO20  (plain GPIO)
  CE    -> GPIO21  (plain GPIO)

Motor driver wiring:
  M1 Drive Left  : INA=GPIO0,  INB=GPIO1,  ENA/PWM=GPIO2  (remove ENA jumper)
  M2 Drive Right : INA=GPIO3,  INB=GPIO4,  ENB/PWM=GPIO5  (remove ENB jumper)
  M3 Lift Left   : INA=GPIO6,  INB=GPIO7,  ENA=3V3 (leave jumper fitted — full speed)
  M4 Lift Right  : INA=GPIO8,  INB=GPIO9,  ENB=3V3 (leave jumper fitted — full speed)
  M5 Bridge      : INA=GPIO10, INB=GPIO11, ENA=3V3 (leave jumper fitted — full speed)

Packet format (9 bytes, little-endian — must match transmitter):
  Byte 0-1 : uint16  left_h
  Byte 2-3 : uint16  left_v
  Byte 4-5 : uint16  right_h
  Byte 6   : uint8   buttons  (bit0=SW1, bit1=SW2, bit2=Left_SW, bit3=Right_SW)
  Byte 7   : uint8   lift_btn (bit0=lift up, bit1=lift down)
  Byte 8   : uint8   bridge   (bit0=bridge fwd, bit1=bridge rev)

Dependencies:
  nrf24l01.py from micropython-lib — copy to the Pico filesystem.
  https://github.com/micropython/micropython-lib/blob/master/micropython/drivers/radio/nrf24l01/nrf24l01.py
"""

import utime
import struct
from machine import Pin, SPI, PWM
from nrf24l01 import NRF24L01

# ---------------------------------------------------------------------------
# Radio configuration — must match the transmitter exactly
# ---------------------------------------------------------------------------
RADIO_CHANNEL  = 90
PAYLOAD_SIZE   = 9
PIPE_ADDRESS   = b"\xe1\xf0\xf0\xf0\xf0"

# ---------------------------------------------------------------------------
# Radio pins (SPI1 — valid RP2040 assignments)
# ---------------------------------------------------------------------------
PIN_MISO = 12
PIN_SCK  = 14
PIN_MOSI = 15
PIN_CSN  = 20
PIN_CE   = 21

# ---------------------------------------------------------------------------
# Motor driver pins
# ---------------------------------------------------------------------------
# Drive motors (PWM speed control)
M1_INA = Pin(0, Pin.OUT)
M1_INB = Pin(1, Pin.OUT)
M1_PWM = PWM(Pin(2))

M2_INA = Pin(3, Pin.OUT)
M2_INB = Pin(4, Pin.OUT)
M2_PWM = PWM(Pin(5))

# Lift motors (full speed on/off — ENA/ENB jumpers left fitted on L298N)
M3_INA = Pin(6, Pin.OUT)
M3_INB = Pin(7, Pin.OUT)

M4_INA = Pin(8, Pin.OUT)
M4_INB = Pin(9, Pin.OUT)

# Bridge motor (full speed on/off — ENA jumper left fitted on L298N)
M5_INA = Pin(10, Pin.OUT)
M5_INB = Pin(11, Pin.OUT)

# Set PWM frequency for drive motors only (20 kHz — above audible range)
PWM_FREQ = 20_000
for _pwm in (M1_PWM, M2_PWM):
    _pwm.freq(PWM_FREQ)

# Onboard status LED
try:
    status_led = Pin("LED", Pin.OUT)   # Pico W
except TypeError:
    status_led = Pin(25, Pin.OUT)      # Standard Pico

# ---------------------------------------------------------------------------
# Motor helper
# ---------------------------------------------------------------------------
DEADZONE   = 2000
ADC_CENTRE = 32768

def _set_motor_pwm(ina, inb, pwm_pin, speed: int):
    """Drive motor with variable speed. speed: -65535 to +65535."""
    speed = max(-65535, min(65535, speed))
    if speed > 0:
        ina.value(1)
        inb.value(0)
        pwm_pin.duty_u16(speed)
    elif speed < 0:
        ina.value(0)
        inb.value(1)
        pwm_pin.duty_u16(-speed)
    else:
        ina.value(0)
        inb.value(0)
        pwm_pin.duty_u16(0)


def _set_motor_onoff(ina, inb, direction: int):
    """Full speed on/off motor. direction: 1=forward, -1=reverse, 0=stop."""
    if direction > 0:
        ina.value(1)
        inb.value(0)
    elif direction < 0:
        ina.value(0)
        inb.value(1)
    else:
        ina.value(0)
        inb.value(0)


def axis_to_speed(raw: int) -> int:
    """Convert raw 16-bit ADC value (0-65535) to signed speed (-65535..65535)."""
    offset = raw - ADC_CENTRE
    if abs(offset) < DEADZONE:
        return 0
    return offset


def stop_all():
    _set_motor_pwm(M1_INA, M1_INB, M1_PWM, 0)
    _set_motor_pwm(M2_INA, M2_INB, M2_PWM, 0)
    _set_motor_onoff(M3_INA, M3_INB, 0)
    _set_motor_onoff(M4_INA, M4_INB, 0)
    _set_motor_onoff(M5_INA, M5_INB, 0)

# ---------------------------------------------------------------------------
# Radio initialisation
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
# Packet decoder
# ---------------------------------------------------------------------------
def decode_packet(buf):
    """
    Returns (left_h, left_v, right_h, buttons, lift_btn, bridge) from a 9-byte buffer.
    """
    left_h, left_v, right_h, buttons, lift_btn, bridge = struct.unpack("<HHHbbb", buf)
    return left_h, left_v, right_h, buttons, lift_btn, bridge

# ---------------------------------------------------------------------------
# Drive logic
# ---------------------------------------------------------------------------
def apply_drive(left_v: int, right_h: int):
    """
    Tank-style mixing:
      left_v  -> forward / backward (both motors together)
      right_h -> turning (differential left vs right)
    """
    fwd  = axis_to_speed(left_v)
    turn = axis_to_speed(right_h)

    left_speed  = max(-65535, min(65535, fwd + turn))
    right_speed = max(-65535, min(65535, fwd - turn))

    _set_motor_pwm(M1_INA, M1_INB, M1_PWM, left_speed)
    _set_motor_pwm(M2_INA, M2_INB, M2_PWM, right_speed)


def apply_lift(lift_btn: int):
    """
    bit0 = lift up, bit1 = lift down.
    M3 and M4 run together at full speed.
    """
    if lift_btn & 0x01:
        _set_motor_onoff(M3_INA, M3_INB,  1)
        _set_motor_onoff(M4_INA, M4_INB,  1)
    elif lift_btn & 0x02:
        _set_motor_onoff(M3_INA, M3_INB, -1)
        _set_motor_onoff(M4_INA, M4_INB, -1)
    else:
        _set_motor_onoff(M3_INA, M3_INB,  0)
        _set_motor_onoff(M4_INA, M4_INB,  0)


def apply_bridge(bridge: int):
    """
    bit0 = bridge forward, bit1 = bridge reverse (M5 only, full speed).
    """
    if bridge & 0x01:
        _set_motor_onoff(M5_INA, M5_INB,  1)
    elif bridge & 0x02:
        _set_motor_onoff(M5_INA, M5_INB, -1)
    else:
        _set_motor_onoff(M5_INA, M5_INB,  0)

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
TIMEOUT_MS = 500   # stop all motors if signal lost for this long

def main():
    print("Buggy receiver starting...")
    nrf = init_radio()
    stop_all()
    print("Listening for packets...")

    last_rx = utime.ticks_ms()

    while True:
        if nrf.any():
            buf = nrf.recv()
            last_rx = utime.ticks_ms()
            status_led.toggle()

            try:
                left_h, left_v, right_h, buttons, lift_btn, bridge = decode_packet(buf)
            except Exception as e:
                print("Bad packet:", e)
                continue

            apply_drive(left_v, right_h)
            apply_lift(lift_btn)
            apply_bridge(bridge)

        else:
            # Safety: stop everything if signal is lost
            if utime.ticks_diff(utime.ticks_ms(), last_rx) > TIMEOUT_MS:
                stop_all()
                status_led.value(0)

        utime.sleep_ms(5)


main()
