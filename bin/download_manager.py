import threading
import logging
import os
import re
import json
import requests


class DownloadManager:
    """Manages game downloads with pause/resume/cancel and real HTTP Range resume.

    Behaviour:
    - `start_download(gid, ...)` will resume a partially-downloaded file at the
      same `filepath` by sending `Range: bytes=N-` and appending bytes.
    - If the server ignores the Range request and returns 200, the partial file
      is overwritten from byte 0 (so the worst case is a re-download, not corruption).
    - `pause_download` keeps the partial file.
    - `stop_download` keeps the partial file (semantically the same as pause,
      exposed so the UI can clear "Downloading…" state). Use `clear_partial`
      to actually delete the file.
    - `clear_partial(gid)` deletes the on-disk partial file.
    """

    # Match a Content-Range header: `bytes 0-1023/5000`
    _CONTENT_RANGE_RE = re.compile(r'bytes\s+(\d+)-(\d+)/(\d+|\*)', re.IGNORECASE)

    def __init__(self):
        self._downloads = {}  # gid -> DownloadInfo
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Helpers: persistent total size
    # ------------------------------------------------------------------

    def _size_path(self, filepath):
        return filepath + '.expected_size'

    def _read_expected_size(self, filepath):
        """Return the file's known total size (from a previous non-Range GET), or 0."""
        sidecar = self._size_path(filepath)
        if not os.path.exists(sidecar):
            return 0
        try:
            with open(sidecar, 'r') as f:
                return int((f.read() or '0').strip() or 0)
        except (OSError, ValueError):
            return 0

    def _write_expected_size(self, filepath, size):
        if not size:
            return
        try:
            with open(self._size_path(filepath), 'w') as f:
                f.write(str(size))
        except OSError as e:
            logging.debug(f"Could not write expected-size sidecar: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_download(self, gid, url, filepath, headers=None, progress_callback=None, complete_callback=None):
        """Start (or resume) a download.

        Args:
            gid: Game ID
            url: Download URL
            filepath: Local file path
            headers: HTTP headers including auth (e.g., Authorization, Accept)
            progress_callback: Callback(progress_percentage)
            complete_callback: Callback(success, message)
        """
        with self._lock:
            if gid in self._downloads and self._downloads[gid]['status'] == 'downloading':
                logging.warning(f"Download already in progress for {gid}")
                return False

            stop_event = threading.Event()

            # If a partial file exists from a previous run, we'll resume from
            # the end of it. Otherwise start at byte 0.
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            existing_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0

            self._downloads[gid] = {
                'status': 'downloading',
                'progress': 0,
                'url': url,
                'filepath': filepath,
                'thread': None,
                'stop_event': stop_event,
                'paused': False,
                'session': None,
                'headers': headers or {},
                'offset': existing_size,
                'total_size': 0,
            }

            def wrapped_progress(percent):
                with self._lock:
                    if gid in self._downloads:
                        self._downloads[gid]['progress'] = percent
                if progress_callback:
                    progress_callback(percent)

            def wrapped_complete(success, message):
                with self._lock:
                    if gid in self._downloads:
                        self._downloads[gid]['status'] = 'complete' if success else 'error'
                if complete_callback:
                    complete_callback(success, message)

        # Start download in background thread
        def download_thread():
            session = None
            try:
                session = requests.Session()
                with self._lock:
                    self._downloads[gid]['session'] = session

                req_headers = dict(self._downloads[gid]['headers'] or {'Accept': 'application/octet-stream, */*'})
                offset = self._downloads[gid]['offset']

                # Learn the file's total size up front with a HEAD request.
                # The server may return either 200 (full file) or 206 (partial);
                # Content-Length on a 200 is the file's total size. Some servers
                # (e.g. GameVault's streamable endpoint) take a long time on HEAD
                # for large files, so we keep the timeout short and fall back to
                # inferring the total from the GET response's headers.
                total_size = 0
                try:
                    head_resp = session.head(url, headers=req_headers, timeout=10, allow_redirects=True)
                    if head_resp.status_code in (200, 206):
                        cl = head_resp.headers.get('Content-Length')
                        if cl and cl.isdigit():
                            total_size = int(cl)
                except Exception as e:
                    logging.debug(f"HEAD preflight failed for {gid}: {e}")

                # If the on-disk partial is at or beyond the total size, the
                # previous download finished. No need to fetch again.
                if total_size and offset >= total_size:
                    logging.debug(f"Partial file for {gid} already complete ({offset} >= {total_size})")
                    with self._lock:
                        self._downloads[gid]['total_size'] = total_size
                        self._downloads[gid]['progress'] = 100
                    wrapped_progress(100)
                    wrapped_complete(True, "Already complete")
                    return

                if offset > 0:
                    req_headers['Range'] = f'bytes={offset}-'
                    logging.debug(f"Resuming download for {gid} from byte {offset}")

                response = session.get(url, headers=req_headers, stream=True, timeout=300)

                if response.status_code not in (200, 206):
                    wrapped_complete(False, f"HTTP {response.status_code}")
                    return

                # Resolve the total file size. We prefer (in order):
                #   1. Content-Range (gives the real total even on a 206)
                #   2. The HEAD preflight's Content-Length (set above)
                #   3. The GET's Content-Length, but only if it's at least as
                #      large as the on-disk partial — otherwise it's a slice.
                cr_total = self._total_from_content_range(response)
                if cr_total:
                    total_size = cr_total

                # When the server returns 200 (full body) but we asked for a
                # Range, the response is ambiguous: did the server ignore us
                # and send the whole file, or did it slice but use the wrong
                # status code? We use a sidecar file (`.expected_size`) to
                # remember the real total from a previous download. If the
                # response's Content-Length matches that total, treat as full
                # and restart; otherwise treat as a slice and append.
                cl = response.headers.get('Content-Length')
                cl_int = int(cl) if cl and cl.isdigit() else None
                if response.status_code == 200 and offset > 0:
                    expected = self._read_expected_size(filepath)
                    if cl_int and expected and cl_int >= expected:
                        logging.warning(
                            f"Server returned full body for resume of {gid} "
                            f"(CL={cl_int} >= expected={expected}); restarting from 0"
                        )
                        offset = 0
                        self._downloads[gid]['offset'] = 0
                        with open(filepath, 'wb') as f:
                            pass
                    else:
                        logging.debug(
                            f"Server returned truncated body for {gid} "
                            f"(CL={cl}, expected={expected}); keeping offset {offset} and appending"
                        )

                # Persist the file's known total size as a sidecar so a future
                # resume can tell "the server sent a slice" from "the server
                # sent the full file". This only fires when the server gave us
                # a full body (offset==0) with a real Content-Length.
                if response.status_code == 200 and offset == 0 and cl_int:
                    if not total_size or cl_int > total_size:
                        total_size = cl_int
                    self._write_expected_size(filepath, cl_int)

                if total_size:
                    with self._lock:
                        self._downloads[gid]['total_size'] = total_size

                chunk_size = 65536  # 64KB chunks
                downloaded = offset

                # Open the file in append mode when resuming, write mode when fresh.
                file_mode = 'ab' if offset > 0 else 'wb'
                with open(filepath, file_mode) as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        # Stop signal
                        if stop_event.is_set():
                            logging.debug(f"Download stopped for {gid}")
                            wrapped_complete(False, "Stopped")
                            return

                        # Pause loop
                        while self._downloads.get(gid, {}).get('paused', False):
                            if stop_event.is_set():
                                wrapped_complete(False, "Stopped")
                                return
                            stop_event.wait(0.5)

                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                            if total_size:
                                progress = (downloaded / total_size) * 100
                                wrapped_progress(progress)

                wrapped_complete(True, "Complete")
                logging.debug(f"Downloaded {gid} to {filepath}")
                # Successful download — drop the sidecar.
                sidecar = self._size_path(filepath)
                if os.path.exists(sidecar):
                    try:
                        os.remove(sidecar)
                    except OSError:
                        pass

            except Exception as e:
                logging.error(f"Download error for {gid}: {e}")
                wrapped_complete(False, str(e))
            finally:
                if session is not None:
                    session.close()

        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()
        with self._lock:
            self._downloads[gid]['thread'] = thread

        logging.debug(f"Download started for {gid}: {url}")
        return True

    def pause_download(self, gid):
        """Pause a download. Keeps the partial file so resume can continue."""
        with self._lock:
            if gid not in self._downloads:
                logging.warning(f"No download found for {gid}")
                return False

            download_info = self._downloads[gid]
            if download_info['status'] != 'downloading':
                logging.warning(f"Download not in progress for {gid}")
                return False

            download_info['paused'] = True
            logging.debug(f"Download paused for {gid}")
            return True

    def resume_download(self, gid):
        """Resume a paused download by clearing the paused flag."""
        with self._lock:
            if gid not in self._downloads:
                logging.warning(f"No download found for {gid}")
                return False

            download_info = self._downloads[gid]
            if download_info['status'] != 'downloading':
                logging.warning(f"Download not in progress for {gid}")
                return False

            if not download_info['paused']:
                logging.warning(f"Download not paused for {gid}")
                return False

            download_info['paused'] = False
            # Set stop event briefly to wake up the wait loop
            download_info['stop_event'].set()
            download_info['stop_event'].clear()
            logging.debug(f"Download resumed for {gid}")
            return True

    def stop_download(self, gid):
        """Stop a download. Keeps the partial file so a future
        start_download can resume from where it left off.
        Use `clear_partial(gid)` to actually delete the file."""
        with self._lock:
            if gid not in self._downloads:
                logging.warning(f"No download found for {gid}")
                return False

            download_info = self._downloads[gid]
            stop_event = download_info['stop_event']

            stop_event.set()
            download_info['status'] = 'stopped'

            if download_info.get('session'):
                try:
                    download_info['session'].close()
                except Exception:
                    pass

            logging.debug(f"Download stopped for {gid} (partial file kept at {download_info.get('filepath')})")
            return True

    def clear_partial(self, gid):
        """Delete the on-disk partial file for a stopped download.

        Also forgets the cached download record, so a future start_download
        begins from byte 0.
        """
        with self._lock:
            info = self._downloads.get(gid)
            filepath = info.get('filepath') if info else None

        # Only delete if the download is not currently in progress.
        if info and info.get('status') == 'downloading':
            logging.warning(f"Refusing to clear partial for active download {gid}")
            return False

        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
                logging.debug(f"Cleared partial file for {gid}: {filepath}")
            except Exception as e:
                logging.error(f"Failed to clear partial for {gid}: {e}")
                return False

        # Also remove the expected-size sidecar if present.
        sidecar = self._size_path(filepath) if filepath else None
        if sidecar and os.path.exists(sidecar):
            try:
                os.remove(sidecar)
            except OSError:
                pass

        with self._lock:
            self._downloads.pop(gid, None)
        return True

    # ------------------------------------------------------------------
    # Read-only helpers (kept for backward compat with main.py / tests)
    # ------------------------------------------------------------------

    def is_downloading(self, gid):
        with self._lock:
            return gid in self._downloads and self._downloads[gid]['status'] == 'downloading'

    def is_paused(self, gid):
        with self._lock:
            return gid in self._downloads and self._downloads[gid].get('paused', False)

    def get_download_info(self, gid):
        with self._lock:
            return self._downloads.get(gid)

    def get_progress(self, gid):
        with self._lock:
            if gid in self._downloads:
                return self._downloads[gid]['progress']
            return 0

    def get_status(self, gid):
        with self._lock:
            if gid in self._downloads:
                return self._downloads[gid]['status']
            return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_total_size(self, response, offset):
        """Return the full file size in bytes, derived from the response headers.

        - When the server returns a 206 with Content-Range, the value after
          the slash is the full size.
        - When the server returns a 200 (full body), Content-Length is the
          full size.
        - When neither is present (chunked transfer), we can't know — return 0
          and accept that the progress callback won't be called.
        """
        content_range = response.headers.get('Content-Range')
        if content_range:
            m = self._CONTENT_RANGE_RE.search(content_range)
            if m:
                total = m.group(3)
                if total.isdigit():
                    return int(total)
        content_length = response.headers.get('Content-Length')
        if content_length and content_length.isdigit():
            # For 200 responses, Content-Length covers the full body we just got.
            # For 206 responses without a Content-Range, fall back to
            # offset + content_length as a best-effort total.
            size = int(content_length)
            if response.status_code == 206 and offset > 0 and size > 0:
                return offset + size
            return size
        return 0

    def _total_from_content_range(self, response):
        """Return the file's total size from a Content-Range header, or 0."""
        cr = response.headers.get('Content-Range')
        if not cr:
            return 0
        m = self._CONTENT_RANGE_RE.search(cr)
        if not m:
            return 0
        total = m.group(3)
        return int(total) if total.isdigit() else 0
