import base64
import requests
import configparser
import os
import json
import logging
import re
import threading
from logging.handlers import RotatingFileHandler
import sqlite3
import time
import keyring
import sys
import shutil
import subprocess
from platformdirs import *
from pathlib import Path
from io import BytesIO
from PIL import Image
from tkinter import messagebox, filedialog

#___________Main Settings___________
appname = 'GameVault-Snake Edition'
settings_file_name = 'settings.ini'
settings_location = user_data_dir(appname, appauthor='Toylerrr')
settings_file = os.path.join(settings_location, settings_file_name)




# Ensure settings directory exists
os.makedirs(settings_location, exist_ok=True)

# Check if settings file exists
if not os.path.exists(settings_file):
    # Create ConfigParser instance
    config = configparser.ConfigParser()

    # Set default values
    config['SETTINGS'] = {
        'username': '',
        'install_location': '',
        'url': '',
        'apperance': 'System',
        'theme': 'blue',
        'debug': 'False',
        # `first_run` flags the freshly-created settings.ini so
        # main.py can auto-open the Settings Wizard on first
        # launch. The wizard's `submit_credentials` flips this
        # to False once the user has saved a URL + install
        # location. We use an explicit boolean (rather than
        # checking for an empty `url`) because a user may
        # intentionally clear their URL later without wanting
        # the wizard to keep popping up.
        'first_run': 'True',
    }

    # Write the default configuration to the file
    with open(settings_file, 'w') as configfile:
        config.write(configfile)
else:
    # Read configuration from file
    config = configparser.ConfigParser()
    config.read(settings_file)

if config['SETTINGS'].get('debug') == 'True':
    # Log to a rotating file in the launcher's working directory, in addition
    # to stderr. The file is appended across runs and rotates at 5MB, keeping
    # the last 5 backups as gvse.log.1 .. gvse.log.5.
    log_format = '%(asctime)s %(levelname)s [%(name)s] %(message)s'
    log_formatter = logging.Formatter(log_format)

    log_path = os.path.join(os.getcwd(), 'gvse.log')
    try:
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8',
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(log_formatter)
    except OSError as e:
        # If we can't open the file in CWD (e.g. read-only install dir), fall
        # back to stderr only and keep going.
        file_handler = None
        print(f"Could not open {log_path} for logging: {e}", file=sys.stderr)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    # Replace any handlers a previous import attached so we get a clean config.
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(log_formatter)
    root_logger.addHandler(stream_handler)
    if file_handler is not None:
        root_logger.addHandler(file_handler)
    logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)
    logging.debug("Debug logging enabled; writing to %s", log_path)


# Get values from config
USERNAME = config['SETTINGS'].get('username')
username = USERNAME  # lowercase alias for compatibility
PASSWORD = keyring.get_password("GameVault-Snake", username)

install_location = config['SETTINGS'].get('install_location')
url = config['SETTINGS'].get('url')
appauthor = 'Toylerrr'



CACHE_DIR = f"{settings_location}/cache"
os.makedirs(settings_location, exist_ok=True)

# Define the path for the SQLite database file
DB_PATH = os.path.join(CACHE_DIR, "cache.db")
# Cache Expiry Time (in seconds)
CACHE_EXPIRY_TIME = 60 * 60  # 1 hour


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(relative_path)


# def is_online():
#     try:
#         response = requests.get(url)
#         if response.status_code == 200:
#             logging.debug("ONLINE")
#             return True
#     except Exception:
#         logging.debug("OFFLINE")
#         return False

def check_url_health(passedurl):
    """Check if the GameVault server is online and healthy."""
    # Try /api/status endpoint (from OpenAPI spec) as primary, /api/health as fallback
    for endpoint in ['/api/status', '/api/health']:
        try:
            response = requests.get(f'{passedurl}{endpoint}', timeout=10)
            if response.status_code == 200:
                json_data = response.json()
                # For /api/status, check 'status' field; for /api/health, check 'status' field
                status = json_data.get('status', '')
                if status == 'HEALTHY':
                    logging.debug(f"Health check passed at {endpoint}")
                    return True
        except Exception as e:
            logging.debug(f"Health check failed at {endpoint}: {e}")
            continue
    return False
online_status = check_url_health(url)



#___________END Main Settings___________

# Default tokens will be populated by refresh_jwt_token / refresh_jwt_token_with_refresh
JWT_TOKEN = ''
JWT_REFRESH = ''

def get_auth_headers(auth_method='jwt'):
    """Get authentication headers based on auth method."""
    global USERNAME, PASSWORD, JWT_TOKEN

    # Default to JWT if token exists
    if auth_method == 'api_key':
        return {
            'accept': 'application/json',
            'X-Api-Key': PASSWORD or ''
        }
    elif auth_method == 'jwt':
        # Use JWT token if available
        if JWT_TOKEN:
            logging.debug("Using JWT token for authentication")
            return {
                'accept': 'application/json',
                'Authorization': f'Bearer {JWT_TOKEN}'
            }
        # If no JWT token, fall back to basic auth
        logging.debug("No JWT token available, using basic auth")
    else:  # basic auth (default)
        if USERNAME and PASSWORD:
            encoded_credentials = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
            logging.debug("Using basic authentication")
            return {
                'accept': 'application/json',
                'Authorization': f'Basic {encoded_credentials}'
            }

    # Fallback for missing credentials
    logging.warning("No credentials available, making unauthenticated request")
    return {
        'accept': 'application/json'
    }

def ensure_url_protocol(url):
    """Ensure URL has a protocol (http:// or https://)."""
    if not url:
        return 'https://gamevaultapi.xyz'  # Default URL
    url = url.strip()
    if not (url.startswith('http://') or url.startswith('https://')):
        logging.warning(f"URL missing protocol, adding https://: {url}")
        return f"https://{url}"
    return url

