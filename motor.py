"""
Simple motor script.
"""
from machine import Pin, PWM
from time import sleep
# from dcmotor import DCMotor

class DCMotor:
    def __init__(self, pin1, pin2, enable_pin, min_duty=15000, max_duty=65535):
        self.pin1 = pin1
        self.pin2 = pin2
        self.enable_pin = enable_pin
        self.min_duty = min_duty
        self.max_duty = max_duty

    def forward(self, speed):
        self.speed = speed
        self.enable_pin.duty_u16(self.duty_cycle(self.speed))
        self.pin1.value(1)
        self.pin2.value(0)

    def backwards(self, speed):
        self.speed = speed
        self.enable_pin.duty_u16(self.duty_cycle(self.speed))
        self.pin1.value(0)
        self.pin2.value(1)

    def stop(self):
        self.enable_pin.duty_u16(0)
        self.pin1.value(0)
        self.pin2.value(0)

    def duty_cycle(self, speed):
        if speed <= 0 or speed > 100:
            duty_cycle = 0
        else:
            duty_cycle = int(self.min_duty + (self.max_duty - self.min_duty) * (speed / 100))
        return duty_cycle

frequency = 1000 # Hz

Pin1 = Pin(3, Pin.OUT)
Pin2 = Pin(4, Pin.OUT)
enable1 = PWM(Pin(2), freq=frequency)

Pin3 = Pin(14, Pin.OUT)
Pin4 = Pin(13, Pin.OUT)
enable2 = PWM(Pin(15), freq=frequency)

dc_motor = DCMotor(Pin1, Pin2, enable1)
dc_motor2 = DCMotor(Pin3, Pin4, enable2
                    )
try:
    print('Forward with speed: 50%')
    dc_motor.forward(50)
    dc_motor2.forward(50)
    sleep(5)
    dc_motor.stop()
    dc_motor2.stop()
    sleep(5)
    print('Backwards with speed: 100%')
    dc_motor.backwards(100)
    dc_motor2.backwards(100)
    sleep(5)
    print('Forward with speed: 5%')
    dc_motor.forward(5)
    dc_motor2.forward(5)
    sleep(5)
    dc_motor.stop()
    dc_motor2.stop()

    
except KeyboardInterrupt:
    print('Keyboard Interrupt')
    dc_motor.stop()