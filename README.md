# Raspberry Pi to Pico UART Console Monitor with OLED Display

Monitor Raspberry Pi boot messages and system logs on a 1.3" OLED display connected to a Raspberry Pi Pico.

## Hardware Requirements

- Raspberry Pi
- Raspberry Pi Pico (with CircuitPython installed)
- 1.3" OLED Display (128x64, I2C, SH1106 or SSD1306)
- USB to Serial adapter (3.3V logic)
- Jumper wires

## Wiring

### OLED to Pico
```
VCC → 3.3V (Pin 36)
GND → GND (Pin 38)
SCL → GP5 (Pin 7)
SDA → GP4 (Pin 6)
```

### USB-Serial to Pico
```
TX  → GP1 (Pin 2)
GND → GND (Pin 38)
```

Plug USB-serial adapter into Raspberry Pi USB port.

## Pico Setup

1. Install `adafruit_framebuf` library to `lib` folder
2. Copy `code.py` to CIRCUITPY drive (uses 115200 baud)

## Raspberry Pi Setup

1. Find your serial device:
   ```bash
   ls -l /dev/ttyUSB*
   ```

2. Edit kernel command line to add console output:
   ```bash
   sudo nano /boot/firmware/cmdline.txt
   ```
   
   Add `console=ttyUSB0,115200` at the beginning of the line:
   ```
   console=ttyUSB0,115200 console=tty1 root=PARTUUID=...
   ```

3. Create service file:
   ```bash
   sudo nano /etc/systemd/system/boot-to-serial.service
   ```

   ```ini
   [Unit]
   Description=Forward boot and system messages to serial console
   After=dev-ttyUSB0.device

   [Service]
   Type=simple
   ExecStartPre=/bin/stty -F /dev/ttyUSB0 115200 cs8 -cstopb -parenb
   ExecStart=/bin/sh -c 'dmesg && journalctl -f'
   StandardOutput=file:/dev/ttyUSB0
   StandardError=file:/dev/ttyUSB0
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

4. Enable and start:
   ```bash
   sudo systemctl enable boot-to-serial.service
   sudo systemctl start boot-to-serial.service
   ```

5. Test:
   ```bash
   sudo reboot
   ```

## Usage

Send messages:
```bash
logger "Your message"
echo "Test" > /dev/ttyUSB0
```

Filter messages in service file:
```bash
# Errors only
ExecStart=/bin/sh -c 'dmesg && journalctl -f -p err'
```

## Configuration

Edit `code.py` for display settings:
```python
MAX_LINES = 8              # Lines to display
MAX_CHARS_PER_LINE = 21    # Characters per line
```

Change baud rate (update both files):
```python
# code.py
uart = busio.UART(board.GP0, board.GP1, baudrate=9600, timeout=0)
```
```bash
# cmdline.txt
console=ttyUSB0,9600 ...

# service file
ExecStartPre=/bin/stty -F /dev/ttyUSB0 9600 cs8 -cstopb -parenb
```

## License

MIT License

