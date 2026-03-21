"""
Simple motor script.
"""
from machine import Pin, PWM
from time import sleep
from dcmotor import DCMotor

frequency = 1000 # Hz

Pin1 = Pin(3, Pin.OUT)
Pin2 = Pin(4, Pin.OUT)
enable = PWM(Pin(2), freq=frequency)

dc_motor = DCMotor(Pin1, Pin2, enable)

try:
    print('Forward with speed: 50%')
    dc_motor.forward(50)
    sleep(5)
    dc_motor.stop()
    sleep(5)
    print('Backwards with speed: 100%')
    dc_motor.backwards(100)
    sleep(5)
    print('Forward with speed: 5%')
    dc_motor.forward(5)
    sleep(5)
    dc_motor.stop()
    
except KeyboardInterrupt:
    print('Keyboard Interrupt')
    dc_motor.stop()