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

# Display buffer - stores last 8 lines
display_lines = []
MAX_LINES = 8

def update_display():
    """Update OLED with current display lines"""
    oled.fill(0)
    for i, line in enumerate(display_lines[-MAX_LINES:]):
        # Truncate line to fit display (~21 chars)
        truncated = line[:21]
        oled.text(truncated, 0, i * 8, 1)
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
                        display_lines.append(line)
                        
                        # Keep buffer manageable
                        if len(display_lines) > 50:
                            display_lines.pop(0)
                        
                        update_display()
    
    time.sleep(0.01)