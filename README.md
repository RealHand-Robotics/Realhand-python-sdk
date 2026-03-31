# RealHand-Python-SDK

## Overview
RealHand Python SDK

[English](README.md)

## Caution
- Please ensure that the dexterous hand is not running any other control methods, such as real_hand_sdk_ros, motion capture glove control, or other topics    controlling the hand, to avoid conflicts.
- Please secure the dexterous hand to prevent it from falling during movement.
- Please ensure the dexterous hand's power and USB-to-CAN connection are correct.

![SDK Version](https://img.shields.io/badge/SDK%20Version-V3.0.1-brightgreen?style=flat-square)
![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python&logoColor=white)
![Windows 11](https://img.shields.io/badge/OS-Windows%2011-0078D4?style=flat-square&logo=windows&logoColor=white)
![Ubuntu 20.04](https://img.shields.io/badge/OS-Ubuntu%2020.04%2B-E95420?style=flat-square&logo=ubuntu&logoColor=white)
![Ubuntu 22.04](https://img.shields.io/badge/OS-Ubuntu%2022.04%2B-E95420?style=flat-square&logo=ubuntu&logoColor=white)
![Ubuntu 24.04](https://img.shields.io/badge/OS-Ubuntu%2024.04-E95420?style=flat-square&logo=ubuntu&logoColor=white)
![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![ROS Noetic](https://img.shields.io/badge/ROS-Noetic-009624?style=flat-square&logo=ros)
![ROS 2 Jazzy](https://img.shields.io/badge/ROS%202-Jazzy-00B3E6?style=flat-square&logo=ros)

## Related Documentation
- For more detailed information, please refer to the following links.
  
[Real Hand API for Python Document](doc/API-Reference.md)

[SDK Functions Summary](doc/SDK-Functions-Summary.md) 

- For functions under testing
  
  [alpha version](https://github.com/RealHand-Robotics/Realhand-python-sdk/tree/testing)

## Installation
&ensp;&ensp;After downloading and extracting the folder, you can run the examples after installing the dependencies in requirements.txt. Only Python 3 is supported.
- install
(optional)
```bash
$ conda create -n realhand-sdk python==3.11
$ conda activate realhand-sdk
```

```bash
$ pip3 install -r requirements.txt
```
## Run the GUI Example (Ubuntu)

### Step 1 — Set up CAN interface

Connect the USB-to-CAN adapter, then bring up the CAN interface (run once per boot):

```bash
# Bring up can0 at 1 Mbps (adjust interface name if needed, e.g. can1)
sudo ip link set can0 type can bitrate 1000000
sudo ip link set up can0

# Verify the interface is up
ip link show can0
```

### Step 2 — Configure the hand

Open `RealHand/config/setting.yaml` and edit the fields to match your hardware:

```yaml
# ── Left hand ──────────────────────────────────────────────────────
EXISTS: True          # True if the left hand is connected
TOUCH: True           # True if a pressure sensor is installed
CAN: “can0”           # CAN port (e.g. can0, can1). Ignored when MODBUS is set.
MODBUS: “None”        # RS485 port, e.g. “/dev/ttyUSB0”. “None” = use CAN.
JOINT: G20            # Hand model: O6 / L6 / L7 / L10 / L20 / G20 / L21 / L25 / L30
NAME:                 # Internal name — do not modify

# ── Right hand (same fields, prefixed R_) ──────────────────────────
R_EXISTS: False
R_TOUCH: False
R_CAN: “can1”
R_MODBUS: “None”
R_JOINT: G20
R_NAME:
```

Common hand models and their CAN default:

| Model | Joints | Notes |
|-------|--------|-------|
| O6 / L6 | 6 | Compact 6-DOF hand |
| L7 | 7 | L6 + Thumb Rotation |
| L10 | 10 | Full abduction/adduction |
| L20 / G20 | 20 | Industrial / high-DOF hand |
| L21 / L25 / L30 | 21 / 25 / 30 | Extended DOF series |

### Step 3 — Run the GUI

```bash
python3 example/gui_control/gui_control.py
```

A slider-based UI will open. Use the sliders to control each joint in real time, or click preset action buttons (Open, Fist, OK, etc.).

### Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `can0: no such device` | Interface not created | Run `sudo ip link set can0 type can bitrate 1000000 && sudo ip link set up can0` |
| No response from hand | Wrong `JOINT` type or CAN port | Double-check `setting.yaml`; verify `ip link show can0` shows `UP` |
| GUI opens but sliders do nothing | Another CAN controller is running | Stop `real_hand_sdk_ros` or other control nodes first |
| `PermissionError` on CAN socket | Missing permissions | Add your user to the `netdev` group or run with `sudo` (not recommended for production) |

---

## For Windows & RS485 Setup

For Windows (PCAN driver install, Windows GUI run) and RS485 protocol switching, see:

[Windows & RS485 Setup Guide](doc/windows_and_rs485_info.md)





## Update Log

- > ### release_3.0.1
 - 1、Supports O6/L6/L10 RS485 communication in pymodbus mode.

- > ### release_2.2.4
 - 1、Added support for G20 industrial version dexterous hand.
 - 2、Redrew the GUI.


- > ### release_2.1.9
 - 1、Added support for O6 dexterous hand.

- > ### release_2.1.8
 - 1、Fixed occasional frame collision issue.


  
- Position and Finger Joint Correspondence Table

  O6:  ["Thumb Flexion", "Thumb Adduction/Abduction","Index Finger Flexion", "Middle Finger Flexion", "Ring Finger Flexion","Pinky Finger Flexion"]

  L6:  ["Thumb Flexion", "Thumb Adduction/Abduction","Index Finger Flexion", "Middle Finger Flexion", "Ring Finger Flexion","Pinky Finger Flexion"]

  L7:  ["Thumb Flexion", "Thumb Adduction/Abduction","Index Finger Flexion", "Middle Finger Flexion", "Ring Finger Flexion","Pinky Finger Flexion","Thumb Rotation"]

  L10: ["Thumb CMC Pitch", "Thumb Adduction/Abduction","Index Finger MCP Pitch", "Middle Finger MCP Pitch", "Ring Finger MCP Pitch","Pinky Finger MCP Pitch","Index Finger Adduction/Abduction","Ring Finger Adduction/Abduction","Pinky Finger Adduction/Abduction","Thumb Rotation"]

  L20: ["Thumb CMC Pitch", "Index Finger MCP Pitch", "Middle Finger MCP Pitch", "Ring Finger MCP Pitch","Pinky Finger MCP Pitch","Thumb Adduction/Abduction","Index Finger Adduction/Abduction","Middle Finger Adduction/Abduction","Ring Finger Adduction/Abduction","Pinky Finger Adduction/Abduction","Thumb CMC Yaw","Reserved","Reserved","Reserved","Reserved","Thumb Distal Tip","Index Finger Distal Tip","Middle Finger Distal Tip","Ring Finger Distal Tip","Pinky Finger Distal Tip"]

  G20: ["Thumb CMC Pitch", "Index Finger MCP Pitch", "Middle Finger MCP Pitch", "Ring Finger MCP Pitch","Pinky Finger MCP Pitch","Thumb Adduction/Abduction","Index Finger Adduction/Abduction","Middle Finger Adduction/Abduction","Ring Finger Adduction/Abduction","Pinky Finger Adduction/Abduction","Thumb CMC Yaw","Reserved","Reserved","Reserved","Reserved","Thumb Distal Tip","Index Finger Distal Tip","Middle Finger Distal Tip","Ring Finger Distal Tip","Pinky Finger Distal Tip"]

  L21: ["Thumb Base Pitch","Index Base Pitch","Middle Base Pitch","Ring Base Pitch","Pinky Base Pitch","Thumb Adduction/Abduction","Index Adduction/Abduction","Middle Adduction/Abduction","Ring Adduction/Abduction","Pinky Adduction/Abduction","Thumb Roll","Reserved","Reserved","Reserved","Reserved","Thumb Middle","Reserved","Reserved","Reserved","Reserved","Thumb Tip","Index Tip","Middle Tip","Ring Tip","Pinky Tip"]

  L25: ["Thumb Base Pitch", "Index Base Pitch", "Middle Base Pitch","Ring Base Pitch","Pinky Base Pitch","Thumb Adduction/Abduction","Index Adduction/Abduction","Middle Adduction/Abduction","Ring Adduction/Abduction","Pinky Adduction/Abduction","Thumb Roll","Reserved","Reserved","Reserved","Reserved","Thumb Middle","Index Middle","Middle Middle","Ring Middle","Pinky Middle","Thumb Tip","Index Tip","Middle Tip","Ring Tip","Pinky Tip"]

## [L10 Examples](example/L10)

&ensp;&ensp; __Before running, please modify the configuration information in [setting.yaml](RealHand/config/setting.yaml) to match your actual dexterous hand configuration.__

- #### [0000-gui_control](example/gui_control/gui_control.py)
When launched, a UI interface will pop up. You can control the corresponding RealHand dexterous hand joint movements using the sliders.

- **Adding or modifying action examples.** You can add or modify actions in the [constants.py](example/gui_control/config/constants.py) file.
```python
# For example, adding action sequences for L6
"L6": HandConfig(
        joint_names_en=["thumb_cmc_pitch", "thumb_cmc_yaw", "index_mcp_pitch", "middle_mcp_pitch", "pinky_mcp_pitch", "ring_mcp_pitch"],
        joint_names=["Thumb Flexion", "Thumb Abduction", "Index Flexion", "Middle Flexion", "Ring Flexion", "Pinky Flexion"],
        init_pos=[250] * 6,
        preset_actions={
            "Open": [250, 250, 250, 250, 250, 250],
            "One": [0, 31, 255, 0, 0, 0],
            "Two": [0, 31, 255, 255, 0, 0],
            "Three": [0, 30, 255, 255, 255, 0], 
            "Four": [0, 30, 255, 255, 255, 255],
            "Five": [250, 250, 250, 250, 250, 250],
            "OK": [54, 41, 164, 250, 250, 250],
            "Thumbs Up": [255, 31, 0, 0, 0, 0],
            "Fist": [49, 61, 0, 0, 0, 0],
            # Add custom actions......
        }
    )
```



- #### [0001-real_hand_fast](example/L10/gesture/real_hand_fast.py)
- #### [0002-real_hand_finger_bend](example/L10/gesture/real_hand_finger_bend.py)
- #### [0003-real_hand_fist](example/L10/gesture/real_hand_fist.py)
- #### [0004-real_hand_open_palm](example/L10/gesture/real_hand_open_palm.py)
- #### [0005-real_hand_opposition](example/L10/gesture/real_hand_opposition.py)
- #### [0006-real_hand_sway](example/L10/gesture/real_hand_sway.py)

- #### [0007-real_hand_get_force](example/L10/get_status/get_force.py) #python3 get_force.py --hand_joint L10 --hand_type right
- #### [0008-real_hand_get_speed](example/L10/get_status/get_set_speed.py) #python3 get_set_speed.py --hand_joint L10 --hand_type right --speed 100 123 211 121 222   Note: L7 has 7 speed parameters, others have 5.
- #### [0009-real_hand_get_state](example/L10/get_status/get_set_state.py) # python3 get_set_state.py --hand_joint L10 --hand_type right --position 100 123 211 121 222 255 255 255 255 255  The number of position parameters should refer to the "Position and Finger Joint Correspondence Table".

- #### [0010-real_hand_dynamic_grasping](example/L10/grab/dynamic_grasping.py)




## API Documentation
[Real Hand API for Python Document](doc/API-Reference.md)
[SDK Functions Summary](doc/SDK-Functions-Summary.md) - For more detailed information, refer to this file.
