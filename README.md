
# Raspberry Pi to Pico UART Console Monitor with OLED Display

Monitor Raspberry Pi boot messages and system logs on a 1.3" OLED display connected to a Raspberry Pi Pico.

| Video |

<video src="https://github.com/user-attachments/assets/a44af3d0-d2a6-4f2a-87f9-9aa5ab4fc1db" width="75" height="75" controls></video>

| Image |

<img src="https://github.com/user-attachments/assets/1d248a58-322e-4a23-ad29-81f45b68591d" width="175" height="175">


## Hardware Requirements

- Raspberry Pi
- Raspberry Pi Pico (with CircuitPython installed)
- 1.3" OLED Display (128x64, I2C, SH1106)
- USB to Serial adapter (3.3V logic)
- Jumper wires

## Wiring

### OLED to Pico
```
VCC → 3.3V
GND → GND
SCL → GP5
SDA → GP4
```

### Raspberry Pi's USB-Serial to Pico
```
USB-Serial TX → Pico GP1 (RX)
USB-Serial RX → Pico GP0 (TX) [optional - not needed for monitoring]
GND           → GND
```

Plug USB-serial adapter into Raspberry Pi USB port.

## Pico Setup
1. Copy adafruit_framebuf.py and font5x8.bin to /

Gotten from https://github.com/adafruit/Adafruit_CircuitPython_framebuf

2. Copy all files in this repo to  /.

## Raspberry Pi Setup

1. Find your serial device:
   ```bash
   ls -l /dev/ttyUSB*
   ```

2. Edit kernel command line to add console output:
   ```bash
   /boot/firmware/cmdline.txt
   ```
   
   Add `console=ttyUSB0,115200` at the beginning of the line:
   ```
   console=ttyUSB0,115200 console=tty1 root=PARTUUID=...
   ```

   Also in ```/boot/firmware/config.txt``` add enable_uart=1

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
After rebooting, it should 'just work'

Test Sending messages:
```bash
logger "Your message"
echo "Test" > /dev/ttyUSB0
```

Consider to filter messages in service file:
```bash
# Errors only
ExecStart=/bin/sh -c 'dmesg && journalctl -f -p err'
```

## Configuration

Edit the Pico script for display settings (Examples):
```python
MAX_LINES = 8              # Lines to display
MAX_CHARS_PER_LINE = 21    # Characters per line
```

Change baud rate (update both files):
```python
# Pico script
uart = busio.UART(board.GP0, board.GP1, baudrate=9600, timeout=0)
```
```bash
# cmdline.txt
console=ttyUSB0,9600 ...

# service file
ExecStartPre=/bin/stty -F /dev/ttyUSB0 9600 cs8 -cstopb -parenb
```
