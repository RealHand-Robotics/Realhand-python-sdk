# Windows & RS485 Setup Guide

## For Windows (L6, L20 supported)

### PCAN (Regular CAN) Driver Install Guide for Windows

1. **Download the PEAK driver package**
   Open: `https://www.peak-system.com/quick/DL-Driver-E`

2. **Extract and run the installer**
   Unzip: `PEAK-System_Driver-Setup.zip`
   Run: `PeakOemDrv.exe`
   Follow the prompts (installs the device driver and PCAN-Basic DLLs)

3. **Plug in the adapter**
   Connect the PCAN USB adapter after installation.
   Windows should detect it and finish driver setup.
   Device Manager should show **PCAN-USB** (not Unknown Device).

4. **Verify (optional)**
   Open PCAN-View (if installed).
   Confirm the channel appears (e.g., `PCAN_USBBUS1`).

If it still shows "Unknown Device":
- Re-run the installer and ensure PCAN-Basic is selected.
- Try a different USB port and reboot if prompted.

Python example (python-can):
```python
import can
bus = can.interface.Bus(interface="pcan", channel="PCAN_USBBUS1", bitrate=1000000)
```

---

### Windows GUI Run

After installing dependencies and the CAN adapter driver:

1. Open a Command Prompt or PowerShell in the extracted project folder.
2. Open `RealHand/config/setting.yaml`.
3. Change `CAN: "can0"` to `CAN: "PCAN_USBBUS1"` for the left or right hand you are using.
4. Run:
```bash
python3 example/gui_control/gui_control.py
```

---

## RS485 Protocol Switching

> Currently supports O6 / L6 / L10. For other models, please refer to the MODBUS RS485 protocol document.

### Overview

Edit `RealHand/config/setting.yaml` and set the `MODBUS` field to the RS485 device port.
On Ubuntu, the USB-RS485 converter usually appears as `/dev/ttyUSB*` or `/dev/ttyACM*`.

Example setting:
```yaml
MODBUS: "/dev/ttyUSB0"   # set to your device port; use "None" to disable RS485
CAN: "can0"              # CAN config is ignored when MODBUS is not "None"
```

### Install RS485 Dependencies

```bash
# If requirements.txt is already installed, these may already be present.
# Install system-level RS485/Modbus drivers:
pip install minimalmodbus --break-system-packages
pip install pyserial --break-system-packages
pip install pymodbus --break-system-packages
```

### Grant Port Permission (Ubuntu)

```bash
# View available USB ports
ls /dev

# You should see a port similar to ttyUSB0. Grant permissions:
sudo chmod 777 /dev/ttyUSB0
```

### Run GUI with RS485

```bash
python3 example/gui_control/gui_control.py
```

### RS485 on Windows

On Windows, the USB-RS485 converter typically appears as `COM3`, `COM4`, etc.
Set the port accordingly in `setting.yaml`:
```yaml
MODBUS: "COM3"
```
No additional permission step is needed on Windows; ensure the correct COM port driver is installed.
