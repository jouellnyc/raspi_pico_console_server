import board
import busio
import digitalio
import time
import adafruit_framebuf as framebuf

# I2C setup
i2c = busio.I2C(board.GP5, board.GP4)

# SH1106 is 128x64
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
        temp[0] = 0x00  # Command mode
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

# Create display
oled = SH1106(i2c)

# Configure UART
uart = busio.UART(board.GP0, board.GP1, baudrate=115200, timeout=0)

# Configure LED
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led_state = False

print("Raspberry Pi Console Monitor Started")
print("Waiting for data from Raspberry Pi...")
print("-" * 40)

buffer = ""
last_blink = time.monotonic()

# Display buffer - 8 lines for 64 pixel height
display_lines = []
MAX_LINES = 8
MAX_CHARS_PER_LINE = 21

def wrap_text(text, width):
    """Wrap text to specified width"""
    words = text.split(' ')
    lines = []
    current_line = ""
    
    for word in words:
        if len(word) > width:
            if current_line:
                lines.append(current_line)
                current_line = ""
            while len(word) > width:
                lines.append(word[:width])
                word = word[width:]
            current_line = word
        elif len(current_line) + len(word) + 1 > width:
            if current_line:
                lines.append(current_line)
            current_line = word
        else:
            if current_line:
                current_line += " " + word
            else:
                current_line = word
    
    if current_line:
        lines.append(current_line)
    
    return lines if lines else [""]

def update_display():
    """Update OLED with current display lines"""
    oled.fill(0)
    for i, line in enumerate(display_lines[-MAX_LINES:]):
        oled.text(line, 0, i * 8, 1)
    oled.show()

# Show startup message
display_lines.append("Monitor Ready")
display_lines.append("Baud: 115200")
update_display()

while True:
    if uart.in_waiting > 0:
        # Blink LED
        now = time.monotonic()
        if now - last_blink > 0.1:
            led_state = not led_state
            led.value = led_state
            last_blink = now
        
        # Read data
        data = uart.read(uart.in_waiting)
        
        if data:
            # Decode as text
            text = ""
            for byte in data:
                if 32 <= byte <= 126 or byte in (10, 13):
                    text += chr(byte)
            
            if text:
                print(text, end='')
                
                buffer += text
                
                # Process lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.replace('\r', '').strip()
                    
                    if line:
                        # Wrap long lines
                        wrapped_lines = wrap_text(line, MAX_CHARS_PER_LINE)
                        
                        for wrapped_line in wrapped_lines:
                            display_lines.append(wrapped_line)
                        
                        # Keep buffer manageable
                        while len(display_lines) > 100:
                            display_lines.pop(0)
                        
                        update_display()
    
    time.sleep(0.01)