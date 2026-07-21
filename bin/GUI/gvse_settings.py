import customtkinter
import os
import logging
from tkinter import filedialog

from bin.util import config, settings_file

# CTkMessagebox is the nicer messagebox used by game_settings.py; if
# it's not installed (some slim customtkinter builds strip it), fall
# back to tkinter.messagebox. The fallback path is silent on success
# — messagebox.showinfo has no equivalent of "auto-close", and the
# dialog's success path is so simple ("file written, restart to
# apply") that a modal OK dialog is fine.
try:
    from CTkMessagebox import CTkMessagebox
except Exception:  # ImportError or anything else
    CTkMessagebox = None
    from tkinter import messagebox


# Settings dialog dimensions. The default size is the same as
# game_settings.py (900x650) so a user opening both from the menu
# doesn't see the dialog jump around. minsize is the smallest
# reasonable size before the form becomes illegible.
DEFAULT_GEOMETRY = "900x650"
MIN_SIZE = (820, 580)

# The valid values for each dropdown. These mirror what customtkinter
# supports (and what main.py:22 + main.py:1310-1314 already accept),
# so we never need to translate between the dialog and the rest of
# the launcher.
APPEARANCE_MODES = ("Light", "Dark", "System")
THEMES = ("blue", "green", "dark-blue")


