"""
test_modules.py - Test item definitions.
"""

from dataclasses import dataclass, field
from enum import Enum, auto


class TestResult(Enum):
    PENDING  = auto()
    RUNNING  = auto()
    OK       = auto()
    NG       = auto()


class TestType(Enum):
    PROGRESS = "progress"
    MANUAL   = "manual"
    AUTO     = "auto"


@dataclass
class TestItem:
    """Base class. Subclass menentukan perilakunya sendiri lewat override
    (polymorphism) — kode luar (widget/controller) tidak perlu tahu jenis
    konkretnya, cukup panggil method/atribut di sini.
    """

    title:       str
    command:     str
    description: str = ""
    run_fn:      object = field(default=None)          # callable() -> "OK"|"NG", opsional
    validate_fn: object = field(default=None)          # callable() -> None|"NG:..." — cek sebelum kirim
    cancel_fn:        object = field(default=None)      # callable() -> None — batalkan test yang sedang jalan
    popup_extra_fn:   object = field(default=None)      # callable(popup, detail_text, scale) -> None — widget tambahan di detail popup
    expect:      dict = field(default_factory=dict)    # {label: value} — hanya dicek saat Start sequence
    no_retry:    bool = field(default=False)           # True = skip outer retry
    test_type:   TestType = field(default=TestType.AUTO, init=False)
    result:      TestResult = field(default=TestResult.PENDING, init=False)
    last_error:  str = field(default="", init=False)

    # Kunci pendaftaran di TEST_TYPE_REGISTRY / dipakai UI untuk memilih RowBehavior.
    # Override di setiap subclass — dengan ini menambah tipe test baru tidak perlu
    # menyentuh if/elif di tempat lain (widget, controller, loader).
    type_key = "auto"

    # True hanya untuk ManualTest — dipakai controller supaya tidak perlu
    # `if test_item.test_type == TestType.MANUAL` di banyak tempat.
    is_manual = False

    def reset(self):
        self.result     = TestResult.PENDING
        self.last_error = ""

    def is_done(self):
        return self.result in (TestResult.OK, TestResult.NG)


@dataclass
class ProgressBarTest(TestItem):
    type_key = "progress"

    steps:   int = 5
    step_ms: int = 300

    def __post_init__(self):
        self.test_type = TestType.PROGRESS


@dataclass
class ManualTest(TestItem):
    type_key  = "manual"
    is_manual = True

    def __post_init__(self):
        self.test_type = TestType.MANUAL


@dataclass
class AutoTest(TestItem):
    type_key = "auto"

    def __post_init__(self):
        self.test_type = TestType.AUTO


# ---------------------------------------------------------------------------
# Factory Pattern — satu titik untuk membuat TestItem subclass yang tepat.
# Menambah tipe baru = menambah 1 class + daftarkan di sini, tanpa menyentuh
# if/elif di test_loader.py / ui / controller.
# ---------------------------------------------------------------------------

TEST_TYPE_REGISTRY = {
    cls.type_key: cls for cls in (ProgressBarTest, ManualTest, AutoTest)
}


def build_test_item(type_key: str, **kwargs) -> TestItem:
    """Factory: instansiasi TestItem subclass berdasar type_key ('auto'/'manual'/'progress').
    Tipe tak dikenal -> fallback ke AutoTest (paling umum)."""
    cls = TEST_TYPE_REGISTRY.get(type_key, AutoTest)
    return cls(**kwargs)


def build_default_tests():
    return [
        ProgressBarTest(title="LED Test", command="TEST_LED",
                        description="Cycles all LEDs and reads back confirmation",
                        steps=8, step_ms=250),
        ManualTest(title="Button Test", command="TEST_BTN",
                   description="Press the physical button and confirm with OK/NG"),
        AutoTest(title="Voltage Test", command="TEST_VOLT",
                 description="Reads supply voltage from ADC"),
        ProgressBarTest(title="Memory Test", command="TEST_MEM",
                        description="Write/read cycle on EEPROM",
                        steps=10, step_ms=200),
        AutoTest(title="Communication Test", command="TEST_COMM",
                 description="Loopback ping to device UART"),
    ]
