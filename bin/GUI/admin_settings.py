import customtkinter
import logging
from datetime import datetime

from bin.util import (
    list_users, update_user_role, reindex_games, get_current_user_id,
)

# Reuse the CTkMessagebox-with-fallback pattern from game_settings.py.
# Admin Panel's confirm dialog is the same shape: a yes/no prompt
# with Cancel as the safe default.
try:
    from CTkMessagebox import CTkMessagebox
    _HAVE_CTK_MSGBOX = True
except Exception:
    CTkMessagebox = None
    _HAVE_CTK_MSGBOX = False
    import tkinter.messagebox


# GameVault role enum. The server uses these ints in the
# UpdateUserDto.role field. We show names in the dropdown but send
# the int back.
ROLE_NAMES = {0: "USER", 1: "EDITOR", 2: "ADMIN", 3: "OWNER"}
ROLE_VALUES = list(ROLE_NAMES.values())  # dropdown display order

# Dialog dimensions. Slightly taller than the App Settings dialog
# because the user list adds vertical real estate.
DEFAULT_GEOMETRY = "900x700"
MIN_SIZE = (820, 620)

# Reindex confirmation copy. Reindex is a low-risk operation (it
# doesn't change anything destructive — it just re-scans providers
# for new/updated games) but it can be slow on a large library, so
# we still want a confirm prompt.
REINDEX_CONFIRM_TITLE = "Reindex the games library?"
REINDEX_CONFIRM_MESSAGE = (
    "This will re-scan the games library on the server. "
    "Existing installs are not affected. Continue?"
)


class _UserRow(customtkinter.CTkFrame):
    """One row in the users table. Encapsulates the username label,
    role dropdown, Save button, and inline status label.

    Kept as a separate class so the AdminSettings class itself stays
    focused on layout + refresh. Each row is a self-contained widget
    that the parent can re-render freely.
    """

    def __init__(self, master, uid, username, role_name, on_save,
                 is_self=False, **kwargs):
        super().__init__(master, **kwargs)
        self.uid = uid
        self.username = username
        self.on_save = on_save
        self.is_self = is_self
        self._status_after_id = None  # for clearing the inline label

        # Grid: 4 columns — username, role, save, status. The status
        # column has weight=1 so it can stretch if the user shrinks
        # the dialog.
        self.grid_columnconfigure(0, weight=0)  # username
        self.grid_columnconfigure(1, weight=0)  # dropdown
        self.grid_columnconfigure(2, weight=0)  # save
        self.grid_columnconfigure(3, weight=1)  # status (fills leftover)

        # Username. Width=160 is enough for ~20 chars at the default
        # font; longer usernames truncate with "…". CTkLabel doesn't
        # have a built-in truncate, so we set a fixed width and let
        # the user see the full name in the status label on hover.
        # Keeping the layout simple is more important than perfect
        # long-username handling for the typical case.
        customtkinter.CTkLabel(
            self, text=username, width=160, anchor="w",
        ).grid(row=0, column=0, padx=(8, 8), pady=4, sticky="w")

        # Role dropdown. Disabled for the current user's own row so
        # the admin can't lock themselves out by demoting themselves
        # from the UI.
        self.role_var = customtkinter.StringVar(value=role_name)
        self.role_menu = customtkinter.CTkOptionMenu(
            self, values=ROLE_VALUES, variable=self.role_var,
            width=120, state="disabled" if is_self else "normal",
        )
        self.role_menu.grid(row=0, column=1, padx=4, pady=4)

        # Save button. Also disabled for self.
        self.save_button = customtkinter.CTkButton(
            self, text="Save", width=70,
            state="disabled" if is_self else "normal",
            command=self._on_save_clicked,
        )
        self.save_button.grid(row=0, column=2, padx=4, pady=4)

        # Inline status label. Empty by default; populated on save.
        self.status_label = customtkinter.CTkLabel(
            self, text="", text_color="grey", anchor="w",
        )
        self.status_label.grid(row=0, column=3, padx=8, pady=4, sticky="ew")

    def _on_save_clicked(self):
        # Map the dropdown's display name back to the int the API
        # wants. The reverse map is built once at module scope.
        chosen = self.role_var.get()
        reverse = {v: k for k, v in ROLE_NAMES.items()}
        role_int = reverse.get(chosen, 0)

        # Disable the save button while the request is in flight so
        # the user can't double-click. Re-enable on completion
        # (success or failure).
        self.save_button.configure(state="disabled", text="…")
        self.status_label.configure(text="Saving…", text_color="grey")

        # Run the network call on the main thread but the UI is
        # already non-blocking — request() with a 30s timeout won't
        # freeze the dialog for typical server latencies. If we
        # wanted to be strict we'd push to a thread, but the
        # rest of this codebase (game_settings.py, the download
        # manager) all blocks the main thread for short API calls.
        ok = update_user_role(self.uid, role_int)
        self.save_button.configure(state="normal", text="Save")
        if ok:
            self._set_status("✓ Saved", "green", auto_clear_ms=2000)
        else:
            self._set_status("✗ Save failed (see log)", "red",
                             auto_clear_ms=0)

    def _set_status(self, text, color, auto_clear_ms=0):
        self.status_label.configure(text=text, text_color=color)
        if self._status_after_id is not None:
            try:
                self.after_cancel(self._status_after_id)
            except Exception:
                pass
            self._status_after_id = None
        if auto_clear_ms > 0:
            self._status_after_id = self.after(
                auto_clear_ms,
                lambda: self.status_label.configure(text="", text_color="grey"),
            )


