"""
L30 Dexterous Hand CAN-FD Communication Protocol Controller

Protocol version: v1.0.5
CAN-FD configuration:
  - Arbitration baud rate: 1Mbps (80%)
  - Data baud rate: 5Mbps (75%)
  - Frame format: Extended frame
  - Frame type: Data frame
"""

import sys
import os
import time
import threading
import struct
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
from enum import Enum, auto
from collections import defaultdict
from ctypes import *


# ==================== CAN-FD Basic Structure Definitions ====================

class CanFD_Config(Structure):
    """CAN-FD configuration structure"""
    _fields_ = [
        ("NomBaud", c_uint),      # Arbitration baud rate
        ("DatBaud", c_uint),      # Data baud rate
        ("NomPres", c_ushort),   # Arbitration phase prescaler
        ("NomTseg1", c_char),     # Arbitration phase TSEG1
        ("NomTseg2", c_char),     # Arbitration phase TSEG2
        ("NomSJW", c_char),       # Arbitration phase SJW
        ("DatPres", c_char),      # Data phase prescaler
        ("DatTseg1", c_char),     # Data phase TSEG1
        ("DatTseg2", c_char),     # Data phase TSEG2
        ("DatSJW", c_char),       # Data phase SJW
        ("Config", c_char),       # Configuration flag
        ("Model", c_char),        # Mode
        ("Cantype", c_char)       # CAN type
    ]


class CanFD_Msg(Structure):
    """CAN-FD message structure"""
    _fields_ = [
        ("ID", c_uint),          # CAN ID
        ("TimeStamp", c_uint),   # Timestamp
        ("FrameType", c_byte),   # Frame type
        ("DLC", c_byte),         # Data length code
        ("ExternFlag", c_byte),  # Extended frame flag
        ("RemoteFlag", c_byte),  # Remote frame flag
        ("BusSatus", c_byte),   # Bus status
        ("ErrSatus", c_byte),   # Error status
        ("TECounter", c_byte),  # Transmit error counter
        ("RECounter", c_byte),  # Receive error counter
        ("Data", c_ubyte * 64)  # Data (up to 64 bytes)
    ]


# ==================== L30 Protocol Constant Definitions ====================

class L30CanID(Enum):
    """
    L30 dexterous hand CAN ID definitions

    Transmit commands:
      - 0x04: Version query
      - 0x05: Motor calibration
      - 0x06: Position control
      - 0x07: Motor enable
      - 0x08: Sensor query
      - 0x0A: Disable-state check
      - 0x0B: Servo restart

    Receive replies:
      - 0x64: Version query reply
      - 0x65-0x69: Sensor 1-5 replies
    """
    # Transmit commands
    VERSION_QUERY = 0x04      # Version query
    CALIBRATION = 0x05        # Motor calibration
    POSITION_CTRL = 0x06      # Position control
    MOTOR_ENABLE = 0x07      # Motor enable (no reply)
    SENSOR_QUERY = 0x08       # Sensor query
    DISABLE_CHECK = 0x0A     # Disable-state check (3 frames with same ID)
    SERVO_RESTART = 0x0B      # Servo restart

    # Receive replies (different IDs)
    VERSION_REPLY = 0x64      # Version query reply
    SENSOR1_REPLY = 0x65      # Sensor 1 reply (thumb)
    SENSOR2_REPLY = 0x66      # Sensor 2 reply
    SENSOR3_REPLY = 0x67      # Sensor 3 reply
    SENSOR4_REPLY = 0x68      # Sensor 4 reply
    SENSOR5_REPLY = 0x69      # Sensor 5 reply (little finger)


class ReplyPatternType(Enum):
    """Reply pattern type"""
    NONE = 'none'           # No reply (motor enable)
    SINGLE = 'single'       # Single frame, single ID (calibration, position control, servo restart)
    MULTI_ID = 'multi_id'  # Multiple frames, different IDs (version query, sensor query)
    MULTI_FRAME = 'multi_frame'  # Multiple frames, same ID (disable-state check)


@dataclass
class ReplyPattern:
    """Reply pattern definition"""
    reply_type: ReplyPatternType
    expected_ids: List[int]
    expected_frames: int = 1
    timeout: float = 1.0


# Command reply pattern mapping
COMMAND_PATTERNS: Dict[int, ReplyPattern] = {
    L30CanID.VERSION_QUERY.value: ReplyPattern(
        ReplyPatternType.MULTI_ID,
        [L30CanID.VERSION_REPLY.value], 1, 1.0),
    L30CanID.CALIBRATION.value: ReplyPattern(
        ReplyPatternType.SINGLE,
        [L30CanID.CALIBRATION.value], 1, 2.0),
    L30CanID.POSITION_CTRL.value: ReplyPattern(
        ReplyPatternType.SINGLE,
        [L30CanID.POSITION_CTRL.value], 1, 0.5),
    L30CanID.MOTOR_ENABLE.value: ReplyPattern(
        ReplyPatternType.NONE,
        [], 0, 0),
    L30CanID.SENSOR_QUERY.value: ReplyPattern(
        ReplyPatternType.MULTI_ID,
        [
            L30CanID.SENSOR1_REPLY.value,
            L30CanID.SENSOR2_REPLY.value,
            L30CanID.SENSOR3_REPLY.value,
            L30CanID.SENSOR4_REPLY.value,
            L30CanID.SENSOR5_REPLY.value
        ], 5, 1.0),
    L30CanID.DISABLE_CHECK.value: ReplyPattern(
        ReplyPatternType.MULTI_FRAME,
        [L30CanID.DISABLE_CHECK.value], 3, 0.5),
    L30CanID.SERVO_RESTART.value: ReplyPattern(
        ReplyPatternType.SINGLE,
        [L30CanID.SERVO_RESTART.value], 1, 2.0),
}


