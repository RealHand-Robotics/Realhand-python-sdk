- `RealHand/core/canfd/real_hand_l30_canfd.py`
  Changed the old L30 CAN FD implementation to the proven command-based L30 controller flow from the working repo.
  Changed connection handling to run version query, motor enable, status verification, and initialization before use.
  Changed hand-side handling to detect left or right from hardware instead of trusting only the requested side.
  Changed joint mapping to use the actual L30 left/right joint limits and controller joint order.
  Changed normalized `0..255` commands to map into the real L30 raw motor ranges underneath.
  Changed runtime output strings from Chinese to English.
  Changed touch methods from returning `None` to returning the raw 8-byte per-finger sensor payloads for sensors 1 through 5.
  Changed `get_matrix_touch()` and per-finger touch getters to expose usable L30 touch data instead of empty placeholders.
  Changed speed and torque methods to explicit compatibility stubs that cached values and printed warnings instead of pretending to perform real hardware control.

- `RealHand/real_hand_api.py`
  Changed the L30 path to use `RealHandL30Canfd` through the normal `RealHandApi` flow.
  Changed `finger_move()` to support 17-value L30 commands correctly through the updated L30 backend.
  Changed the validation path so L30 continued to use normalized `0..255` GUI inputs consistently with the rest of the SDK.

- `example/gui_control/gui_control.py`
  Changed the L30 GUI support from a generic layout to an L30-specific layout and mapping.
  Changed the displayed slider order to group joints by finger instead of showing controller order directly.
  Changed the display-to-controller mapping so sliders were shown in grouped finger order but were still published back in the real controller order.
  Changed the middle finger mapping after testing so `middle_root` and `middle_tip` matched observed hardware behavior.
  Changed L30 sliders to stay in the same normalized `0..255` style as the other models instead of exposing raw signed motor ranges in the UI.
  Changed L30 preset positions to use normalized open/fist values consistent with the corrected mapping.
  Changed the matrix visualization to use `1x8` per finger for L30 only.
  Changed other models to keep the original `12x6` matrix visualization unchanged.

- `example/gui_control/config/constants.py`
  Changed the L30 joint labels from the old mismatched order to labels aligned with the corrected L30 GUI layout.
  Changed the L30 default positions and preset configuration to match the corrected normalized L30 GUI behavior.