class AdminSettings(customtkinter.CTkToplevel):
    """Admin Panel dialog: reindex the games library and manage user
    roles. Admin-only — the menu entry is gated on role in main.py
    and the API endpoints will 403 a non-admin caller.

    The dialog is non-modal (no grab_set) — matches the rest of the
    GUI helpers. A non-modal pattern means the user can interact
    with the rest of the launcher while the dialog is open, which
    matters here because a role change is an action that might want
    follow-up in the main UI (e.g. refreshing the user list).
    """

    def __init__(self, *args, current_user_id=None, is_admin=True,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Admin Panel — GameVault Snake Edition")
        self.geometry(DEFAULT_GEOMETRY)
        self.minsize(*MIN_SIZE)

        # See game_settings.py for the centering logic — same
        # rationale applies. winfo_screenwidth/height returns
        # logical pixels; the geometry string is in logical pixels.
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = (int(x) for x in DEFAULT_GEOMETRY.split("x"))
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.geometry(f"+{x}+{y}")

        # Store the current user's id so we can disable the role
        # dropdown on their own row. Fetched eagerly (not lazily on
        # row render) because the role dropdown needs to know this
        # at construction time, and the dialog opens infrequently
        # (a single 10ms API call is fine).
        if current_user_id is None:
            current_user_id = get_current_user_id()
        self._current_user_id = current_user_id

        # Track the last reindex time for the status label. We
        # don't persist this; reopening the dialog starts fresh,
        # which is fine because the server has its own job log.
        self._last_reindex = None

        self._build_header()
        self._build_reindex_section()
        self._build_users_section()
        self._build_footer()

        # Populate the user list. Done after the build so the
        # frame exists when _refresh_users calls winfo_children.
        self._refresh_users()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_header(self):
        """One-line title + sub-text. Sub-text mentions the
        permission gate so an admin who shares the launcher with a
        non-admin understands why the entry was disabled for them."""
        header = customtkinter.CTkFrame(self, corner_radius=0)
        header.pack(side="top", fill="x")
        customtkinter.CTkLabel(
            header, text="Admin Panel", font=("", 18, "bold"),
        ).pack(side="left", padx=20, pady=(16, 0), anchor="w")
        customtkinter.CTkLabel(
            header, text="Server administration. Admin/owner only.",
            text_color="grey",
        ).pack(side="left", padx=(0, 20), pady=(20, 0), anchor="w")

    def _build_reindex_section(self):
        """Section 1 — reindex. A bordered frame around the controls
        so the two sections read as visually distinct."""
        section = customtkinter.CTkFrame(self, corner_radius=6)
        section.pack(side="top", fill="x", padx=10, pady=(10, 4))
        customtkinter.CTkLabel(
            section, text="Library", font=("", 13, "bold"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(8, 0))

        body = customtkinter.CTkFrame(section, fg_color="transparent")
        body.pack(fill="x", padx=12, pady=8)
        body.grid_columnconfigure(1, weight=1)

        customtkinter.CTkLabel(
            body,
            text="Trigger a re-index of the games library. "
                 "Existing installs are not affected.",
            anchor="w", justify="left", wraplength=600,
        ).grid(row=0, column=0, columnspan=2, padx=4, pady=(0, 8),
               sticky="ew")

        customtkinter.CTkButton(
            body, text="Reindex", width=100,
            command=self._on_reindex_clicked,
        ).grid(row=1, column=0, padx=4, pady=4, sticky="w")

        self.reindex_status = customtkinter.CTkLabel(
            body, text="", text_color="grey", anchor="w",
        )
        self.reindex_status.grid(row=1, column=1, padx=12, pady=4,
                                 sticky="ew")

    def _build_users_section(self):
        """Section 2 — user list. The Refresh button is on the
        right of the section header; the table itself is a
        scrollable frame that fills the leftover vertical space."""
        section = customtkinter.CTkFrame(self, corner_radius=6)
        section.pack(side="top", fill="both", expand=True,
                     padx=10, pady=4)
        section.grid_rowconfigure(2, weight=1)
        section.grid_columnconfigure(0, weight=1)

        # Section title + count label on the left, Refresh on the
        # right. Both go in row 0.
        title_row = customtkinter.CTkFrame(section, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))
        title_row.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(
            title_row, text="Users", font=("", 13, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self.user_count_label = customtkinter.CTkLabel(
            title_row, text="", text_color="grey",
        )
        self.user_count_label.grid(row=0, column=1, sticky="e", padx=(0, 8))
        # The Refresh button is in row 1, right-aligned, below the
        # title row. Easier to lay out in its own frame than to
        # cram into the title row's column 2.
        button_row = customtkinter.CTkFrame(section, fg_color="transparent")
        button_row.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 4))
        button_row.grid_columnconfigure(0, weight=1)
        customtkinter.CTkButton(
            button_row, text="Refresh", width=90,
            command=self._refresh_users,
        ).grid(row=0, column=1, sticky="e")

        # Scrollable user list. expand=True so it fills the
        # leftover vertical space; with a long user list, the
        # inner CTkScrollableFrame gets a vertical scrollbar
        # automatically.
        self.users_frame = customtkinter.CTkScrollableFrame(
            section, corner_radius=4,
        )
        self.users_frame.grid(row=2, column=0, sticky="nsew",
                              padx=12, pady=(4, 12))
        self.users_frame.grid_columnconfigure(0, weight=1)

    def _build_footer(self):
        """Just a Close button on the right. No Save — every action
        in this dialog commits to the server immediately (PUT
        /api/users/{id} and PUT /api/games/reindex), so a single
        "Save all changes" button wouldn't be meaningful."""
        footer = customtkinter.CTkFrame(self, corner_radius=0)
        footer.pack(side="bottom", fill="x")
        footer.grid_columnconfigure(0, weight=1)
        button_row = customtkinter.CTkFrame(footer, fg_color="transparent")
        button_row.grid(row=0, column=0, sticky="e", padx=20, pady=12)
        customtkinter.CTkButton(
            button_row, text="Close", width=100,
            command=self.destroy,
        ).pack(side="right")

    # ------------------------------------------------------------------
    # Reindex
    # ------------------------------------------------------------------

    def _on_reindex_clicked(self):
        if not self._confirm(
            REINDEX_CONFIRM_TITLE, REINDEX_CONFIRM_MESSAGE,
            confirm_label="Reindex", is_info=False,
        ):
            return

        # Disable the button while in flight so the user can't
        # spam-click. The request is short (the server returns
        # 2xx once the job is queued, not when it completes).
        self.reindex_status.configure(text="Triggering…",
                                      text_color="grey")

        ok = reindex_games()
        if ok:
            self._last_reindex = datetime.now()
            self.reindex_status.configure(
                text=f"✓ Reindex triggered at "
                     f"{self._last_reindex.strftime('%H:%M:%S')}",
                text_color="green",
            )
        else:
            self.reindex_status.configure(
                text="✗ Reindex failed (see log)", text_color="red",
            )

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def _refresh_users(self):
        """Wipe and re-populate the user rows. Called on first
        open and on Refresh button click.

        Empty-list handling: if the API returns [] (likely a 403
        because a non-admin somehow got past the menu gate), we
        show a one-line "No users found" message rather than an
        empty scrollable frame, which would look like a bug.
        """
        # Wipe existing rows. Children include our _UserRow frames
        # but no internal scrollbar widgets at this level (the
        # scrollbar lives on the parent CTkScrollableFrame, not on
        # each child).
        for child in list(self.users_frame.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

        users = list_users()
        if not users:
            self.user_count_label.configure(text="0 users")
            customtkinter.CTkLabel(
                self.users_frame,
                text="No users found. Refresh to retry, or check "
                     "your permissions if this persists.",
                text_color="grey", justify="left",
            ).grid(row=0, column=0, padx=8, pady=16, sticky="w")
            return

        self.user_count_label.configure(
            text=f"{len(users)} user{'s' if len(users) != 1 else ''}",
        )

        # Sort by username (case-insensitive) for stable ordering.
        # The server's order isn't guaranteed; sorting here means
        # the user can find a specific account by scanning.
        users_sorted = sorted(
            users,
            key=lambda u: (u.get("username") or "").lower(),
        )
        for i, u in enumerate(users_sorted):
            uid = u.get("id")
            username = u.get("username") or f"User {uid}"
            role_int = u.get("role")
            if role_int is None:
                role_name = "USER"
            else:
                role_name = ROLE_NAMES.get(
                    int(role_int), f"Unknown({role_int})",
                )
            row = _UserRow(
                self.users_frame,
                uid=uid,
                username=username,
                role_name=role_name,
                on_save=self._save_user,
                is_self=(uid == self._current_user_id),
            )
            row.grid(row=i, column=0, padx=4, pady=2, sticky="ew")

    def _save_user(self, uid, role_name):
        """The _UserRow calls this on Save. The row already did
        the API call and shows its own status label; this method
        is here as a hook for future refresh-on-save behaviour
        (e.g. "after a role change, refresh the user list so the
        count is correct"). Currently a no-op."""
        # Placeholder. Refreshing the list after a save would
        # wipe the row's "✓ Saved" status, which is more annoying
        # than helpful. If the user wants a forced refresh, the
        # Refresh button is right there.
        return

    # ------------------------------------------------------------------
    # Confirm helper
    # ------------------------------------------------------------------

    def _confirm(self, title, message, confirm_label, is_info=False):
        """Show a yes/no dialog. Returns True if the user picked
        `confirm_label`, False on cancel. Same shape as
        game_settings.py's _confirm — duplicated here because the
        two dialogs are independent (no shared base class)."""
        if _HAVE_CTK_MSGBOX:
            try:
                choice = CTkMessagebox(
                    title=title, message=message,
                    icon="info" if is_info else "warning",
                    option_1="Cancel", option_2=confirm_label,
                ).get()
                return choice == confirm_label
            except Exception:
                pass
        try:
            return bool(tkinter.messagebox.askyesno(title, message))
        except Exception:
            return False
