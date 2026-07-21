import customtkinter
from platformdirs import *
from PIL import Image
from .util import *


class Sidebar(customtkinter.CTkFrame):
    """Sidebar with a live filter input, a sort dropdown, and a
    scrollable button list of every game the server has.

    The list is rendered in two visual tiers (no headers, just
    ordering): by default installed games come first, then
    not-installed games. The colour hint on each button (white vs
    grey) reinforces the visual separation.

    Public API:
        Sidebar(master, callback, **kwargs)
            `initial_state` kwarg, if present, must be a dict of
            {"query": str, "sort": str}. Used to restore filter +
            sort across a destroy/rebuild (see App._rebuild_sidebar).
            Default sort: "Installed first".
        get_state() -> {"query": str, "sort": str}
            Snapshot the current filter + sort. The App captures
            this before destroying the sidebar so the rebuilt
            instance can pick up where the old one left off.
    """

    SORT_MODES = (
        "Installed first",
        "Name (A->Z)",
        "Name (Z->A)",
        "Recently added",
        "Rating",
    )
    DEFAULT_SORT = "Installed first"
    DEFAULT_STATE = {"query": "", "sort": DEFAULT_SORT}

    def __init__(self, master, callback, **kwargs):
        # Pop the Sidebar-specific kwarg BEFORE passing the rest
        # to CTkFrame.__init__, which raises on unknown kwargs.
        initial_state = kwargs.pop("initial_state", None) or {}
        super().__init__(master, **kwargs)
        self.callback = callback

        # Capture the initial state. The App passes this in so
        # the filter/sort survive a destroy/rebuild. Default to
        # the canonical empty state on first launch.
        self._query = initial_state.get("query", "") or ""
        sort = initial_state.get("sort", self.DEFAULT_SORT)
        if sort not in self.SORT_MODES:
            sort = self.DEFAULT_SORT

        # StringVars back the entry and the option menu. This
        # keeps the read/write symmetrical and lets the App
        # inspect the current state via get_state().
        self._query_var = customtkinter.StringVar(value=self._query)
        self._sort_var = customtkinter.StringVar(value=sort)

        # Layout uses pack (top-down) rather than grid, because
        # `CTkScrollableFrame` doesn't reliably size to its
        # parent's leftover space under grid — its content height
        # ends up dictating the row height, leaving a giant empty
        # gap. `pack(side=TOP, expand=True, fill=BOTH)` on the
        # list is the only configuration that consistently
        # produces "logo, then controls, then list fills the
        # rest" on every system.
        #
        #   [logo]                (side=TOP, fill=X)
        #   [search | sort]       (side=TOP, fill=X)
        #   [game list...]        (side=TOP, expand=True, fill=BOTH)
        self.grid_columnconfigure(0, weight=1)

        # --- Logo ---
        # The sidebar's own fg_color="blue" was set by the App,
        # so any frame that doesn't set its own fg_color ends up
        # bright blue. Match the list's dark grey here so the
        # whole sidebar reads as one colour, and only the entry
        # + sort menu have any visual contrast.
        self.logo_frame = customtkinter.CTkFrame(
            self, corner_radius=0, fg_color="#2b2b2b",
        )
        self.logo_frame.pack(side="top", fill="x")
        self.logo_image = customtkinter.CTkImage(
            size=(200, 25),
            light_image=Image.open("bin/img/GV-dark.png"),
            dark_image=Image.open("bin/img/GV-light.png"),
        )
        self.logo_label = customtkinter.CTkLabel(
            self.logo_frame, image=self.logo_image, text=""
        )
        self.logo_label.pack(side="top", padx=20, pady=(20, 10), anchor="w")

        # --- Controls (filter entry + sort dropdown) ---
        self.controls_frame = customtkinter.CTkFrame(
            self, corner_radius=0, fg_color="#2b2b2b",
        )
        self.controls_frame.pack(side="top", fill="x", padx=10, pady=(0, 8))
        self.controls_frame.grid_columnconfigure(0, weight=1)
        self.controls_frame.grid_columnconfigure(1, weight=0)

        self.search_entry = customtkinter.CTkEntry(
            self.controls_frame,
            placeholder_text="Filter…",
            textvariable=self._query_var,
            width=140,
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        # Re-render the list on every keystroke. <KeyRelease> fires
        # after the textvariable has already been updated, so the
        # filter sees the new query.
        self.search_entry.bind("<KeyRelease>", lambda _e: self._render_rows())

        self.sort_menu = customtkinter.CTkOptionMenu(
            self.controls_frame,
            values=list(self.SORT_MODES),
            variable=self._sort_var,
            command=lambda _v: self._render_rows(),
            width=160,
        )
        self.sort_menu.grid(row=0, column=1, sticky="e")

        # --- Scrollable list ---
        # expand=True + fill=BOTH is the critical part: it makes
        # the list consume all the leftover vertical space below
        # the logo and controls, and the internal scrollbar
        # handles the overflow when 62 games don't fit.
        self.sidebar_frame = customtkinter.CTkScrollableFrame(self, corner_radius=0)
        self.sidebar_frame.pack(side="top", fill="both", expand=True)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)

        # Fetch the full game list once. `fetch_game_titles` is
        # already cached, so this is fast after the first call.
        # We project the dict down to the few fields we need so
        # the render path doesn't keep reaching into the raw
        # server payload.
        raw_games = fetch_game_titles() or []
        self._all_games = []
        for g in raw_games:
            gid = g.get("id")
            if gid is None:
                continue
            title = g.get("title") or f"Game {gid}"
            metadata = g.get("metadata") or {}
            try:
                rating = float(metadata.get("rating") or 0.0)
            except (TypeError, ValueError):
                rating = 0.0
            self._all_games.append({
                "id": gid,
                "title": title,
                # `sort_title` is what the GameVault server uses
                # for "ignore leading articles" sorting (e.g. it
                # already lowercases + strips "The "). Falling back
                # to a plain lowercased title is fine if the
                # server didn't supply one.
                "sort_title": (g.get("sort_title") or title).lower(),
                "created_at": g.get("created_at") or "",
                "rating": rating,
            })

        self._render_rows()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_state(self):
        """Return the current filter query and sort mode. The App
        captures this before destroying the sidebar so the rebuilt
        instance can pick up where the old one left off."""
        return {
            "query": self._query_var.get(),
            "sort": self._sort_var.get(),
        }

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render_rows(self):
        """Wipe and re-create the button list, applying the current
        filter query and sort mode. Cheap for the ~60-game list
        the user has today (~62 titles in production)."""
        # Capture scroll position so the user doesn't get bounced
        # back to the top every keystroke. _parent_canvas is the
        # internal Canvas the CTkScrollableFrame wraps.
        try:
            yview = self.sidebar_frame._parent_canvas.yview()
        except Exception:
            yview = (0.0, 1.0)

        # Wipe the existing buttons. CTkScrollableFrame children
        # include its internal scrollbar; destroying all of them
        # and then re-adding buttons in a clean state is the
        # simplest reliable way to re-render.
        for child in list(self.sidebar_frame.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

        # Pull the current query from the StringVar (not from
        # self._query — we don't cache the query on self).
        query = (self._query_var.get() or "").strip().lower()
        sort_mode = self._sort_var.get()
        if sort_mode not in self.SORT_MODES:
            sort_mode = self.DEFAULT_SORT

        # Filter. Substring match on the lowercased title. Empty
        # query is a no-op (renders everything).
        if query:
            games = [g for g in self._all_games if query in g["title"].lower()]
        else:
            games = list(self._all_games)

        # Pre-compute the installed map so the sort key doesn't
        # hit the filesystem 60 times per render. is_game_installed
        # is a cheap dir check but we still want to do it once.
        installed_map = {g["id"]: is_game_installed(g["id"]) for g in games}

        # Sort. Each branch returns a key function.
        if sort_mode == "Installed first":
            # (0, name) for installed, (1, name) for not installed.
            # The tuple orders installed above not-installed; the
            # second element keeps both groups alphabetical.
            def key(g):
                return (0 if installed_map.get(g["id"]) else 1, g["sort_title"])
        elif sort_mode == "Name (A->Z)":
            def key(g):
                return (g["sort_title"],)
        elif sort_mode == "Name (Z->A)":
            # Negate the sort key by wrapping in a tuple whose
            # first element flips the order. Using a custom class
            # would be overkill.
            def key(g):
                # Negate via descending key: we want highest first.
                # A simple `reverse=True` is cleaner; use that.
                return (g["sort_title"],)
        elif sort_mode == "Recently added":
            def key(g):
                # ISO 8601 strings sort correctly lexicographically
                # for the same timezone. Reverse=True below flips
                # to newest-first.
                return (g["created_at"],)
        elif sort_mode == "Rating":
            def key(g):
                return (g["rating"],)
        else:  # defensive — should not happen because of the guard above
            def key(g):
                return (g["sort_title"],)

        reverse = sort_mode in ("Name (Z->A)", "Recently added", "Rating")
        games.sort(key=key, reverse=reverse)

        for game in games:
            gid = game["id"]
            title = game["title"]

            label = customtkinter.CTkButton(
                self.sidebar_frame,
                text=title,
                corner_radius=0,
                fg_color="transparent",
                anchor="w",
                command=lambda gid=gid: self._select_game(gid),
            )

            # Same colour hint as the original sidebar: black/white
            # for installed, grey for not-installed.
            if installed_map.get(gid):
                label.configure(text_color=("black", "white"))
            else:
                label.configure(text_color="grey")

            label.grid(row=len(self.sidebar_frame.winfo_children()) - 1,
                       column=0, padx=0, pady=0, sticky="ew")

        # Restore the scroll position. We only restore if the new
        # list is long enough to have a meaningful yview; for a
        # filter that returns 2 rows there's nothing to scroll.
        if games and yview != (0.0, 1.0):
            try:
                self.sidebar_frame._parent_canvas.yview_moveto(yview[0])
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _select_game(self, game_id):
        """Wrap the App's callback. Keeping the closure here (rather
        than inlining it inside _render_rows) makes the per-button
        command lambda easy to read."""
        if self.callback:
            self.callback(game_id)
