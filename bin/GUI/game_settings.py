"""Game Settings dialog — admin-editable Custom Metadata for a single game.

Mirrors the Custom Metadata sub-page from the official GameVault web
client. The dialog is a non-modal `CTkToplevel`: the user can keep
interacting with the launcher (other tabs, downloads) while it's open.
Closing the window does NOT cancel a save — saves complete on the UI
thread and either succeed (dialog auto-closes, parent refreshes) or
fail (dialog stays open with an error label).

Used by the Game tab's ⚙️ button via `App.open_game_settings(gid)`. The
button itself is gated on admin role (see `main.py.sidebar_callback`);
this class doesn't re-check — `is_admin` is passed in by the caller and
controls whether the Save/Wipe buttons are enabled. The same class
works for non-admins (read-only) so a non-admin viewing the dialog can
see what admins are allowed to edit.
"""

import logging
import tkinter.messagebox

import customtkinter

# CTkMessagebox ships with customtkinter>=5.2 but lives in a separate
# package on some installs. Import defensively so the dialog still
# works (with a tk fallback) if it's missing.
try:
    from CTkMessagebox import CTkMessagebox
    _HAVE_CTK_MSGBOX = True
except Exception:
    _HAVE_CTK_MSGBOX = False

from bin.util import (
    fetch_game_info,
    update_game_user_metadata,
)


# --- value coercion helpers (module-scope so the FIELDS tuple can
# reference them). ---


def _safe_int_str(v):
    if v is None:
        return ""
    try:
        return str(int(v))
    except (TypeError, ValueError):
        return ""


def _safe_float_str(v):
    if v is None:
        return ""
    try:
        return str(float(v))
    except (TypeError, ValueError):
        return ""


