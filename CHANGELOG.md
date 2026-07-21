# Changelog

All notable changes to GameVault Snake Edition are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Per-game Settings dialog** (`bin/GUI/game_settings.py`) — full
  rewrite of the previous stub. Lets an admin edit any of the 13
  Custom Metadata fields (title, sort title, description, notes,
  average playtime, age rating, release date, rating, early access,
  default launch executable + parameters, default installer
  executable + parameters) on a per-game basis. Reads from
  `user_metadata` with a `metadata` fallback; saves via
  `PUT /api/games/{id}` (`UpdateGameDto.user_metadata`). Non-admins
  see the gear button disabled with a hover tooltip — they can't
  accidentally PUT and get a 403.
- **App Settings dialog** (`bin/GUI/gvse_settings.py`) — full
  rewrite of the previous stub. Lets any user edit runtime
  tweakables: appearance mode (Light / Dark / System), color theme
  (blue / green / dark-blue), install location (with a folder
  picker), and debug mode. Saves to `settings.ini`. Always visible
  in the Settings menu (no role gate).
- **Admin Panel dialog** (`bin/GUI/admin_settings.py`) — full
  rewrite of the previous stub. Two sections:
  - **Library → Reindex**: a button that calls
    `PUT /api/games/reindex` with a confirmation prompt. Status
    label shows when the reindex was triggered.
  - **Users**: a scrollable list of every server user with their
    role in a dropdown. Each row has a Save button that calls
    `PUT /api/users/{id}` to change the role. The current user's
    own row is disabled to prevent self-demotion.
  Gated on admin role in the menu (greyed out for non-admins with
  a tooltip).
- **Sidebar filtering + sort** (`bin/sidebar.py`) — full rewrite.
  Adds a filter entry (substring match on title) and a sort dropdown
  with five modes:
  - Installed first (default)
  - Name (A→Z)
  - Name (Z→A)
  - Recently added
  - Rating
  Each row is colour-coded: black/white text for installed games,
  grey for not-installed. Scroll position is preserved on every
  re-render.
- **Download manager** (`bin/download_manager.py`) — extracted from
  `bin/util.py` into a dedicated module.
- **Setup runner dialog** (`bin/GUI/setup_runner.py`) — UI for
  running game-setup executables after install.
- **OpenAPI spec** (`docs-json.json`) — checked in for offline API
  reference and to keep the launcher aligned with the server's
  actual schema.

### Changed

- **`bin/util.py`** — split out a number of focused helpers next
  to the existing request/response plumbing:
  - `get_current_user_role()` — cached `GET /api/users/me` caller
    used for menu gating and tooltips.
  - `get_current_user_id()` — same shape, reads the `id` field.
    Used by Admin Settings to disable the current user's own row.
  - `list_users()`, `update_user_role(uid, role)`,
    `reindex_games()` — small `request()` wrappers for the Admin
    Panel.
  - `update_game_user_metadata(gid, user_metadata)` — `PUT` for
    the per-game Settings dialog; invalidates the `fetch_game_info`
    cache for the game on success.
  - `delete_cache(gid)` — drops a single row from the SQLite
    cache. Used after a metadata edit so the game page re-renders
    with fresh data instead of waiting for the cache to expire.
- **Settings menu** (`main.py`) — the "Admin Panel" option is now
  gated on `role >= 2` (admin/owner). Non-admins see the entry
  greyed out with the same hover tooltip used by the gear button.
  The "App Settings" option stays enabled for everyone. The Admin
  Panel's click handler re-checks the role as defense in depth.
- **Appearance/theming** — the menu's existing Light/Dark/System
  options (and the new App Settings dialog) all save to the
  `apperance` key in `settings.ini` (yes, the typo is intentional
  — it's the spelling the existing file uses, and renaming it
  would split the install into "menu-driven" vs "dialog-driven"
  depending on which was used last).
- **GitHub Actions workflow** (`.github/workflows/build_executable.yml`)
  — replaced the single Windows job with a 3-job pipeline:
  1. `build-windows` (windows-latest) — produces
     `GameVault-Snake-Edition.exe`.
  2. `build-linux` (ubuntu-latest) — produces
     `GameVault-Snake-Edition` (x86_64 binary, runs on Steam
     Deck). Installs X11 client libs for the build VM, filters
     the Windows-only deps out of `requirements.txt` before
     `pip install`, and `chmod +x`'s the binary.
  3. `release` — gated on `refs/tags/v*`, attaches both
     artifacts to a GitHub Release with auto-generated notes
     via `softprops/action-gh-release@v2`.
  Triggers: push to main, push of `v*` tags, pull requests, and
  manual `workflow_dispatch`. Action versions bumped to current
  majors (`checkout@v4`, `setup-python@v5`, `upload-artifact@v4`,
  `download-artifact@v4`).

### Fixed

- **Sidebar blue strip** — a frame between the controls row and
  the game list was rendering as bright blue because it inherited
  the sidebar's `fg_color="blue"` and didn't override it. Changed
  to `fg_color="#2b2b2b"` (matching the rest of the sidebar's
  dark grey palette) at both call sites in `main.py`. The whole
  sidebar now reads as one solid colour top-to-bottom.
- **Game page not refreshing after metadata edit** — without
  cache invalidation, the game page would keep showing the
  pre-save title/description for up to `CACHE_EXPIRY` seconds
  after a successful PUT. The new `delete_cache(gid)` call inside
  `update_game_user_metadata` drops the cached row so the next
  `fetch_game_info` re-fetches from the server.
- **Game Settings dialog** — the previous stub did nothing useful
  (it just showed the game id in a 400×400 window). Now opens to
  a real 900×650 form pre-populated from the server.

### Removed

- `zip_test/` — leftover directory from earlier 7z extraction
  testing.
- `full_extract/` and `full_install/` — empty scratch directories
  from debugging the install pipeline.
- `requirements.txt.bak` — empty placeholder file.

[Unreleased]: https://github.com/Toylerrr/GameVault-Snake-Edition/compare/main...HEAD