# ==================== Data Class Definitions ====================

@dataclass
class L30HandInfo:
    """Dexterous hand information"""
    version: str = ""
    is_left_hand: bool = False
    motor_count: int = 17
    
    def __str__(self):
        hand_type = "Left Hand" if self.is_left_hand else "Right Hand"
        return f"L30 Dexterous Hand [{hand_type}] Firmware Version: v{self.version}"


@dataclass
class SensorData:
    """Sensor data"""
    sensor_id: int           # Sensor ID (1-5)
    raw_data: bytes         # Raw data (8 bytes)
    
    @property
    def value(self) -> int:
        """Get the sensor value by summing the 8 bytes as decimal values"""
        return sum(b for b in self.raw_data)
    
    def __str__(self):
        return f"Sensor {self.sensor_id}: " + " ".join(f"{b:02X}" for b in self.raw_data)


@dataclass
class MotorStatus:
    """Motor status"""
    motor_id: int           # Motor ID (1-17)
    is_enabled: bool        # Whether enabled
    position: int = 0       # Current position value


# ==================== L30 Dexterous Hand Controller ====================

class L30HandController:
    """
    L30 dexterous hand controller

    Supports CAN-FD communication protocol v1.0.5:
      1. Position control (0x06): controls the positions of 17 motors
      2. Motor enable (0x07): enables all motors
      3. Motor calibration (0x05): calibrates motor positions
      4. Version query (0x04): queries hand type and firmware version
      5. Sensor query (0x08): queries 5 pressure sensors
      6. Disable-state check (0x0A): queries motor enable states
      7. Servo restart (0x0B): restarts servos

    Features:
      - Supports three reply modes: single frame, multi-frame different IDs, and multi-frame same ID
      - Background receive thread automatically processes CAN messages
      - Thread-safe command send and receive
    """

    # Number of motors
    MOTOR_COUNT = 17

    # Joint names (in motor order)
    JOINT_NAMES = [
        "thumb_root",    # 0: Thumb base
        "thumb_tip",     # 1: Thumb tip
        "thumb_side",    # 2: Thumb lateral swing
        "thumb_rotate",  # 3: Thumb rotation
        "ring_side",     # 4: Ring finger lateral swing
        "ring_tip",      # 5: Ring finger tip
        "ring_root",     # 6: Ring finger base
        "middle_tip",    # 7: Middle finger tip
        "middle_root",   # 8: Middle finger base
        "little_root",   # 9: Little finger base
        "little_tip",    # 10: Little finger tip
        "little_side",   # 11: Little finger lateral swing
        "middle_side",   # 12: Middle finger lateral swing
        "index_side",    # 13: Index finger lateral swing
        "index_root",    # 14: Index finger base
        "index_tip",     # 15: Index finger tip
        "wrist"          # 16: Wrist joint
    ]

    # Motor position command ranges (min, max)
    JOINT_LIMITS_LEFT = [
        (-1500, 0), (-1500, 0), (-750, 0), (-1000, 0),
        (-200, 200), (-1500, 0), (-1500, 0),
        (-1500, 0), (-1500, 0),
        (-1500, 0), (-1500, 0),
        (-200, 200), (-200, 200), (-200, 200),
        (-1500, 0), (-1500, 0),
        (-1000, 500)
    ]
    JOINT_LIMITS_RIGHT = [
        (0, 1500), (0, 1500), (0, 750), (0, 1000),
        (-200, 200), (0, 1500), (0, 1500),
        (0, 1500), (0, 1500),
        (0, 1500), (0, 1500),
        (-200, 200), (-200, 200), (-200, 200),
        (0, 1500), (0, 1500),
        (-500, 1000)
    ]
    
    # Angle ranges (degrees) (min, max)
    ANGLE_LIMITS = [
        (0, 90), (0, 90), (0, 45), (0, 60),
        (-15, 15), (0, 90), (0, 90),
        (0, 90), (0, 90),
        (0, 90), (0, 90),
        (-15, 15), (-15, 15), (-15, 15),
        (0, 90), (0, 90),
        (-30, 60)
    ]
    
    # Mapping from DLC to data length
    DLC_TO_LEN = [0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64]
    
    # Mapping from joint name to ID
    JOINT_NAME_TO_ID = {name: idx for idx, name in enumerate(JOINT_NAMES)}
    
    # Mapping from sensor ID to finger
    SENSOR_TO_FINGER = {
        1: "Thumb",
        2: "Index",
        3: "Middle",
        4: "Ring",
        5: "Little"
    }

    def __init__(self, channel: int = 0):
        """
        Initialize the L30 dexterous hand controller

        Args:
            channel: CAN channel number (default 0)
        """
        self.channel = channel
        self.canDLL = None
        self.is_connected = False
        self.is_enabled = False
        self.hand_info: Optional[L30HandInfo] = None
        self.is_left_hand = self.hand_info.is_left_hand if self.hand_info else False
        # Receive buffers
        self._general_buffer: Dict[int, bytes] = {}
        self._multi_frame_buffer: Dict[int, List[bytes]] = defaultdict(list)
        self._lock = threading.Lock()
        self._recv_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Command waiting state
        self._pending_pattern: Optional[ReplyPattern] = None
        self._pending_cmd_id: Optional[int] = None
        self._command_event = threading.Event()
        self._command_results: Dict[int, List[bytes]] = defaultdict(list)

    def __del__(self):
        """Destructor; automatically disconnect"""
        self.disconnect()

    # ==================== Connection and Disconnection ====================

    def connect(
        self,
        libusb_path: str = "/usr/local/lib/libusb-1.0.so",
        libcanbus_path: str = "/usr/local/lib/libcanbus.so"
    ) -> bool:
        """
        Connect to and initialize the CAN-FD device

        CAN-FD configuration:
          - Arbitration baud rate: 1Mbps (80%)
          - Data baud rate: 5Mbps (75%)

        Args:
            libusb_path: libusb library path
            libcanbus_path: libcanbus library path

        Returns:
            bool: Whether the connection succeeded
        """
        try:
            print("Initializing L30 dexterous hand controller...")
            CDLL(libusb_path, RTLD_GLOBAL)
            time.sleep(0.1)
            self.canDLL = cdll.LoadLibrary(libcanbus_path)
            
            # Scan devices
            ret = self.canDLL.CAN_ScanDevice()
            if ret <= 0:
                print("❌ CAN FD device not found")
                return False
            
            # Open device
            ret = self.canDLL.CAN_OpenDevice(0, self.channel)
            if ret != 0:
                print(f"❌ Failed to open CAN device: {ret}")
                return False
            
            # Configure CAN-FD
            # Arbitration baud rate: 1Mbps, data baud rate: 5Mbps
            can_config = CanFD_Config(
                NomBaud=1000000,   # 1Mbps arbitration baud rate
                DatBaud=5000000,   # 5Mbps data baud rate
                NomPres=0x0,       # Arbitration phase prescaler
                NomTseg1=0x0,      # Arbitration phase TSEG1
                NomTseg2=0x0,      # Arbitration phase TSEG2
                NomSJW=0x0,        # Arbitration phase SJW
                DatPres=0x0,       # Data phase prescaler
                DatTseg1=0x0,      # Data phase TSEG1
                DatTseg2=0x0,      # Data phase TSEG2
                DatSJW=0x0,        # Data phase SJW
                Config=0x0,        # Configuration flag
                Model=0x0,        # Mode
                Cantype=0x1        # CAN type
            )
            
            ret = self.canDLL.CANFD_Init(0, self.channel, byref(can_config))
            if ret != 0:
                print(f"❌ CAN FD initialization failed: {ret}")
                self.canDLL.CAN_CloseDevice(0, self.channel)
                return False
            
            # Set filter (receive all IDs)
            self.canDLL.CAN_SetFilter(self.channel, 0, 0, 0, 0, 1)
            
            self.is_connected = True
            self._start_recv_thread()
            
            # Query version to confirm successful connection
            if not self.query_version():
                print("❌ Version query failed, communication error")
                self.disconnect()
                return False
            
            print(f"✅ L30 dexterous hand connected successfully: {self.hand_info}")
            return True
            
        except Exception as e:
            print(f"❌ Connection error: {e}")
            self.disconnect()
            return False

    def disconnect(self):
        """
        Disconnect the CAN-FD connection

        Note: Disconnecting will not disable the motors. To disable them,
        power off the main control board.
        """
        self._running = False
        if self._recv_thread and self._recv_thread.is_alive():
            self._recv_thread.join(timeout=1.0)
        if self.canDLL and self.is_connected:
            try:
                self.canDLL.CAN_CloseDevice(0, self.channel)
            except Exception:
                pass
        self.is_connected = False
        self.is_enabled = False

    # ==================== Low-Level CAN Communication ====================

    def _get_dlc_from_length(self, length: int) -> int:
        """
        Get the DLC value based on the data length

        Args:
            length: Data length (bytes)

        Returns:
            int: DLC value
        """
        if length <= 8:
            return length
        elif length <= 12:
            return 9
        elif length <= 16:
            return 10
        elif length <= 20:
            return 11
        elif length <= 24:
            return 12
        elif length <= 32:
            return 13
        elif length <= 48:
            return 14
        else:
            return 15

    def send_message(self, can_id: int, data: bytes) -> bool:
        """
        Send a CAN-FD message

        Args:
            can_id: CAN ID
            data: Data bytes

        Returns:
            bool: Whether sending succeeded
        """
        if not self.is_connected:
            return False

        try:
            data_len = min(len(data), 64)
            data_array = (c_ubyte * 64)()
            for i in range(64):
                data_array[i] = 0
            for i, byte_val in enumerate(data[:data_len]):
                data_array[i] = byte_val

            msg = CanFD_Msg(
                ID=can_id,
                TimeStamp=0,
                FrameType=4,        # CAN-FD frame
                DLC=self._get_dlc_from_length(data_len),
                ExternFlag=1,      # Extended frame
                RemoteFlag=0,       # Data frame
                BusSatus=0,
                ErrSatus=0,
                TECounter=0,
                RECounter=0,
                Data=data_array
            )

            ret = self.canDLL.CANFD_Transmit(0, self.channel, byref(msg), 1, 100)
            return ret == 1

        except Exception as e:
            print(f"Send error: {e}")
            return False

    def _start_recv_thread(self):
        """Start the background receive thread"""
        self._running = True
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()

    def _recv_loop(self):
        """Background receive loop"""
        while self._running and self.is_connected:
            try:
                messages = self._receive_batch(timeout_ms=50, max_msgs=20)
                
                for can_id, data in messages:
                    with self._lock:
                        self._process_received_frame(can_id, data)
                
                time.sleep(0.001)
            except Exception as e:
                if self._running:
                    print(f"Receive error: {e}")
                break

    def _process_received_frame(self, can_id: int, data: bytes):
        """
        Process a received frame

        Dispatch it to the correct buffer according to the current expected reply pattern.
        """
        if self._pending_pattern is not None:
            pattern = self._pending_pattern
            
            if can_id in pattern.expected_ids:
                if pattern.reply_type == ReplyPatternType.MULTI_FRAME:
                    # Multiple frames with the same ID (disable-state check)
                    self._command_results[can_id].append(data)
                    if len(self._command_results[can_id]) >= pattern.expected_frames:
                        self._command_event.set()
                
                elif pattern.reply_type == ReplyPatternType.MULTI_ID:
                    # Multiple frames with different IDs (sensor query)
                    self._command_results[can_id] = [data]
                    if all(cid in self._command_results for cid in pattern.expected_ids):
                        self._command_event.set()
                
                elif pattern.reply_type == ReplyPatternType.SINGLE:
                    # Single frame
                    self._command_results[can_id] = [data]
                    self._command_event.set()
            
            # Sensor data is also stored in the general buffer
            if L30CanID.SENSOR1_REPLY.value <= can_id <= L30CanID.SENSOR5_REPLY.value:
                self._general_buffer[can_id] = data
        
        else:
            # When no command is waiting, store it in the general buffer
            self._general_buffer[can_id] = data
            self._multi_frame_buffer[can_id].append(data)

    def _receive_batch(
        self,
        timeout_ms: int,
        max_msgs: int
    ) -> List[Tuple[int, bytes]]:
        """
        Receive CAN-FD messages in batches

        Args:
            timeout_ms: Timeout in milliseconds
            max_msgs: Maximum number of messages to receive

        Returns:
            List[Tuple[can_id, data]]: List of received messages
        """
        if not self.is_connected:
            return []

        try:
            class CanFD_Msg_ARRAY(Structure):
                _fields_ = [('SIZE', c_uint16), ('STRUCT_ARRAY', POINTER(CanFD_Msg))]
                def __init__(self, num):
                    self.STRUCT_ARRAY = cast((CanFD_Msg * num)(), POINTER(CanFD_Msg))
                    self.SIZE = num
                    self.ADDR = self.STRUCT_ARRAY[0]

            buf = CanFD_Msg_ARRAY(max_msgs)
            ret = self.canDLL.CANFD_Receive(
                0, self.channel, byref(buf.ADDR), max_msgs, timeout_ms
            )

            messages = []
            for i in range(ret):
                msg = buf.STRUCT_ARRAY[i]
                if msg.DLC < len(self.DLC_TO_LEN):
                    data_len = self.DLC_TO_LEN[msg.DLC]
                    messages.append((msg.ID, bytes(msg.Data[:data_len])))
            return messages
        except Exception:
            return []

    def send_and_wait(
        self,
        can_id: int,
        data: bytes,
        custom_timeout: Optional[float] = None
    ) -> Dict[int, List[bytes]]:
        """
        Send a command and wait for replies

        Supports four reply modes:
          - none: no reply (motor enable)
          - single: single frame, single ID (calibration, position control, servo restart)
          - multi_id: multiple frames, different IDs (version query, sensor query)
          - multi_frame: multiple frames, same ID (disable-state check)

        Args:
            can_id: CAN ID
            data: Payload data
            custom_timeout: Custom timeout

        Returns:
            Dict[int, List[bytes]]: {can_id: [frame1, frame2, ...], ...}
        """
        pattern = COMMAND_PATTERNS.get(
            can_id,
            ReplyPattern(ReplyPatternType.SINGLE, [can_id], 1, 1.0)
        )
        
        # Command with no reply
        if pattern.reply_type == ReplyPatternType.NONE:
            self.send_message(can_id, data)
            return {}
        
        # Prepare to wait
        with self._lock:
            self._pending_pattern = pattern
            self._pending_cmd_id = can_id
            self._command_results = defaultdict(list)
            self._command_event.clear()
        
        # Send
        if not self.send_message(can_id, data):
            with self._lock:
                self._pending_pattern = None
                self._pending_cmd_id = None
            return {}
        
        # Wait for replies
        timeout = custom_timeout or pattern.timeout
        success = self._command_event.wait(timeout=timeout)
        
        with self._lock:
            self._pending_pattern = None
            self._pending_cmd_id = None
            results = dict(self._command_results) if success else {}
        
        return results

    # ==================== L30 Protocol Command Implementations ====================

    def query_version(self, timeout: float = 1.0) -> bool:
        """
        Version query (protocol item 4)

        Send: 0x04, data: 00 00 00 00 ...
        Reply: 0x64, data: [version number, left/right hand flag]

        Args:
            timeout: Timeout

        Returns:
            bool: Whether the query succeeded
        """
        data = bytes([0x00] * 8)
        results = self.send_and_wait(L30CanID.VERSION_QUERY.value, data, timeout)
        
        reply_list = results.get(L30CanID.VERSION_REPLY.value, [])
        if not reply_list or len(reply_list[0]) < 2:
            return False
        
        reply = reply_list[0]
        version_byte = reply[0]
        hand_type_byte = reply[1]
        
        self.hand_info = L30HandInfo(
            version=f"{version_byte:02X}",
            is_left_hand=(hand_type_byte == 1),
            motor_count=self.MOTOR_COUNT
        )
        self.is_left_hand = self.hand_info.is_left_hand
        return True

    def calibrate(self, timeout: float = 2.0) -> bool:
        """
        Motor calibration (protocol item 3)

        Send: 0x05, data: 00 00 00 00 ...
        Reply: 0x05, data: 01 00 ...

        Note:
          1. Calibration should be completed before enabling
          2. After startup, query the version first to confirm communication is normal

        Args:
            timeout: Timeout

        Returns:
            bool: Whether calibration succeeded
        """
        if not self.is_enabled:
            print("⚠️ Warning: Some motors are not enabled. Power-cycle before calibration.")
        
        print("Starting motor calibration...")
        data = bytes([0x00] * 2)
        results = self.send_and_wait(L30CanID.CALIBRATION.value, data, timeout)
        reply_list = results.get(L30CanID.CALIBRATION.value, [])
        if reply_list and len(reply_list[0]) > 0 and reply_list[0][0] == 0x01:
            #print("✅ Motor calibration succeeded")
            return True
        #print("❌ Calibration failed")
        return False

    def enable_motors(self) -> bool:
        """
        Motor enable (protocol item 2)

        Send: 0x07, data: 01 00 00 00 ...
        Reply: None

        Note:
          1. Calibration may not be accurate while enabling
          2. After startup, query the version first to confirm communication is normal
          3. Do not enable repeatedly; it has no effect
          4. To disable, power off the main control board

        Returns:
            bool: Whether sending succeeded
        """
        print("Enabling motors...")
        data = bytes([0x01] + [0x00])
        
        # Send directly without waiting for a reply
        if not self.send_message(L30CanID.MOTOR_ENABLE.value, data):
            return False
        
        time.sleep(0.1)
        
        # Confirm using the disable-state check
        status = self.check_enable_status()
        print(status)
        if status and all(status):
            self.is_enabled = True
            print("✅ Motors enabled successfully")
            return True
        print("❌ Failed to enable motors")
        return False

    def set_positions(self, positions: List[int], wait_reply: bool = False) -> bool:
        """
        Position control (protocol item 1)

        Send: 0x06, data: [motor1 low byte, motor1 high byte, motor2 low byte, ...]
        Reply: 0x06, data: 01 00 ... (optional)

        Data format: each motor position occupies 2 bytes (little-endian),
        34 bytes total for 17 motors
        DLC can be configured as 48

        Args:
            positions: Target position values for 17 motors
            wait_reply: Whether to wait for a reply

        Returns:
            bool: Whether sending succeeded
        """
        # Motor 5 requires reversed handling
        positions[4] = -positions[4]
        if not self.is_enabled:
            print("⚠️ Warning: Motors are not enabled")
        
        if len(positions) != self.MOTOR_COUNT:
            print(f"❌ Invalid position data length: expected {self.MOTOR_COUNT} values")
            return False
        
        # Validate position ranges
        self._validate_positions(positions)

        # Build payload: 2 bytes per motor (little-endian)
        data = bytearray()
        for pos in positions:
            # Support signed 16-bit range (-32768 to 32767), encoded as big-endian
            pos = max(-32768, min(65535, int(pos)))
            if pos < 0:
                pos = 65536 + pos  # Convert to unsigned representation
            data.extend(struct.pack('>H', pos))

        # Pad to 48 bytes (DLC=14)
        while len(data) < 48:
            data.append(0x00)
        
        if wait_reply:
            results = self.send_and_wait(
                L30CanID.POSITION_CTRL.value,
                bytes(data),
                timeout=0.5
            )
            reply_list = results.get(L30CanID.POSITION_CTRL.value, [])
            return len(reply_list) > 0 and len(reply_list[0]) > 0 and reply_list[0][0] == 0x01
        else:
            return self.send_message(L30CanID.POSITION_CTRL.value, bytes(data))

    def set_position_single(self, motor_id: int, position: int) -> bool:
        """
        Set a single motor position

        Args:
            motor_id: Motor ID (1-17)
            position: Target position

        Returns:
            bool: Whether sending succeeded
        """
        if not 1 <= motor_id <= self.MOTOR_COUNT:
            print(f"❌ Invalid motor ID: {motor_id}")
            return False
        positions = [0] * self.MOTOR_COUNT
        positions[motor_id - 1] = position
        return self.set_positions(positions)

    def query_sensor(self, sensor_id: int, timeout: float = 1.0) -> Optional[SensorData]:
        """
        Sensor query (protocol item 5)

        Send: 0x08, data: [sensor ID, 00 00 ...]
        Reply: 0x65-0x69, data: 8 valid data bytes

        Sensor mapping:
          - Sensor 1 (ID=1): Thumb
          - Sensor 2 (ID=2): Index
          - Sensor 3 (ID=3): Middle
          - Sensor 4 (ID=4): Ring
          - Sensor 5 (ID=5): Little

        Args:
            sensor_id: Sensor ID (1-5)
            timeout: Timeout

        Returns:
            Optional[SensorData]: Sensor data
        """
        if not 1 <= sensor_id <= 5:
            print(f"❌ Invalid sensor ID: {sensor_id}")
            return None
        
        reply_can_id = L30CanID.SENSOR1_REPLY.value + (sensor_id - 1)
        
        with self._lock:
            self._pending_pattern = ReplyPattern(
                ReplyPatternType.MULTI_ID,
                [reply_can_id],
                1,
                timeout
            )
            self._pending_cmd_id = L30CanID.SENSOR_QUERY.value
            self._command_results = defaultdict(list)
            self._command_event.clear()
        
        data = bytes([sensor_id] + [0x00] * 7)
        self.send_message(L30CanID.SENSOR_QUERY.value, data)
        
        self._command_event.wait(timeout=timeout)
        
        with self._lock:
            reply_list = self._command_results.get(reply_can_id, [])
        
        if not reply_list:
            print(f"❌ Sensor {sensor_id} query timed out")
            reply_list = [[-1, -1, -1, -1, -1, -1, -1, -1]]
        
        return SensorData(sensor_id=sensor_id, raw_data=reply_list[0][:8])

    def query_all_sensors(self, timeout: float = 1.0) -> Dict[int, Optional[int]]:
        """
        Query all 5 sensors

        Args:
            timeout: Timeout

        Returns:
            Dict[int, Optional[int]]: {sensor_id: raw_value, ...}, where raw_value is a decimal integer
        """
        expected_ids = [
            L30CanID.SENSOR1_REPLY.value,
            L30CanID.SENSOR2_REPLY.value,
            L30CanID.SENSOR3_REPLY.value,
            L30CanID.SENSOR4_REPLY.value,
            L30CanID.SENSOR5_REPLY.value
        ]

        with self._lock:
            self._pending_pattern = ReplyPattern(
                ReplyPatternType.MULTI_ID,
                expected_ids,
                5,
                timeout
            )
            self._pending_cmd_id = L30CanID.SENSOR_QUERY.value
            self._command_results = defaultdict(list)
            self._command_event.clear()

        # Send query requests one by one
        for i in range(1, 6):
            query_data = bytes([i] + [0x00] * 7)
            self.send_message(L30CanID.SENSOR_QUERY.value, query_data)
            time.sleep(0.018)

        self._command_event.wait(timeout=timeout)

        sensors: Dict[int, Optional[int]] = {}
        with self._lock:
            for can_id in expected_ids:
                reply_list = self._command_results.get(can_id, [])
                sensor_id = can_id - 0x64
                if reply_list:
                    raw_bytes = reply_list[0][:8]
                    # Convert the 8 bytes to decimal values and sum them
                    raw_value = sum(b for b in raw_bytes)
                    sensors[sensor_id] = raw_value
                else:
                    sensors[sensor_id] = None
            
            self._pending_pattern = None
            self._pending_cmd_id = None

        return sensors

    def check_enable_status(self, timeout: float = 0.5) -> Optional[List[bool]]:
        """
        Disable-state check (protocol item 6)

        Send: 0x0A, data: 00 00 00 00 ...
        Reply: 0x0A, data: 20 bytes total, first 17 bytes are motor enable states

        Note: The reply uses 3 frames with the same ID and must be concatenated

        Args:
            timeout: Timeout

        Returns:
            Optional[List[bool]]: List of enable states for 17 motors, True = enabled
        """
        data = bytes([0x00] * 2)
        results = self.send_and_wait(L30CanID.DISABLE_CHECK.value, data, timeout)
        
        reply_list = results.get(L30CanID.DISABLE_CHECK.value, [])
        
        if not reply_list:
            print("❌ Enable-state check timed out")
            return None
        
        # Concatenate multi-frame data
        full_data = b''.join(reply_list)

        # Need at least 17 bytes
        if len(full_data) < self.MOTOR_COUNT:
            print(f"❌ Insufficient data length: {len(full_data)} < {self.MOTOR_COUNT}")
            return None
        
        # Parse the first 17 bytes as motor enable states
        status = [full_data[i] == 0x01 for i in range(self.MOTOR_COUNT)]
        return status

    def restart_servo(self, timeout: float = 2.0) -> bool:
        """
        Servo restart (protocol item 7)

        Send: 0x0B, data: 00 00 00 00 ...
        Reply: 0x0B, data: 01 (success) / 00 (failure)

        Note: Only useful when disabled due to stall.
              Usage: after a stall disable, restart first, then enable again.

        Args:
            timeout: Timeout

        Returns:
            bool: Whether the restart succeeded
        """
        print("Restarting servos...")
        data = bytes([0x00] * 8)
        results = self.send_and_wait(L30CanID.SERVO_RESTART.value, data, timeout)
        
        reply_list = results.get(L30CanID.SERVO_RESTART.value, [])
        if reply_list and len(reply_list[0]) > 0 and reply_list[0][0] == 0x01:
            print("✅ Servo restart succeeded")
            self.is_enabled = False
            return True
        print("❌ Servo restart failed")
        return False

    # ==================== Helper Methods ====================

    def _validate_positions(self, positions: List[int]) -> bool:
        """
        Validate whether position values are within the valid range

        Args:
            positions: Position value list

        Returns:
            bool: Whether validation passed

        Raises:
            ValueError: Position value out of range
        """
        if len(positions) != self.MOTOR_COUNT:
            raise ValueError(f"Position data length must be {self.MOTOR_COUNT}")
        if self.is_left_hand:
            joint_limits = self.JOINT_LIMITS_LEFT
        else:
            joint_limits = self.JOINT_LIMITS_RIGHT
        for i, pos in enumerate(positions):
            min_val, max_val = joint_limits[i]
            if pos < min_val or pos > max_val:
                raise ValueError(
                    f"Motor {i+1} ({self.JOINT_NAMES[i]}) position out of range: "
                    f"{pos} should be within [{min_val}, {max_val}]"
                )
        return True

    def angle_to_position(self, motor_id: int, angle: float) -> int:
        """
        Convert an angle to a motor position value

        Args:
            motor_id: Motor ID (0-16)
            angle: Target angle (degrees)

        Returns:
            int: Motor position value

        Raises:
            ValueError: Angle out of range
        """
        if not 0 <= motor_id < self.MOTOR_COUNT:
            raise ValueError(f"Invalid motor ID: {motor_id}")
        
        min_angle, max_angle = self.ANGLE_LIMITS[motor_id]
        if angle < min_angle or angle > max_angle:
            raise ValueError(
                f"Motor {motor_id} ({self.JOINT_NAMES[motor_id]}) angle out of range: "
                f"{angle} should be within [{min_angle}, {max_angle}]"
            )
        if self.is_left_hand:
            joint_limits = self.JOINT_LIMITS_LEFT
        else:
            joint_limits = self.JOINT_LIMITS_RIGHT
        min_pos, max_pos = joint_limits[motor_id]
        
        # Linear mapping
        ratio = (angle - min_angle) / (max_angle - min_angle)
        return int(min_pos + ratio * (max_pos - min_pos))

    def set_angles(self, angles: List[float]) -> bool:
        """
        Control all motors using angles

        Args:
            angles: Target angles for 17 motors

        Returns:
            bool: Whether sending succeeded
        """
        if len(angles) != self.MOTOR_COUNT:
            print(f"❌ Invalid angle data length: expected {self.MOTOR_COUNT} values")
            return False
        
        positions = []
        for i, angle in enumerate(angles):
            try:
                positions.append(self.angle_to_position(i, angle))
            except ValueError as e:
                print(f"❌ {e}")
                return False
        
        return self.set_positions(positions)

    def set_joint(self, joint_name: str, position: int) -> bool:
        """
        Control a single motor by joint name

        Args:
            joint_name: Joint name
            position: Target position

        Returns:
            bool: Whether sending succeeded
        """
        if joint_name not in self.JOINT_NAME_TO_ID:
            print(f"❌ Unknown joint name: {joint_name}")
            return False
        
        idx = self.JOINT_NAME_TO_ID[joint_name]
        positions = [0] * self.MOTOR_COUNT
        positions[idx] = position
        return self.set_positions(positions)

    # ==================== Preset Actions ====================

    def open_hand(self) -> bool:
        """
        Open the hand (all motors return to zero)

        Returns:
            bool: Whether sending succeeded
        """
        return self.set_positions([0] * self.MOTOR_COUNT)

    def close_hand(self) -> bool:
        """
        Close into a fist

        Returns:
            bool: Whether sending succeeded
        """
        return self.set_positions([
            1500, 1500, 700, 800,   # Thumb
            0, 1500, 1500,          # Ring finger
            1500, 1500,             # Middle finger
            1500, 1500,             # Little finger
            0, 0, 0,                # Lateral swing
            1500, 1500,             # Index finger
            0                       # Wrist joint
        ])

    def move_to_zero(self) -> bool:
        """
        Return all motors to zero position

        Returns:
            bool: Whether sending succeeded
        """
        return self.set_positions([0] * self.MOTOR_COUNT)

    # ==================== Initialization Procedure ====================

    def init_sequence(self, skip_calibration: bool = False) -> bool:
        """
        Standard initialization procedure

        Procedure:
          1. Query the version to confirm communication is normal
          2. Motor calibration (optional)
          3. Enable motors

        Args:
            skip_calibration: Whether to skip calibration

        Returns:
            bool: Whether initialization succeeded
        """
        print("\n" + "="*40)
        print("Running L30 dexterous hand initialization...")
        print("="*40)
        
        # 1. Query version
        if not self.query_version():
            print("❌ Version query failed")
            return False
        print(f"✅ Version info: {self.hand_info}")
        time.sleep(0.5)

        # 2. Enable motors
        if not self.enable_motors():
            print("❌ Enable failed")
            return False
        time.sleep(0.5)

        # 3. Motor calibration
        if skip_calibration == True:
            if not self.calibrate():
                #print("❌ Calibration failed")
                #return False
                pass
        else:
            print("⏭️ Skipping calibration")
        time.sleep(0.5)
        
        print("="*40)
        print("✅ Initialization complete")
        print("="*40)
        return True


