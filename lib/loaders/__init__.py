"""
loaders/ — Internal package untuk semua test-source loaders.

test_loader.py adalah facade publik di atasnya; modul lain sebaiknya
import dari test_loader, bukan langsung dari loaders.*.
"""

from loaders.context import (
    context, set_tk_root, watch_context, get_context,
    update_context, show_countdown_popup,
)

from loaders.base import JsonTestSource

from loaders.flash import (
    flash_project_names, flash_project_label, flash_module_names,
    load_flash_tests_named, load_flash_tests,
    _read_flash_json, _load_flash_by_name,
    get_flash_sources,
)

from loaders.voltage import (
    load_voltage_tests, voltage_module_names, _load_voltage_by_name,
    get_voltage_sources,
)

from loaders.tm81 import (
    TM81OtaTestSource, TM81GenericTestSource,
    load_tm81_tests, load_tm81_test, tm81_module_names, tm81_label,
    get_tm81_extra_sources, reload_tm81_extra_sources,
)

from loaders.bexa import (
    BexaTestSource, load_bexa_tests, load_bexa_test,
    bexa_module_names, bexa_label,
)
