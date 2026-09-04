"""
commands/tm81/ping.py — Ping MCU (CMD 0x00)
Response: ACK jika device aktif.
"""

try:
    from commands.tm81.base import TM81Command, CmdId
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "lib"))
    from commands.tm81.base import TM81Command, CmdId


class Ping(TM81Command):

    def execute(self) -> str:
        # Pantau bytes mentah yang masuk selama ping — untuk membedakan
        # jenis timeout: tidak ada respons vs device kirim data tidak valid.
        import serial_manager as sm
        comm = sm.get_comm(self._conn)

        raw_buf = bytearray()

        def _on_raw(data: bytes):
            raw_buf.extend(data)

        if comm is not None and hasattr(comm, "on_raw"):
            comm.on_raw(_on_raw)

        result = self.xfer(CmdId.PING)

        if comm is not None and hasattr(comm, "off_raw"):
            comm.off_raw(_on_raw)

        if not result.valid and result.error != "ACK":
            if result.error == "Timeout":
                if not raw_buf:
                    # Tidak ada byte sama sekali — device tidak ditemukan di bus
                    return "NG:Timeout — Device tidak ditemukan (tidak ada respons di bus)"
                # Ada bytes masuk tapi tidak membentuk frame valid
                unique = set(raw_buf)
                if unique == {0xFF} or unique == {0xFF, 0x00}:
                    # Hanya 0xFF — device ada di bus tapi tidak merespons program ping JIG
                    return "NG:Timeout — Device tidak merespons pada program ping JIG (hanya 0xFF diterima)"
                # Respons lain yang tidak dikenali
                hex_str = raw_buf[:16].hex(" ") + ("..." if len(raw_buf) > 16 else "")
                return f"NG:Timeout — Respons tidak valid dari device: {hex_str}"
            return f"NG:{result.error}"
        return "OK"


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
    import serial_manager as sm
    sm.connect("ch340")
    print(Ping().execute())
