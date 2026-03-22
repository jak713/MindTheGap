from machine import Pin
btn = Pin(11, Pin.IN, Pin.PULL_DOWN)
btn2 = Pin(10, Pin.IN, Pin.PULL_DOWN)
while True:
    print(btn.value())
    print(btn2.value())
    import utime
    utime.sleep_ms(200)