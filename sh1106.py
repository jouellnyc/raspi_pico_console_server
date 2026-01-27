#Attribution : Claude.ai
import adafruit_framebuf as framebuf

WIDTH = 128
HEIGHT = 64

class SH1106:
    def __init__(self, i2c, addr=0x3C):
        self.i2c = i2c
        self.addr = addr
        self.buffer = bytearray(WIDTH * HEIGHT // 8)
        self.framebuf = framebuf.FrameBuffer(self.buffer, WIDTH, HEIGHT, framebuf.MVLSB)
        self._init_display()
    
    def _write_cmd(self, cmd):
        temp = bytearray(2)
        temp[0] = 0x00
        temp[1] = cmd
        while not self.i2c.try_lock():
            pass
        try:
            self.i2c.writeto(self.addr, temp)
        finally:
            self.i2c.unlock()
    
    def _init_display(self):
        for cmd in [0xAE, 0xD5, 0x80, 0xA8, 0x3F, 0xD3, 0x00, 0x40,
                    0x8D, 0x14, 0x20, 0x00, 0xA1, 0xC8, 0xDA, 0x12,
                    0x81, 0xCF, 0xD9, 0xF1, 0xDB, 0x40, 0xA4, 0xA6, 0xAF]:
            self._write_cmd(cmd)
    
    def show(self):
        while not self.i2c.try_lock():
            pass
        try:
            for page in range(8):
                self.i2c.writeto(self.addr, bytearray([0x00, 0xB0 + page]))
                self.i2c.writeto(self.addr, bytearray([0x00, 0x02]))
                self.i2c.writeto(self.addr, bytearray([0x00, 0x10]))
                
                data = bytearray(WIDTH + 1)
                data[0] = 0x40
                data[1:] = self.buffer[page * WIDTH:(page + 1) * WIDTH]
                self.i2c.writeto(self.addr, data)
        finally:
            self.i2c.unlock()
    
    def fill(self, color):
        self.framebuf.fill(color)
    
    def text(self, string, x, y, color=1):
        self.framebuf.text(string, x, y, color)