def _try_int(v):
    """Best-effort int coercion; None on failure. Used to populate
    `_loaded` so the diff path compares int-vs-int, not
    int-vs-string."""
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _try_float(v):
    """Best-effort float coercion; None on failure. Used to populate
    `_loaded` so the diff path compares float-vs-float, not
    float-vs-string."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _bool_to_str(v):
    return "1" if v else "0"


# (key, label, kind, raw_loaded_converter)
#
# `kind` is one of:
#   "entry"       — single-line text entry
#   "text"        — multi-line textbox
#   "entry_int"   — single-line, coerced to int on save
#   "entry_float" — single-line, coerced to float on save
#   "check"       — boolean checkbox
FIELDS = [
    ("title",                "Title",                         "entry",       str),
    ("sort_title",           "Sorting Title",                 "entry",       str),
    ("description",          "Description",                   "text",        str),
    ("notes",                "Notes",                         "text",        str),
    ("average_playtime",     "Avg. Playtime Minutes",         "entry_int",   _safe_int_str),
    ("age_rating",           "Age Rating",                    "entry_int",   _safe_int_str),
    ("release_date",         "Release Date (ISO 8601)",       "entry",       str),
    ("rating",               "Rating (0–100)",                "entry_float", _safe_float_str),
    ("early_access",         "Early Access",                  "check",       _bool_to_str),
    ("launch_executable",    "Default Launch Executable",     "entry",       str),
    ("launch_parameters",    "Default Launch Parameters",     "entry",       str),
    ("installer_executable", "Default Installer Executable",  "entry",       str),
    ("installer_parameters", "Default Installer Parameters",  "entry",       str),
]


class GameSettings(customtkinter.CTkToplevel):
    """A non-modal Toplevel that lets an admin edit a game's
    user_metadata via `PUT /api/games/{gid}`.

    Args:
        parent: the App. Used to refresh the game page after a
            successful save.
        gid: integer game ID.
        is_admin: when False, all mutating controls (Save, Wipe) are
            disabled and the inputs are read-only. Defaults to True
            so the dialog is usable as a read-only viewer if a caller
            forgets to pass it.

    The Toplevel does NOT call `grab_set()` — the user can keep
    switching tabs and queuing downloads while the dialog is open.
    """

    HELP_TEXT = (
        "Custom Metadata overrides the provider-supplied values for this "
        "game. Fields left blank fall back to the provider's data. Use "
        "Wipe Custom Metadata to clear every override in one go."
    )

    def __init__(self, parent, gid, is_admin=True):
        super().__init__(parent)
        self.parent = parent
        self.gid = gid
        self.is_admin = bool(is_admin)

        # The values we loaded from the server, keyed by FIELDS key.
        # We diff against this on save so we only send fields the user
        # actually changed — keeps the PUT body small and avoids
        # accidentally overwriting a provider field with a stale None.
        self._loaded = {}

        # The widget for each field, keyed by FIELDS key. For "entry"
        # / "entry_int" / "entry_float" we store the CTkEntry; for
        # "text" the CTkTextbox; for "check" a dict
        # {"var": StringVar, "widget": CTkCheckBox}.
        self._widgets = {}

        self.title("Game Settings")
        # Use a smaller initial size than 1100x780 so the dialog
        # fits on common 1920x1080 / 1080p / 1440p displays. The
        # window can still be resized by the user — `minsize` is
        # the floor. On a 4K screen, the user can grow it; on 1080p
        # they get a usable dialog by default.
        self.geometry("900x650")
        self.minsize(820, 580)
        # Centre the dialog on the parent. `winfo_screenwidth` /
        # `winfo_screenheight` return the logical-pixel size of the
        # parent's screen — same units `self.geometry()` takes.
        # On a DPI-scaled monitor, this is the value to use for
        # offsets; using `parent.winfo_width()` (physical pixels)
        # gives a result that's too far right because the actual
        # rendered parent is bigger than its own logical size.
        try:
            self.update_idletasks()
            sw = int(self.winfo_screenwidth())
            sh = int(self.winfo_screenheight())
            self.update_idletasks()
            dw = int(self.winfo_reqwidth())
            dh = int(self.winfo_reqheight())
            # Clamp to the screen so a huge window doesn't get
            # pushed off the right/bottom edge.
            x = max(0, (sw - dw) // 2)
            y = max(0, (sh - dh) // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            # Fall back to default positioning on any error.
            pass

        # ----------------------------------------------------------------
        # Top: header (title + help + close) + subtitle
        # ----------------------------------------------------------------
        header = customtkinter.CTkFrame(self, fg_color="transparent")
        header.pack(side="top", fill="x", padx=16, pady=(14, 6))
        header.columnconfigure(0, weight=1)

        title_label = customtkinter.CTkLabel(
            header,
            text="Custom Metadata",
            font=(None, 18, "bold"),
            anchor="w",
        )
        title_label.grid(row=0, column=0, sticky="w")

        help_btn = customtkinter.CTkButton(
            header, text="?", width=32,
            command=self._on_help_clicked,
        )
        help_btn.grid(row=0, column=1, padx=(0, 6))

        close_btn = customtkinter.CTkButton(
            header, text="✕", width=32,
            fg_color="#4a4a4a", hover_color="#5a5a5a",
            command=self._on_close_clicked,
        )
        close_btn.grid(row=0, column=2)

        subtitle = customtkinter.CTkLabel(
            self,
            text=(
                "Overwrite any existing metadata with custom values. "
                "Fields left blank will fall back to the provider data."
            ),
            anchor="w",
            text_color="#bbbbbb",
        )
        subtitle.pack(side="top", fill="x", padx=16, pady=(0, 6))

        # ----------------------------------------------------------------
        # Wipe button row (right-aligned)
        # ----------------------------------------------------------------
        wipe_row = customtkinter.CTkFrame(self, fg_color="transparent")
        wipe_row.pack(side="top", fill="x", padx=16, pady=(0, 8))
        wipe_row.columnconfigure(0, weight=1)

        self.wipe_btn = customtkinter.CTkButton(
            wipe_row,
            text="Wipe Custom Metadata",
            fg_color="#a83232", hover_color="#c53838",
            command=self._on_wipe_clicked,
        )
        self.wipe_btn.grid(row=0, column=1, sticky="e")
        if not self.is_admin:
            self.wipe_btn.configure(state="disabled")

        # ----------------------------------------------------------------
        # Body: scrollable form. expand=True so it consumes the
        # remaining vertical space between the wipe row above and the
        # bottom bar below.
        # ----------------------------------------------------------------
        self.body = customtkinter.CTkScrollableFrame(self)
        self.body.pack(side="top", fill="both", expand=True, padx=16, pady=(0, 8))
        self.body.columnconfigure(0, weight=0)  # label column (fixed)
        self.body.columnconfigure(1, weight=1)  # widget column (grows)

        self._build_fields()

        # ----------------------------------------------------------------
        # Bottom: status line + info bar + save button.
        # Packed bottom-up so the visual order is: form (top),
        # wipe row, status, info, save button (bottom).
        # ----------------------------------------------------------------
        self.status_label = customtkinter.CTkLabel(
            self, text="", anchor="w", text_color="#aaaaaa", height=18,
        )
        self.status_label.pack(side="bottom", fill="x", padx=16, pady=(4, 0))

        bottom = customtkinter.CTkFrame(self, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=16, pady=(4, 14))
        bottom.columnconfigure(0, weight=1)

        self.info_label = customtkinter.CTkLabel(
            bottom,
            text="",
            anchor="w",
            justify="left",
            text_color="#cccccc",
        )
        self.info_label.grid(row=0, column=0, sticky="w")

        self.save_btn = customtkinter.CTkButton(
            bottom, text="💾 Save", width=120,
            fg_color="#3d9e3d", hover_color="#4cb84c",
            command=self._on_save_clicked,
        )
        self.save_btn.grid(row=0, column=1, sticky="e")
        if not self.is_admin:
            self.save_btn.configure(state="disabled")

        # ----------------------------------------------------------------
        # Populate the form from the current game, snapshot loaded
        # values, fill the bottom info bar.
        # ----------------------------------------------------------------
        self._load()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _build_fields(self):
        """Create one row per FIELDS entry. Each row is a 2-column
        grid: label on the left, the input on the right. Single-line
        text fields fill the row; multi-line text fields get a fixed
        height."""
        for row_idx, (key, label, kind, _) in enumerate(FIELDS):
            lbl = customtkinter.CTkLabel(
                self.body, text=label, anchor="e", width=220,
            )
            lbl.grid(row=row_idx, column=0, sticky="ne", padx=(0, 12), pady=6)

            if kind == "text":
                widget = customtkinter.CTkTextbox(self.body, wrap="word", height=80)
                widget.grid(row=row_idx, column=1, sticky="ew", pady=6)
                self._widgets[key] = widget
            elif kind == "check":
                var = customtkinter.StringVar(value="0")
                widget = customtkinter.CTkCheckBox(
                    self.body, text="",
                    variable=var,
                    onvalue="1", offvalue="0",
                )
                widget.grid(row=row_idx, column=1, sticky="w", pady=6)
                self._widgets[key] = {"var": var, "widget": widget}
            else:  # entry / entry_int / entry_float
                widget = customtkinter.CTkEntry(self.body, placeholder_text="")
                widget.grid(row=row_idx, column=1, sticky="ew", pady=6)
                self._widgets[key] = widget
            if not self.is_admin:
                self._set_field_disabled(key, True)

    def _set_field_disabled(self, key, disabled):
        """Toggle a single field's input. Entries go to state='disabled';
        checkboxes to state='disabled'; textboxes to state='disabled'."""
        w = self._widgets[key]
        if isinstance(w, dict):
            try:
                w["widget"].configure(state="disabled" if disabled else "normal")
            except Exception:
                pass
        else:
            try:
                w.configure(state="disabled" if disabled else "normal")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def _load(self):
        """Pull the current game, populate every field, snapshot the
        loaded values for the diff-on-save step, fill the bottom info
        bar."""
        info = fetch_game_info(self.gid) or {}
        umd = info.get("user_metadata") or {}
        md = info.get("metadata") or {}

        # Pre-fill from user_metadata first; fall back to metadata
        # (provider data) for fields the admin hasn't customized yet;
        # fall back to "" if neither has a value. This way a fresh
        # game shows the actual title/description/rating, not blanks.
        #
        # `_loaded` stores the python-typed value (int / float / bool /
        # str / None), NOT the stringified version that goes into the
        # entry widget. The save path diffs against `_loaded` to avoid
        # sending every field on every save (a string "1060" would
        # otherwise look different from int 1060 even though they're
        # semantically equal).
        for key, _label, kind, converter in FIELDS:
            raw = umd.get(key)
            if raw is None:
                raw = md.get(key)
            if kind == "check":
                self._widgets[key]["var"].set("1" if raw else "0")
                self._loaded[key] = bool(raw)
            elif kind == "text":
                value = "" if raw is None else str(raw)
                self._widgets[key].delete("0.0", "end")
                self._widgets[key].insert("0.0", value)
                self._loaded[key] = value
            elif kind == "entry_int":
                text = "" if raw is None else _safe_int_str(raw)
                self._widgets[key].delete(0, "end")
                self._widgets[key].insert(0, text)
                self._loaded[key] = None if raw is None else _try_int(raw)
            elif kind == "entry_float":
                text = "" if raw is None else _safe_float_str(raw)
                self._widgets[key].delete(0, "end")
                self._widgets[key].insert(0, text)
                self._loaded[key] = None if raw is None else _try_float(raw)
            else:  # entry
                text = "" if raw is None else str(raw)
                self._widgets[key].delete(0, "end")
                self._widgets[key].insert(0, text)
                self._loaded[key] = text

        # Bottom info: "Title (year)  ·  ID gid  ·  Version v  ·  Installed v"
        title = (
            umd.get("title")
            or md.get("title")
            or info.get("title")
            or f"Game {self.gid}"
        )
        release = umd.get("release_date") or md.get("release_date")
        year = ""
        if release:
            # ISO 8601: take the first 4 chars as the year
            year = str(release)[:4]
        version = umd.get("version") or info.get("version") or "N/A"
        # Installed version lives in the local install dir, not on the
        # server. We don't have a portable way to read it here; show
        # "N/A" and let the game page surface the real value.
        installed_version = "N/A"

        line1 = f"{title}" + (f" ({year})" if year else "")
        self.info_label.configure(
            text=(
                f"{line1}\n"
                f"ID {self.gid}  ·  Version {version}  ·  "
                f"Installed Version {installed_version}"
            )
        )
        self.title(f"Game Settings — {title}")

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def _collect_current(self):
        """Return a dict {key: current_python_value} for every field,
        using the loaded raw types (int / float / bool / str). Empty
        entries become None so the server treats them as 'clear this
        override' rather than an empty string."""
        out = {}
        for key, _label, kind, _converter in FIELDS:
            w = self._widgets[key]
            if kind == "check":
                out[key] = (w["var"].get() == "1")
            elif kind == "text":
                out[key] = w.get("0.0", "end").rstrip("\n")
            else:
                text = w.get()
                if text == "":
                    out[key] = None
                elif kind == "entry_int":
                    try:
                        out[key] = int(text)
                    except ValueError:
                        raise ValueError(
                            f"{key}: '{text}' is not a whole number"
                        )
                elif kind == "entry_float":
                    try:
                        out[key] = float(text)
                    except ValueError:
                        raise ValueError(f"{key}: '{text}' is not a number")
                else:
                    out[key] = text
        return out

    def _on_save_clicked(self):
        if not self.is_admin:
            return
        try:
            current = self._collect_current()
        except ValueError as e:
            self._set_status(str(e), error=True)
            return

        # Build the diff. Only send fields the user actually changed.
        # For check, send the new value if it changed. For text/str,
        # treat None and "" as the same "cleared" state for the diff;
        # otherwise typed-string "abc" vs server-stored "abc" would
        # round-trip and trigger a pointless PUT.
        payload = {}
        for key, _label, kind, _ in FIELDS:
            new = current[key]
            old = self._loaded.get(key)
            if kind == "check":
                if new != old:
                    payload[key] = new
            else:
                if (new in (None, "") and old in (None, "")):
                    continue
                if new == old:
                    continue
                payload[key] = new

        if not payload:
            self._set_status("No changes to save.", error=False)
            return

        self._set_status("Saving…", error=False)
        self.save_btn.configure(state="disabled")

        result = update_game_user_metadata(self.gid, payload)
        if result is None:
            # update_game_user_metadata already logged the status code.
            # 403 is by far the most common in practice.
            self._set_status(
                "Save failed. If you are not an admin, this endpoint "
                "is read-only for you. See the log for details.",
                error=True,
            )
            self.save_btn.configure(state="normal")
            return

        # On success, refresh the game page so the new title /
        # description show up immediately. update_game_user_metadata
        # already invalidated the cache, so this re-fetches the
        # fresh values from the server.
        try:
            if self.parent is not None and hasattr(self.parent, "sidebar_callback"):
                self.parent.sidebar_callback(self.gid)
        except Exception as e:
            logging.debug(f"Post-save refresh failed: {e}")

        self._set_status("Saved.", error=False)
        # Auto-close on success. The user can re-open the dialog if
        # they want to make more changes.
        self.after(150, self._on_close_clicked)

    def _on_wipe_clicked(self):
        """Clear every override in one PUT. Sends an empty
        user_metadata so the server falls back to provider data for
        every field. Confirm first — destructive but cheap to recover
        from (just re-save)."""
        if not self.is_admin:
            return
        ok = self._confirm(
            title="Wipe Custom Metadata?",
            message=(
                "This will clear every custom override for this game. "
                "The provider-supplied metadata will be used instead. "
                "Continue?"
            ),
            confirm_label="Wipe",
        )
        if not ok:
            return

        self._set_status("Wiping…", error=False)
        # Empty payload == clear every field. The server stores an
        # empty/null user_metadata and falls back to provider data.
        result = update_game_user_metadata(self.gid, {})
        if result is None:
            self._set_status("Wipe failed. See the log for details.", error=True)
            return
        # Reload the form from the now-empty user_metadata so the
        # user sees the provider values, then refresh the game page.
        self._load()
        try:
            if self.parent is not None and hasattr(self.parent, "sidebar_callback"):
                self.parent.sidebar_callback(self.gid)
        except Exception:
            pass
        self._set_status("Wiped. Showing provider data.", error=False)

    def _on_close_clicked(self):
        try:
            self.destroy()
        except Exception:
            pass

    def _on_help_clicked(self):
        self._confirm(
            title="About Custom Metadata",
            message=self.HELP_TEXT,
            confirm_label="OK",
            is_info=True,
        )

    def _confirm(self, title, message, confirm_label, is_info=False):
        """Show a confirmation dialog. Returns True if the user picked
        `confirm_label`, False on cancel. Prefers CTkMessagebox when
        available; falls back to tkinter.messagebox otherwise so the
        dialog still works on installs without CTkMessagebox."""
        if _HAVE_CTK_MSGBOX:
            try:
                choice = CTkMessagebox(
                    title=title,
                    message=message,
                    icon="info" if is_info else "warning",
                    option_1="Cancel",
                    option_2=confirm_label,
                ).get()
                return choice == confirm_label
            except Exception:
                pass
        # tk fallback
        try:
            return bool(tkinter.messagebox.askyesno(title, message))
        except Exception:
            # If even the fallback is broken, default to "no" so
            # destructive actions don't fire by accident.
            return False

    # ------------------------------------------------------------------
    # Status line
    # ------------------------------------------------------------------

    def _set_status(self, text, error=False):
        """Show a transient message in the status line. Errors are red,
        success/info is muted grey. Auto-clears after 4s for success
        messages; errors stay until the user changes a field or saves."""
        try:
            self.status_label.configure(
                text=text,
                text_color="#ff8888" if error else "#aaaaaa",
            )
        except Exception:
            return
        if not error:
            try:
                self.after(4000, lambda: self._clear_status_if_same(text))
            except Exception:
                pass

    def _clear_status_if_same(self, expected):
        try:
            if self.status_label.cget("text") == expected:
                self.status_label.configure(text="", text_color="#ff8888")
        except Exception:
            pass