class GVSESettings(customtkinter.CTkToplevel):
    """App-level settings dialog: appearance, theme, install location,
    debug mode.

    Reads/writes the same `settings.ini` that Settings_Wizard.py and
    the View menu's theme options write to. The dialog is non-modal
    (no grab_set) — matches the rest of the GUI helpers.

    The `apperance` key in settings.ini is misspelled (the file
    already shipped that way and `change_appearance_mode_event` at
    main.py:1312 reads/writes the misspelling). We keep the typo to
    avoid orphaning the user's current setting. A new key would split
    the install into "this dialog" vs "menu" depending on which was
    used last, which is worse than the typo.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("App Settings — GameVault Snake Edition")
        self.geometry(DEFAULT_GEOMETRY)
        self.minsize(*MIN_SIZE)

        # Center the dialog on the screen using logical pixels. We
        # can't use self.master.winfo_width/height because at this
        # point in __init__ the master hasn't been laid out yet, and
        # the values we get are physical pixels (DPI-scaled) which
        # over-shoot on high-DPI monitors. winfo_screenwidth/height
        # returns the logical-pixel screen size, which is what
        # geometry strings use.
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = (int(x) for x in DEFAULT_GEOMETRY.split("x"))
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.geometry(f"+{x}+{y}")

        # Track whether the user has made any changes — used to skip
        # the "save?" prompt on close. Currently we just close
        # without prompting; the field is here for a future
        # unsaved-changes warning.
        self._dirty = False

        # Build the form. Two main sections: a body that holds the
        # fields, and a footer with Save/Cancel.
        self._build_body()
        self._build_footer()
        self._load()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_body(self):
        """Header + scrollable form area. The form is a vertical
        stack of labeled rows; each row is its own grid (label
        left, control right). Using one grid per row is simpler
        than a 2-column grid for the whole frame, and the form is
        short enough (4 rows) that the extra plumbing is minor."""
        # Header. Sub-text "Runtime tweaks…" is a one-liner so the
        # user knows this dialog is not the Settings Wizard (which
        # is for first-time setup / server credentials).
        header = customtkinter.CTkFrame(self, corner_radius=0)
        header.pack(side="top", fill="x")
        customtkinter.CTkLabel(
            header, text="App Settings", font=("", 18, "bold"),
        ).pack(side="left", padx=20, pady=(16, 0), anchor="w")
        customtkinter.CTkLabel(
            header,
            text="Runtime tweaks for this launcher. "
                 "Some changes need a restart.",
            text_color="grey",
        ).pack(side="left", padx=(0, 20), pady=(20, 0), anchor="w")

        # Scrollable body. We use a CTkScrollableFrame in case the
        # user's DPI is high enough that 4 fields don't fit on
        # 820px; the scrollbar is a safety net, not a typical
        # affordance.
        self.body = customtkinter.CTkScrollableFrame(self, corner_radius=0)
        self.body.pack(side="top", fill="both", expand=True, padx=10, pady=10)
        self.body.grid_columnconfigure(1, weight=1)

        # --- Appearance ---
        customtkinter.CTkLabel(
            self.body, text="Appearance mode",
        ).grid(row=0, column=0, padx=8, pady=8, sticky="w")
        self.appearance_var = customtkinter.StringVar(value="System")
        self.appearance_menu = customtkinter.CTkOptionMenu(
            self.body, values=list(APPEARANCE_MODES),
            variable=self.appearance_var, width=180,
        )
        self.appearance_menu.grid(row=0, column=1, padx=8, pady=8, sticky="ew")

        # --- Theme ---
        customtkinter.CTkLabel(
            self.body, text="Color theme",
        ).grid(row=1, column=0, padx=8, pady=8, sticky="w")
        self.theme_var = customtkinter.StringVar(value="blue")
        self.theme_menu = customtkinter.CTkOptionMenu(
            self.body, values=list(THEMES),
            variable=self.theme_var, width=180,
        )
        self.theme_menu.grid(row=1, column=1, padx=8, pady=8, sticky="ew")

        # --- Install location ---
        # Row 1 of this sub-row: label. Row 2: entry (expand) +
        # browse button (fixed width). Two columns inside column 1
        # of the outer grid.
        customtkinter.CTkLabel(
            self.body, text="Install location",
        ).grid(row=2, column=0, padx=8, pady=8, sticky="nw")
        install_frame = customtkinter.CTkFrame(self.body, fg_color="transparent")
        install_frame.grid(row=2, column=1, padx=8, pady=8, sticky="ew")
        install_frame.grid_columnconfigure(0, weight=1)
        self.install_var = customtkinter.StringVar(value="")
        self.install_entry = customtkinter.CTkEntry(
            install_frame, textvariable=self.install_var,
            placeholder_text=os.path.expanduser("~"),
        )
        self.install_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        customtkinter.CTkButton(
            install_frame, text="Browse…", width=90,
            command=self._browse_install_location,
        ).grid(row=0, column=1)

        # --- Debug ---
        # Checkbox in the right column, no label on the left (the
        # text is on the checkbox itself).
        customtkinter.CTkLabel(
            self.body, text="Debug mode",
        ).grid(row=3, column=0, padx=8, pady=8, sticky="w")
        self.debug_var = customtkinter.BooleanVar(value=False)
        self.debug_checkbox = customtkinter.CTkCheckBox(
            self.body,
            text="Enable verbose logging and the Debug menu",
            variable=self.debug_var,
        )
        self.debug_checkbox.grid(row=3, column=1, padx=8, pady=8, sticky="w")

    def _build_footer(self):
        """Save / Cancel row. Anchored to the bottom of the dialog;
        the body fills the leftover space via pack(expand=True)."""
        footer = customtkinter.CTkFrame(self, corner_radius=0)
        footer.pack(side="bottom", fill="x")
        footer.grid_columnconfigure(0, weight=1)

        button_row = customtkinter.CTkFrame(footer, fg_color="transparent")
        button_row.grid(row=0, column=0, sticky="e", padx=20, pady=12)
        customtkinter.CTkButton(
            button_row, text="Cancel", width=100,
            command=self.destroy,
        ).pack(side="right", padx=(8, 0))
        customtkinter.CTkButton(
            button_row, text="Save", width=100,
            command=self._on_save,
        ).pack(side="right")

    # ------------------------------------------------------------------
    # Field plumbing
    # ------------------------------------------------------------------

    def _load(self):
        """Read current values from `config` (already loaded from
        settings.ini at startup) into the widgets. Defensive reads:
        if a key is missing or empty, fall back to the documented
        default. Defaults match what main.py:22 + main.py:60 expect."""
        try:
            appearance = config['SETTINGS'].get('apperance', 'System')
        except (KeyError, TypeError):
            appearance = 'System'
        if appearance not in APPEARANCE_MODES:
            appearance = 'System'
        self.appearance_var.set(appearance)

        try:
            theme = config['SETTINGS'].get('theme', 'blue')
        except (KeyError, TypeError):
            theme = 'blue'
        if theme not in THEMES:
            theme = 'blue'
        self.theme_var.set(theme)

        try:
            install = config['SETTINGS'].get('install_location', '')
        except (KeyError, TypeError):
            install = ''
        # Show the literal string the user has on file. If it's empty,
        # the entry's placeholder (~/ ) takes over.
        self.install_var.set(install or "")

        # The ini stores debug as the literal string "True" / "False"
        # (the menu check at main.py:60 is `== 'True'`). A direct
        # BooleanVar-from-config would need a conversion here.
        try:
            debug = config['SETTINGS'].get('debug', 'False')
        except (KeyError, TypeError):
            debug = 'False'
        self.debug_var.set(debug == 'True')

    def _browse_install_location(self):
        """Folder picker. The CTkOptionMenu / Entry don't need any
        extra setup for this — filedialog.askdirectory() returns a
        path or "" on cancel. We normalize the path (expanduser +
        normpath) so the saved value doesn't carry a trailing slash
        or a Windows-mixed-separator mess."""
        initial = self.install_var.get().strip() or os.path.expanduser("~")
        chosen = filedialog.askdirectory(
            parent=self, initialdir=initial,
            title="Choose install location",
        )
        if chosen:
            self.install_var.set(os.path.normpath(chosen))

    def _on_save(self):
        """Write the form values back to config + the INI file. The
        appearance/theme/install_location values are also pushed into
        the live configparser object the rest of the launcher reads
        from, so e.g. `change_appearance_mode_event` will see the new
        value on its next call.

        We do NOT call customtkinter.set_appearance_mode /
        set_default_color_theme here. The dialog is for tweaking
        the next launch, not for live-applying — instant-replacing
        the theme mid-session would require rebuilding every
        widget, which is a much larger change. The restart-required
        note in the header covers the user-facing side."""
        appearance = self.appearance_var.get()
        if appearance not in APPEARANCE_MODES:
            appearance = "System"

        theme = self.theme_var.get()
        if theme not in THEMES:
            theme = "blue"

        # Strip whitespace from the install path but keep empty
        # string if the user cleared it — the Settings Wizard's
        # `os.path.expanduser` default kicks in on the next launch.
        install = (self.install_var.get() or "").strip()

        debug = "True" if self.debug_var.get() else "False"

        # Update the live config in-memory so other parts of the
        # app see the new value without re-reading the INI.
        try:
            config['SETTINGS']['apperance'] = appearance
            config['SETTINGS']['theme'] = theme
            config['SETTINGS']['install_location'] = install
            config['SETTINGS']['debug'] = debug
        except Exception as e:
            logging.error(f"GVSESettings: failed to update config: {e}")
            self._show_error(
                "Could not save settings",
                f"The in-memory config update failed: {e}",
            )
            return

        # Persist to disk. This is the only step that can fail in
        # practice (read-only file, no permission, full disk).
        try:
            os.makedirs(os.path.dirname(settings_file), exist_ok=True)
            with open(settings_file, 'w') as fh:
                config.write(fh)
        except Exception as e:
            logging.error(f"GVSESettings: failed to write {settings_file}: {e}")
            self._show_error(
                "Could not save settings",
                f"Writing {settings_file} failed: {e}",
            )
            return

        # Success. The message is informational only — the user
        # has already seen the form. The dialog closes after the
        # OK click.
        self._show_info(
            "Settings saved",
            "Settings saved. Restart the launcher for the changes "
            "to take full effect.",
        )
        self.destroy()

    # ------------------------------------------------------------------
    # Messagebox helpers
    # ------------------------------------------------------------------

    def _show_info(self, title, message):
        if CTkMessagebox is not None:
            CTkMessagebox(title=title, message=message, icon="check")
        else:
            messagebox.showinfo(title, message, parent=self)

    def _show_error(self, title, message):
        if CTkMessagebox is not None:
            CTkMessagebox(title=title, message=message, icon="cancel")
        else:
            messagebox.showerror(title, message, parent=self)