def refresh_jwt_token(username, password):
    """Log in via basic auth and store both access and refresh tokens."""
    global JWT_TOKEN, JWT_REFRESH
    try:
        # Ensure URL has protocol
        base_url = ensure_url_protocol(config['SETTINGS'].get('url'))
        url = f"{base_url}/api/auth/basic/login"
        response = requests.get(url, auth=(username, password), timeout=30)
        if response.status_code == 200:
            try:
                data = response.json()
                JWT_TOKEN = data.get('access_token', '')
                JWT_REFRESH = data.get('refresh_token', '')
                logging.debug("JWT token refreshed successfully")
                return True
            except Exception as json_err:
                logging.error(f"Failed to parse JWT response: {json_err}")
                return False
        elif response.status_code == 401:
            logging.error("Authentication failed (401). Please check your credentials.")
            return False
        elif response.status_code == 500:
            logging.error("Server error (500). Please try again later.")
            return False
        else:
            logging.warning(f"JWT token refresh failed with status {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        logging.error("JWT login timeout. Please check your internet connection.")
        return False
    except Exception as e:
        logging.error(f"JWT token refresh error: {e}")
        return False


def refresh_jwt_token_with_refresh():
    """Use the stored refresh token to mint a new access/refresh pair.
    Per the GameVault OpenAPI spec, the refresh token is sent as
    `Authorization: Bearer <refresh_token>` to POST /api/auth/refresh.
    """
    global JWT_TOKEN, JWT_REFRESH
    if not JWT_REFRESH:
        return False
    try:
        base_url = ensure_url_protocol(config['SETTINGS'].get('url'))
        url = f"{base_url}/api/auth/refresh"
        response = requests.post(
            url,
            headers={'Authorization': f'Bearer {JWT_REFRESH}'},
            timeout=30,
        )
        if response.status_code == 200:
            data = response.json()
            JWT_TOKEN = data.get('access_token', JWT_TOKEN)
            JWT_REFRESH = data.get('refresh_token', JWT_REFRESH)
            logging.debug("JWT refreshed via refresh token")
            return True
        elif response.status_code == 401:
            # refresh token expired; force a full re-login
            logging.warning("Refresh token rejected; falling back to re-login")
            JWT_TOKEN = ''
            JWT_REFRESH = ''
            return False
        else:
            logging.warning(f"Refresh failed with status {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"Refresh-token request error: {e}")
        return False


def _relogin_with_keyring():
    """Last-resort recovery: re-login using the username/password stored in keyring."""
    username = config['SETTINGS'].get('username')
    password = keyring.get_password("GameVault-Snake", username) if username else None
    if username and password:
        return refresh_jwt_token(username, password)
    return False


def request(method, path, **kwargs):
    """Authenticated request wrapper.

    Sends a request through `requests.request`. If the response is 401 and we
    have a refresh token, attempts to refresh once and retry. If that fails,
    falls back to a full re-login using keyring credentials, then retries a
    final time. Callers don't need to know about the refresh flow.
    """
    # Default to JWT headers unless the caller passed their own.
    headers = kwargs.pop('headers', None)
    if not headers:
        headers = get_auth_headers('jwt')
    kwargs['headers'] = headers

    response = requests.request(method, path, **kwargs)

    if response.status_code != 401:
        return response

    # Try to recover the session.
    recovered = False
    if JWT_REFRESH and refresh_jwt_token_with_refresh():
        recovered = True
    elif _relogin_with_keyring():
        recovered = True

    if recovered:
        kwargs['headers'] = get_auth_headers('jwt')
        response = requests.request(method, path, **kwargs)

    return response


def fetch_server_news():
    """Fetch the server's news markdown from /api/config/news.

    Returns the decoded body as a string on success, or None on failure
    (offline, auth error, non-2xx). The endpoint is described in the
    OpenAPI spec at docs-json.json (operationId: getNews) and returns
    `application/octet-stream` — a UTF-8 markdown body. Intentionally
    uncached: callers re-fetch on demand so the user sees fresh news.
    """
    base = config['SETTINGS'].get('url')
    if not base:
        return None
    url = f"{base}/api/config/news"
    try:
        response = request('GET', url, timeout=10)
    except Exception as e:
        logging.debug(f"News fetch transport error: {e}")
        return None
    if response.status_code != 200:
        logging.debug(f"News fetch returned {response.status_code}")
        return None
    # Some servers send UTF-8 with a BOM; .content is bytes, decode
    # defensively so we don't crash on a leading BOM.
    try:
        return response.content.decode('utf-8-sig')
    except UnicodeDecodeError:
        return response.content.decode('utf-8', errors='replace')


def fetch_game_info(gid):
    """Fetch game info with caching and proper authentication."""
    # Check if the response is already in the cache and if it's expired
    cached_data = load_cache(gid)
    if cached_data:
        if is_cache_expired(cached_data['timestamp']):
            logging.debug(f"Cache for game {gid} expired, fetching new data...")
        else:
            logging.debug(f"Fetching game info from cache...")
            return cached_data['data']

    # GET /api/games/{id} takes no query parameters.
    url = f"{config['SETTINGS'].get('url')}/api/games/{gid}"
    response = request('GET', url, timeout=30)
    if response.status_code == 200:
        data = response.json()
        save_cache(gid, data)
        logging.debug(f"Successfully fetched game info for {gid}")
        return data
    else:
        logging.error(f"Failed to fetch game info for {gid}. Status code: {response.status_code}")
        return None


def update_game_user_metadata(gid, user_metadata):
    """PUT the admin-overridable `user_metadata` for `gid`.

    Calls `PUT /api/games/{gid}` with body
    `{"user_metadata": { ...fields... }}` (the GameVault `UpdateGameDto`
    schema). Endpoint is admin-only; a non-admin caller will get a
    403/401 and we return None so the caller can surface the error.

    On success, invalidates the local `fetch_game_info` cache for
    `gid` so the next page render shows the fresh values — otherwise
    the game page would keep showing the pre-save title/description
    for up to CACHE_EXPIRY seconds.

    Returns the parsed JSON response on success, or None on failure.
    """
    base = config['SETTINGS'].get('url')
    if not base:
        return None
    url = f"{base}/api/games/{gid}"
    body = {"user_metadata": user_metadata}
    try:
        response = request('PUT', url, json=body, timeout=30)
    except Exception as e:
        logging.error(f"update_game_user_metadata({gid}) transport error: {e}")
        return None
    if response.status_code not in (200, 201):
        logging.error(
            f"update_game_user_metadata({gid}) failed: "
            f"{response.status_code} {response.text[:200]}"
        )
        return None
    # Drop the cached copy so the next read picks up the saved values.
    try:
        delete_cache(gid)
    except Exception:
        pass
    try:
        return response.json()
    except Exception:
        return {}


def get_current_user_role():
    """Return the logged-in user's role number (0=USER, 1=EDITOR,
    2=ADMIN per the GameVault role enum) or None on failure.

    Hits `GET /api/users/me` and reads the `role` field. Cached
    in-memory for the lifetime of the process — the role doesn't
    change during a launcher session, so re-fetching on every gear
    click would be wasted round-trips.

    A None return is treated as "not admin" by every caller. We
    don't raise on transport errors (offline / not logged in) so the
    UI can degrade gracefully into the disabled-gear-button state.
    """
    cached = getattr(get_current_user_role, "_cache", None)
    if cached is not None:
        return cached
    base = config['SETTINGS'].get('url')
    if not base:
        return None
    try:
        response = request('GET', f"{base}/api/users/me", timeout=10)
        if response.status_code != 200:
            return None
        role = response.json().get("role")
        get_current_user_role._cache = role
        return role
    except Exception as e:
        logging.debug(f"get_current_user_role transport error: {e}")
        return None


def get_current_user_id():
    """Return the logged-in user's id, or None on failure.

    Hits `GET /api/users/me` and reads the `id` field. Cached in-memory
    for the lifetime of the process — the user can't change their own
    id, so re-fetching on every dialog open would be wasted round-trips.

    Mirrors `get_current_user_role`. The two helpers share the same
    endpoint but read different fields; we could refactor them into a
    single `get_current_user_info()` that returns the full /me payload
    but that's premature — adding a third field is a one-line change
    and the two callers (menu gate / Admin Panel self-demote check)
    need different fields.
    """
    cached = getattr(get_current_user_id, "_cache", None)
    if cached is not None:
        return cached
    base = config['SETTINGS'].get('url')
    if not base:
        return None
    try:
        response = request('GET', f"{base}/api/users/me", timeout=10)
        if response.status_code != 200:
            return None
        uid = response.json().get("id")
        get_current_user_id._cache = uid
        return uid
    except Exception as e:
        logging.debug(f"get_current_user_id transport error: {e}")
        return None


def list_users():
    """GET /api/users — return the parsed JSON list (or [] on error).

    Used by the Admin Panel to populate the user list. The endpoint
    is admin-only; a non-admin caller will get a 403 and we'll surface
    an empty list. We don't raise on failure because the dialog's
    "Refresh" button is the user's escape hatch from an empty list.
    """
    base = config['SETTINGS'].get('url')
    if not base:
        return []
    try:
        response = request('GET', f"{base}/api/users", timeout=30)
        if response.status_code != 200:
            logging.error(
                f"list_users failed: {response.status_code} "
                f"{response.text[:200]}"
            )
            return []
        return response.json() or []
    except Exception as e:
        logging.error(f"list_users transport error: {e}")
        return []


def update_user_role(user_id, role):
    """PUT /api/users/{user_id} with body `{"role": <int>}`.

    Used by the Admin Panel's per-row Save button. The endpoint is
    admin-only; a non-admin caller will get a 403 and we return False.

    We send only `role` per the UpdateUserDto shape (the server treats
    the rest of the body as "leave unchanged"), so a successful
    role-only PUT won't clobber the user's other fields. The
    GameVault source confirms PUT semantics are partial-update, not
    full-replace.
    """
    base = config['SETTINGS'].get('url')
    if not base:
        return False
    try:
        response = request(
            'PUT',
            f"{base}/api/users/{user_id}",
            json={"role": int(role)},
            timeout=30,
        )
        if response.status_code not in (200, 201):
            logging.error(
                f"update_user_role({user_id}, {role}) failed: "
                f"{response.status_code} {response.text[:200]}"
            )
        return response.status_code in (200, 201)
    except Exception as e:
        logging.error(f"update_user_role transport error: {e}")
        return False


def reindex_games():
    """PUT /api/games/reindex — trigger a server-side reindex.

    The endpoint is admin-only and the reindex runs asynchronously on
    the server (the response is 2xx once the job is queued, not once
    it finishes). We treat any 2xx as success and let the user know
    via the dialog's status label that the reindex has been
    triggered, not completed.

    60s timeout because reindex triggers a full provider rescan on
    the server, which can take a few seconds on a slow server even
    though the response is immediate.
    """
    base = config['SETTINGS'].get('url')
    if not base:
        return False
    try:
        response = request(
            'PUT', f"{base}/api/games/reindex", timeout=60,
        )
        if response.status_code not in (200, 201, 202):
            logging.error(
                f"reindex_games failed: {response.status_code} "
                f"{response.text[:200]}"
            )
        return response.status_code in (200, 201, 202)
    except Exception as e:
        logging.error(f"reindex_games transport error: {e}")
        return False


# Function to initialize the database and create the cache table if it doesn't exist
def init_db():
    # Ensure the directory for the database exists
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    # Create the database and the cache table if they don't exist
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                gid TEXT PRIMARY KEY,
                data TEXT,
                timestamp INTEGER
            )
        ''')

        # Create table for image BLOBs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache_images (
                gid TEXT PRIMARY KEY,
                image_data BLOB,
                UNIQUE(gid)
            )
        ''')
        conn.commit()

