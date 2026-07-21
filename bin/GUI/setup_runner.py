import os
import subprocess
import threading
import logging

import customtkinter


class SetupRunner(customtkinter.CTkToplevel):
    """A Toplevel that runs a setup executable in a subprocess and
    streams its stdout/stderr into a scrollable log. When the
    subprocess exits with returncode 0,
    `on_complete(gid, True, 0)` is invoked on the parent; otherwise
    `on_complete(gid, False, returncode)`.

    The Toplevel is non-modal. Closing it does NOT cancel the
    subprocess — most installers need to run to completion, and
    cancelling via the OS (Task Manager on Windows, `kill` on
    Linux) is the right escape hatch if the user wants out.

    Used by the Game tab's W_S / L_S install flow: `App._open_setup_window`
    constructs one of these with the installer's path and the
    `on_complete` callback that drops the
    `gamevault-setup-complete` marker and refreshes the sidebar.
    """

    def __init__(self, master, gid, game_type, setup_exe, on_complete):
        super().__init__(master)
        self.gid = gid
        self.game_type = game_type
        self.setup_exe = setup_exe
        self.on_complete = on_complete
        self.proc = None
        self._stdout_thread = None
        self._stderr_thread = None
        self._watcher_thread = None
        # Whether we've already fired the completion callback, so
        # we don't double-fire on a stray watcher / stream error.
        self._finished = False

        self.title(f"Installing game {gid}  ·  ({game_type})")
        self.geometry("700x500")
        self.minsize(500, 300)
        # Intentionally NOT calling grab_set() — the user should be
        # able to switch tabs while the installer runs (e.g. read
        # the news, queue more downloads).

        # Header
        header = customtkinter.CTkLabel(
            self,
            text=f"Running setup: {os.path.basename(setup_exe)}",
            font=(None, 14, "bold"),
            anchor="w",
        )
        header.pack(fill="x", padx=10, pady=(10, 5))

        # Log
        self.log = customtkinter.CTkTextbox(self, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, padx=10, pady=5)

        # Status bar
        self.status = customtkinter.CTkLabel(self, text="Starting…", anchor="w")
        self.status.pack(fill="x", padx=10, pady=(0, 5))

        # Button row
        button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.cancel_btn = customtkinter.CTkButton(
            button_frame, text="Close", width=100,
            command=self._on_close_clicked,
        )
        self.cancel_btn.pack(side="right")

        # Launch the subprocess.
        self._start_subprocess()

    def _append_log(self, text):
        """Append a line to the log textbox. Must be called on the
        UI thread (we use `self.after(0, ...)` to marshal)."""
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _start_subprocess(self):
        """Spawn the setup executable and wire up the stream drains
        and the watcher. Errors before the process is even alive
        are caught and reported via the same on_complete path."""
        try:
            # On Windows, CREATE_NEW_PROCESS_GROUP so the installer
            # gets a fresh process group and doesn't inherit our
            # console handles. We don't actually send Ctrl+Break to
            # cancel — the user can kill via Task Manager if needed.
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP", 0
                )
            self.proc = subprocess.Popen(
                [self.setup_exe],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
        except Exception as e:
            self._append_log(f"\n[launcher] Failed to start setup: {e}\n")
            self.status.configure(text="Failed to start")
            self._on_proc_exit(returncode=-1)
            return

        self.status.configure(text="Running…")
        self._stdout_thread = threading.Thread(
            target=self._drain_stream,
            args=(self.proc.stdout, "stdout"),
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._drain_stream,
            args=(self.proc.stderr, "stderr"),
            daemon=True,
        )
        self._stdout_thread.start()
        self._stderr_thread.start()
        # Watcher thread: poll the process and fire the callback.
        self._watcher_thread = threading.Thread(
            target=self._watch, daemon=True
        )
        self._watcher_thread.start()

    def _drain_stream(self, stream, label):
        """Read a stdout/stderr stream line by line and marshal each
        line to the UI thread. Runs on a background thread; do not
        touch UI widgets directly."""
        def _alive():
            try:
                return bool(self.winfo_exists())
            except Exception:
                return False
        try:
            for line in iter(stream.readline, ""):
                if not _alive():
                    # Window was destroyed mid-install; stop trying
                    # to push log lines into a dead widget.
                    break
                self.after(
                    0, lambda l=line, lb=label: self._append_log(
                        f"[{lb}] {l}"
                    )
                )
        except Exception as e:
            if _alive():
                self.after(
                    0, lambda: self._append_log(
                        f"[{label}] stream error: {e}\n"
                    )
                )
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _watch(self):
        """Block on the subprocess and marshal its exit code to the
        UI thread. Runs on a background thread."""
        try:
            rc = self.proc.wait()
        except Exception as e:
            logging.warning(f"setup wait() failed for game {self.gid}: {e}")
            rc = -1
        # Skip the UI hop if the user already closed the window —
        # the underlying widgets no longer exist and `self.after`
        # would raise TclError.
        try:
            alive = bool(self.winfo_exists())
        except Exception:
            alive = False
        if not alive:
            # Fire the parent's callback directly from this thread;
            # the App-level handler is thread-safe enough for the
            # "mark complete + refresh sidebar" actions we need.
            try:
                self._fire_complete_from_thread(rc)
            except Exception as e:
                logging.warning(
                    f"setup on_complete callback failed for {self.gid}: {e}"
                )
            return
        self.after(0, lambda: self._on_proc_exit(rc))

    def _fire_complete_from_thread(self, returncode):
        """Same as `_on_proc_exit` but safe to call from a background
        thread when the Toplevel is gone. Only invokes the parent's
        callback — the UI updates are skipped."""
        if self._finished:
            return
        self._finished = True
        success = returncode == 0
        try:
            self.on_complete(self.gid, success, returncode)
        except Exception as e:
            logging.warning(
                f"setup on_complete callback failed for {self.gid}: {e}"
            )

    def _on_proc_exit(self, returncode):
        """UI-thread callback for the subprocess exit. Updates the
        status bar, flips the button label, and fires the parent's
        `on_complete` exactly once. Runs on the UI thread."""
        if self._finished:
            return
        self._finished = True
        success = returncode == 0
        if success:
            self.status.configure(text="Setup finished (returncode 0)")
        else:
            self.status.configure(text=f"Setup exited with code {returncode}")
        # The button is now a plain Close — the install already
        # ran, so there's nothing left to cancel.
        try:
            self.cancel_btn.configure(text="Close", state="normal")
        except Exception:
            pass
        # Fire the parent's callback. Errors here are logged but
        # shouldn't take the UI down.
        try:
            self.on_complete(self.gid, success, returncode)
        except Exception as e:
            logging.warning(
                f"setup on_complete callback failed for {self.gid}: {e}"
            )

    def _on_close_clicked(self):
        """Close button handler. The subprocess keeps running in
        the background even after the window is destroyed — most
        installers need to run to completion. The watcher thread
        will still call `_on_proc_exit` on the (now-destroyed)
        Toplevel; `_finished` guards against re-entry and any
        `self.log.configure(...)` call after destruction is
        wrapped in a try/except where it matters.
        """
        try:
            self.destroy()
        except Exception:
            pass
