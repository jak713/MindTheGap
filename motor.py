"""
Simple motor script.
"""
from machine import Pin, PWM
from time import sleep

PWM_FREQ = 1000
MIN_POWER = 18000
MAX_POWER = 65635
DRIVE_SPEED = 50
BRIDGE_SPEED = 18
CROSS_TIME = 3.5


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

    def brake(self):
        self.enable_pin.duty_u16(MAX_POWER)
        self.pin1.value(1)
        self.pin2.value(1)
        

    def duty_cycle(self, speed):
        if speed <= 0 or speed > 100:
            duty_cycle = 0
        else:
            duty_cycle = int(self.min_duty + (self.max_duty - self.min_duty) * (speed / 100))
        return duty_cycle
    
    def cross_gap_sequence(self):
        print("OPERATIONAL: Entering Bridge Mode")
        for s in range(0, BRIDGE_SPEED + 1, 2):
            dc_motor.forward(s)
            dc_motor2.forward(s)
            sleep(0.05)

            dc_motor.brake()
            dc_motor2.brake()
            print("SUCESS")

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

def main():
        while True:

            cmd = input("Command (w=fwd, s=bwd, x=cross, space=stop): ").lower()

            if cmd == 'w':
                dc_motor.forward(DRIVE_SPEED)
                dc_motor2.forward(DRIVE_SPEED)
            elif cmd == 's':
                dc_motor.backwards(DRIVE_SPEED)
                dc_motor2.backwards(DRIVE_SPEED)
            elif cmd == 'x':
                dc_motor.cross_gap_sequence()
                dc_motor2.cross_gap_sequence()
            elif cmd == '':
                dc_motor.stop()
                dc_motor2.stop()
            else:
                dc_motor.brake()
                dc_motor2.brake()

     
    except KeyboardInterrupt:
        print('Keyboard Interrupt')
        dc_motor.stop()


if __name__ == "__main__":
    main()