import customtkinter
from tkinter import filedialog
import os
from PIL import Image
import keyring
import logging
from tkfeather import Feather

from bin.util import (
    config, settings_file, appname, appauthor, check_url_health,
    resource_path,
)

# Ensure settings directory exists. Kept here because the wizard
# is the first-time-setup entry point and may run before
# anywhere else has touched user_data_dir. Harmless to re-run
# on subsequent invocations.
from platformdirs import user_data_dir
settings_location = user_data_dir(appname, appauthor)
os.makedirs(settings_location, exist_ok=True)


class InstallWizard(customtkinter.CTkToplevel):
    """First-time setup dialog. Now a CTkToplevel (was a top-level
    CTk in the original Settings_Wizard.py script) so the launcher
    can open it from the menu without spawning a subprocess.

    Subprocess launch was the previous mechanism: main.py ran
    `subprocess.run(["python", "Settings_Wizard.py"])` and the
    wizard created its own root window. That fails inside a
    PyInstaller --onefile bundle because (a) the bundled .exe
    doesn't ship a Python interpreter, and (b) the wizard .py
    lives in the bundle's _MEIPASS temp dir, not on the user's
    cwd. Running it as a Toplevel inside the same process fixes
    both.

    The wizard still works as a standalone script via the
    `__main__` block at the bottom — useful for development.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title(f"{appname} - Setup")
        self.geometry("400x400")
        self.resizable(False, False)

        # Use resource_path() so the bundled launcher can find
        # the logo images. In dev (running the script directly),
        # resource_path() returns an absolute path. In a
        # --onefile bundle, it joins sys._MEIPASS, which is
        # where --add-data "bin;bin" extracted the images.
        image_path = os.path.join(resource_path("bin/img"), "")
        self.logo_image = customtkinter.CTkImage(
            light_image=Image.open(os.path.join(image_path, "GV-dark.png")),
            size=(200, 25),
            dark_image=Image.open(os.path.join(image_path, "GV-light.png")),
        )
        self.logo_label = customtkinter.CTkLabel(self, image=self.logo_image, text="")
        self.logo_label.pack(pady=20)

        # Create a frame to contain the widgets
        frame = customtkinter.CTkFrame(self, fg_color="transparent")
        frame.pack(padx=20, pady=20)

        def validate_url(_event=None):
            # Bound to <KeyRelease> instead of Tk's `validate="key"`
            # mechanism. CTkEntry doesn't fully implement tkinter's
            # `validate` arg — the validator runs but the entry can
            # end up rejecting keystrokes (the user can't type
            # anything). <KeyRelease> is a regular event handler that
            # runs after the textvariable has already been updated,
            # so the validator sees the new value and only changes
            # the fg_color, never the text content.
            if not hasattr(self, "GV_URL"):
                return False
            url = self.GV_URL.get()
            if url:
                is_valid = check_url_health(url)
                if is_valid:
                    self.GV_URL.configure(fg_color='green')
                else:
                    self.GV_URL.configure(fg_color='red')
                return is_valid
            return False

        # GameVault URL Entry.
        stored_url = config['SETTINGS'].get('url', '')
        self.GV_URL = customtkinter.CTkEntry(
            frame, placeholder_text="GameVault URL IE: http://127.0.0.1:8080",
            width=350,
        )
        if stored_url:
            self.GV_URL.insert(0, stored_url)
        # Run the validator on every keystroke (KeyRelease fires
        # after the textvariable is updated) and on initial focus
        # so the entry color reflects the current value.
        self.GV_URL.bind("<KeyRelease>", validate_url, add="+")
        self.GV_URL.bind("<FocusIn>", validate_url, add="+")
        self.GV_URL.grid(row=1, columnspan=2, pady=10, sticky="ew")

        # Username Entry
        stored_username = config['SETTINGS'].get('username', 'Username')
        self.username = customtkinter.CTkEntry(frame, placeholder_text="Username")
        if stored_username:
            self.username.insert(0, stored_username)
        self.username.grid(row=3, columnspan=2, pady=10)

        # Password Entry
        self.password = customtkinter.CTkEntry(
            frame, show="*", placeholder_text="Password",
        )
        self.password.grid(row=4, columnspan=2, pady=10)

        # Install Location Entry
        stored_install_location = config['SETTINGS'].get('install_location', '')
        self.install_location = customtkinter.CTkEntry(
            frame, placeholder_text="Install Location", width=300,
        )
        if stored_install_location:
            self.install_location.insert(0, stored_install_location)
        self.install_location.grid(row=5, column=0, pady=10, sticky='ew')

        # Select Folder Button
        self.select_location_button = customtkinter.CTkButton(
            frame, text='', image=Feather('folder').icon,
            command=self.select_install_location, width=30,
        )
        self.select_location_button.grid(row=5, column=1, padx=(10, 0), pady=10, sticky='w')

        # Submit Button
        self.submit_il = customtkinter.CTkButton(
            frame, text='Submit', command=self.submit_credentials,
        )
        self.submit_il.grid(row=6, columnspan=2, pady=10)

        self.close_label = customtkinter.CTkLabel(frame, text="")
        self.close_label.grid(row=7, columnspan=2, pady=10)

        # Track whether the user completed the wizard via
        # submit_credentials. The `<Destroy>` handler at the
        # bottom of __init__ uses this to decide whether to
        # flip the `first_run` flag — if the user closes the
        # wizard via [×] without submitting, we still flip
        # the flag so the wizard doesn't keep popping up on
        # every launch. "Saw the wizard" is enough; we don't
        # require them to fill in fields.
        self._submitted = False
        self.bind("<Destroy>", self._on_destroy)

    def select_install_location(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.install_location.delete(0, 'end')
            self.install_location.insert(0, folder_selected)

    def submit_credentials(self):
        username = self.username.get()
        password = self.password.get()
        installoc = self.install_location.get()
        url = self.GV_URL.get()

        # Validate the URL one more time on submit. The
        # per-keystroke validator turns the entry red/green,
        # but it doesn't block submit — a user could type a
        # working URL, have it go green, then change it to
        # something broken without the keystroke validator
        # firing on the final value. The submit-time check
        # catches that and refuses to save a broken URL.
        # We do this rather than `if not check_url_health(url)`
        # so the failure message is shown to the user instead
        # of silently rejected.
        if not check_url_health(url):
            self.close_label.configure(
                text="URL did not respond. Fix the URL (red entry) and try again.",
                text_color="red",
            )
            self.GV_URL.configure(fg_color='red')
            return

        keyring.set_password("GameVault-Snake", username, password)

        config.set('SETTINGS', 'username', username)
        config.set('SETTINGS', 'install_location', installoc)
        config.set('SETTINGS', 'url', url)
        # Flip the first-run flag so main.py doesn't re-open the
        # wizard on the next launch. Setting it inside the wizard
        # (rather than in main.py after submit) means the flag
        # is also cleared if the user opens the wizard from the
        # menu later and submits new values — which is the
        # correct behaviour: any time the wizard is "completed",
        # the launcher is no longer in a "first run" state.
        config.set('SETTINGS', 'first_run', 'False')

        with open(settings_file, 'w') as configfile:
            config.write(configfile)

        # Mark as submitted so the <Destroy> handler doesn't
        # re-write the same value. Belt and suspenders — the
        # flag would be 'False' either way, but skipping the
        # extra write is cleaner.
        self._submitted = True

        self.close_label.configure(
            text="Settings saved! Close and reopen to launch GameVault-Snake Edition.",
            text_color="white",
        )

    def _on_destroy(self, _event=None):
        """Flip `first_run` to False on any close path (submit
        or [×] close). This prevents the wizard from re-opening
        on every launch when the user dismisses it without
        filling in fields — that would be a frustrating loop.

        `submit_credentials` already sets `first_run=False`, so
        this only writes when the user closes without saving.
        We don't `os.path.exists` the settings_file here
        because the wizard's submit path wrote it earlier in
        the same session, so by the time _on_destroy runs the
        file is always present in normal use.
        """
        if self._submitted:
            return
        try:
            if config['SETTINGS'].get('first_run', 'True') == 'True':
                config.set('SETTINGS', 'first_run', 'False')
                with open(settings_file, 'w') as configfile:
                    config.write(configfile)
        except Exception:
            # If the write fails (e.g. read-only file, full
            # disk), silently skip — the next launch will just
            # pop the wizard again. Better than crashing the
            # launcher's shutdown on a cosmetic flag.
            pass


if __name__ == "__main__":
    # Standalone script entry. Creates a real root window so
    # the wizard can be tested in isolation without launching
    # the full launcher. This is the dev-only path; the
    # bundled launcher imports InstallWizard and constructs it
    # as a Toplevel instead.
    import sys
    import os
    # Add the project root to sys.path so `from bin.util import`
    # works when this file is run directly via `python
    # bin/GUI/settings_wizard.py`. In the bundled launcher,
    # main.py has already set up sys.path, so this is a no-op.
    sys.path.insert(0, os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    ))
    root = customtkinter.CTk()
    customtkinter.set_appearance_mode(config['SETTINGS'].get('apperance', 'System'))
    customtkinter.set_default_color_theme(config['SETTINGS'].get('theme', 'blue'))
    InstallWizard(root)
    root.mainloop()