# ==================== Usage Example ====================

def demo():
    """
    Usage example for the L30 dexterous hand controller
    """
    hand = L30HandController(channel=0)
    
    try:
        # Connect
        if not hand.connect():
            return
        
        # Initialize (skip calibration by default; set to False if calibration is needed)
        hand.init_sequence(skip_calibration=True)

        # Display hand information
        if hand.hand_info:
            hand_type = "Left Hand" if hand.hand_info.is_left_hand else "Right Hand"
            print(f"Hand Type: {hand_type}")
            print(f"Firmware Version: v{hand.hand_info.version}")
        
        # Test enable-state check
        print("\nTesting enable-state check...")
        status = hand.check_enable_status()
        if status:
            enabled_count = sum(status)
            print(f"Motor enable status: {enabled_count}/{len(status)}")
        
        # Return to zero position
        hand.move_to_zero()
        time.sleep(1)
        
        # Query all sensors
        print("\nQuerying all sensors...")
        sensors = hand.query_all_sensors()
        for sensor_id, data in sensors.items():
            if data:
                finger = hand.SENSOR_TO_FINGER.get(sensor_id, "Unknown")
                print(f"  {finger}: {data}")
        
        # Set a single motor
        print("\nSetting motor 17 to position -100...")
        hand.set_position_single(motor_id=17, position=-100)
        time.sleep(1)
        hand.move_to_zero()
        time.sleep(1)
        
        # Close into a fist
        print("\nClosing hand...")
        #hand.close_hand()
        #time.sleep(1)
        
        # Open
        print("\nOpening hand...")
        hand.move_to_zero()
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        hand.disconnect()
        print("Disconnected")


