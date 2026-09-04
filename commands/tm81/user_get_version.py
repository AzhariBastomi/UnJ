"""
commands/tm81/user_get_version.py - Get Firmware Version (CMD 0x0C)
Response payload (6 bytes): major, minor, patch, bl_major, bl_minor, bl_patch.
"""

import logging
_log = logging.getLogger(__name__)

try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId


class UserGetVersion(TM81Command):

    def execute(self) -> str:
        result = self.xfer(CmdId.USR_GET_VER)
        if not result.valid:
            return f"NG:{result.error}"

        d = result.payload
        if len(d) < 3:
            return f"NG:payload terlalu pendek ({len(d)} bytes)"

        self._app_version = f"v{d[0]}.{d[1]}.{d[2]}"
        self._bl_version  = f"v{d[3]}.{d[4]}.{d[5]}" if len(d) >= 6 else "N/A"
        _log.debug(f"  App Version: {self._app_version}")
        _log.debug(f"  Bootloader Version: {self._bl_version}")
        return f"OK:App {self._app_version} / BL {self._bl_version}"

    def get_version(self) -> str:
        return getattr(self, "_app_version", "")

    def get_bl_version(self) -> str:
        return getattr(self, "_bl_version", "")


# -- Standalone test ----------------------------------------------------------
if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    result = UserGetVersion().execute()
    print(result)
    sm.disconnect_all()
