# L30 CANFD Control Guide

## Overview

The L30 is a 17-DOF (degree-of-freedom) dexterous hand that communicates over **CANFD** (CAN with Flexible Data-rate).
Unlike L6/L10/L20/G20 models that use standard socketcan, the L30 uses a vendor-supplied C library (`libcanbus.so` / `hcanbus.dll`) accessed via Python `ctypes`.

**Key differences from other models:**

| Item | L6 / L10 / L20 / G20 | L30 |
|------|----------------------|-----|
| Protocol | CAN 2.0 | **CANFD** |
| Linux interface | socketcan (`can0`) | `libcanbus.so` (vendor) |
| Windows interface | python-can + PCAN | `hcanbus.dll` (vendor) |
| `ip link set can0 ...` needed | Yes | **No** |
| `CAN:` field in setting.yaml | Used | Ignored |

---

## Hardware Requirements

- L30 dexterous hand (left or right)
- Vendor-supplied **USB-CANFD adapter** (bundled with the hardware)
- The vendor C libraries:
  - **Linux:** `libcanbus.so` + `libusb-1.0.so`
  - **Windows:** `hcanbus.dll`

---

## Installation

### Step 1 — Install Python dependencies

```bash
pip3 install -r requirements.txt
```

### Step 2 — Place the vendor CANFD libraries

Copy the vendor-supplied library files into:

```
RealHand/third_party/canfd/
├── libcanbus.so        # Linux only
└── libusb-1.0.so       # Linux only
```

On Windows, place `hcanbus.dll` in the same folder (or in the system PATH).

> If the libraries are missing, both the GUI and the example scripts will raise an error at startup.

### Step 3 — Connect the hardware

1. Connect the USB-CANFD adapter to the PC.
2. Connect the L30 hand to the adapter via the CANFD cable.
3. Power on the hand.

No `can0` interface setup is needed on Linux.

---

## Configure setting.yaml

Open `RealHand/config/setting.yaml` and set the hand model to `L30`:

```yaml
EXISTS: True
TOUCH: False          # L30 CANFD touch not yet supported via this SDK
CAN: "can0"           # Ignored for L30 — CANFD uses its own driver
MODBUS: "None"        # Not applicable for L30
JOINT: L30
NAME:
```

For the right hand, set `JOINT: L30` under the `RIGHT_HAND` section; for the left hand, set it under `LEFT_HAND`.

---

## Joint Definitions

The L30 has **17 joints**. Position commands use an array of 17 values (index 0–16).

| Index | Motor ID | Finger | Joint |
|-------|----------|--------|-------|
| 0 | 1 | Thumb | MCP Bend (指根弯曲) |
| 1 | 2 | Thumb | IP Bend (指尖弯曲) |
| 2 | 3 | Thumb | ABD/ADD (侧摆) |
| 3 | 4 | Thumb | CMC Rotation (旋转) |
| 4 | 5 | Ring | ABD/ADD (侧摆) |
| 5 | 6 | Ring | IP Bend (指尖弯曲) |
| 6 | 7 | Ring | MCP Bend (指根弯曲) |
| 7 | 8 | Middle | MCP Bend (指根弯曲) |
| 8 | 9 | Middle | IP Bend (指尖弯曲) |
| 9 | 10 | Pinky | MCP Bend (指根弯曲) |
| 10 | 11 | Pinky | IP Bend (指尖弯曲) |
| 11 | 12 | Pinky | ABD/ADD (侧摆) |
| 12 | 13 | Middle | ABD/ADD (侧摆) |
| 13 | 14 | Index | ABD/ADD (侧摆) |
| 14 | 15 | Index | MCP Bend (指根弯曲) |
| 15 | 16 | Index | IP Bend (指尖弯曲) |
| 16 | 17 | Wrist | Pitch (俯仰) |

**Value range:** `0–255` (normalized). `0` = fully flexed / minimum, `255` = fully extended / maximum.
The SDK maps these to the raw protocol range automatically.

**Position unit (raw):** `0.087 °/LSB`
**Velocity unit (raw):** `0.732 RPM/LSB`

---

## API Usage

The L30 uses the same high-level `RealHandApi` as all other models. Do **not** pass a `can` argument — it is ignored.

```python
from RealHand.real_hand_api import RealHandApi

hand = RealHandApi(hand_joint="L30", hand_type="right")   # or "left"
```

### Set joint positions

```python
# All joints open (255 = extended)
hand.finger_move([255] * 17)

# All joints closed (fist)
hand.finger_move([0] * 17)

# Custom pose — only move index finger (indices 13-15), rest open
pose = [255] * 17
pose[13] = 255   # index ABD neutral
pose[14] = 50    # index MCP slightly bent
pose[15] = 50    # index IP slightly bent
hand.finger_move(pose)
```

### Set speed

Speed values are `0–255` (mapped to `0–1000` internally):

```python
hand.set_speed([150] * 17)   # moderate speed for all joints
```

### Set torque

Torque values are `0–255` (mapped to `0–1000` internally):

```python
hand.set_torque([200] * 17)  # moderate torque limit for all joints
```

### Read joint positions

```python
positions = hand.get_state()  # list of 17 raw int16 values
# Convert to degrees: angle_deg = raw_value * 0.087
```

### Read error status

```python
errors = hand.get_fault()  # list of 17 error codes; 0 = no error
if errors:
    for i, code in enumerate(errors):
        if code != 0:
            print(f"Motor {i+1} error: {code}")
```

---

## Running the Examples

All examples are in `example/L30/`. Run from the project root or directly:

### Open / Close gesture

```bash
python3 example/L30/gesture/open_close.py --hand_type right
python3 example/L30/gesture/open_close.py --hand_type left --repeat 5 --interval 1.5
```

Repeatedly opens and closes the hand.

### Preset gesture sequence

```bash
python3 example/L30/gesture/preset_actions.py --hand_type right
python3 example/L30/gesture/preset_actions.py --hand_type right --interval 2.5
```

Runs through: Open → Fist → Point → Thumbs Up → OK.

### Read joint state

```bash
python3 example/L30/get_status/get_state.py --hand_type right
python3 example/L30/get_status/get_state.py --hand_type right --loop 0 --interval 0.5
```

Prints a table of all 17 joint positions (raw + degrees) and error codes.
`--loop 0` runs continuously until `Ctrl+C`.

---

## GUI Control

The GUI (`example/gui_control/gui_control.py`) also supports L30.
Set `JOINT: L30` in `setting.yaml`, then run:

```bash
python3 example/gui_control/gui_control.py
```

The GUI validates that `libcanbus.so` / `libusb-1.0.so` are present at startup and shows an error if they are missing.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `OSError: ... libcanbus.so` | Vendor lib missing | Copy libs to `RealHand/third_party/canfd/` |
| `RuntimeError: L30 CANFD connect failed` | USB-CANFD adapter not found or not plugged in | Check USB connection; verify adapter LED |
| `❌ 未找到CANFD设备` | Driver not installed or adapter not recognized | Install vendor USB driver; try a different USB port |
| All joints read `0` | Hand powered off or cable disconnected | Check power and cable; retry after reconnecting |
| Motor error code `!= 0` | Joint over-current / stall / limit exceeded | Move joint back to safe range; power-cycle the hand |
