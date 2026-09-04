"""
main.py — Test Point Application entry point.

Run:
    python main.py

Architecture
------------
  App                  — root window; lihat app/_app.py
    BuildMixin         — _build_*, input callbacks    (app/_build_mixin.py)
    RunMixin           — Start/Stop/done              (app/_run_mixin.py)
    DbMixin            — database session             (app/_db_mixin.py)
    StateMixin         — resume state + persist tasks (app/_state_mixin.py)
    SettingsMixin      — dialog settings + dyn btns   (app/_settings_mixin.py)
    TestMgmtMixin      — add/clear test items         (app/_test_mgmt_mixin.py)
  ui.TestListPanel     — scrollable list of TestRowWidget
  controllers.TestController   — orchestrates running tests
  controllers.KeepaliveManager — background TM81 ping
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

import logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from app import App

if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception:
        import traceback
        traceback.print_exc()
        input("Tekan Enter untuk keluar...")
