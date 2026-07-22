from PIL import Image
import customtkinter
import os
import logging
import platform
import subprocess
import threading
from platformdirs import *
from CTkMenuBar import *
from bin.util import *
from bin.tabview import MyTabView
from bin.sidebar import Sidebar
import dateparser
from bin.GUI.game_settings import GameSettings
from bin.GUI.admin_settings import AdminSettings
from bin.GUI.gvse_settings import GVSESettings
from bin.GUI.settings_wizard import InstallWizard
from bin.download_manager import DownloadManager


# Set appearance mode and default color theme
customtkinter.set_appearance_mode(config['SETTINGS'].get('apperance'))  # Modes: "System" (standard), "Dark", "Light"
customtkinter.set_default_color_theme(config['SETTINGS'].get('theme'))  # Themes: "blue" (standard), "green", "dark-blue"




class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        logging.debug(username)
        logging.debug(install_location)
        logging.debug(url)
        os_type = platform.system()
        logging.debug(os_type)
        # configure window
        self.title(f"{appname} - Online: {online_status}")
        self.geometry("1200x600")
        self.minsize(1200, 600)
        # Configure Grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Menu bar
        self.menu = CTkMenuBar(self)
        self.menu.grid(row=0, column=0, sticky="new", columnspan=2)
        button_1 = self.menu.add_cascade("View")
        button_2 = self.menu.add_cascade("Settings")
        button_3 = self.menu.add_cascade("About")
        dropdown1 = CustomDropdownMenu(widget=button_1)
        dropdown1.add_option(option="Light theme", command=lambda: self.change_appearance_mode_event("Light"))
        dropdown1.add_option(option="Dark theme", command=lambda: self.change_appearance_mode_event("Dark"))
        dropdown1.add_option(option="System theme", command=lambda: self.change_appearance_mode_event("System"))
        dropdown2 = CustomDropdownMenu(widget=button_2)
        # Capture the "Admin Panel" option widget so we can
        # disable it later based on the current user's role. The
        # endpoint behind it (PUT /api/users/{id}) is admin-only
        # and we don't want a non-admin to click through and get
        # a 403 on every action. App Settings stays enabled for
        # everyone.
        # The command is wrapped in a role check so a non-admin
        # who somehow gets past the disabled option (e.g. via
        # keyboard focus) is still blocked at click time.
        self._admin_panel_option = dropdown2.add_option(
            option="Admin Panel", command=self._open_admin_panel,
        )
        dropdown2.add_option(option="App Settings", command=lambda: GVSESettings(self))
        dropdown2.add_option(option="Settings Wizard", command=lambda: InstallWizard(self))
        dropdown3 = CustomDropdownMenu(widget=button_3)
        dropdown3.add_option(option="Server News", command=lambda: self._kickoff_news_load(initial=False))
        dropdown3.add_option(option="Credits", command=lambda: print("open about here"))
        if config['SETTINGS'].get('debug') == 'True':
            button_4 = self.menu.add_cascade("Debug")
            dropdown4 = CustomDropdownMenu(widget=button_4)
            dropdown4.add_option(option="Clear Cache", command=lambda: clear_cache())

        # Sidebar + main content. The sidebar enforces its own
        # dark grey background; the App just needs to pick
        # something close. (See bin/sidebar.py — the inner
        # `logo_frame` and `controls_frame` are also dark grey, so
        # the entire sidebar reads as one solid colour top-to-
        # bottom.)
        self.sidebar = Sidebar(master=self, fg_color="transparent", callback=self.sidebar_callback)
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.rowconfigure(1, weight=1)
        self.tab_view = MyTabView(master=self, anchor="s", fg_color="transparent")
        self.tab_view.grid(row=1, column=1, sticky="nsew")
        self.tab_view.rowconfigure(0, weight=1)

        # Download manager
        self.download_manager = DownloadManager()

        # Wire the Downloads tab's per-row actions to a single
        # dispatcher. The right-side progress panel / pause / stop /
        # resume buttons are gone — each row carries its own buttons
        # and routes through `_handle_download_action` below.
        self.tab_view.set_action_handler(self._handle_download_action)

        # Screenshot loader bookkeeping. The sidebar click kicks off a
        # background thread that does network I/O; the UI updates when
        # the thread finishes. `self._ss_current_gid` is the gid the
        # running thread is for — when the user switches games, the
        # callback compares against it and ignores the stale result.
        self._ss_thread = None
        self._ss_current_gid = None
        self._ss_lock = threading.Lock()

        # Install pipeline bookkeeping. We allow multiple gids to
        # install concurrently (limited only by disk bandwidth), but
        # guard against re-clicking Install on the same gid while a
        # previous extract is still running. The set is mutated on
        # the UI thread; the worker thread never touches it.
        self._installing_gids: set[int] = set()

        # News loader bookkeeping. Mirrors the screenshot loader: a
        # background thread fetches the markdown, then hops back to the
        # UI thread via `self.after(0, ...)` to render it. The first-
        # load call lands under "Select a Game to View"; the menu entry
        # re-uses the same plumbing. Only one fetch is in flight at a
        # time — `_news_loading` is set on the UI thread before start().
        # `_news_pending_window` is the menu-driven Toplevel that the
        # in-flight callback will update in place so we don't end up
        # with a stale "Loading…" window plus a new content window.
        self._news_loading = False
        self._news_thread = None
        self._news_pending_window = None
        self._kickoff_news_load(initial=True)

        # First-run detection. `first_run` defaults to True in
        # bin/util.py when settings.ini doesn't exist, and is
        # flipped to False by the wizard's submit_credentials
        # method. We open the wizard as modal (grab_set) so the
        # user has to either complete setup or close the dialog
        # before interacting with the rest of the launcher. This
        # is the intended UX for a first-time launch: block
        # until the user has at least seen and dismissed the
        # wizard.
        #
        # We check after `self._kickoff_news_load` so the rest
        # of the UI is built before the modal pops. Otherwise
        # the user sees a brief flash of unstyled / half-built
        # widgets before the wizard appears on top.
        if config['SETTINGS'].get('first_run', 'True') == 'True':
            self._open_first_run_wizard()

        # Apply role-based state to the Admin Panel menu option. We
        # do this at startup (not lazily on first hover) so the
        # entry is correctly disabled for non-admins from the
        # beginning. `get_current_user_role` is cached in-memory
        # after the first call, so the second one in
        # `sidebar_callback` (when the user clicks a game) is free.
        self._update_admin_menu_state()

    # ------------------------------------------------------------------
    # Callbacks (formerly nested closures)
    # ------------------------------------------------------------------

    def sidebar_callback(self, gid):
        """Render the selected game in the main content area."""
        game_info = fetch_game_info(gid)
        # Tear down the whole placeholder (prelabel + news textbox + frame)
        # so the game_window_frame can take over the tab. If the user
        # already picked a game, the placeholder was destroyed on the
        # first click — fall back to the bare prelabel for safety.
        if hasattr(self.tab_view, "placeholder_frame"):
            try:
                self.tab_view.placeholder_frame.destroy()
            except Exception:
                pass
        else:
            self.tab_view.prelabel.destroy()
        self.tab_view.game_window_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        # Gate the gear button on admin role. The PUT endpoint
        # `/api/games/{gid}` is admin-only (GameVault role enum
        # 0=USER, 1=EDITOR, 2=ADMIN, 3=OWNER), so non-admins get a
        # disabled button + an "Admin only" tooltip instead of a
        # Save flow that will 403.
        role = get_current_user_role()
        is_admin = (role is not None and role >= 2)
        self.tab_view.game_config.configure(
            state="normal" if is_admin else "disabled",
            command=lambda: self.open_game_settings(gid, is_admin=is_admin),
        )
        # Attach a tooltip ONLY when the button is disabled. Admin
        # users don't need a tooltip — they have access.
        if not is_admin:
            self._attach_tooltip(
                self.tab_view.game_config,
                "Admin only — sign in as an admin to edit metadata",
            )

        metadata = (game_info or {}).get("metadata") or {}
        self.tab_view.game_name.configure(text=metadata.get("title") or "")

        # Description
        description = metadata.get("description")
        self.tab_view.description.configure(state="normal")
        self.tab_view.description.delete("0.0", "end")
        if description:
            self.tab_view.description.insert("0.0", description)
        self.tab_view.description.configure(state="disabled")

        # Release year
        release_date = metadata.get("release_date")
        if release_date:
            try:
                year = dateparser.parse(release_date).strftime("%Y")
            except Exception:
                year = "Unknown"
            self.tab_view.release_year.configure(text=f"Release Year: {year}")
        else:
            self.tab_view.release_year.configure(text="Release Year: Unknown")

        # Rating
        rating = metadata.get("rating")
        if rating is not None:
            self.tab_view.rating.configure(text=f"Rating: {round(rating, 2)}/100")
        else:
            self.tab_view.rating.configure(text="Rating: Unknown")

        # Version
        version = metadata.get("version")
        if version is not None:
            self.tab_view.version.configure(text=f"Version: {version}")
        else:
            self.tab_view.version.configure(text="Version: Unknown")

        # Box art. Force-read the image up front so a broken/empty file
        # surfaces as a clear error instead of leaving a stale placeholder on
        # screen, and assign a fresh CTkImage to the label so the displayed
        # bitmap actually changes.
        try:
            img_path = get_image(gid, boxart=True)
            pil_image = Image.open(img_path)
            pil_image.load()  # force the file read; raises if unreadable
            self.tab_view.game_image = customtkinter.CTkImage(
                size=(200, 300), light_image=pil_image, dark_image=pil_image
            )
            self.tab_view.game_image_label.configure(image=self.tab_view.game_image)
        except Exception as e:
            logging.warning(f"Could not load cover art for {gid} from {img_path}: {e}")
            placeholder = Image.open(resource_path("bin/img/not_found.jpg"))
            placeholder.load()
            self.tab_view.game_image = customtkinter.CTkImage(
                size=(200, 300), light_image=placeholder, dark_image=placeholder
            )
            self.tab_view.game_image_label.configure(image=self.tab_view.game_image)

        # Activity button: Play / Install / Download / "Not supported".
        # Branches on the *type* of game (W_P / W_S / W_SW / L_P / L_SW)
        # so a W_S game stops showing "Play" right after extraction —
        # it has to run setup.exe first. See `_game_install_state`
        # for the state machine.
        state = self._game_install_state(gid)
        ist = state["install_state"]
        if ist == "installed":
            # W_P / L_P → launch the .exe / .sh. W_S / L_S → either
            # launch whatever the installer deployed, or open
            # GameSettings where the user can re-run setup on demand.
            if state["kind"] == "setup":
                self.tab_view.activity_button.configure(
                    text="Play", command=lambda: self._launch_or_setup(gid)
                )
            else:
                self.tab_view.activity_button.configure(
                    text="Play", command=lambda: self.launch_game(gid)
                )
            logging.debug(
                f"Game {gid} (type={state['type']}) is installed. "
                f"Setting button to Play."
            )
        elif ist == "downloaded_ready":
            # W_P / L_P: extract and you're done.
            self.tab_view.activity_button.configure(
                text="Install",
                command=lambda: self._install_from_game_tab(gid),
            )
            logging.debug(
                f"Game {gid} (type={state['type']}) downloaded, "
                f"needs install."
            )
        elif ist == "downloaded_needs_setup":
            # W_S / L_S: extract, then run setup.exe in a Toplevel.
            self.tab_view.activity_button.configure(
                text="Install",
                command=lambda: self._install_from_game_tab(gid),
            )
            logging.debug(
                f"Game {gid} (type={state['type']}) downloaded, "
                f"needs setup."
            )
        elif ist == "unsupported":
            # W_SW / L_SW / unknown — don't show Play/Install. The
            # button is disabled and labelled so the user knows why.
            self.tab_view.activity_button.configure(
                text="Not supported", state="disabled", command=lambda: None
            )
            logging.debug(
                f"Game {gid} (type={state['type']}) is software — "
                f"not supported."
            )
        else:
            # not_downloaded
            self.tab_view.activity_button.configure(
                text="Download",
                command=lambda: self._enqueue_download(gid),
            )
            logging.debug(f"Game {gid} is not downloaded.")

        # EXE selector
        exes = get_exes(gid)
        if exes:
            self.tab_view.exe_selector.configure(values=exes)
            self.tab_view.exe_selector.set(get_exe_selection(gid))
        else:
            self.tab_view.exe_selector.configure(values=["Install to Play"])
            self.tab_view.exe_selector.set("Install to Play")

        # Screenshots: kick off a background thread so the network fetch
        # never blocks the UI. We do the URL discovery (read from
        # `game_info`, which is already in memory) on the UI thread so
        # games with no screenshots clear the strip immediately without
        # even showing the loading label.
        self._kickoff_screenshot_load(gid, game_info)

        self.tab_view.set("Game")

    def _screenshot_urls_for(self, game_info):
        """Pull `url_screenshots` out of `game_info` in the same order
        `get_screenshots` would: user_metadata first, then a single
        non-empty provider_metadata. URLs that match the game's
        `cover.source_url` or `background.source_url` are filtered out so
        the marketing hero/boxshot image doesn't show as a screenshot.
        Returns [] when no real screenshot URLs remain.
        """
        user_md = (game_info or {}).get("user_metadata") or {}
        urls = []
        if isinstance(user_md, dict):
            candidate = user_md.get("url_screenshots")
            if isinstance(candidate, list) and candidate:
                urls = [u for u in candidate if isinstance(u, str) and u]
        if not urls:
            for provider in (game_info or {}).get("provider_metadata") or []:
                if not isinstance(provider, dict):
                    continue
                candidate = provider.get("url_screenshots")
                if isinstance(candidate, list) and candidate:
                    urls = [u for u in candidate if isinstance(u, str) and u]
                    if urls:
                        break

        # Exclude any URL that appears as the cover's or background's
        # `source_url` in any metadata source — the server commonly lists
        # the marketing hero image as the last screenshot, which would
        # duplicate the cover.
        exclude = set()
        sources = []
        if isinstance(user_md, dict):
            sources.append(user_md)
        for provider in (game_info or {}).get("provider_metadata") or []:
            if isinstance(provider, dict):
                sources.append(provider)
        for src in sources:
            for field in ("cover", "background"):
                obj = src.get(field) or {}
                if isinstance(obj, dict):
                    s = obj.get("source_url")
                    if isinstance(s, str) and s:
                        exclude.add(s)

        if exclude:
            urls = [u for u in urls if u not in exclude]
        return urls

    def _kickoff_screenshot_load(self, gid, game_info):
        """Decide whether to fetch screenshots for `gid`, then either hide
        the strip (no URLs) or kick off a background fetch and render the
        results on the UI thread when it finishes.

        The thread's work is `get_screenshots(gid)`, which itself does
        on-disk + BLOB lookups and only hits the network for URLs that
        aren't cached. Once the thread is done, it schedules
        `_on_screenshots_ready` on the UI thread via `self.after(0, ...)`.
        Stale results (user switched games while the thread was running)
        are discarded by comparing the gid at completion time.
        """
        urls = self._screenshot_urls_for(game_info)
        if not urls:
            # No screenshots at all — hide the strip and drop any stale tiles.
            self.tab_view.clear_screenshots()
            with self._ss_lock:
                self._ss_current_gid = None
            return

        # Claim this gid so any prior in-flight thread for a different game
        # knows to drop its result. The old thread will still complete
        # but its `self.after` callback will see a mismatch and no-op.
        with self._ss_lock:
            self._ss_current_gid = gid

        self.tab_view.show_loading_screenshots()

        def worker():
            from bin.util import get_screenshots
            try:
                paths = get_screenshots(gid)
            except Exception as e:
                logging.warning(f"Screenshot fetch failed for {gid}: {e}")
                paths = []
            # Hand off to the UI thread.
            self.after(0, lambda: self._on_screenshots_ready(gid, paths))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        with self._ss_lock:
            self._ss_thread = thread

    def _on_screenshots_ready(self, gid, paths):
        """UI-thread callback: render `paths` if `gid` is still the current
        selection. Otherwise drop the result — the user already moved on.
        """
        with self._ss_lock:
            current = self._ss_current_gid
        if current != gid:
            logging.debug(f"Discarding stale screenshot result for {gid} (current is {current})")
            return

        if not paths:
            # Either every URL failed or this game has no real screenshots.
            self.tab_view.clear_screenshots()
            return

        # Replace the loading label with the real tiles.
        self.tab_view.update_screenshots(paths)

    def _kickoff_news_load(self, initial=False):
        """Fetch the server's news in a background thread and render it.

        On first load we populate the inline textbox in the Game tab
        under "Select a Game to View". When invoked from the menu
        (`initial=False`), we open a Toplevel window with the same
        content. A single in-flight fetch is allowed at a time;
        concurrent menu clicks while a fetch is running focus the
        in-flight window (and show a loading state) so the existing
        callback updates it in place — no duplicate windows.
        """
        from bin.util import fetch_server_news

        if self._news_loading:
            # A fetch is already in flight. The in-flight Toplevel
            # (if any) will be updated in place by the existing
            # callback when the fetch lands. Just bring it forward.
            if not initial and self._news_pending_window is not None:
                try:
                    self._news_pending_window.deiconify()
                    self._news_pending_window.lift()
                except Exception:
                    pass
            return

        self._news_loading = True
        # Create the pending Toplevel for the menu-driven path so
        # the user has immediate feedback. The fetch callback will
        # write the real content into this same window.
        pending = None
        if not initial:
            pending = self._create_news_window(
                "Loading server news…", grab=True
            )
        self._news_pending_window = pending

        def worker():
            try:
                text = fetch_server_news()
            except Exception as e:
                logging.debug(f"News fetch failed: {e}")
                text = None
            self.after(0, lambda: self._on_news_loaded(text, initial=initial))

        self._news_thread = threading.Thread(target=worker, daemon=True)
        self._news_thread.start()

    def _on_news_loaded(self, text, initial):
        """UI-thread callback: render the news body for the path that
        kicked off the fetch. A `None` text means the fetch failed
        (offline, auth error, non-2xx) — the inline textbox hides
        itself in that case so the placeholder area just shows the
        "Select a Game to View" label; the menu Toplevel is closed."""
        self._news_loading = False
        pending = self._news_pending_window
        self._news_pending_window = None
        if initial:
            if text:
                self.tab_view.set_news(text)
            else:
                # Failure: hide the textbox so the placeholder area
                # just shows the "Select a Game to View" label.
                try:
                    self.tab_view.news_widget.grid_remove()
                except Exception:
                    pass
            return

        # Menu-driven path: write into the pending Toplevel, or
        # close it on failure. Never open a second window.
        if pending is None:
            # Caller never opened one (shouldn't happen for the
            # menu path, but defend anyway).
            if text:
                self._create_news_window(text)
            return
        if text is None:
            try:
                pending.destroy()
            except Exception:
                pass
            return
        self._fill_news_window(pending, text)

    def _create_news_window(self, text, grab=False):
        """Open a fresh Toplevel with the news body. Returns the
        window, or None for a no-op call (text is None).

        `grab=True` makes the window modal — used for the initial
        loading state so the user knows to wait. The window's
        textbox is a real widget attribute so the fetch callback
        can rewrite its content in place via `_fill_news_window`."""
        if text is None:
            return None
        win = customtkinter.CTkToplevel(self)
        win.title(f"{appname} - Server News")
        win.geometry("700x500")
        win.minsize(500, 300)
        if grab:
            win.grab_set()
        box = customtkinter.CTkTextbox(win, wrap="word")
        box.pack(fill="both", expand=True, padx=10, pady=10)
        # Store the textbox on the window so `_fill_news_window`
        # can find it without re-walking the widget tree.
        win._news_box = box
        box.insert("0.0", text)
        box.configure(state="disabled")
        return win

    def _fill_news_window(self, win, text):
        """Replace the contents of an existing news Toplevel in place.
        Used by `_on_news_loaded` to populate the "Loading…" window
        with the real news text so we don't end up with two windows
        (a stale "Loading…" and a new one with the content)."""
        if win is None:
            return
        try:
            box = getattr(win, "_news_box", None)
            if box is None:
                # Fallback: walk the children looking for a Textbox.
                # Should not happen in practice.
                return
            box.configure(state="normal")
            box.delete("0.0", "end")
            box.insert("0.0", text)
            box.configure(state="disabled")
        except Exception as e:
            logging.debug(f"Could not update news window in place: {e}")

    def open_game_settings(self, gid, is_admin=True):
        """Open the Game Settings dialog for `gid`. The dialog is
        non-modal — the user can keep using the launcher while it's
        open. `is_admin` is passed in by `sidebar_callback` (which
        already fetched the role); defaults to True so manual
        callers don't have to think about it."""
        GameSettings(self, gid=gid, is_admin=is_admin)

    def _open_admin_panel(self):
        """Open the Admin Panel. The menu option is already gated
        on role via `_update_admin_menu_state`; this re-checks at
        click time as defense in depth (a non-admin who gets
        keyboard focus on the option should still be blocked)."""
        role = get_current_user_role()
        if role is None or role < 2:
            # Shouldn't happen — the option is disabled — but if
            # a user gets here via some other path, fail closed.
            return
        AdminSettings(self)

    def _open_first_run_wizard(self):
        """Open the Settings Wizard as a modal on first launch.

        Modal means `grab_set()` — the wizard captures all input
        until the user dismisses it. This is intentional: on
        first run, the launcher has no URL, no install location,
        and no credentials, so the user can't do anything useful
        until they've at least seen the wizard.

        Unlike the menu-driven InstallWizard(self) call, this
        helper exists so the wizard can be opened as a one-time
        setup step without leaving a residual `first_run: True`
        flag if the user closes the wizard without submitting
        (which they can do via the window's [×] button). The
        wizard only flips the flag inside submit_credentials,
        so closing without submitting is a no-op for the flag.
        """
        wizard = InstallWizard(self)
        wizard.grab_set()
        wizard.focus_set()

    def _update_admin_menu_state(self):
        """Enable / disable the Admin Panel menu option based on
        the current user's role. Mirrors the gear-button gating in
        `sidebar_callback` (which gates on the same role threshold
        for the same reason: the API endpoints are admin-only).

        Non-admins see the option greyed out with a hover
        tooltip — same UX as the disabled gear button. We don't
        HIDE the entry entirely because a non-admin who shares
        this launcher with an admin user would otherwise wonder
        where the feature is.

        Idempotent: called once at startup and could be called
        again at any time (e.g. on logout) without harm. The
        tooltip is attached only on the disabled branch and uses
        `_attach_tooltip`, which is already idempotent (only
        builds the floating Toplevel once and reuses it).
        """
        role = get_current_user_role()
        is_admin = (role is not None and role >= 2)
        if self._admin_panel_option is not None:
            self._admin_panel_option.configure(
                state="normal" if is_admin else "disabled",
            )
            if not is_admin:
                self._attach_tooltip(
                    self._admin_panel_option,
                    "Admin only — sign in as an admin to open",
                )

    def _attach_tooltip(self, widget, text, delay_ms=400):
        """Show `text` in a small floating Toplevel when the cursor
        hovers `widget`. CTkButton has no native tooltip; this is the
        ~20-line manual implementation.

        The tooltip is a `CTkToplevel` with `wm_overrideredirect(True)`
        (no window decorations), positioned a few px below the
        button. The tooltip is shared across the lifetime of the
        process — we just keep references on the function so the
        widget doesn't get GC'd while the user hovers.
        """
        # Lazily build the tooltip Toplevel the first time anyone
        # calls this. Re-used across every gear-button attach.
        state = getattr(self, "_tooltip_state", None)
        if state is None:
            tip = customtkinter.CTkToplevel(self)
            tip.wm_overrideredirect(True)
            tip.withdraw()  # hidden until first hover
            tip_label = customtkinter.CTkLabel(
                tip, text="", padx=8, pady=4,
                fg_color="#1f1f1f", text_color="#dddddd",
                corner_radius=4,
            )
            tip_label.pack(fill="both", expand=True)
            state = {"tip": tip, "label": tip_label, "after_id": None}
            self._tooltip_state = state

        def _show(_event=None):
            tip = state["tip"]
            label = state["label"]
            label.configure(text=text)
            # Position: a few px below the widget's screen position.
            # If the widget is no longer mapped (e.g. the game page
            # was torn down), bail.
            try:
                x = widget.winfo_rootx() + 4
                y = widget.winfo_rooty() + widget.winfo_height() + 4
            except Exception:
                return
            tip.wm_geometry(f"+{x}+{y}")
            tip.deiconify()

        def _hide(_event=None):
            try:
                state["tip"].withdraw()
            except Exception:
                pass

        def _schedule_show(event):
            # Coalesce repeated <Enter> events (focus + mouse) so the
            # tooltip doesn't flicker on every mouse jiggle.
            if state["after_id"] is not None:
                try:
                    self.after_cancel(state["after_id"])
                except Exception:
                    pass
            state["after_id"] = self.after(delay_ms, lambda: _show(event))

        def _cancel_show(_event=None):
            if state["after_id"] is not None:
                try:
                    self.after_cancel(state["after_id"])
                except Exception:
                    pass
                state["after_id"] = None
            _hide()

        widget.bind("<Enter>", _schedule_show, add="+")
        widget.bind("<Leave>", _cancel_show, add="+")
        # Also hide on button press — the dialog opening makes the
        # tooltip look stale.
        widget.bind("<Button-1>", _cancel_show, add="+")

    def _handle_download_action(self, action, gid):
        """Single dispatch point for every per-row action on the
        Downloads tab. Kept as a single method so the tab never needs
        to know about DownloadManager or auth headers — it just calls
        this with `(action, gid)`.

        Action catalogue:
          start    — promote queued → downloading; DownloadManager call
          pause    — DownloadManager.pause_download(gid)
          resume   — DownloadManager.resume_download(gid)
          stop     — DownloadManager.stop_download(gid) (keeps partial)
          remove   — drop a queued row without ever starting it
          install  — unpack_game + refresh sidebar; row goes away
          open     — open the downloads folder in the OS file manager
          clear    — drop a finished/failed row + delete its partial
          retry    — transition back to 'queued' (partial file kept)
        """
        if action == "start":
            self._start_download(gid)

        elif action == "pause":
            if self.download_manager.pause_download(gid):
                self.tab_view.set_status(gid, "paused")

        elif action == "resume":
            if self.download_manager.resume_download(gid):
                self.tab_view.set_status(gid, "downloading")

        elif action == "stop":
            if self.download_manager.stop_download(gid):
                # If the row was the active download, clear
                # `_active_gid` so the queue can promote the next
                # entry. `set_status` will also call
                # `_promote_next_queued` because the new status is
                # not 'downloading', but clearing the flag here is
                # required for the promotion to actually fire.
                info = self.tab_view.downloads.get(gid) or {}
                if info.get("status") == "downloading":
                    self.tab_view._active_gid = None
                self.tab_view.set_status(gid, "stopped")

        elif action == "remove":
            # Drop a queued row without ever starting it. No network call.
            info = self.tab_view.downloads.get(gid)
            if info and info["status"] == "queued":
                try:
                    info["frame"].destroy()
                except Exception:
                    pass
                self.tab_view.downloads.pop(gid, None)
                self.tab_view._refresh_header()

        elif action == "install":
            self._install_from_downloads(gid)

        elif action == "open":
            self._open_downloads_folder(gid)

        elif action == "clear":
            self._clear_download_row(gid)

        elif action == "retry":
            # The retry path keeps the on-disk partial file so
            # DownloadManager's HTTP Range resume picks up where it
            # left off. The row just transitions back to 'queued'
            # and the queue machinery promotes it.
            info = self.tab_view.downloads.get(gid)
            if info:
                info["error"] = None
                info["progress"] = 0.0
                self.tab_view.set_status(gid, "queued")

    def _enqueue_download(self, gid):
        """Add a download row in 'queued' state. The queue machinery
        in MyTabView will promote it to 'downloading' automatically
        if no other download is in flight.

        Called by the Game tab's "Download" activity button. Reads
        the type tag from the filename and stashes `game_type` /
        `kind` on the row so `_install_from_downloads` can branch
        on them later (W_P → extract, W_S → setup Toplevel, W_SW →
        "not supported" error).
        """
        from bin.util import (
            detect_game_type, install_kind_for, get_download_info_for_gid,
        )

        download_url, download_path, filename = get_download_info_for_gid(gid)
        game_type = detect_game_type(filename) if filename else None
        kind = install_kind_for(game_type) if game_type else "extract"

        if not download_url:
            # No URL — surface the failure as a row in the list so the
            # user sees what went wrong, then bail.
            self.tab_view.add_download(
                gid=gid, title=f"Game {gid}", download_path="",
                download_url="", headers={}, filename=filename or "",
                game_type=game_type, kind=kind,
            )
            # Force the row into the error state immediately; the
            # add_download call would otherwise have promoted it.
            self.tab_view.set_status(gid, "error", error="Failed to get download info")
            self.tab_view.set("Downloads")
            return

        self.tab_view.add_download(
            gid=gid,
            title=filename or f"Game {gid}",
            download_path=download_path,
            download_url=download_url,
            headers={},  # filled in by _start_download (fresh JWT)
            filename=filename or "",
            game_type=game_type,
            kind=kind,
        )
        self.tab_view.set("Downloads")

    def _start_download(self, gid):
        """Start (or kick off) a download for `gid`. Called by
        `_handle_download_action("start", gid)` — the tab's queue
        machinery is what decides which gid gets to run.
        """
        from bin.util import get_auth_headers

        info = self.tab_view.downloads.get(gid)
        if not info:
            return

        download_url = info["download_url"]
        download_path = info["download_path"]
        filename = info["filename"]

        if not download_url:
            self.tab_view.set_status(gid, "error", error="Failed to get download info")
            self.tab_view._active_gid = None
            self.tab_view._promote_next_queued()
            return

        # Re-fetch headers every time — JWT may have expired since
        # the row was created (long-lived rows for queued games).
        headers = get_auth_headers('jwt')
        headers['Accept'] = 'application/octet-stream, application/zip, application/x-rar, */*'
        info["headers"] = headers

        def progress_callback(progress):
            self.after(0, lambda p=progress: self.tab_view.set_progress(gid, p))

        def complete_callback(success, message):
            def finalize():
                if success:
                    self.tab_view.set_status(gid, "complete")
                else:
                    self.tab_view.set_status(gid, "error", error=message)
                # Whether the download succeeded or failed, the slot
                # is no longer "downloading" — promote the next
                # queued entry, if any.
                self.tab_view._active_gid = None
                self.tab_view._promote_next_queued()
            self.after(0, finalize)

        started = self.download_manager.start_download(
            gid=gid, url=download_url, filepath=download_path,
            headers=headers,
            progress_callback=progress_callback,
            complete_callback=complete_callback,
        )
        if not started:
            # Another download is already in flight for this gid.
            # (Shouldn't happen because we only promote when
            # _active_gid is None, but defend anyway.)
            self.tab_view.set_status(gid, "error", error="Failed to start download")
            self.tab_view._active_gid = None
            self.tab_view._promote_next_queued()

    def _install_from_downloads(self, gid):
        """Install a completed download and refresh the sidebar.
        Branches on the install kind the same way
        `_install_from_game_tab` does, so a download finished via
        the Downloads tab behaves identically to one started from
        the Game tab.

        Runs the actual extraction on a background thread so the
        Downloads row's progress bar can update while 7z works.
        The row's status flips to 'extracting' before the worker
        starts, and to 'complete' (setup kind) or to a drop
        (extract kind) when the worker finishes.
        """
        info = self.tab_view.downloads.get(gid)
        if not info:
            return
        kind = info.get("kind", "extract")
        game_type = info.get("game_type")

        if kind == "unsupported":
            self.tab_view.set_status(
                gid, "error",
                error=f"Software titles ({game_type}) are not yet supported",
            )
            return

        if gid in self._installing_gids:
            logging.debug(f"Install for game {gid} already in flight; ignoring")
            return
        self._installing_gids.add(gid)

        # Flip the row to 'extracting' so the bar appears and the
        # action buttons hide. Done on the UI thread (we're already
        # on it) before the worker starts.
        self.tab_view.set_status(gid, "extracting")

        def progress_cb(percent, current_file):
            # The callback runs on the worker thread. Marshal to
            # the UI thread for the widget update.
            self.after(
                0,
                lambda p=percent: self.tab_view.set_progress(gid, p),
            )

        def worker():
            from bin.util import unpack_game
            try:
                result = unpack_game(
                    gid, kind=kind, game_type=game_type,
                    progress_callback=progress_cb,
                )
            except Exception as e:
                logging.error(f"Install thread for {gid} crashed: {e}")
                result = {"ok": False, "kind": kind, "error": str(e)}

            # On the UI thread: surface the outcome and clean up.
            def finalize():
                try:
                    if not result["ok"]:
                        self.tab_view.set_status(
                            gid, "error",
                            error=f"Extract failed: {result.get('error', 'unknown')}",
                        )
                        return
                    if kind == "extract":
                        # Drop the row (install is done) and
                        # refresh the Game tab so the activity
                        # button flips to Play.
                        self._on_extract_done(gid)
                        return
                    # kind == "setup" — leave the row visible
                    # in 'complete' state so the user can see
                    # the install is in progress; it'll be
                    # cleared when they hit Clear on the row.
                    self._on_setup_extract_done(
                        gid, game_type, result.get("entry_point"),
                    )
                finally:
                    self._installing_gids.discard(gid)

            self.after(0, finalize)

        threading.Thread(target=worker, daemon=True).start()

    def _open_downloads_folder(self, gid):
        """Open the per-game download folder in the OS file manager.

        Falls back to the install_location/Downloads directory if the
        per-game path can't be resolved. Errors are logged but never
        raised — opening a folder is a side-channel, not a control
        flow primitive.
        """
        from bin.util import _get_download_path
        download_path, _ = _get_download_path(gid, path_only=True)
        if download_path:
            folder = os.path.dirname(download_path)
        else:
            install_location = config['SETTINGS'].get('install_location')
            folder = os.path.join(install_location, "Downloads") if install_location else None
        if not folder:
            logging.warning(f"Could not resolve downloads folder for {gid}")
            return
        try:
            if platform.system() == "Windows":
                os.startfile(folder)  # noqa: S606 — intentional user action
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            logging.warning(f"Could not open downloads folder: {e}")

    def _clear_download_row(self, gid):
        """Remove a finished/failed/stopped row from the list, and
        ask DownloadManager to delete the partial file (so a future
        retry starts from byte 0)."""
        self.download_manager.clear_partial(gid)
        info = self.tab_view.downloads.get(gid)
        if info:
            try:
                info["frame"].destroy()
            except Exception:
                pass
            self.tab_view.downloads.pop(gid, None)
            self.tab_view._refresh_header()

    def install_and_refresh(self, gid):
        """Install game and refresh sidebar. Kept as a back-compat
        shim around the new type-aware install pipeline — callers
        that don't know about kinds still get the old behaviour
        (extract the archive, treat the install as done)."""
        from bin.util import unpack_game, detect_game_type, install_kind_for, fetch_game_info

        info = fetch_game_info(gid) or {}
        file_path = info.get("file_path", "") or ""
        import urllib.parse
        decoded = urllib.parse.unquote(file_path) if file_path else f"Game {gid}.zip"
        filename = decoded.split("/")[-1]
        game_type = detect_game_type(filename)
        kind = install_kind_for(game_type) if game_type else "extract"

        result = unpack_game(gid, kind=kind, game_type=game_type)
        if result.get("ok"):
            # Rebuild the sidebar so the colour hint updates.
            # `_rebuild_sidebar` captures the current filter +
            # sort state, destroys the old sidebar, and rebuilds
            # a fresh one that picks up where the old one left
            # off.
            self._rebuild_sidebar(gid)
            logging.debug(f"Install complete for {gid}, refreshed sidebar")

    # ------------------------------------------------------------------
    # Type-aware install pipeline
    # ------------------------------------------------------------------

    def _game_install_state(self, gid):
        """Return a dict describing the install state of `gid`:

            {"type": "W_P"|"W_S"|"W_SW"|"L_P"|"L_SW"|None,
             "kind": "extract"|"setup"|"unsupported",
             "filename": str,           # e.g. "Game (W_P).zip"
             "install_state": "installed"
                              | "downloaded_ready"
                              | "downloaded_needs_setup"
                              | "not_downloaded"
                              | "unsupported"}

        Used by the Game tab's activity button and the install-
        from-downloads path to decide which action to expose.
        """
        from bin.util import (
            detect_game_type, install_kind_for, fetch_game_info,
            is_game_downloaded, is_game_installed,
        )

        info = fetch_game_info(gid) or {}
        file_path = info.get("file_path", "") or ""
        # Build the on-disk filename so we can detect the type from it.
        import urllib.parse
        decoded = urllib.parse.unquote(file_path) if file_path else f"Game_{gid}.zip"
        filename = decoded.split("/")[-1]
        game_type = detect_game_type(filename)
        kind = install_kind_for(game_type) if game_type else "extract"

        if kind == "unsupported":
            return {"type": game_type, "kind": "unsupported",
                    "filename": filename,
                    "install_state": "unsupported"}
        if is_game_installed(gid, game_type=game_type):
            return {"type": game_type, "kind": kind, "filename": filename,
                    "install_state": "installed"}
        if is_game_downloaded(gid):
            return {
                "type": game_type, "kind": kind, "filename": filename,
                "install_state": "downloaded_ready" if kind == "extract"
                                  else "downloaded_needs_setup",
            }
        return {"type": game_type, "kind": kind, "filename": filename,
                "install_state": "not_downloaded"}

    def _install_from_game_tab(self, gid):
        """Install the game the user picked on the Game tab.

        The Game tab doesn't carry its own progress bar — the user
        clicks Install and we route the work to the Downloads tab
        (switching to it if needed) so the row's progress bar
        drives the visual feedback. The actual install runs on a
        background thread; this method returns immediately.
        """
        state = self._game_install_state(gid)
        kind = state["kind"]
        game_type = state.get("type")

        if kind == "unsupported":
            logging.warning(
                f"Cannot install game {gid} ({game_type}): "
                f"software titles are not yet supported."
            )
            return

        if gid in self._installing_gids:
            logging.debug(f"Install for game {gid} already in flight; ignoring")
            return
        self._installing_gids.add(gid)

        # Make sure there is a Downloads row for this game. The
        # user may have already cleared the original download
        # row; we still need *some* row to host the progress bar.
        row_was_created = self._ensure_extracting_row(gid, state)
        if row_was_created:
            # Make sure the user can see the bar. We only switch
            # tabs if we just created the row — for an existing
            # row the user already has the Downloads tab open
            # (or has chosen to install from here intentionally).
            try:
                self.tab_view.set("Downloads")
            except Exception:
                pass

        # Disable the activity button while we work. The sidebar
        # callback re-renders the button, so this is just a
        # belt-and-braces guard for the case where the user is
        # already on the Game tab and tries to click again before
        # the worker finishes.
        try:
            self.tab_view.activity_button.configure(state="disabled")
        except Exception:
            pass

        def progress_cb(percent, current_file):
            self.after(
                0,
                lambda p=percent: self.tab_view.set_progress(gid, p),
            )

        def worker():
            from bin.util import unpack_game
            try:
                result = unpack_game(
                    gid, kind=kind, game_type=game_type,
                    progress_callback=progress_cb,
                )
            except Exception as e:
                logging.error(f"Install thread for {gid} crashed: {e}")
                result = {"ok": False, "kind": kind, "error": str(e)}

            def finalize():
                try:
                    if not result["ok"]:
                        # Drop the synthetic row (or flip the
                        # existing one to error). The user can
                        # retry by re-downloading.
                        err = f"Extract failed: {result.get('error', 'unknown')}"
                        existing = self.tab_view.downloads.get(gid)
                        if existing is not None:
                            self.tab_view.set_status(
                                gid, "error", error=err,
                            )
                        else:
                            logging.error(
                                f"Install for game {gid} failed and no row: {err}"
                            )
                        # Re-render the Game tab so the activity
                        # button goes back to "Install" — the
                        # user can retry after re-downloading.
                        self.sidebar_callback(gid)
                        return
                    if kind == "extract":
                        # Drop the row and flip the Game tab.
                        self._on_extract_done(gid)
                        return
                    # kind == "setup" — leave the row, open the
                    # setup Toplevel.
                    self._on_setup_extract_done(
                        gid, game_type, result.get("entry_point"),
                    )
                finally:
                    self._installing_gids.discard(gid)

            self.after(0, finalize)

        threading.Thread(target=worker, daemon=True).start()

    def _ensure_extracting_row(self, gid, state):
        """Make sure a Downloads row exists for `gid` in the
        'extracting' state. Returns True if a new row was created
        (the caller may want to switch to the Downloads tab),
        False if an existing row was reused.

        The Game tab's "Install" click can fire even when the
        user has already cleared the original Downloads row
        (because they finished installing once and do not need
        the row anymore — or because they got the game from
        elsewhere). When that happens we still want somewhere
        to put the progress bar, so we create a synthetic row
        on the fly.
        """
        existing = self.tab_view.downloads.get(gid)
        if existing is not None:
            # Flip the existing row to extracting. (For a
            # 'complete' row that is already done downloading,
            # this is exactly what we want. For an 'error' or
            # 'stopped' row it is a retry-via-install path.)
            self.tab_view.set_status(gid, "extracting")
            return False

        # Build a synthetic row. We need a title and filename so
        # the row looks like a normal download.
        from bin.util import fetch_game_info, _get_download_path
        info = fetch_game_info(gid) or {}
        title = (info.get("title") or f"Game {gid}")
        # The download path is just metadata for the row —
        # the synthetic row never actually downloads.
        download_path, _ = _get_download_path(gid)
        download_path = download_path or ""
        filename = os.path.basename(download_path) if download_path else (
            f"({gid}){title}"
            + (f" {state.get('type')}" if state.get("type") else "")
            + ".zip"
        )

        self.tab_view.add_download(
            gid=gid,
            title=title,
            download_path=download_path,
            download_url="",       # no actual download
            headers={},
            filename=filename,
            game_type=state.get("type"),
            kind=state.get("kind", "extract"),
        )
        # Flip from "queued" (the default) to "extracting" so
        # the bar appears.
        self.tab_view.set_status(gid, "extracting")
        return True

    def _on_extract_done(self, gid):
        """UI-thread handler for a successful 'extract' install.
        Drops the Downloads row and refreshes the Game tab so the
        activity button flips to Play. The user can navigate
        back to the Game tab to see the updated state.
        """
        # Drop the row. `_clear_download_row` also asks
        # DownloadManager to delete the partial file — for a
        # synthetic row (no actual download) that is a no-op.
        self._clear_download_row(gid)
        # Refresh the Game tab so the activity button is up to
        # date. `sidebar_callback` re-renders the right pane;
        # `_refresh_after_install` rebuilds the sidebar so the
        # colour hint flips.
        self._refresh_after_install(gid)

    def _on_setup_extract_done(self, gid, game_type, entry_point):
        """UI-thread handler for a successful 'setup' install.
        Leaves the row visible (in 'complete' state — the user
        can see the install is in progress) and opens the
        SetupRunner Toplevel.
        """
        info = self.tab_view.downloads.get(gid)
        if info is not None:
            self.tab_view.set_status(gid, "complete")
        # The sidebar / Game tab still need a refresh so the
        # activity button moves off "Install" — for a W_S game
        # the new state is "Play" (which routes through
        # _launch_or_setup), and we want it to reflect that the
        # extract finished even though setup has not started yet.
        self._refresh_after_install(gid)
        if entry_point:
            self._open_setup_window(gid, game_type, entry_point)
    def _open_setup_window(self, gid, game_type, setup_exe):
        """Open a Toplevel that runs `setup_exe` in a subprocess
        and streams its stdout/stderr into a log. When the process
        exits with returncode 0, the install is marked complete
        and the sidebar is refreshed.

        The Toplevel is non-modal so the user can switch tabs
        while the installer runs. Closing the Toplevel does NOT
        cancel the subprocess — most installers need to run to
        completion regardless of whether the launcher window is
        open. The user can use Task Manager to actually kill it.
        """
        if not setup_exe or not os.path.exists(setup_exe):
            logging.error(
                f"Setup entry point not found for {gid}: {setup_exe!r}"
            )
            return None
        from bin.GUI.setup_runner import SetupRunner

        win = SetupRunner(
            master=self,
            gid=gid,
            game_type=game_type,
            setup_exe=setup_exe,
            on_complete=self._on_setup_finished,
        )
        return win

    def _on_setup_finished(self, gid, success, returncode):
        """UI-thread callback invoked by `SetupRunner` when the
        setup subprocess exits. Marks the install complete on
        success and refreshes the sidebar so the activity button
        flips to Play."""
        from bin.util import mark_setup_complete
        if success:
            mark_setup_complete(gid)
            logging.info(
                f"Setup for game {gid} completed (returncode={returncode})"
            )
        else:
            logging.warning(
                f"Setup for game {gid} failed (returncode={returncode})"
            )
        # Sidebar rebuild is the only UI work that needs the UI
        # thread. Safe to call from the runner's UI-thread callback.
        self._refresh_after_install(gid)

    def _refresh_after_install(self, gid):
        """Re-run `sidebar_callback(gid)` so the Game tab's activity
        button + EXE selector update to match the new install
        state. Also rebuilds the whole sidebar so the install
        colour hint for `gid` changes from "not installed" to
        "installed" — same as `install_and_refresh` did for the
        old code path."""
        # Re-render the current selection; this updates the
        # activity button + EXE selector to reflect the new state.
        self.sidebar_callback(gid)
        # The sidebar's per-game colour hint is set when the
        # sidebar is built, not when a single game is selected —
        # rebuild it so the just-installed game's hint flips.
        try:
            self._rebuild_sidebar(gid)
        except Exception as e:
            logging.warning(f"Could not refresh sidebar after install: {e}")

    def _rebuild_sidebar(self, gid=None):
        """Destroy and re-create the sidebar, preserving the current
        filter query and sort mode. Re-runs the sidebar callback
        for `gid` (or whatever was last selected) so the right
        pane stays in sync.

        The new `Sidebar` carries an `initial_state=` kwarg that
        restores the user's filter and sort, so this method is
        the only place to call when you want a clean rebuild.
        """
        # Capture state from the current sidebar before we
        # destroy it. If there is no sidebar yet (first launch),
        # fall back to the canonical empty defaults.
        if self.sidebar is not None:
            try:
                state = self.sidebar.get_state()
            except Exception:
                state = {"query": "", "sort": "Installed first"}
        else:
            state = {"query": "", "sort": "Installed first"}

        self.sidebar.destroy()
        self.sidebar = Sidebar(
            master=self,
            fg_color="transparent",
            callback=self.sidebar_callback,
            initial_state=state,
        )
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.rowconfigure(1, weight=1)
        # Re-select the same game so the right pane matches.
        if gid is not None:
            self.sidebar_callback(gid)

    def _launch_or_setup(self, gid):
        """W_S / L_S Play path. Tries to launch the exe the
        installer deployed; if no runnable is found, opens the
        SetupRunner Toplevel so the user can re-run setup.

        Most installers (Inno Setup, NSIS, etc.) drop the game
        .exe into the install dir after the user clicks through.
        The EXE selector will pick it up via `get_exes`. If for
        some reason the installer left nothing launchable (or the
        user wants to re-run setup), we fall through to opening
        the runner."""
        from bin.util import get_exes
        exes = get_exes(gid)
        if exes:
            self.launch_game(gid)
            return
        # No runnable in the install dir — the user likely wants
        # to re-run setup. Pull the original setup exe from the
        # install_path's previously-located entry point.
        from bin.util import _find_setup_entry, _get_download_path
        _, install_path = _get_download_path(gid, path_only=True)
        setup_exe = _find_setup_entry(install_path) if install_path else None
        if not setup_exe:
            logging.warning(
                f"No runnable or setup exe found for {gid}; cannot launch"
            )
            return
        self._open_setup_window(gid, None, setup_exe)

    def launch_game(self, gid):
        """Launch the game using the selected exe."""
        from bin.util import get_exe_selection
        exe_path = get_exe_selection(gid)
        if exe_path and exe_path != "Install to Play" and os.path.exists(exe_path):
            logging.debug(f"Launching game {gid}: {exe_path}")
            subprocess.Popen([exe_path])
        else:
            logging.warning(f"No valid exe selected for {gid}")

    def change_appearance_mode_event(self, new_appearance_mode: str):
        customtkinter.set_appearance_mode(new_appearance_mode)
        config['SETTINGS']['apperance'] = new_appearance_mode
        with open(settings_file, 'w') as configfile:
            config.write(configfile)


if __name__ == "__main__":
    app = App()
    app.mainloop()
