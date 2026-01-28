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

print("Raspberry Pi Status Monitor Started")
print("Waiting for data from Raspberry Pi...")
print("-" * 40)

buffer = ""
last_blink = time.monotonic()
last_display_update = time.monotonic()
last_data_received = time.monotonic()
script_start_time = time.monotonic()
last_boot_line_time = time.monotonic()

# Display settings
display_lines = []
status_lines = []
boot_lines = []  # Store boot messages
pending_boot_lines = []  # Boot lines waiting to be displayed
MAX_LINES = 8
MAX_CHARS_PER_LINE = 21
DISPLAY_UPDATE_INTERVAL = 0.5
BOOT_TIMEOUT = 5.0  # If no data for 5 seconds, try to login
BOOT_LOG_SCROLL_DELAY = 0.3  # Seconds between displaying each boot line (configurable!)
POST_BOOT_DELAY = 30.0  # Wait 30 seconds after last boot log before starting login
display_needs_update = False
last_boot_line_display = time.monotonic()

# Auto-login settings
LOGIN_USERNAME = "pi"
LOGIN_PASSWORD = "Fifty1$Fifty"
UPDATE_INTERVAL = 300  # 5 minutes in seconds

# Formatted status commands
COMMANDS = [
    "echo \"Date: $(date '+%m/%d %H:%M')\"",
    "echo \"Host: $(hostname)\"",
    "echo \"Up: $(uptime -p | sed 's/up //')\"",
    "echo \"Load: $(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}')\"",
    "echo \"Temp: $(vcgencmd measure_temp | cut -d= -f2)\"",
    "echo \"Mem: $(free -h | awk 'NR==2{print $3\"/\"$2}')\"",
    "echo \"Disk: $(df -h / | awk 'NR==2{print $5\" used\"}')\"",
]

login_state = "waiting_for_data"  # Start by waiting for any data
prompt_detected_time = 0
next_cycle_time = time.monotonic()
command_index = 0
cycle_count = 0
command_sent_time = 0
waiting_for_output = False
data_received_ever = False

def update_display():
    """Update OLED with current display lines"""
    oled.fill(0)
    for i, line in enumerate(display_lines[-MAX_LINES:]):
        oled.text(line, 0, i * 8, 1)
    oled.show()

def send_command(cmd):
    """Send command via UART"""
    global command_sent_time, waiting_for_output
    uart.write((cmd + "\r\n").encode('utf-8'))
    command_sent_time = time.monotonic()
    waiting_for_output = True
    print(f"[Sent: {cmd}]")

def trigger_prompt():
    """Send newlines to get a fresh prompt"""
    print("\n[Triggering prompt...]")
    for _ in range(3):
        uart.write(b"\r\n")
        time.sleep(0.2)

def wrap_text(text, max_width):
    """Wrap text to fit within max_width characters, breaking at word boundaries"""
    if len(text) <= max_width:
        return [text]
    
    lines = []
    current_line = ""
    words = text.split()
    
    for word in words:
        # If adding this word would exceed max_width
        if len(current_line) + len(word) + 1 > max_width:
            if current_line:
                lines.append(current_line)
                current_line = word
            else:
                # Word itself is too long, break it
                while len(word) > max_width:
                    lines.append(word[:max_width])
                    word = word[max_width:]
                current_line = word
        else:
            if current_line:
                current_line += " " + word
            else:
                current_line = word
    
    if current_line:
        lines.append(current_line)
    
    return lines

def clean_line(line):
    """Remove ANSI escape sequences from line"""
    # Remove common ANSI sequences
    while '[?' in line and ('h' in line or 'l' in line):
        start = line.find('[?')
        if start == -1:
            break
        # Find the end (h or l)
        end = -1
        for i in range(start + 2, min(start + 20, len(line))):
            if line[i] in ['h', 'l']:
                end = i + 1
                break
        if end == -1:
            break
        line = line[:start] + line[end:]
    
    return line.strip()

def is_status_line(line):
    """Check if line starts with one of our status prefixes"""
    prefixes = ["Date:", "Host:", "Up:", "Load:", "Temp:", "Mem:", "Disk:"]
    for prefix in prefixes:
        if line.startswith(prefix):
            return True
    return False