if __name__ == "__main__":
    demo()



class RealHandL30Canfd:

    def __init__(self, hand_type="right", channel=0):
        self.requested_hand_type = hand_type
        self.hand_type = hand_type
        self.channel = channel
        self.controller = L30HandController(channel=self.channel)
        self._last_positions_norm = [0] * 17
        self._last_speed = [0] * 17
        self._last_torque = [0] * 17

        if not self.controller.connect():
            raise RuntimeError("L30 CANFD connect failed")
        if not self.controller.init_sequence(skip_calibration=False):
            raise RuntimeError("L30 CANFD initialization failed")

        self.hand_type = "left" if self.controller.hand_info and self.controller.hand_info.is_left_hand else "right"
        if self.requested_hand_type != self.hand_type:
            print(
                f"Warning: requested hand_type={self.requested_hand_type}, "
                f"but hardware reports {self.hand_type}. Using detected hardware side.",
                flush=True,
            )
        self.controller.open_hand()
        time.sleep(0.1)

    def _active_limits(self):
        if self.hand_type == "left":
            return self.controller.JOINT_LIMITS_LEFT
        return self.controller.JOINT_LIMITS_RIGHT

    @staticmethod
    def _neutral_norm(min_pos: int, max_pos: int) -> int:
        return 128 if min_pos < 0 < max_pos else 255

    def _norm_to_raw_value(self, value: int, limits: Tuple[int, int]) -> int:
        min_pos, max_pos = limits
        clamped = max(0, min(255, int(value)))

        if min_pos < 0 < max_pos:
            if clamped == 128:
                return 0
            if clamped < 128:
                ratio = (128 - clamped) / 128.0
                return int(round(min_pos * ratio))
            ratio = (clamped - 128) / 127.0
            return int(round(max_pos * ratio))

        if max_pos == 0 and min_pos < 0:
            ratio = clamped / 255.0
            return int(round(min_pos + ratio * (max_pos - min_pos)))

        if min_pos == 0 and max_pos > 0:
            ratio = (255 - clamped) / 255.0
            return int(round(min_pos + ratio * (max_pos - min_pos)))

        ratio = clamped / 255.0
        return int(round(min_pos + ratio * (max_pos - min_pos)))

    def _raw_to_norm_value(self, value: int, limits: Tuple[int, int]) -> int:
        min_pos, max_pos = limits
        raw = int(value)

        if min_pos < 0 < max_pos:
            if raw == 0:
                return 128
            if raw < 0:
                ratio = raw / float(min_pos)
                return max(0, min(128, int(round(128 - ratio * 128.0))))
            ratio = raw / float(max_pos)
            return max(128, min(255, int(round(128 + ratio * 127.0))))

        if max_pos == 0 and min_pos < 0:
            ratio = (raw - min_pos) / float(max_pos - min_pos)
            return max(0, min(255, int(round(ratio * 255.0))))

        if min_pos == 0 and max_pos > 0:
            ratio = (raw - min_pos) / float(max_pos - min_pos)
            return max(0, min(255, int(round(255.0 - ratio * 255.0))))

        ratio = (raw - min_pos) / float(max_pos - min_pos)
        return max(0, min(255, int(round(ratio * 255.0))))

    def _denormalize_positions(self, pose: List[int]) -> List[int]:
        raw_positions = []
        for idx, value in enumerate(pose):
            raw_positions.append(self._norm_to_raw_value(value, self._active_limits()[idx]))
        return raw_positions

    def _normalize_positions(self, pose: List[int]) -> List[int]:
        normalized = []
        for idx, value in enumerate(pose):
            normalized.append(self._raw_to_norm_value(value, self._active_limits()[idx]))
        return normalized

    def set_joint_positions(self, pose):
        if len(pose) != 17:
            raise ValueError("L30 requires 17 joint values")
        int_pose = [int(round(v)) for v in pose]
        if any(v < 0 or v > 255 for v in int_pose):
            raise ValueError("L30 normalized positions must be in range [0, 255]")
        raw_positions = self._denormalize_positions(int_pose)
        if self.controller.set_positions(raw_positions):
            self._last_positions_norm = [int(max(0, min(255, v))) for v in int_pose]
            return True
        return False

    def set_raw_joint_positions(self, pose):
        if len(pose) != 17:
            raise ValueError("L30 requires 17 joint values")
        raw_positions = [int(round(v)) for v in pose]
        if self.controller.set_positions(raw_positions):
            self._last_positions_norm = self._normalize_positions(raw_positions)
            return True
        return False

    def set_speed(self, speed):
        if len(speed) == 0:
            return False
        if len(speed) == 1:
            speed = speed * 17
        if len(speed) != 17:
            raise ValueError("L30 speed requires 17 values")
        self._last_speed = [int(max(0, min(255, v))) for v in speed]
        print("Warning: L30 CANFD speed control is not exposed by the proven controller path; values cached only.", flush=True)
        return True

    def set_torque(self, torque):
        if len(torque) == 0:
            return False
        if len(torque) == 1:
            torque = torque * 17
        if len(torque) != 17:
            raise ValueError("L30 torque requires 17 values")
        self._last_torque = [int(max(0, min(255, v))) for v in torque]
        print("Warning: L30 CANFD torque control is not exposed by the proven controller path; values cached only.", flush=True)
        return True

    def get_version(self):
        if self.controller.hand_info is None:
            return None
        hand_label = "left" if self.controller.hand_info.is_left_hand else "right"
        return f"L30:v{self.controller.hand_info.version}:{hand_label}"

    def get_current_status(self):
        return list(self._last_positions_norm)

    def get_current_pub_status(self):
        return self.get_current_status()

    def get_speed(self):
        return list(self._last_speed)

    def get_force(self):
        return None

    def get_touch_type(self):
        return None

    def get_touch(self):
        return self.get_matrix_touch()

    def get_matrix_touch(self):
        return [
            self.get_thumb_matrix_touch(),
            self.get_index_matrix_touch(),
            self.get_middle_matrix_touch(),
            self.get_ring_matrix_touch(),
            self.get_little_matrix_touch(),
        ]

    def get_matrix_touch_v2(self):
        return self.get_matrix_touch()

    def get_thumb_matrix_touch(self, *args, **kwargs):
        sensor = self.controller.query_sensor(1)
        return list(sensor.raw_data) if sensor is not None else None

    def get_index_matrix_touch(self, *args, **kwargs):
        sensor = self.controller.query_sensor(2)
        return list(sensor.raw_data) if sensor is not None else None

    def get_middle_matrix_touch(self, *args, **kwargs):
        sensor = self.controller.query_sensor(3)
        return list(sensor.raw_data) if sensor is not None else None

    def get_ring_matrix_touch(self, *args, **kwargs):
        sensor = self.controller.query_sensor(4)
        return list(sensor.raw_data) if sensor is not None else None

    def get_little_matrix_touch(self, *args, **kwargs):
        sensor = self.controller.query_sensor(5)
        return list(sensor.raw_data) if sensor is not None else None

    def get_torque(self):
        return list(self._last_torque)

    def get_temperature(self):
        return None

    def get_fault(self):
        status = self.controller.check_enable_status()
        if status is None:
            return None
        return [0 if enabled else 1 for enabled in status]

    def clear_faults(self):
        return None

    def set_enable_mode(self):
        return None

    def set_disability_mode(self):
        return None

    def get_finger_order(self):
        return list(self.controller.JOINT_NAMES)

    def close(self):
        try:
            self.controller.disconnect()
        except Exception:
            pass