# Function to save cache data to the SQLite database
def save_cache(gid, data):
    """Persist `data` (a JSON-serializable object) in the `cache` table under
    the key `gid`. This stores game metadata only — image BLOBs are written
    by `get_box_art` (cover art) and `get_screenshots` (screenshots), which
    know which bytes belong to which game.
    """
    init_db()  # Ensure the database is initialized
    timestamp = int(time.time())  # Current timestamp in seconds

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO cache (gid, data, timestamp) VALUES (?, ?, ?)
        ''', (gid, json.dumps(data), timestamp))
        conn.commit()

# Function to load cache data from the SQLite database
def load_cache(gid):
    init_db()  # Ensure the database is initialized
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT data, timestamp FROM cache WHERE gid = ?', (gid,))
        result = cursor.fetchone()
        cache_result = None
        if result:
            data, timestamp = result
            # Only return if we have valid data AND a valid timestamp
            if timestamp is not None:
                cache_result = {
                    'data': json.loads(data),
                    'timestamp': timestamp
                }

        return cache_result


def delete_cache(gid):
    """Drop the cached `fetch_game_info` payload for `gid`. Used by
    `update_game_user_metadata` so the next page load sees the freshly
    saved values instead of the pre-save copy. No-op if the row
    doesn't exist; failures are logged but not raised."""
    try:
        init_db()
    except Exception:
        return
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM cache WHERE gid = ?', (gid,))
            conn.commit()
    except Exception as e:
        logging.debug(f"delete_cache({gid}) failed: {e}")


def load_image_blob(gid):
    """Load a cached image BLOB for a game under an arbitrary string key.
    Returns bytes or None. Used for both box art (key == gid) and
    screenshots (key == f"{gid}_screenshot_{i}").
    """
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT image_data FROM cache_images WHERE gid = ?', (gid,))
        row = cursor.fetchone()
        return row[0] if row else None


def save_image_blob(key, blob):
    """Upsert an image BLOB into `cache_images` under an arbitrary string key.

    The same table stores both box art (key == gid) and screenshots
    (key == f"{gid}_screenshot_{i}"). A non-empty `blob` is required.
    """
    if not blob:
        return
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT OR REPLACE INTO cache_images (gid, image_data) VALUES (?, ?)',
            (key, blob),
        )
        conn.commit()

# Function to check if the cached data has expired
def is_cache_expired(timestamp):
    current_time = int(time.time())
    if timestamp is None:
        return True  # No valid timestamp means cache is expired
    return current_time - timestamp > CACHE_EXPIRY_TIME


def fetch_game_titles():
    """Fetch game titles with caching and proper authentication.
    Uses cached credentials from keyring automatically.
    """
    gid = "game_titles"
    cached_data = load_cache(gid)

    # Get cached credentials from keyring
    username = config['SETTINGS'].get('username')
    password = keyring.get_password("GameVault-Snake", username)

    # First, refresh JWT token if credentials exist
    if username and password:
        refresh_jwt_token(username, password)

    # Use cached data if available and not expired
    if cached_data and not is_cache_expired(cached_data['timestamp']):
        logging.debug("Using cached game titles")
        return cached_data['data']

    # Ensure URL has protocol
    base_url = ensure_url_protocol(config['SETTINGS'].get('url'))

    # If online, fetch new titles
    if online_status:
        params = {'sortBy': 'title:ASC', 'limit': 100}
        try:
            response = request('GET', f"{base_url}/api/games", params=params, timeout=30)
            if response.status_code == 200:
                try:
                    data = response.json()
                    # GameVault returns a plain array of GamevaultGame.
                    # Defensive: some proxies wrap responses as {data: [...]}.
                    if isinstance(data, dict):
                        games = data.get('data', [])
                    else:
                        games = data
                    if not games:
                        return []
                    save_cache(gid, games)
                    return games
                except (ValueError, TypeError) as e:
                    logging.error(f"Failed to parse API response: {e}")
                    logging.debug(f"Response: {response.text[:500]}")
                    return []
            else:
                logging.error(f"Failed to fetch game titles. Status code: {response.status_code}")
                logging.debug(f"Response: {response.text[:500]}")
                return []
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch game titles: {e}")
            return []

    # Offline: fall back to whatever's cached (even if expired).
    logging.debug("GV Client Offline. Using cached game titles.")
    if cached_data and isinstance(cached_data, dict):
        return cached_data.get('data') or []
    return []


# GameVault encodes the install type in the download filename as
# `(W_P)`, `(W_S)`, etc. just before the file extension. The full
# tag list per the GameVault docs / OpenAPI spec:
#   W_P  — Windows Portable (extract + run .exe)
#   W_S  — Windows Setup   (extract + run setup.exe)
#   W_SW — Windows Software (launchers/tools — not yet supported here)
#   L_P  — Linux Portable  (extract + run .sh / .appimage)
#   L_S  — Linux Setup     (extract + run install.sh / .run)
#   L_SW — Linux Software  (not yet supported here)
_GAME_TYPE_TAGS = ("W_P", "W_S", "W_SW", "L_P", "L_S", "L_SW")
# Capture the type tag at the end of a filename, just before the
# extension. Examples:
#   "Foo (W_P).zip"           -> "W_P"
#   "Foo (v1.10) (W_S).7z"    -> "W_S"
#   "Foo.zip"                 -> None
_GAME_TYPE_RE = re.compile(
    r"\((W_P|W_S|W_SW|L_P|L_S|L_SW)\)\.[^.]+$", re.IGNORECASE
)


def detect_game_type(filename):
    """Return the GameVault type tag ('W_P', 'W_S', ...) parsed from
    `filename`, or None if no tag is present. The check is case-
    insensitive and matches `(TYPE).ext` at the end of the basename.
    """
    if not filename:
        return None
    m = _GAME_TYPE_RE.search(os.path.basename(filename))
    if not m:
        return None
    return m.group(1).upper()


def install_kind_for(game_type):
    """Map a GameVault type tag to the internal `install_kind` used
    by the new install pipeline:

      - "extract"     : portable game — extract, then launch the entry
                        point (.exe on Windows, .sh / .appimage on Linux).
      - "setup"       : setup-based game — extract, then run the
                        installer. Mark installed only after the
                        installer process exits cleanly.
      - "unsupported" : software (W_SW / L_SW) or unknown — surface
                        a "not yet supported" error in the UI.
    """
    if game_type in ("W_P", "L_P"):
        return "extract"
    if game_type in ("W_S", "L_S"):
        return "setup"
    return "unsupported"


# Patterns for files that look like a setup entry point. Mirrors the
# GameVault docs (setup.exe, install.exe, autorun.exe, setup_*.exe,
# setup-*.exe, unarc.exe) plus the Linux equivalents
# (install.sh, setup.sh, *.run).
_SETUP_BASENAMES = {
    "setup", "setup.exe", "install", "install.exe", "autorun",
    "autorun.exe", "unarc", "unarc.exe",
}


def _find_setup_entry(install_path):
    """Walk `install_path` for the setup executable. Returns the
    absolute path of the first match, preferring the GameVault-
    documented patterns. Returns None if nothing looks like a setup
    entry point.
    """
    for root, _dirs, files in os.walk(install_path):
        for name in files:
            lower = name.lower()
            if lower in _SETUP_BASENAMES:
                return os.path.join(root, name)
            if lower.startswith("setup_") and lower.endswith(".exe"):
                return os.path.join(root, name)
            if lower.startswith("setup-") and lower.endswith(".exe"):
                return os.path.join(root, name)
            if lower == "install.sh" or lower == "setup.sh" or lower.endswith(".run"):
                return os.path.join(root, name)
    return None


# Same ignore set as get_exes() — list of basenames (no .exe) for
# .exe files we should never offer as a launch candidate. Kept
# module-scope so the new helpers can reuse it without duplicating
# the long list.
_EXE_IGNORE_BASENAMES = [
    "arc", "autorun", "bssndrpt", "crashpad_handler", "crashreportclient",
    "crashreportserver", "dxdiag", "dxsetup", "dxwebsetup", "dxwebsetupinstaller",
    "installationkit", "installationmanager", "installationscript", "installationwizard",
    "installer", "installerassistant", "installersetup", "installerupdater", "installfile",
    "installscript", "installwizard", "notification_helper", "oalinst", "patcher",
    "patchinstaller", "patchmanager", "patchscript", "patchsetup", "patchupdater",
    "python", "pythonw", "quicksfv", "quickuninstall", "sendrpt", "setup",
    "setupassistant", "setupconfig", "setupfile", "setupinstaller", "setupkit",
    "setupmanager", "setupscript", "setuputility", "setupwizard", "skidrow",
    "smartsteaminstaller", "smartsteamloader_x32", "smartsteamloader_x64",
    "smartsteamuninstaller", "ubisoftgamelauncherinstaller", "ue4prereqsetup_x64",
    "unarc", "unins000", "unins001", "unins002", "uninst", "uninstall", "uninstallagent",
    "uninstallapplication", "uninstalldriver", "uninstaller", "uninstallerassistant",
    "uninstallhandler", "uninstallhelper", "uninstallmanager", "uninstallprogram",
    "uninstallscript", "uninstallservice", "uninstalltool", "uninstalltoolkit",
    "uninstallupdater", "uninstallutility", "uninstallwizard", "unitycrashhandler",
    "unitycrashhandler32", "unitycrashhandler64", "unrealcefsubprocess", "vc_redist.x64",
    "vc_redist.x86", "vcredist_x64", "vcredist_x642", "vcredist_x643", "vcredist_x86",
    "vcredist_x862", "vcredist_x863", "vcredist_x86_2008", "verify", "VC_redist.x86",
    "VC_redist.x64", "DXSETUP", "gfwlivesetup", "GfWLPKSetter",
]
_EXE_IGNORE_LIST = {f"{n}.exe" for n in _EXE_IGNORE_BASENAMES}


def _exes_under(install_path):
    """Walk `install_path` and return the first viable .exe candidate
    (using the same installer/unins/VC_redist ignore set as
    `get_exes()`). Returns an empty list if nothing matches.

    Unlike `get_exes()` this operates on an arbitrary path rather
    than resolving one from a gid, so it can be reused by the
    type-aware install pipeline.
    """
    for root, _dirs, files in os.walk(install_path):
        for name in files:
            if name.endswith(".exe") and name not in _EXE_IGNORE_LIST:
                return [os.path.join(root, name)]
    return []


def _walk_for_entry(install_path):
    """Return a list of likely entry-point files (Windows + Linux).
    Order is 'first match wins' — we return as soon as we have one
    absolute path. Linux .sh / .appimage / .run files at the top
    level are preferred since they're unambiguous entry points;
    otherwise we fall back to the .exe ignore set above.
    """
    if not install_path or not os.path.isdir(install_path):
        return []
    # Top-level Linux entry points first.
    for name in sorted(os.listdir(install_path)):
        full = os.path.join(install_path, name)
        if not os.path.isfile(full):
            continue
        lower = name.lower()
        if lower.endswith(".appimage") or lower.endswith(".sh") or lower.endswith(".run"):
            return [full]
    # Windows portable .exe (after installer/unins/VC_redist filter).
    return _exes_under(install_path)


def _find_entry_point(install_path, kind):
    """Return the absolute path of the runnable for this install:

      - "setup" (W_S / L_S) -> the setup executable, or None if no
        setup-named file was found.
      - "extract" (W_P / L_P) -> the first viable .exe / .sh /
        .appimage, or None.
    """
    if not install_path or not os.path.isdir(install_path):
        return None
    if kind == "setup":
        return _find_setup_entry(install_path)
    if kind == "extract":
        candidates = _walk_for_entry(install_path)
        return candidates[0] if candidates else None
    return None


def mark_setup_complete(gid):
    """Drop a `gamevault-setup-complete` marker in the install dir
    for `gid`. Called after a W_S / L_S setup process exits cleanly,
    so `is_game_installed` can distinguish 'extracted but not
    installed' from 'ready to play'. Idempotent — touching an
    existing marker is fine.

    Looks up the install dir by gid prefix glob so this works
    even when the title isn't known (e.g. from a background
    SetupRunner callback that fires without a prior game_info
    fetch)."""
    install_location = config['SETTINGS'].get('install_location')
    if not install_location:
        return False
    installs = os.path.join(install_location, "Installations")
    if not os.path.isdir(installs):
        return False
    prefix = f"({gid})"
    install_path = None
    try:
        for name in os.listdir(installs):
            if name.startswith(prefix):
                install_path = os.path.join(installs, name)
                break
    except OSError as e:
        logging.debug(f"Could not scan Installations for {gid}: {e}")
        return False
    if not install_path:
        logging.warning(f"No install dir found for {gid} to mark complete")
        return False
    os.makedirs(install_path, exist_ok=True)
    marker = os.path.join(install_path, "gamevault-setup-complete")
    try:
        Path(marker).touch()
        return True
    except OSError as e:
        logging.error(f"Could not mark setup complete for {gid}: {e}")
        return False


# ------------------------------------------------------------------
# 7z binary bootstrap
# ------------------------------------------------------------------
# 7z handles .zip, .7z, and .rar (both RAR3 and RAR5) in one binary,
# so we use it for every archive format. The user can either have
# `7z` (Windows) or `7z` / `7zz` (Linux) on PATH, or we download a
# portable build on first use.
#
# Build selection matters:
#
#   - `7zr.exe` (602KB) is the "lite" build that only handles 7z /
#     LZMA / split archives. It does NOT support .zip or .rar.
#     Good enough to bootstrap us — but not for actual extraction.
#   - `7za.exe` (859KB, in 7z2602-extra.7z) is the "standalone
#     console" build. Supports .zip + .7z + .tar.* but NOT .rar.
#   - `7z.exe` (576KB) with `7z.dll` (1.9MB) is the FULL build
#     that supports every format 7-Zip can read, including RAR3
#     and RAR5. This is what we want for actual extraction.
#
# On Windows, the full 7z.exe + 7z.dll ship INSIDE the NSIS
# installer `7z2602-x64.exe` (1.6MB) — which is itself a 7z
# self-extracting archive. So the Windows bootstrap is a two-step
# dance: (1) download the small 7zr.exe lite; (2) use it to crack
# open the installer SFX and pull out the full 7z.exe + 7z.dll.
# On Linux + macOS the .tar.xz already contains the full 7zz
# binary, so the bootstrap is one step.
_SEVEN_ZIP_VERSION = "26.02"
_SEVEN_ZIP_GITHUB_BASE = (
    f"https://github.com/ip7z/7zip/releases/download/{_SEVEN_ZIP_VERSION}"
)
# `7zr.exe` is universal across all Windows archs (it's a 32-bit
# x86 binary, runs on x64 via WoW64). It's only used for the one-
# time bootstrap of extracting the full 7z.exe from the SFX.
_BOOTSTRAP_WINDOWS_LITE = (
    f"{_SEVEN_ZIP_GITHUB_BASE}/7zr.exe",
    "7zr.exe",
    "exe",
)
# Per-platform downloads of the FULL 7-Zip build. The Linux/macOS
# tarballs contain a `7zz` (and `7zzs`) binary that supports every
# format including RAR. The Windows path is the NSIS installer,
# which is a 7z self-extracting archive containing the full
# 7z.exe + 7z.dll.
_7Z_DOWNLOAD_URLS = {
    ("Windows", "x86_64"): (
        f"{_SEVEN_ZIP_GITHUB_BASE}/7z{_SEVEN_ZIP_VERSION.replace('.', '')}-x64.exe",
        "7z-installer.exe",
        "sfx7z",   # NSIS / 7z self-extracting installer
    ),
    ("Linux", "x86_64"): (
        f"{_SEVEN_ZIP_GITHUB_BASE}/7z{_SEVEN_ZIP_VERSION.replace('.', '')}-linux-x64.tar.xz",
        "7z-linux-x64.tar.xz",
        "tarxz",
    ),
    ("Linux", "aarch64"): (
        f"{_SEVEN_ZIP_GITHUB_BASE}/7z{_SEVEN_ZIP_VERSION.replace('.', '')}-linux-arm64.tar.xz",
        "7z-linux-arm64.tar.xz",
        "tarxz",
    ),
    ("Linux", "armv7l"): (
        f"{_SEVEN_ZIP_GITHUB_BASE}/7z{_SEVEN_ZIP_VERSION.replace('.', '')}-linux-arm.tar.xz",
        "7z-linux-arm.tar.xz",
        "tarxz",
    ),
    ("Darwin", "x86_64"): (
        f"{_SEVEN_ZIP_GITHUB_BASE}/7z{_SEVEN_ZIP_VERSION.replace('.', '')}-mac.tar.xz",
        "7z-mac-x64.tar.xz",
        "tarxz",
    ),
    ("Darwin", "arm64"): (
        f"{_SEVEN_ZIP_GITHUB_BASE}/7z{_SEVEN_ZIP_VERSION.replace('.', '')}-mac.tar.xz",
        "7z-mac-arm64.tar.xz",
        "tarxz",
    ),
}


def _7z_tools_dir():
    """Return the on-disk directory where we keep a downloaded
    7z binary, creating it if necessary."""
    d = os.path.join(settings_location, "tools")
    os.makedirs(d, exist_ok=True)
    return d


def _find_7z_on_path():
    """Return the path to a system `7z` binary on PATH, or None.

    Looks for the conventional names per OS. Returns the first one
    that exists and is executable. The caller is responsible for
    invoking it correctly (the command line is the same across
    these names — only the binary name differs)."""
    import shutil
    if os.name == "nt":
        # Windows: the user might have 7z from the standard install
        # or a portable copy. Check the conventional names.
        for name in ("7z.exe", "7za.exe", "7zr.exe"):
            p = shutil.which(name)
            if p:
                return p
        return None
    # POSIX (Linux + macOS). 7-Zip ships `7zz` on Linux to avoid
    # the system `7z` shadow; the legacy `7z` is fine too.
    for name in ("7z", "7zz", "7zr", "7za"):
        p = shutil.which(name)
        if p:
            return p
    return None


def _ensure_windows_lite_bootstrap(tools_dir):
    """Download the small `7zr.exe` (lite, 7z-only) into `tools_dir`
    if it isn't already there. On Windows we use it as a one-time
    bootstrapper to crack open the NSIS installer SFX and pull out
    the full `7z.exe` + `7z.dll` — 7zr handles 7z archives, which
    is exactly what the installer is wrapped in.

    Returns the path to 7zr.exe. Raises RuntimeError on network
    failure (the caller surfaces a user-facing message)."""
    lite_path = os.path.join(tools_dir, "7zr.exe")
    if os.path.exists(lite_path):
        return lite_path
    url, archive_name, _ = _BOOTSTRAP_WINDOWS_LITE
    archive_path = os.path.join(tools_dir, archive_name)
    logging.debug(f"Downloading 7z lite bootstrapper from {url}")
    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(archive_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)
    except Exception as e:
        try:
            if os.path.exists(archive_path):
                os.remove(archive_path)
        except OSError:
            pass
        raise RuntimeError(
            f"Failed to download 7-Zip bootstrap from {url}: {e}"
        ) from e
    # The downloaded file IS the lite binary.
    try:
        os.replace(archive_path, lite_path)
    except OSError:
        if not os.path.exists(lite_path):
            shutil.copy2(archive_path, lite_path)
            try:
                os.remove(archive_path)
            except OSError:
                pass
    return lite_path


def _download_7z_binary():
    """Download the right 7-Zip binary for the current OS into
    `<user_data>/tools/`, extract if needed, mark executable on
    POSIX, and return the absolute path to the resulting binary.

    Raises a clear error if the OS/arch isn't in the URL table.
    """
    import platform
    import stat
    import tarfile
    import zipfile  # not used today, but kept for future formats

    system = platform.system()
    machine = platform.machine().lower()
    # Normalize machine names to the keys in _7Z_DOWNLOAD_URLS.
    machine_map = {
        "amd64": "x86_64", "x86_64": "x86_64", "x64": "x86_64",
        "aarch64": "aarch64", "arm64": "aarch64",
        "armv7l": "armv7l", "armv6l": "armv7l", "arm": "armv7l",
    }
    machine_key = machine_map.get(machine)
    if machine_key is None:
        raise RuntimeError(
            f"No 7-Zip download available for {system} / {machine}. "
            f"Please install `7z` and add it to PATH."
        )

    key = (system, machine_key)
    if key not in _7Z_DOWNLOAD_URLS:
        raise RuntimeError(
            f"No 7-Zip download available for {system} / {machine_key}. "
            f"Please install `7z` and add it to PATH."
        )

    url, archive_name, kind = _7Z_DOWNLOAD_URLS[key]
    tools_dir = _7z_tools_dir()
    archive_path = os.path.join(tools_dir, archive_name)

    # The final binary lives next to the downloaded archive. We pick
    # a stable name so get_7z_binary() can find it across runs. On
    # Windows the full build is `7z.exe` (which uses `7z.dll`); on
    # POSIX the equivalent standalone is `7zz`.
    if system == "Windows":
        binary_name = "7z.exe"
    else:
        binary_name = "7zz"
    binary_path = os.path.join(tools_dir, binary_name)

    if os.path.exists(binary_path):
        return binary_path  # already downloaded

    logging.debug(f"Downloading 7z from {url} -> {archive_path}")
    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(archive_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)
    except Exception as e:
        # Clean up a partial download so the next attempt retries
        # from scratch.
        try:
            if os.path.exists(archive_path):
                os.remove(archive_path)
        except OSError:
            pass
        raise RuntimeError(
            f"Failed to download 7-Zip from {url}: {e}. "
            f"Install `7z` manually and add it to PATH."
        ) from e

    if kind == "exe":
        # No current platform uses the bare-exe path; kept for
        # future use. The downloaded file IS the binary.
        try:
            os.replace(archive_path, binary_path)
        except OSError:
            shutil.copy2(archive_path, binary_path)
            try:
                os.remove(archive_path)
            except OSError:
                pass
    elif kind == "sfx7z":
        # Windows: the NSIS installer is a 7z self-extracting
        # archive. Use the lite 7zr.exe (downloaded as a bootstrap
        # step) to extract the full 7z.exe + 7z.dll from it. The
        # lite 7zr handles 7z archives natively, and the installer
        # SFX is a 7z payload wrapped in an NSIS stub.
        try:
            lite = _ensure_windows_lite_bootstrap(tools_dir)
        except Exception as e:
            raise RuntimeError(
                f"Failed to download the 7-Zip bootstrap binary: {e}. "
                f"Install 7-Zip and add it to PATH."
            ) from e
        extract_dir = os.path.join(tools_dir, "7z-full")
        if os.path.isdir(extract_dir):
            shutil.rmtree(extract_dir, ignore_errors=True)
        os.makedirs(extract_dir, exist_ok=True)
        try:
            proc = subprocess.run(
                [lite, "x", "-y",
                 f"-o{extract_dir.rstrip(os.sep)}",
                 archive_path, "7z.exe", "7z.dll", "7-zip.dll"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to run 7z lite bootstrap: {e}"
            ) from e
        if proc.returncode != 0:
            err_tail = (proc.stderr or "").strip().splitlines()[-5:]
            raise RuntimeError(
                "Failed to unpack 7-Zip installer: " +
                ("\n".join(err_tail) or f"exit code {proc.returncode}")
            )
        # Move the full 7z.exe (and its DLLs) up to tools_dir.
        for name in ("7z.exe", "7z.dll", "7-zip.dll"):
            p = os.path.join(extract_dir, name)
            if not os.path.exists(p):
                continue
            final = os.path.join(tools_dir, name)
            try:
                if os.path.exists(final):
                    os.remove(final)
                os.replace(p, final)
            except OSError as e:
                raise RuntimeError(
                    f"Could not move extracted {name} into place: {e}"
                ) from e
        if not os.path.exists(binary_path):
            raise RuntimeError(
                "7-Zip installer did not contain 7z.exe — "
                "the GitHub release may have changed layout."
            )
        # Drop the downloaded installer now that we have the binary.
        try:
            os.remove(archive_path)
        except OSError:
            pass
        try:
            shutil.rmtree(extract_dir, ignore_errors=True)
        except OSError:
            pass
    elif kind == "tarxz":
        # POSIX: the archive contains a `7zz` binary somewhere in
        # the tree. Extract and find it.
        try:
            with tarfile.open(archive_path, "r:xz") as tf:
                # The Linux archive has files at the top level
                # (e.g. `./7zz`, `./7zzs`, `./License.txt`). Extract
                # into a sibling dir so we don't pollute tools_dir
                # with hundreds of loose files.
                extract_dir = os.path.join(tools_dir, "7z-pkg")
                os.makedirs(extract_dir, exist_ok=True)
                tf.extractall(extract_dir)
        except Exception as e:
            raise RuntimeError(
                f"Downloaded 7-Zip archive is invalid: {e}"
            ) from e
        # Find the binary inside the extracted tree.
        candidate = None
        for root, _dirs, files in os.walk(os.path.join(tools_dir, "7z-pkg")):
            for name in files:
                if name == "7zz" or name == "7zzs":
                    candidate = os.path.join(root, name)
                    break
            if candidate:
                break
        if not candidate:
            raise RuntimeError(
                "Downloaded 7-Zip archive did not contain a 7zz binary"
            )
        # Move the binary to the canonical tools_dir path and clean up.
        try:
            if os.path.exists(binary_path):
                os.remove(binary_path)
            os.replace(candidate, binary_path)
        except OSError as e:
            raise RuntimeError(
                f"Could not move 7zz into place: {e}"
            ) from e
        try:
            shutil.rmtree(os.path.join(tools_dir, "7z-pkg"), ignore_errors=True)
        except OSError:
            pass
        # Drop the downloaded archive now that we have the binary.
        try:
            os.remove(archive_path)
        except OSError:
            pass
    else:
        raise RuntimeError(f"Unknown 7z download kind: {kind!r}")

    # On POSIX, mark the binary executable. The downloaded archive
    # usually has the bit set, but a move / copy can strip it.
    if os.name != "nt":
        try:
            st = os.stat(binary_path)
            os.chmod(binary_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError as e:
            logging.warning(f"Could not chmod 7zz: {e}")

    logging.debug(f"7z binary ready at {binary_path}")
    return binary_path


def get_7z_binary():
    """Return the absolute path to a working full 7-Zip binary
    (one that supports .zip, .7z, and .rar including RAR5).

    Resolution order:
      1. `7z` / `7zz` / `7za` on PATH. Returned without copying.
      2. A previously-downloaded copy in `<user_data>/tools/`.
      3. Auto-download the FULL build for the current OS:
           Windows: NSIS installer SFX, cracked open to extract
                    the bundled 7z.exe + 7z.dll.
           Linux/macOS: tar.xz that already contains 7zz.

    Raises RuntimeError with a user-actionable message if all three
    paths fail. The error is short enough to surface in the
    Downloads row's status text."""
    cached = _find_7z_on_path()
    if cached:
        return cached

    # Cached download?
    tools_dir = _7z_tools_dir()
    if os.name == "nt":
        candidate = os.path.join(tools_dir, "7z.exe")
    else:
        candidate = os.path.join(tools_dir, "7zz")
    if os.path.exists(candidate):
        return candidate

    # Last resort: download. This is what makes the app work on a
    # fresh Windows or Linux install with no system 7z.
    return _download_7z_binary()


def extract_with_7z(archive_path, dest_dir, seven_z_binary=None,
                     progress_callback=None):
    """Run `7z x -y -o<dest> <archive>` and raise on non-zero exit.

    When `progress_callback` is provided, it is called from this
    function's worker thread as 7z reports progress. The signature
    is `progress_callback(percent: float, current_file: str | None)`
    where `percent` is a float in 0..100 and `current_file` is the
    path of the file currently being extracted (just the basename
    for display), or None for intra-file progress lines that don't
    name a file.

    The callback is invoked on the worker thread; the caller is
    responsible for marshalling to the UI thread (e.g. via
    `self.after(0, ...)`). Pass `None` to disable progress
    reporting entirely.

    Output is captured and only logged at DEBUG. Returns the
    dest_dir on success; raises on failure with the captured
    stderr included in the error message.
    """
    if seven_z_binary is None:
        seven_z_binary = get_7z_binary()

    # 7z's `-o` switch needs a path with no trailing separator.
    dest = dest_dir.rstrip(os.sep)

    # The cmdline. -bsp1 turns on per-file progress to stdout
    # (we parse it below). It's harmless to leave on even when
    # no callback is set — the extra stdout is just ignored.
    cmd = [
        seven_z_binary,
        "x",          # extract with full paths
        "-y",         # auto-answer "yes" to overwrite prompts
        "-bsp1",      # per-file progress to stdout
        f"-o{dest}",
        archive_path,
    ]
    logging.debug(f"Running: {' '.join(cmd)}")

    # 7z's -bsp1 lines we care about look like:
    #     "  0%"
    #     " 99% 70"
    #     " 22% 63 - HOLE\\Binaries\\Win64\\HOLE-Win64-Shipping.exe"
    # We only need the percent (group 1) and the filename
    # (group 3, optional). The trailing file index (group 2) is
    # informational and not surfaced to the caller.
    progress_re = re.compile(
        r"^\s*(\d{1,3})%(?:\s+(\d+))?(?:\s+-\s+(.+?))?\s*$"
    )

    # We need to drain stdout and stderr in real time to avoid
    # the OS pipe buffer filling and blocking 7z. We use two
    # reader threads for that, plus the main thread waits for
    # the process to exit.
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,         # line-buffered
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            f"7z binary not found at {seven_z_binary!r}; please reinstall"
        ) from e

    # Per-thread state to collect what we read. Lists are
    # thread-safe for `append` under the GIL.
    stdout_chunks = []
    stderr_chunks = []

    def _drain(stream, sink):
        try:
            for line in iter(stream.readline, ""):
                sink.append(line)
        except Exception:
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    stdout_thread = threading.Thread(
        target=_drain, args=(proc.stdout, stdout_chunks), daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_drain, args=(proc.stderr, stderr_chunks), daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    # Parse progress lines as they arrive. The reader thread is
    # appending to stdout_chunks; we snapshot the length each
    # iteration so we only process new lines.
    parsed_last = 0
    try:
        while True:
            # Has the process exited?
            rc = proc.poll()
            # Process any new stdout lines. We don't strictly need
            # to wait until process exit to start parsing — 7z
            # emits the percent updates as files are extracted.
            while parsed_last < len(stdout_chunks):
                line = stdout_chunks[parsed_last]
                parsed_last += 1
                m = progress_re.match(line)
                if m and progress_callback is not None:
                    try:
                        pct = float(m.group(1))
                        current = m.group(3)  # may be None
                        progress_callback(pct, current)
                    except Exception as cb_err:
                        # A bad callback shouldn't kill the
                        # extract. Log at DEBUG and keep going.
                        logging.debug(f"progress_callback raised: {cb_err}")
                else:
                    # Non-progress line ("Extracting archive: ...",
                    # "Everything is Ok", etc.) — debug-log it
                    # so a missing 7z behavior is traceable.
                    stripped = line.rstrip()
                    if stripped:
                        logging.debug(f"7z: {stripped}")
            if rc is not None:
                break
            # Sleep a tick to avoid burning CPU. 50ms is the
            # sweet spot: snappy enough to feel live, slow
            # enough to not pin a core.
            time.sleep(0.05)
    except Exception:
        # The polling loop died for some reason — kill the
        # subprocess so we don't leak a half-extracted archive.
        try:
            proc.kill()
        except Exception:
            pass
        raise

    # Drain the rest of stdout/stderr (the reader threads will
    # exit naturally once their pipes close). We join with a
    # short timeout to avoid hanging the caller.
    stdout_thread.join(timeout=2.0)
    stderr_thread.join(timeout=2.0)
    # One more pass over any lines that arrived after our last
    # poll but before the reader threads finished.
    while parsed_last < len(stdout_chunks):
        line = stdout_chunks[parsed_last]
        parsed_last += 1
        m = progress_re.match(line)
        if m and progress_callback is not None:
            try:
                progress_callback(float(m.group(1)), m.group(3))
            except Exception:
                pass

    rc = proc.returncode

    if rc != 0:
        stderr_text = "".join(stderr_chunks)
        err_tail = stderr_text.strip().splitlines()[-5:]
        err = "\n".join(err_tail) or f"exit code {rc}"
        raise RuntimeError(
            f"7z failed to extract {archive_path} (rc={rc}): {err}"
        )

    return dest_dir


def _get_download_path(gid, path_only=False):
    """Get the correct download path for a game.

    Args:
        gid: Game ID.
        path_only: If True, do not call fetch_game_info — derive filenames from
            the gid only. Use this for cheap existence checks (sidebar
            rendering, "is installed?") that don't need the game's title.

    Returns:
        tuple: (download_path, install_path) or (None, None) on error
    """
    install_location = config['SETTINGS'].get('install_location')
    if path_only:
        game_name = None
        file_path_field = ''
    else:
        game_info = fetch_game_info(gid)
        if not game_info:
            return None, None
        game_name = game_info.get('title', f'Game_{gid}')
        # Extract filename from file_path (e.g., /files/Driftwood (W_P).rar -> Driftwood (W_P).rar)
        file_path_field = game_info.get('file_path', '')

    if file_path_field:
        import urllib.parse
        decoded = urllib.parse.unquote(file_path_field)
        filename = decoded.split('/')[-1]
    else:
        # No title/filename available; pick a deterministic stub.
        # The real filename is filled in once fetch_game_info is called.
        filename = f"game_{gid}.zip"

    if game_name is None:
        # Without the title we can't build a stable install_path. Use a stable
        # placeholder so the cheap path check at least works.
        game_name = f"Game_{gid}"

    download_dir = os.path.join(install_location, "Downloads")
    os.makedirs(download_dir, exist_ok=True)
    download_path = os.path.join(download_dir, f"({gid}){filename}")

    # Install path format: (GID)Game Name
    extract_dir = os.path.join(install_location, f"Installations/({gid}){game_name}")
    # Don't create the directory here - only unpack_game creates it
    install_path = extract_dir

    return download_path, install_path


def is_game_downloaded(gid):
    """Check if a game is downloaded (cheap path check, no network).

    The download path is `<install_location>/Downloads/(<gid>)<filename with type tag>`.
    We don't know the title or filename without a network call, so we
    glob for `(gid)*` — the gid prefix in parens is unique per game.
    """
    install_location = config['SETTINGS'].get('install_location')
    if not install_location:
        return False
    downloads = os.path.join(install_location, "Downloads")
    if not os.path.isdir(downloads):
        return False
    prefix = f"({gid})"
    try:
        for name in os.listdir(downloads):
            if name.startswith(prefix):
                return True
    except OSError:
        return False
    return False


def is_game_installed(gid, game_type=None):
    """Check if a game is fully installed and ready to play.

    The install path is `<install_location>/Installations/(<gid>)<Title>`.
    We don't know the title without a network call, so we glob for
    `(gid)*` under the Installations dir — the gid prefix in parens
    is unique per game. Once we find the install dir:

    - For "extract" (W_P / L_P) kinds, the dir existing is enough —
      extraction IS the install.
    - For "setup" (W_S / L_S) kinds, the dir must also have a
      `gamevault-setup-complete` marker (we drop it after the
      setup process exits cleanly). Without the marker, the game
      is "extracted but not installed".
    - Without a `game_type` hint (e.g. older callers), fall back
      to the cheap dir check.
    """
    install_location = config['SETTINGS'].get('install_location')
    if not install_location:
        return False
    installs = os.path.join(install_location, "Installations")
    if not os.path.isdir(installs):
        return False
    prefix = f"({gid})"
    install_path = None
    try:
        for name in os.listdir(installs):
            if name.startswith(prefix):
                # Subdir on disk: `<install_path>/(23)Geometry Survivor`
                install_path = os.path.join(installs, name)
                break
    except OSError:
        return False
    if not install_path or not os.path.isdir(install_path):
        return False
    if game_type is None:
        return True
    kind = install_kind_for(game_type)
    if kind == "setup":
        return os.path.exists(os.path.join(install_path, "gamevault-setup-complete"))
    if kind == "unsupported":
        return False
    return True


def unpack_game(gid, kind="extract", game_type=None,
                progress_callback=None):
    """Unpack a downloaded game archive. Behavior depends on `kind`:

      - "extract"  : portable game. Extract the archive, drop the
                     `gamevault-exec` marker, leave the archive on
                     disk (the user can clear it later).
      - "setup"    : setup-based game. Extract the archive, locate
                     the setup entry point (setup.exe on Windows,
                     install.sh / .run on Linux), but do NOT mark
                     the game as installed yet — that happens after
                     the setup process completes. The caller is
                     responsible for invoking the setup.
      - "unsupported" : no-op. Returns a failed result so callers
                     can surface an error.

    `progress_callback(percent, current_file)` is forwarded to
    `extract_with_7z` for the 7z code paths (.zip, .7z, .rar,
    and the 7z fallback for unknown extensions). For the stdlib
    `shutil.unpack_archive` path (.tar.* etc.) no per-file
    progress is available, so the callback is invoked once with
    (0.0, None) on entry and (100.0, None) on success. Pass None
    to disable progress reporting entirely. The callback is
    invoked from this function's worker thread; the caller is
    responsible for marshalling to the UI thread.

    Returns a dict:
        {"ok": bool, "kind": str, "install_path": str|None,
         "entry_point": str|None, "error": str|None}

    `entry_point` is the absolute path to the runnable for
    extract-kind games (the first non-installer .exe / .sh found),
    or the absolute path to the setup executable for setup-kind
    games. None for unsupported kinds or on failure.

    The archive is intentionally NOT deleted on success — the
    Downloads tab's "Clear" button handles that. We used to delete
    it, but that broke W_S games whose installer is bundled inside
    the same archive.
    """
    if kind == "unsupported":
        return {"ok": False, "kind": "unsupported", "install_path": None,
                "entry_point": None,
                "error": f"Software titles ({game_type}) are not yet supported"}

    download_path, install_path = _get_download_path(gid)

    if not download_path:
        return {"ok": False, "kind": kind, "install_path": None,
                "entry_point": None,
                "error": "Could not resolve download path"}

    if not os.path.exists(download_path):
        return {"ok": False, "kind": kind, "install_path": None,
                "entry_point": None,
                "error": f"Download file not found: {download_path}"}

    # 7z creates the install dir if it's missing, but `shutil.unpack_archive`
    # (used for .tar.*) does not. Create it up front so both code paths
    # behave the same.
    os.makedirs(install_path, exist_ok=True)

    archive_ext = os.path.splitext(download_path)[1].lower()

    try:
        # All .zip / .7z / .rar archives go through 7z. 7z handles
        # every modern variant (RAR3, RAR5, etc.) in one binary,
        # so we don't need py7zr / rarfile / pyunpack at all.
        if archive_ext in (".zip", ".7z", ".rar"):
            extract_with_7z(
                download_path, install_path,
                progress_callback=progress_callback,
            )
        elif archive_ext in (".tar", ".tar.gz", ".tar.bz2", ".tar.xz",
                             ".gz", ".tgz", ".bz2", ".xz"):
            # tar.* archives are best handled by the stdlib —
            # avoiding a 7z round-trip — and they don't usually
            # need multi-volume support.
            extract_path = os.path.join(install_path, "Files")
            os.makedirs(extract_path, exist_ok=True)
            if progress_callback is not None:
                try:
                    progress_callback(0.0, None)
                except Exception:
                    pass
            shutil.unpack_archive(download_path, extract_path)
            if progress_callback is not None:
                try:
                    progress_callback(100.0, None)
                except Exception:
                    pass
        else:
            # Unknown extension: try the stdlib, then 7z as a
            # last resort. 7z can sometimes read formats the
            # stdlib doesn't know about (e.g. .apk, .jar are
            # .zip under the hood and 7z handles them cleanly).
            try:
                extract_path = os.path.join(install_path, "Files")
                os.makedirs(extract_path, exist_ok=True)
                if progress_callback is not None:
                    try:
                        progress_callback(0.0, None)
                    except Exception:
                        pass
                shutil.unpack_archive(download_path, extract_path)
                if progress_callback is not None:
                    try:
                        progress_callback(100.0, None)
                    except Exception:
                        pass
            except (shutil.ReadError, ValueError):
                extract_with_7z(
                    download_path, install_path,
                    progress_callback=progress_callback,
                )

        # Create the gamevault-exec file after extraction. Used by
        # get_exe_selection() to know the install path is real.
        gamevault_exec = Path(install_path) / "gamevault-exec"
        gamevault_exec.touch()

        # Find the entry point based on kind. For 'extract' this is
        # the game's .exe / .sh; for 'setup' this is the installer
        # the caller will run.
        entry_point = _find_entry_point(install_path, kind)

        # Note: the downloaded archive is intentionally NOT deleted.
        # The Downloads tab's "Clear" button handles that.
        logging.debug(
            f"Unpacked {gid} (type={game_type or '?'}, kind={kind}) "
            f"to {install_path}, entry={entry_point}"
        )
        return {"ok": True, "kind": kind, "install_path": install_path,
                "entry_point": entry_point, "error": None}

    except RuntimeError as e:
        # Raised by extract_with_7z with a user-actionable message.
        logging.error(f"Failed to unpack {gid}: {e}")
        err = str(e)
    except Exception as e:
        logging.error(f"Failed to unpack {gid}: {type(e).__name__}: {e}")
        err = f"{type(e).__name__}: {e}"

    # Clean up on failure
    try:
        if install_path and os.path.exists(install_path):
            shutil.rmtree(install_path)
            logging.debug(f"Cleaned up failed install for {gid}")
    except Exception as cleanup_error:
        logging.error(f"Failed to clean up {install_path}: {cleanup_error}")
    return {"ok": False, "kind": kind, "install_path": None,
            "entry_point": None, "error": err}


def uninstall_game(gid):
    """Uninstall a game by removing its installation directory."""
    _, install_path = _get_download_path(gid)

    if not install_path:
        logging.warning(f"Could not get install path for {gid}")
        return False

    try:
        if os.path.exists(install_path):
            shutil.rmtree(install_path)
            logging.debug(f"Uninstalled {gid}")
            return True
        return True
    except Exception as e:
        logging.error(f"Failed to uninstall {gid}: {e}")
        return False

def get_exes(gid):
    """List the runnable files inside a game's install directory.

    Windows .exe candidates are filtered against the same installer
    / unins / VC_redist / dxsetup ignore set the type-aware helpers
    use (see `_EXE_IGNORE_LIST`).

    Linux entry points — `.sh`, `.appimage`, `.run` — are also
    picked up so L_P games show a valid runnable in the EXE
    selector. There's no installer/unins equivalent to filter on
    Linux, so they're included as-is.
    """
    _, install_path = _get_download_path(gid)
    if not install_path:
        return []
    destination = os.path.join(install_path, "")  # normalize trailing sep

    exes = []
    for root, _dirs, files in os.walk(destination):
        for filename in files:
            lower = filename.lower()
            if lower.endswith(".exe") and filename not in _EXE_IGNORE_LIST:
                exes.append(os.path.join(root, filename))
            elif lower.endswith(".sh") or lower.endswith(".appimage") or lower.endswith(".run"):
                exes.append(os.path.join(root, filename))
    return exes

def delete_download(gid):
    """Delete a downloaded game file (keep unpacked game)."""
    download_path, _ = _get_download_path(gid)

    if download_path and os.path.exists(download_path):
        try:
            os.remove(download_path)
            logging.debug(f"Deleted download for {gid}")
            return True
        except Exception as e:
            logging.error(f"Failed to delete download {gid}: {e}")
            return False

    return False


def get_box_art(gid):
    """Download and cache box art from GameVault server.

    Returns a path to a real JPEG file on disk (or the bundled placeholder
    when the server has no cover art for this game). The returned path is
    stable across calls so the caller can hand it to PIL without worrying
    about temp-file cleanup.
    """
    not_found = resource_path("bin/img/not_found.jpg")

    try:
        game_info = fetch_game_info(gid)

        # Resolve a cover Media object. Prefer user_metadata.cover (admin-uploaded,
        # single, usually present); fall back to provider_metadata[*].cover.
        image_id = None
        user_md = (game_info or {}).get('user_metadata') or {}
        user_cover = user_md.get('cover') if isinstance(user_md, dict) else None
        if user_cover and isinstance(user_cover, dict) and user_cover.get('id'):
            image_id = user_cover['id']
        else:
            for provider in (game_info or {}).get('provider_metadata') or []:
                if not isinstance(provider, dict):
                    continue
                cover_info = provider.get('cover') or {}
                if cover_info.get('id'):
                    image_id = cover_info['id']
                    break

        if not image_id:
            logging.debug(f"No cover data for game {gid}")
            return not_found

        # Stable on-disk cache path keyed by the media id.
        image_dir = os.path.join(settings_location, "cache", "boxart")
        os.makedirs(image_dir, exist_ok=True)
        safe_id = str(image_id).replace('/', '_').replace('\\', '_')
        image_path = os.path.join(image_dir, f"{safe_id}.jpg")

        # Fast path: the file is already on disk from a previous run.
        if os.path.exists(image_path) and os.path.getsize(image_path) > 0:
            logging.debug(f"Using on-disk box art for {gid}: {image_path}")
            return image_path

        # Slower path: a BLOB exists in the database from a previous run, but
        # the on-disk file is gone. Re-hydrate the on-disk cache from the BLOB.
        cached_blob = load_image_blob(gid)
        if cached_blob:
            try:
                with open(image_path, 'wb') as f:
                    f.write(cached_blob)
                logging.debug(f"Re-hydrated box art for {gid} from BLOB cache: {image_path}")
                return image_path
            except OSError as e:
                logging.warning(f"Failed to write BLOB to {image_path}: {e}")

        # Cold path: download from GameVault /api/media/{id} endpoint.
        # Use the request() wrapper so 401s auto-refresh the JWT.
        base_url = ensure_url_protocol(config['SETTINGS'].get('url'))
        media_url = f"{base_url}/api/media/{image_id}"
        logging.debug(f"get_box_art: requesting {media_url}")

        try:
            response = request('GET', media_url, headers={'accept': 'image/*'}, timeout=15)
            logging.debug(f"get_box_art: response status = {response.status_code}, content length = {len(response.content)}")
        except requests.exceptions.RequestException as e:
            logging.warning(f"Request error fetching cover art: {e}")
            return not_found

        if response.status_code == 200 and response.content:
            # Save to on-disk cache first (so the label has a stable path even
            # if the DB write fails).
            try:
                with open(image_path, 'wb') as f:
                    f.write(response.content)
            except OSError as e:
                logging.warning(f"Failed to write box art to {image_path}: {e}")
                return not_found

            # Persist as a BLOB for cross-machine portability (the on-disk
            # cache is platform-specific, the BLOB is the same everywhere).
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        'INSERT OR REPLACE INTO cache_images (gid, image_data) VALUES (?, ?)',
                        (gid, response.content),
                    )
                    conn.commit()
            except Exception as db_err:
                logging.warning(f"Failed to store image in database: {db_err}")

            logging.debug(f"Downloaded and cached box art: {image_path}")
            return image_path
        else:
            logging.warning(f"Failed to fetch box art: Status {response.status_code}")
            return not_found

    except Exception as e:
        logging.warning(f"Unexpected error fetching cover art: {e}")
        import traceback
        logging.debug(traceback.format_exc())
        return not_found

def get_image(gid, boxart=True):
    """Get image path for game (box art or other).
    Uses cached credentials from keyring automatically.
    """
    if boxart:
        return get_box_art(gid)
    return resource_path("bin/img/not_found.jpg")


def get_screenshots(gid):
    """Return a list of on-disk file paths to screenshot thumbnails for `gid`.

    Sources URLs in this order:
      1. user_metadata.url_screenshots (admin-curated; preferred)
      2. provider_metadata[*].url_screenshots (first non-empty)

    URLs that match the game's `cover.source_url` or `background.source_url`
    are filtered out — the server commonly includes the marketing hero image
    in `url_screenshots` as the last entry, which the user sees duplicated in
    the cover-art widget. Treating the cover/background as a "screenshot" is
    almost never what was intended.

    Each URL is cached as a BLOB in `cache_images` keyed
    `f"{gid}_screenshot_{i}"` and re-hydrated to disk on subsequent runs under
    `<settings_location>/cache/screenshots/{gid}_{i}.{ext}`. The function
    returns [] when the game has no `url_screenshots` (most don't) or every
    fetch failed — it never raises into the UI.
    """
    try:
        game_info = fetch_game_info(gid)

        # Resolve a list of screenshot URLs. Prefer user_metadata (admin-curated,
        # single list); fall back to provider_metadata[*].url_screenshots.
        urls = []
        user_md = (game_info or {}).get('user_metadata') or {}
        if isinstance(user_md, dict):
            candidate = user_md.get('url_screenshots')
            if isinstance(candidate, list) and candidate:
                urls = [u for u in candidate if isinstance(u, str) and u]
        if not urls:
            for provider in (game_info or {}).get('provider_metadata') or []:
                if not isinstance(provider, dict):
                    continue
                candidate = provider.get('url_screenshots')
                if isinstance(candidate, list) and candidate:
                    urls = [u for u in candidate if isinstance(u, str) and u]
                    if urls:
                        break

        # Collect URLs that should NOT be shown as screenshots: the cover's
        # and background's source URLs across all metadata sources. The
        # server often lists the marketing hero/boxshot as the last
        # screenshot, which the user perceives as a duplicate of the cover.
        exclude = set()
        for src in ([user_md] if isinstance(user_md, dict) else []):
            for field in ('cover', 'background'):
                obj = src.get(field) or {}
                if isinstance(obj, dict):
                    s = obj.get('source_url')
                    if isinstance(s, str) and s:
                        exclude.add(s)
        for provider in (game_info or {}).get('provider_metadata') or []:
            if not isinstance(provider, dict):
                continue
            for field in ('cover', 'background'):
                obj = provider.get(field) or {}
                if isinstance(obj, dict):
                    s = obj.get('source_url')
                    if isinstance(s, str) and s:
                        exclude.add(s)

        if exclude:
            before = len(urls)
            urls = [u for u in urls if u not in exclude]
            filtered = before - len(urls)
            if filtered:
                logging.debug(
                    f"Filtered {filtered} cover/background URL(s) from "
                    f"screenshot list for game {gid}"
                )

        if not urls:
            logging.debug(f"No url_screenshots for game {gid}")
            return []

        # Stable on-disk cache dir.
        image_dir = os.path.join(settings_location, "cache", "screenshots")
        os.makedirs(image_dir, exist_ok=True)

        # Helper: pick a sensible file extension from a URL.
        import urllib.parse
        def _ext_for(url):
            try:
                path = urllib.parse.urlsplit(url).path
            except ValueError:
                return '.jpg'
            _, ext = os.path.splitext(path.lower())
            if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                return '.jpg' if ext == '.jpeg' else ext
            return '.jpg'

        paths = []
        for i, url in enumerate(urls):
            key = f"{gid}_screenshot_{i}"
            image_path = os.path.join(image_dir, f"{gid}_{i}{_ext_for(url)}")

            # Fast path: the file is already on disk from a previous run.
            if os.path.exists(image_path) and os.path.getsize(image_path) > 0:
                logging.debug(f"Using on-disk screenshot for {gid}#{i}: {image_path}")
                paths.append(image_path)
                continue

            # Slower path: a BLOB exists in the database from a previous run,
            # but the on-disk file is gone. Re-hydrate from BLOB.
            cached_blob = load_image_blob(key)
            if cached_blob:
                try:
                    with open(image_path, 'wb') as f:
                        f.write(cached_blob)
                    logging.debug(f"Re-hydrated screenshot for {gid}#{i} from BLOB")
                    paths.append(image_path)
                    continue
                except OSError as e:
                    logging.warning(f"Failed to write BLOB to {image_path}: {e}")

            # Cold path: download the external URL. The request() wrapper is
            # the same one used elsewhere and auto-refreshes JWT on 401, but
            # external screenshot hosts won't need auth — Accept: image/* is
            # just to be polite to the server.
            logging.debug(f"get_screenshots: fetching {gid}#{i} from {url}")
            try:
                response = request('GET', url, headers={'accept': 'image/*'}, timeout=20)
            except requests.exceptions.RequestException as e:
                logging.warning(f"Request error fetching screenshot {gid}#{i}: {e}")
                continue

            if response.status_code != 200 or not response.content:
                logging.warning(
                    f"Failed to fetch screenshot {gid}#{i}: status "
                    f"{response.status_code}, {len(response.content)} bytes"
                )
                continue

            # Write to disk first so the caller has a stable path even if the
            # BLOB write fails.
            try:
                with open(image_path, 'wb') as f:
                    f.write(response.content)
            except OSError as e:
                logging.warning(f"Failed to write screenshot to {image_path}: {e}")
                continue

            try:
                save_image_blob(key, response.content)
            except Exception as db_err:
                logging.warning(f"Failed to store screenshot BLOB for {key}: {db_err}")

            paths.append(image_path)

        return paths

    except Exception as e:
        logging.warning(f"Unexpected error fetching screenshots for {gid}: {e}")
        import traceback
        logging.debug(traceback.format_exc())
        return []


def get_exe_selection(gid):
    """Get the selected executable for a game.

    Reads the `gamevault-exec` marker file in the install dir for
    a saved `Executable=<path>` line. If the marker exists but is
    empty (the common case — `unpack_game` just `touch()`es the
    file), fall back to the first valid .exe / .sh / .appimage
    found by `get_exes()`. If neither yields a path, return
    "Install to Play" so the EXE selector shows the placeholder.
    """
    install_location = config['SETTINGS'].get('install_location')
    game_name = fetch_game_info(gid)['title']
    extract_path = os.path.join(install_location, f"Installations/({gid}){game_name}")

    marker = os.path.join(extract_path, "gamevault-exec")
    if os.path.exists(marker):
        try:
            with open(marker, "r") as file:
                content = file.read()
            for line in content.splitlines():
                if line.startswith('Executable='):
                    value = line.split('=', 1)[1].strip()
                    if value and os.path.exists(value):
                        return value
        except OSError as e:
            logging.debug(f"Could not read {marker}: {e}")

    # Marker missing, empty, or its recorded exe is gone — fall
    # back to the first viable runnable in the install dir. This
    # keeps the EXE selector useful right after a fresh install.
    exes = get_exes(gid)
    if exes:
        return exes[0]

    # No runnable found — show the placeholder text in the selector.
    return "Install to Play"


def clear_cache():
    """Clear the cache database."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    image_dir = os.path.join(settings_location, "cache", "boxart")
    if os.path.exists(image_dir):
        for f in os.listdir(image_dir):
            os.remove(os.path.join(image_dir, f))
    logging.debug("Cache cleared")


def get_download_info_for_gid(gid):
    """Get download URL and path for a game ID. Used by DownloadManager.

    Returns:
        tuple: (download_url, download_path, filename) or (None, None, None) on error
    """
    ensure_url_protocol(config['SETTINGS'].get('url'))

    # Get credentials from keyring
    username = config['SETTINGS'].get('username')
    password = keyring.get_password("GameVault-Snake", username)

    # Refresh JWT token
    refresh_jwt_token(username, password)

    # Fetch game info to get the download URL
    game_info = fetch_game_info(gid)
    if not game_info:
        logging.error(f"Failed to fetch game info for {gid}")
        return None, None, None

    # GameVault API returns download URL in different possible field names
    download_url = game_info.get('downloadUrl') or game_info.get('download_url') or game_info.get('file_url')

    # If no downloadUrl in game info, use the proper API download endpoint
    if not download_url:
        base_url = config['SETTINGS'].get('url')
        if base_url and not base_url.startswith('http://') and not base_url.startswith('https://'):
            base_url = f"https://{base_url}"
        base_url = base_url.rstrip('/')
        download_url = f"{base_url}/api/games/{gid}/download"

    # Get the filename from the file_path in game_info
    filename = game_info.get('file_path', '')
    if filename:
        import urllib.parse
        decoded_filename = urllib.parse.unquote(filename)
        filename = decoded_filename.split('/')[-1]
    else:
        logging.warning(f"No filename in game_info for {gid}")
        filename = f"game_{gid}.zip"

    install_location = config['SETTINGS'].get('install_location')
    download_dir = os.path.join(install_location, "Downloads")
    os.makedirs(download_dir, exist_ok=True)

    download_path = os.path.join(download_dir, f"({gid}){filename}")

    logging.debug(f"Download info for {gid}: {download_url} -> {download_path}")
    return download_url, download_path, filename