"""
test_base.py - Base class untuk semua test berbasis class.

Cara pakai:
    from test_base import TestBase

    class NamaTest(TestBase):
        TITLE       = "Nama Test"
        TYPE        = "auto"          # "auto" | "manual" | "progress"
        COMMAND     = "TEST_CMD"
        DESCRIPTION = "Keterangan test"

        def run(self) -> str:
            # logika test di sini
            return "OK"   # atau "NG"
"""


class TestBase:
    # --- Metadata wajib diisi di subclass ---
    TITLE:       str = "Unnamed Test"
    TYPE:        str = "auto"        # "auto" | "manual" | "progress"
    COMMAND:     str = "TEST_CMD"
    DESCRIPTION: str = ""

    # --- Opsional (hanya untuk TYPE="progress") ---
    STEPS:   int = 5
    STEP_MS: int = 300

    def __init__(self):
        self._progress_cb = None   # di-set oleh TestController sebelum run()

    def set_progress_cb(self, cb):
        """Dipanggil TestController untuk menghubungkan progress bar ke run()."""
        self._progress_cb = cb

    def report_progress(self, percent: int):
        """Panggil ini dari run() untuk update progress bar secara real-time."""
        if self._progress_cb:
            self._progress_cb(min(int(percent), 100))

    def run(self) -> str:
        """
        Override di subclass.
        Return "OK" jika lulus, "NG" jika gagal.
        """
        raise NotImplementedError(f"{self.__class__.__name__}.run() belum diimplementasikan")
