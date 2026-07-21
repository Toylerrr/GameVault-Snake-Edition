"""Backward-compatibility shim.

The real implementation moved to `bin/GUI/settings_wizard.py` so
the Settings Wizard can be opened in-process by the bundled
launcher (it was previously spawned as a subprocess via
`subprocess.run(["python", "Settings_Wizard.py"])` in main.py,
which fails in a PyInstaller --onefile bundle because the bundle
doesn't ship a Python interpreter).

This shim keeps the old `python Settings_Wizard.py` invocation
working for developers. It's a 4-line re-export; once the dev
workflow is on the new path, this file can be removed.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "bin", "GUI")
))
from settings_wizard import InstallWizard  # noqa: E402,F401


if __name__ == "__main__":
    # Re-launch the canonical main block. We don't replicate it
    # here because the canonical path is in settings_wizard.py and
    # keeping it in one place avoids drift.
    import runpy
    runpy.run_path(
        os.path.join(os.path.dirname(__file__), "bin", "GUI", "settings_wizard.py"),
        run_name="__main__",
    )
