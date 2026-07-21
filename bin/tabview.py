import customtkinter
from platformdirs import *
import os
import configparser
from .util import *
import notifypy
import functools
notifypy.Notify._selected_notification_system = functools.partial(notifypy.Notify._selected_notification_system, override_windows_version_detection=True)
from PIL import Image


install_dir = config['SETTINGS'].get('install_location')

class MyTabView(customtkinter.CTkTabview):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)


        
        # create tabs
        self.add("Game")
        self.add("Downloads")
        self.tab("Game").rowconfigure(0, weight=1)
        self.tab("Game").columnconfigure(0, weight=1)
        self.tab("Downloads").rowconfigure(0, weight=1)
        self.tab("Downloads").columnconfigure(0, weight=1)

        # START GAME TAB
        # Placeholder area shown when no game is selected. Holds the
        # "Select a Game to View" label plus an inline news display
        # that is populated once at startup (and re-populated on
        # demand from the menu). Both are destroyed by
        # `App.sidebar_callback` the moment the user picks a game.
        self.placeholder_frame = customtkinter.CTkFrame(self.tab("Game"), fg_color="transparent")
        self.placeholder_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.placeholder_frame.columnconfigure(0, weight=1)
        self.placeholder_frame.rowconfigure(0, weight=0)
        self.placeholder_frame.rowconfigure(1, weight=1)

        self.prelabel = customtkinter.CTkLabel(self.placeholder_frame, text="Select a Game to View", anchor="n", font=(None, 20))
        self.prelabel.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        self.news_widget = customtkinter.CTkTextbox(self.placeholder_frame, wrap="word", state="disabled")
        self.news_widget.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        # Hidden on construction — `set_news` is the only path that
        # reveals it. Avoids a "Loading…" flash on a successful fetch.
        self.news_widget.grid_remove()

        # everything after this shows once a game is selected
        self.game_window_frame = customtkinter.CTkFrame(self.tab("Game"), fg_color="transparent")
        # self.game_window_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.game_window_frame.columnconfigure(2, weight=1)

        self.game_image = customtkinter.CTkImage(size=(200, 300), light_image=Image.open(resource_path("bin/img/not_found.jpg")))
        self.game_image_label = customtkinter.CTkLabel(self.game_window_frame, image=self.game_image, text="")
        self.game_image_label.grid(row=0, column=0, rowspan=2)

        self.game_name = customtkinter.CTkLabel(self.game_window_frame, text="NAME HERE", anchor="n", font=(None, 20))
        self.game_name.grid(row=0, column=1, columnspan=2, sticky="wn", padx=10, pady=5)
        self.game_config = customtkinter.CTkButton(self.game_window_frame, text="⚙️", anchor="center", fg_color="transparent", width=5)
        self.game_config.grid(row=0, column=2, sticky="ne")

        # Screenshot strip. Built unconditionally but starts hidden — the
        # visible tile count is decided at runtime by `update_screenshots`,
        # which is called from `App.sidebar_callback` in main.py. The strip
        # is a horizontal scrollable frame so it can grow to hold any
        # number of tiles; tiles are added/removed dynamically.
        self.screenshots = customtkinter.CTkScrollableFrame(self.game_window_frame, orientation="horizontal", fg_color="transparent")
        self.screenshots.grid(row=1, column=1, padx=10, pady=5, sticky="wens", columnspan=2)
        # List of CTkImage refs currently shown — kept here (not on each
        # child label) so we can clear the strip in O(N) without losing
        # tile references when the user switches games.
        self._screenshot_tiles = []  # list of (label, ctk_image)
        self.screenshots.rowconfigure(0, weight=1)
        self.screenshots.grid_remove()  # start hidden — show when populated

        self.activity_button = customtkinter.CTkButton(self.game_window_frame, text="")
        self.activity_button.grid(row=2, column=1, padx=10, pady=5)
        self.exe_selector = customtkinter.CTkComboBox(self.game_window_frame, state="readonly")
        self.exe_selector.set("Select an executable")
        self.exe_selector.grid(row=2, column=2, padx=5, pady=5, sticky="ew")
        self.description = customtkinter.CTkTextbox(self.game_window_frame, wrap="word")
        self.description.grid(row=3, column=1, columnspan=2, rowspan=4, sticky="we", padx=10, pady=5)
        self.activity_button.grid_info()
        self.release_year = customtkinter.CTkLabel(self.game_window_frame, justify="right", text="")
        self.release_year.grid(row=2, column=0, sticky="w")
        self.rating = customtkinter.CTkLabel(self.game_window_frame, justify="right", text="")
        self.rating.grid(row=3, column=0, sticky="w")
        self.version = customtkinter.CTkLabel(self.game_window_frame, justify="right", text="")
        self.version.grid(row=4, column=0, sticky="w")

        # END GAME TAB

        # START DOWNLOADS TAB
        # Single-pane list layout. Each download is one row with its
        # own progress bar, status text, and context-appropriate action
        # buttons. The old right-side "Download Progress" panel
        # duplicated information that already lived on each row and
        # forced a "one current download" model that DownloadManager
        # doesn't actually need.
        self.download_window_frame = customtkinter.CTkFrame(self.tab("Downloads"), fg_color="transparent")
        self.download_window_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.download_window_frame.columnconfigure(0, weight=1)
        self.download_window_frame.rowconfigure(1, weight=1)

        # Header row: title + global "Clear finished" button. Lives on
        # row 0 of the tab content so it stays visible when the list
        # below scrolls.
        header = customtkinter.CTkFrame(self.download_window_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        header.columnconfigure(0, weight=1)

        self.downloads_label = customtkinter.CTkLabel(
            header, text="Downloads", anchor="w", font=(None, 14, "bold")
        )
        self.downloads_label.grid(row=0, column=0, sticky="w")

        self.clear_finished_btn = customtkinter.CTkButton(
            header,
            text="Clear finished",
            width=120,
            fg_color="#4a4a4a",
            hover_color="#5a5a5a",
            command=self._clear_finished,
        )
        self.clear_finished_btn.grid(row=0, column=1, sticky="e")
        # Disabled until at least one row is in a finished/failed state.
        self.clear_finished_btn.configure(state="disabled")

        # Single scrollable list — one frame per download. We let it
        # own its scrollbar (CTkScrollableFrame brings one), so the
        # earlier dead `download_scrollbar` is gone.
        self.download_list_frame = customtkinter.CTkScrollableFrame(
            self.download_window_frame, fg_color="transparent"
        )
        self.download_list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.download_list_frame.columnconfigure(0, weight=1)

        # Bookkeeping. Each entry tracks everything the row needs to
        # render itself and to re-enter the queue after a pause/stop.
        # gid -> {
        #   "frame": CTkFrame,
        #   "title": str,
        #   "status": "queued" | "downloading" | "paused" | "complete"
        #             | "error" | "stopped",
        #   "progress": float (0..100),
        #   "error": Optional[str],
        #   "filename": str,         # local file basename
        #   "download_path": str,    # full local path
        #   "download_url": str,
        #   "headers": dict,         # auth headers cached for retry
        #   "title_label", "bar", "status_label", "actions",
        #   "detail_actions", "action_widgets":  # widget refs
        # }
        self.downloads = {}
        # The gid whose DownloadManager slot is currently
        # `downloading`. None when nothing is in flight. Used to gate
        # queue promotion so we never start two downloads at once.
        self._active_gid = None
        # Callback installed by main.py — `_handle_download_action`.
        self._action_handler = None

        # END DOWNLOADS TAB

    def _clear_screenshot_tiles(self):
        """Destroy all current tiles and drop CTkImage references."""
        for label, _ctk in self._screenshot_tiles:
            try:
                label.destroy()
            except Exception:
                pass
        self._screenshot_tiles = []

    def clear_screenshots(self):
        """Hide the strip and drop every tile. Used when switching games
        and when a game has no screenshots."""
        self._clear_screenshot_tiles()
        self.screenshots.grid_remove()

    def show_loading_screenshots(self):
        """Show a single 'Loading…' label inside the strip. Used while the
        background thread is fetching external screenshot URLs."""
        self._clear_screenshot_tiles()
        loading = customtkinter.CTkLabel(
            self.screenshots,
            text="Loading screenshots…",
            anchor="w",
            font=(None, 13),
        )
        loading.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        # Stored as a tile-like entry so clear_screenshots() cleans it up.
        self._screenshot_tiles.append((loading, None))
        self.screenshots.grid()

    def add_screenshot_tile(self, image_path):
        """Append one thumbnail tile for `image_path` to the strip. Tiles are
        shown in the order added; the caller is expected to clear first if
        switching games."""
        try:
            pil = Image.open(image_path)
            pil.load()
            ctk_image = customtkinter.CTkImage(
                size=(334, 188), light_image=pil, dark_image=pil
            )
            label = customtkinter.CTkLabel(self.screenshots, image=ctk_image, text="", anchor="s")
            label.grid(row=0, column=len(self._screenshot_tiles), padx=5, sticky="s")
            # Hold a reference on the tuple so the bitmap isn't GC'd.
            self._screenshot_tiles.append((label, ctk_image))
        except Exception as e:
            logging.warning(f"Failed to render screenshot {image_path}: {e}")

    def update_screenshots(self, image_paths):
        """Replace the strip with one tile per path. Empty list hides it.

        Convenience method for synchronous use; the threaded `load_screenshots`
        in main.py uses `clear_screenshots` + `add_screenshot_tile` for
        per-tile progress instead of a single bulk replace.
        """
        self._clear_screenshot_tiles()
        if not image_paths:
            self.screenshots.grid_remove()
            return
        for path in image_paths:
            self.add_screenshot_tile(path)
        self.screenshots.grid()

    def set_news(self, news_text):
        """Render `news_text` in the inline news textbox. Replaces any
        prior content. The widget is shown when called; if `news_text`
        is empty the textbox stays hidden (treated as "no news")."""
        self.news_widget.configure(state="normal")
        self.news_widget.delete("0.0", "end")
        if news_text:
            self.news_widget.insert("0.0", news_text)
            self.news_widget.grid()
        else:
            self.news_widget.grid_remove()
        self.news_widget.configure(state="disabled")

    def show_news_loading(self):
        """Indicate that the news fetch is in flight without blocking
        the UI. Replaces any prior content with a 'Loading server news…'
        label and reveals the textbox."""
        self.news_widget.configure(state="normal")
        self.news_widget.delete("0.0", "end")
        self.news_widget.insert("0.0", "Loading server news…")
        self.news_widget.configure(state="disabled")
        self.news_widget.grid()

    def add_download(self, gid, title, download_path, download_url, headers,
                     filename, game_type=None, kind="extract"):
        """Add a row to the download list in the 'queued' state. The
        first row added to an empty queue is promoted to 'downloading'
        immediately by `_promote_next_queued`; the rest wait their turn.

        Idempotent: if `gid` already has a row, the existing row is
        returned and the new args ignored.

        `game_type` and `kind` are stashed on the row so the
        install/clear paths in main.py can branch on them later
        (W_P → extract, W_S → setup Toplevel, W_SW → "not supported").
        """
        if gid in self.downloads:
            return self.downloads[gid]["frame"]

        title = title or f"Game {gid}"
        # Match the rest of the dark customtkinter look.
        row = customtkinter.CTkFrame(self.download_list_frame, fg_color="#2a2a2a")
        row.columnconfigure(0, weight=1)  # title column grows
        row.columnconfigure(1, weight=0)  # button column is fixed

        # Title line. Single label that we rewrite as state changes.
        title_label = customtkinter.CTkLabel(
            row, text="", anchor="w", font=(None, 12, "bold"),
        )
        title_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))

        # Right-side action buttons (Pause/Stop, Resume/Stop, etc.)
        actions = customtkinter.CTkFrame(row, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=10, pady=(8, 2))

        # Progress bar across the whole width.
        bar = customtkinter.CTkProgressBar(row, height=8)
        bar.set(0)
        bar.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 2))

        # Right-aligned status text (percent, "Paused", "Done!", etc.)
        status_label = customtkinter.CTkLabel(
            row, text="", anchor="e", font=(None, 10), text_color="#888888",
        )
        status_label.grid(row=1, column=1, sticky="e", padx=10, pady=(0, 2))

        # Second row of action buttons for completed / failed rows
        # (Install / Open / Clear, Retry / Open / Clear). Hidden by
        # default; `_render_row` reveals it for those states.
        detail_actions = customtkinter.CTkFrame(row, fg_color="transparent")
        detail_actions.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 6))

        actions.grid_remove()
        detail_actions.grid_remove()

        row.grid(row=len(self.downloads), column=0, sticky="ew", padx=0, pady=4)

        info = {
            "frame": row,
            "title": title,
            "status": "queued",
            "progress": 0.0,
            "error": None,
            "filename": filename,
            "download_path": download_path,
            "download_url": download_url,
            "headers": headers or {},
            # Type tag from the filename (e.g. "W_P") and the kind it
            # maps to ("extract" / "setup" / "unsupported"). Stashed
            # at queue time so the install/clear paths in main.py
            # don't have to re-detect them.
            "game_type": game_type,
            "kind": kind,
            # widget refs
            "title_label": title_label,
            "bar": bar,
            "status_label": status_label,
            "actions": actions,
            "detail_actions": detail_actions,
            "action_widgets": [],
        }
        self.downloads[gid] = info
        self._render_row(gid)
        self._refresh_header()
        # If the queue is empty, promote this row immediately. We do
        # this *after* `self.downloads[gid] = info` so the promotion
        # helper sees the new row and can grab it.
        if self._active_gid is None:
            self._promote_next_queued()
        return row

    def set_status(self, gid, status, error=None):
        """Update the row's status and (optionally) its error text,
        then re-render. The queue behaves differently depending on
        the new status:

          - 'paused' / 'downloading' / 'extracting' : keep
            `_active_gid` as-is (the row is still the active
            download — paused/extracting still hold the slot).
          - 'stopped' / 'error' / 'complete' : clear `_active_gid` so
            the next queued row can be promoted.
          - 'queued' : if the queue is currently empty (no
            `_active_gid`), promote *this* row — used by the retry
            path that goes `error → queued → downloading` in one step.
        """
        info = self.downloads.get(gid)
        if not info:
            return
        # Free the active slot when the active row leaves the
        # in-flight pool. Paused / extracting keep the slot (the
        # row is still ours — we just paused or are still working
        # on it).
        if self._active_gid == gid and status in ("stopped", "error", "complete"):
            self._active_gid = None
        info["status"] = status
        if error is not None:
            info["error"] = error
        # Decide whether the queue should run after the render. We
        # compute this before rendering so a queued→downloaded
        # promotion in the same call (the retry path) renders the
        # right buttons in one go instead of a queued→downloading
        # two-step flicker.
        if status == "queued" and self._active_gid is None:
            self._active_gid = gid
            info["status"] = "downloading"
            self._render_row(gid)
            self._refresh_header()
            self._request("start", gid)
            return
        self._render_row(gid)
        self._refresh_header()
        if status in ("stopped", "error", "complete"):
            self._promote_next_queued()

    def set_progress(self, gid, percent):
        """Update just the bar + percent label. Does NOT change status,
        and does NOT trigger queue promotion — the row is already in
        flight when this is called."""
        info = self.downloads.get(gid)
        if not info:
            return
        info["progress"] = max(0.0, min(100.0, float(percent)))
        info["bar"].set(info["progress"] / 100.0)
        # Only overwrite the status label for the "in flight" states
        # — paused/queued/etc. have their own subtitles and we don't
        # want progress callbacks to clobber them. The "extracting"
        # state re-renders the subtitle each tick to keep the
        # percent current; every other in-flight state shows
        # the bare percent.
        if info["status"] == "downloading":
            info["status_label"].configure(text=f"{info['progress']:.0f}%")
        elif info["status"] == "extracting":
            info["status_label"].configure(
                text=f"Extracting…  ·  {info['progress']:.0f}%"
            )

    def _render_row(self, gid):
        """Rebuild the action buttons + status text for a single row
        to match its current `status`. Idempotent: wipes the action
        frames first, then re-creates the buttons that belong to this
        state."""
        info = self.downloads.get(gid)
        if not info:
            return

        # Reset action frames
        for w in info["action_widgets"]:
            try:
                w.destroy()
            except Exception:
                pass
        info["action_widgets"] = []
        info["actions"].grid_remove()
        info["detail_actions"].grid_remove()

        status = info["status"]
        title = info["title"]
        icon = _status_icon(status)

        # Title line: "▣ Game 1.zip" (or "▣ Game 1.zip  ·  HTTP 503"
        # when the row carries an error message).
        title_text = f"{icon} {title}"
        if info.get("error") and status in ("error", "stopped"):
            title_text += f"  ·  {info['error']}"
        info["title_label"].configure(text=title_text)

        # Subtitle: percent or state-specific text.
        info["status_label"].configure(
            text=_status_subtitle(status, info["progress"])
        )

        # Progress bar
        info["bar"].set(info["progress"] / 100.0)

        # Per-state action buttons.
        if status == "downloading":
            info["actions"].grid()
            info["action_widgets"] += _add_buttons(
                info["actions"], [
                    ("⏸ Pause", lambda: self._request("pause", gid), "#4a4a4a", None),
                    ("⏹ Stop",  lambda: self._request("stop", gid),  "#a83232", "#c53838"),
                ]
            )
        elif status == "paused":
            info["actions"].grid()
            info["action_widgets"] += _add_buttons(
                info["actions"], [
                    ("▶ Resume", lambda: self._request("resume", gid), "#3d9e3d", "#4cb84c"),
                    ("⏹ Stop",   lambda: self._request("stop", gid),   "#a83232", "#c53838"),
                ]
            )
        elif status == "extracting":
            # Mid-install: no action buttons. The user can clear
            # the row once the extract finishes (which transitions
            # to 'complete' and re-renders the buttons). Cancellng
            # a half-extracted archive would leave a half-built
            # install dir; not a useful user action, so we hide
            # the affordance entirely.
            pass
        elif status == "queued":
            # No right-side buttons for queued rows — there's nothing
            # to pause/resume. A "Remove" lives on the second row so
            # the user can drop a queued entry without ever starting it.
            info["detail_actions"].grid()
            info["action_widgets"] += _add_buttons(
                info["detail_actions"], [
                    ("✕ Remove", lambda: self._request("remove", gid), "#4a4a4a", None),
                ]
            )
        elif status == "complete":
            info["detail_actions"].grid()
            info["action_widgets"] += _add_buttons(
                info["detail_actions"], [
                    ("Install", lambda: self._request("install", gid), "#3d9e3d", "#4cb84c"),
                    ("Open",    lambda: self._request("open", gid),    "#4a4a4a", None),
                    ("Clear",   lambda: self._request("clear", gid),   "#4a4a4a", None),
                ]
            )
        elif status in ("error", "stopped"):
            info["detail_actions"].grid()
            info["action_widgets"] += _add_buttons(
                info["detail_actions"], [
                    ("Retry", lambda: self._request("retry", gid),  "#3d9e3d", "#4cb84c"),
                    ("Open",  lambda: self._request("open", gid),  "#4a4a4a", None),
                    ("Clear", lambda: self._request("clear", gid), "#a83232", "#c53838"),
                ]
            )

    def _promote_next_queued(self):
        """If the queue is empty (no row is currently 'downloading')
        and at least one row is 'queued', promote the first queued
        row to 'downloading' and fire a `start` request for it.

        The actual DownloadManager call is delegated to `App` via
        `_request("start", gid)`. We don't call DownloadManager
        directly from the tab because auth headers live in main.py's
        scope.
        """
        if self._active_gid is not None:
            return
        for gid, info in self.downloads.items():
            if info["status"] == "queued":
                self._active_gid = gid
                info["status"] = "downloading"
                self._render_row(gid)
                self._refresh_header()
                self._request("start", gid)
                return

    def set_action_handler(self, handler):
        """Install the App-level callback for per-row actions.

        Signature: handler(action: str, gid: int) -> None, where
        `action` is one of:

          "start"   — promote queued → downloading (DownloadManager)
          "pause"   — DownloadManager.pause_download(gid)
          "resume"  — DownloadManager.resume_download(gid)
          "stop"    — DownloadManager.stop_download(gid)
          "remove"  — drop a queued row (no network call)
          "install" — unpack_game(gid) + refresh sidebar
          "open"    — open the downloads folder
          "clear"   — drop a finished/failed row, optionally delete partial
          "retry"   — re-promote a failed row to queued
        """
        self._action_handler = handler

    def _request(self, action, gid):
        """Dispatch a per-row action to the App-level handler. Errors
        are logged but never raised — a failed action shouldn't take
        the UI down."""
        handler = getattr(self, "_action_handler", None)
        if handler:
            try:
                handler(action, gid)
            except Exception as e:
                logging.warning(f"Action {action!r} for {gid} failed: {e}")

    def _refresh_header(self):
        """Update the "Downloads (N)  ·  X active  ·  Y finished" label
        and toggle the Clear-finished button."""
        n_total = len(self.downloads)
        n_finished = sum(
            1 for info in self.downloads.values()
            if info["status"] in ("complete", "error", "stopped")
        )
        n_active = sum(
            1 for info in self.downloads.values()
            if info["status"] in ("downloading", "paused", "queued")
        )
        parts = [f"Downloads ({n_total})"]
        if n_active:
            parts.append(f"{n_active} active")
        if n_finished:
            parts.append(f"{n_finished} finished")
        try:
            self.downloads_label.configure(text="    ·  ".join(parts))
        except Exception:
            pass
        # The Clear button is enabled only when there's something to clear.
        try:
            self.clear_finished_btn.configure(
                state="normal" if n_finished else "disabled"
            )
        except Exception:
            pass

    def _clear_finished(self):
        """Drop every row in a finished/failed/stopped state. The
        action handler is asked to delete the partial file for each
        so a future retry starts from byte 0."""
        for gid in list(self.downloads.keys()):
            info = self.downloads.get(gid)
            if info and info["status"] in ("complete", "error", "stopped"):
                self._request("clear", gid)

    def get_downloads(self):
        """Return the downloads dict (kept for any external callers)."""
        return self.downloads


