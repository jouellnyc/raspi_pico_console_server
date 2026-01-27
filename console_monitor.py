import board
import busio
import digitalio
import time
from sh1106 import SH1106

# I2C setup
i2c = busio.I2C(board.GP5, board.GP4)
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
last_display_update = time.monotonic()

# Display settings
display_lines = []
MAX_LINES = 8
MAX_CHARS_PER_LINE = 21
DISPLAY_UPDATE_INTERVAL = 0.5  # Update display every 0.5 seconds (adjustable)
display_needs_update = False

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
    # Always read UART data immediately to prevent buffer overflow
    if uart.in_waiting > 0:
        # Blink LED
        now = time.monotonic()
        if now - last_blink > 0.1:
            led_state = not led_state
            led.value = led_state
            last_blink = now
        
        # Read data immediately
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
                
                # Process lines but don't update display yet
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.replace('\r', '').strip()
                    
                    if line:
                        wrapped_lines = wrap_text(line, MAX_CHARS_PER_LINE)
                        
                        for wrapped_line in wrapped_lines:
                            display_lines.append(wrapped_line)
                        
                        while len(display_lines) > 100:
                            display_lines.pop(0)
                        
                        display_needs_update = True
    
    # Only update display at the specified interval
    now = time.monotonic()
    if display_needs_update and (now - last_display_update >= DISPLAY_UPDATE_INTERVAL):
        update_display()
        display_needs_update = False
        last_display_update = now
    
    time.sleep(0.01)