def is_boot_indicator(line):
    """Check if this line indicates a reboot is happening"""
    boot_keywords = [
        "Booting Linux",
        "Starting kernel",
        "Linux version",
        "BOOT_IMAGE",
        "Raspberry Pi",
        "systemd[1]",
        "debian",
        "raspbian"
    ]
    line_lower = line.lower()
    for keyword in boot_keywords:
        if keyword.lower() in line_lower:
            return True
    return False

def should_show_boot_line(line):
    """Check if a boot line should be shown on display"""
    # Skip empty lines
    if not line or len(line) < 2:
        return False
    # Skip lines that are just brackets or ANSI codes
    if line.startswith('[') and len(line) < 5:
        return False
    # Skip lines with only special characters
    if all(c in '[]?0-9hl ' for c in line):
        return False
    return True

# Show startup message
display_lines.append("Status Monitor")
display_lines.append("Waiting for Pi...")
display_lines.append(f"Scroll: {BOOT_LOG_SCROLL_DELAY}s")
update_display()

while True:
    now = time.monotonic()
    
    # Display pending boot lines slowly (one at a time with delay)
    if pending_boot_lines and login_state == "waiting_for_data":
        if now - last_boot_line_display >= BOOT_LOG_SCROLL_DELAY:
            # Add one line from pending to display
            line = pending_boot_lines.pop(0)
            boot_lines.append(line)
            
            # Keep only recent boot lines
            if len(boot_lines) > 50:
                boot_lines.pop(0)
            
            # Update display
            display_lines = ["=== Boot Log ==="] + boot_lines
            display_needs_update = True
            last_boot_line_display = now
    
    # If waiting for data and no data received after BOOT_TIMEOUT, proactively try to login
    if login_state == "waiting_for_data":
        if not data_received_ever and (now - script_start_time >= BOOT_TIMEOUT):
            print(f"\n[No boot data after {BOOT_TIMEOUT}s - attempting login]")
            login_state = "need_prompt"
            trigger_prompt()
        # If boot logs finished (no pending lines and no new data), wait POST_BOOT_DELAY
        elif data_received_ever and not pending_boot_lines and (now - last_boot_line_time >= POST_BOOT_DELAY):
            print(f"\n[Boot complete - waiting {POST_BOOT_DELAY}s before login]")
            print(f"[{POST_BOOT_DELAY}s elapsed since last boot log - attempting login]")
            login_state = "need_prompt"
            trigger_prompt()
    
    # Check if it's time to start a new cycle (only when in cycle_complete state)
    if now >= next_cycle_time and login_state == "cycle_complete":
        cycle_count += 1
        print("\n" + "=" * 40)
        print(f"STARTING CYCLE #{cycle_count}")
        print("=" * 40)
        
        login_state = "need_prompt"
        command_index = 0
        buffer = ""
        status_lines = []
        
        trigger_prompt()
        next_cycle_time = now + UPDATE_INTERVAL
    
    # Read UART data
    if uart.in_waiting > 0:
        if now - last_blink > 0.1:
            led_state = not led_state
            led.value = led_state
            last_blink = now
        
        data = uart.read(uart.in_waiting)
        last_data_received = now
        
        if data:
            data_received_ever = True  # Mark that we've received data
            
            # Decode as text
            text = ""
            for byte in data:
                if 32 <= byte <= 126 or byte in (10, 13):
                    text += chr(byte)
            
            if text:
                print(text, end='')
                buffer += text
                
                # Check for login prompt or shell prompt
                if login_state in ["waiting_for_data", "need_prompt"]:
                    # Check for shell prompt (already logged in)
                    if ("$" in buffer or "#" in buffer) and "@" in buffer:
                        prompt_detected_time = now
                        login_state = "prompt_detected"
                        print("\n[Shell prompt detected - already logged in]")
                        boot_lines = []  # Clear boot messages
                        pending_boot_lines = []  # Clear pending lines
                    # Check for login prompt
                    elif "login:" in buffer.lower():
                        prompt_detected_time = now
                        login_state = "login_prompt_detected"
                        print("\n[Login prompt detected]")
                        boot_lines = []  # Clear boot messages
                        pending_boot_lines = []  # Clear pending lines
                
                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.replace('\r', '').strip()
                    
                    # Check if this is a boot indicator - switch to boot mode if detected
                    if line and is_boot_indicator(line):
                        if login_state != "waiting_for_data":
                            print(f"\n!!! REBOOT DETECTED - switching to boot log mode")
                            login_state = "waiting_for_data"
                            boot_lines = []
                            pending_boot_lines = []
                            status_lines = []
                            cycle_count = 0  # Reset cycle counter
                            last_boot_line_time = now
                    
                    # Collect boot messages while waiting for login (don't display immediately)
                    if line and login_state == "waiting_for_data":
                        cleaned = clean_line(line)
                        if should_show_boot_line(cleaned):
                            # Wrap the line if it's too long
                            wrapped_lines = wrap_text(cleaned, MAX_CHARS_PER_LINE)
                            
                            # Add to pending lines (will be displayed slowly)
                            for wrapped in wrapped_lines:
                                pending_boot_lines.append(wrapped)
                            
                            # Update last boot line time
                            last_boot_line_time = now
                    
                    # Capture status lines during command sending
                    elif line and login_state == "sending_commands":
                        cleaned = clean_line(line)
                        
                        if is_status_line(cleaned):
                            # Truncate if needed (status lines don't wrap)
                            if len(cleaned) > MAX_CHARS_PER_LINE:
                                cleaned = cleaned[:MAX_CHARS_PER_LINE]
                            
                            print(f"\n!!! CAPTURED: {cleaned}")
                            
                            # Check if we already have this type
                            prefix = cleaned.split(':')[0] + ':'
                            already_have = False
                            for existing in status_lines:
                                if existing.startswith(prefix):
                                    already_have = True
                                    break
                            
                            if not already_have:
                                status_lines.append(cleaned)
                                waiting_for_output = False
                                
                                # Update display
                                display_lines = ["=== Pi Status ==="] + status_lines
                                display_needs_update = True
    
    # State machine
    if login_state == "login_prompt_detected":
        if now - prompt_detected_time >= 1.0:
            send_command(LOGIN_USERNAME)
            login_state = "username_sent"
            waiting_for_output = False
            time.sleep(0.5)
    
    elif login_state == "username_sent":
        send_command(LOGIN_PASSWORD)
        login_state = "password_sent"
        waiting_for_output = False
        time.sleep(2)
    
    elif login_state == "password_sent":
        if "$" in buffer or "#" in buffer:
            login_state = "prompt_detected"
            print("\n[Logged in successfully]")
            buffer = ""
    
    elif login_state == "prompt_detected":
        if now - prompt_detected_time >= 1.0:
            # First login - start first cycle immediately
            if cycle_count == 0:
                cycle_count = 1
                print(f"\n[Starting initial cycle #{cycle_count}]")
                next_cycle_time = now + UPDATE_INTERVAL
            
            login_state = "sending_commands"
            command_index = 0
            buffer = ""
            status_lines = []
            display_lines = ["=== Pi Status ==="]
            display_needs_update = True
            print("\n[Sending commands]")
    
    elif login_state == "sending_commands":
        # Only send next command if not waiting
        if not waiting_for_output:
            if command_index < len(COMMANDS):
                send_command(COMMANDS[command_index])
                command_index += 1
            else:
                # All commands sent
                print(f"\n[Cycle #{cycle_count} complete]")
                print(f"Captured {len(status_lines)} status lines:")
                for sl in status_lines:
                    print(f"  {sl}")
                print(f"[Next update in {UPDATE_INTERVAL} seconds]")
                login_state = "cycle_complete"
        
        # Timeout after 3 seconds
        elif waiting_for_output and (now - command_sent_time > 3.0):
            print("\n[Timeout - moving on]")
            waiting_for_output = False
    
    # Update display
    if display_needs_update and (now - last_display_update >= DISPLAY_UPDATE_INTERVAL):
        update_display()
        display_needs_update = False
        last_display_update = now
    
    time.sleep(0.01)