# ------------------------------------------------------------------
# Module-scope helpers for the download rows. Kept private to this
# module — they exist to keep `_render_row` readable by pulling the
# per-state button specs and status text out of it.
# ------------------------------------------------------------------

_STATUS_ICONS = {
    "queued":      "⏳",
    "downloading": "▣",
    "paused":      "⏸",
    "extracting":  "▣",   # install in progress; same "in flight" feel as downloading
    "complete":    "✓",
    "error":       "✗",
    "stopped":     "■",
}


def _status_icon(status):
    return _STATUS_ICONS.get(status, "·")


def _status_subtitle(status, percent):
    if status == "complete":
        return "Done!"
    if status == "error":
        return "Download failed"
    if status == "stopped":
        return "Stopped"
    if status == "paused":
        return f"Paused  ·  {percent:.0f}%"
    if status == "queued":
        return "Waiting…"
    if status == "extracting":
        # Just the leading label. `set_progress` (line ~382)
        # owns the percent display during extraction and rebuilds
        # the full "Extracting…  ·  X%" string on every tick.
        return "Extracting…"
    return f"{percent:.0f}%"


def _add_buttons(parent, specs):
    """Create CTkButtons from `(label, command[, fg, hover])` specs.

    Returns the list of created button widgets so callers can keep
    references and destroy them on re-render.
    """
    out = []
    for i, spec in enumerate(specs):
        label, cmd = spec[0], spec[1]
        fg = spec[2] if len(spec) > 2 else None
        hover = spec[3] if len(spec) > 3 else None
        kwargs = {"text": label, "width": 90, "command": cmd}
        if fg:
            kwargs["fg_color"] = fg
        if hover:
            kwargs["hover_color"] = hover
        b = customtkinter.CTkButton(parent, **kwargs)
        b.grid(row=0, column=i, padx=3, pady=0)
        out.append(b)
    return out
