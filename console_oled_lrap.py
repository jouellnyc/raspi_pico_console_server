import board
import busio
import digitalio
import time
import adafruit_ssd1306

# Configure I2C for OLED (GPIO 4 = SDA, GPIO 5 = SCL)
i2c = busio.I2C(board.GP5, board.GP4)  # SCL, SDA
oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)

# Clear display
oled.fill(0)
oled.show()

# Configure UART with correct baudrate
uart = busio.UART(board.GP0, board.GP1, baudrate=115200, timeout=0)

# Configure onboard LED
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led_state = False

print("Raspberry Pi Console Monitor Started")
print("Waiting for data from Raspberry Pi...")
print("-" * 40)

buffer = ""
last_blink = time.monotonic()

# Display buffer - stores last 8 lines (64 pixels / 8 pixels per line)
display_lines = []
MAX_LINES = 8
MAX_CHARS_PER_LINE = 21  # Characters that fit in 128 pixels

def wrap_text(text, width):
    """Wrap text to specified width, returning list of lines"""
    words = text.split(' ')
    lines = []
    current_line = ""
    
    for word in words:
        # If word itself is too long, split it
        if len(word) > width:
            if current_line:
                lines.append(current_line)
                current_line = ""
            # Split long word across lines
            while len(word) > width:
                lines.append(word[:width])
                word = word[width:]
            current_line = word
        # If adding word would exceed width, start new line
        elif len(current_line) + len(word) + 1 > width:
            if current_line:
                lines.append(current_line)
            current_line = word
        # Add word to current line
        else:
            if current_line:
                current_line += " " + word
            else:
                current_line = word
    
    # Add remaining text
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
        
        # Read available data
        data = uart.read(uart.in_waiting)
        
        if data:
            # Decode as text
            text = ""
            for byte in data:
                if 32 <= byte <= 126 or byte in (10, 13):  # Printable + newline/CR
                    text += chr(byte)
            
            if text:
                # Print to console
                print(text, end='')
                
                # Add to buffer
                buffer += text
                
                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.replace('\r', '').strip()  # Remove CR and whitespace
                    
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