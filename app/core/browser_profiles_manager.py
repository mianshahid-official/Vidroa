"""
Chrome Browser Profiles Manager for PromptBeast.
Manages multi-account Chrome browser profiles (acc1..acc6) for automated
Google Gemini image generation and script synthesis with full session persistence.
"""

import os
import re
import sys
import json
import time
import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

_GOOGLE_SIGNIN_COOKIES = (
    "SID",
    "__Secure-1PSID",
    "__Secure-3PSID",
    "SAPISID",
    "APISID",
    "HSID",
    "SSID",
    "__Secure-1PAPISID",
    "__Secure-3PAPISID",
)


class BrowserProfilesManager:
    """Manages Chrome user-data-dir profiles and validates Google authentication states."""

    _DEFAULT_ACCOUNTS = ["acc1", "acc2", "acc3", "acc4", "acc5", "acc6"]

    @classmethod
    def get_profiles_dir(cls) -> Path:
        """Returns the directory where Chrome user-data profiles are saved."""
        custom = os.environ.get("PROMPTBEAST_PROFILES_DIR")
        if custom:
            p = Path(custom)
        else:
            base_dir = Path(__file__).resolve().parent.parent.parent
            p = base_dir / "data" / "browser_profiles"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def find_chrome_exe(cls) -> Optional[str]:
        """Locates Google Chrome, Brave, or Microsoft Edge executable on Windows."""
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return shutil.which("chrome") or shutil.which("msedge")

    @classmethod
    def _cookie_key_usable(cls, profile_dir: Path) -> Optional[bool]:
        """
        Validates if this Windows machine can decrypt the profile's DPAPI-encrypted cookies.
        Chrome stores the AES master key inside 'Local State' wrapped by Windows DPAPI.
        """
        local_state_path = profile_dir / "Local State"
        if not local_state_path.is_file():
            return None
        try:
            import base64
            import ctypes
            import ctypes.wintypes as wt

            with open(local_state_path, encoding="utf-8", errors="replace") as f:
                blob = json.load(f).get("os_crypt", {}).get("encrypted_key")
            if not blob:
                return None
            raw = base64.b64decode(blob)
            if raw[:5] != b"DPAPI":
                return None
            raw = raw[5:]

            class _DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

            src = _DATA_BLOB(
                len(raw),
                ctypes.cast(ctypes.create_string_buffer(raw), ctypes.POINTER(ctypes.c_char)),
            )
            out = _DATA_BLOB()
            ok = ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(src), None, None, None, None, 0, ctypes.byref(out)
            )
            if ok:
                ctypes.windll.kernel32.LocalFree(out.pbData)
                return True
            return False
        except Exception:
            return None

    @classmethod
    def profile_login_state(cls, profile_dir: Path) -> str:
        """
        Returns the authentication status of the given profile folder:
          - 'yes': Valid Google sign-in cookies exist and can be decrypted on this PC.
          - 'no': Profile exists but no Google sign-in cookies are present.
          - 'in use': Chrome has the cookie SQLite database locked (browser is currently running).
          - 'foreign': Cookies exist but were created on a different PC and cannot be decrypted.
        """
        locked = False
        cookie_rel_paths = [
            ("Default", "Network", "Cookies"),
            ("Default", "Cookies"),
            ("Network", "Cookies"),
            ("Cookies",),
        ]

        for rel in cookie_rel_paths:
            db_path = profile_dir.joinpath(*rel)
            if not db_path.is_file():
                continue

            tmp_path = profile_dir / f"cookies_check_{time.time_ns()}.tmp"
            try:
                shutil.copy2(db_path, tmp_path)
                conn = sqlite3.connect(str(tmp_path))
                try:
                    marks = ",".join("?" * len(_GOOGLE_SIGNIN_COOKIES))
                    query = (
                        "SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%google.com' "
                        f"AND name IN ({marks})"
                    )
                    count = conn.execute(query, _GOOGLE_SIGNIN_COOKIES).fetchone()[0]
                finally:
                    conn.close()

                if count > 0:
                    if cls._cookie_key_usable(profile_dir) is False:
                        return "foreign"
                    return "yes"
            except Exception:
                locked = True
            finally:
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except OSError:
                    pass

        return "in use" if locked else "no"

    @classmethod
    def get_all_profiles(cls) -> List[Dict[str, Any]]:
        """
        Returns status for all configured profiles (acc1..acc6 plus any user-created profiles).
        """
        root = cls.get_profiles_dir()

        # Ensure default acc1..acc6 exist
        for d in cls._DEFAULT_ACCOUNTS:
            (root / d).mkdir(parents=True, exist_ok=True)

        _LABEL = {
            "yes": "Signed in",
            "no": "Not signed in — click Open & Login",
            "in use": "In use (Chrome window is open)",
            "foreign": "Session from another PC — log in on this machine",
        }

        profiles = []
        for item in sorted(root.iterdir()):
            if not item.is_dir():
                continue
            name = item.name
            state = cls.profile_login_state(item)
            profiles.append({
                "name": name,
                "path": str(item.resolve()),
                "login": state,
                "is_signed_in": state == "yes",
                "in_use": state == "in use",
                "status_label": _LABEL.get(state, state),
            })
        return profiles

    @classmethod
    def create_profile(cls, name: str) -> Tuple[bool, str]:
        """Creates a new isolated Chrome profile folder."""
        clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "", name).strip()
        if not clean_name:
            return False, "Invalid profile name. Use alphanumeric characters and underscores."
        root = cls.get_profiles_dir()
        p_path = root / clean_name
        p_path.mkdir(parents=True, exist_ok=True)
        return True, clean_name

    @classmethod
    def configure_download_dir(cls, name: str, download_dir: Path) -> bool:
        """
        Configures Chrome's Default/Preferences to automatically download files
        straight into the specified folder without download prompts.
        """
        try:
            download_path = Path(download_dir).resolve()
            download_path.mkdir(parents=True, exist_ok=True)
            root = cls.get_profiles_dir()
            p_path = root / name
            default_dir = p_path / "Default"
            default_dir.mkdir(parents=True, exist_ok=True)
            prefs_file = default_dir / "Preferences"

            prefs = {}
            if prefs_file.is_file():
                try:
                    with open(prefs_file, "r", encoding="utf-8", errors="replace") as f:
                        prefs = json.load(f)
                except Exception:
                    prefs = {}

            prefs["download"] = {
                "default_directory": str(download_path),
                "directory_upgrade": True,
                "prompt_for_download": False
            }
            if "savefile" not in prefs or not isinstance(prefs["savefile"], dict):
                prefs["savefile"] = {}
            prefs["savefile"]["default_directory"] = str(download_path)

            with open(prefs_file, "w", encoding="utf-8") as f:
                json.dump(prefs, f, indent=2)
            return True
        except Exception as e:
            print(f"[BrowserProfilesManager] Failed to configure download directory for {name}: {e}")
            return False

    @classmethod
    def open_browser_profile(
        cls,
        name: str,
        download_dir: Optional[Path] = None,
        prompts_text: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Launches real Google Chrome with the profile's dedicated user-data-dir,
        opening Google Accounts sign-in and Gemini app.
        Optionally sets the download directory to download_dir.
        If prompts_text is provided, copies to Windows clipboard and verifies before launch.
        """
        if prompts_text:
            try:
                from app.core.export import copy_to_system_clipboard
                copy_to_system_clipboard(prompts_text)
            except Exception as e:
                print(f"[BrowserProfilesManager] Notice copying prompts to clipboard: {e}")

        chrome_exe = cls.find_chrome_exe()
        if not chrome_exe:
            return False, "Google Chrome / Edge executable not found on system."

        root = cls.get_profiles_dir()
        p_path = root / name
        p_path.mkdir(parents=True, exist_ok=True)

        if download_dir:
            cls.configure_download_dir(name, download_dir)

        google_url = "https://accounts.google.com"
        gemini_url = "https://gemini.google.com/app"
        bulk_canvas_url = "https://share.gemini.google/cTnZQ3bpoER7"

        cmd = [
            chrome_exe,
            f"--user-data-dir={str(p_path.resolve())}",
            "--new-window",
            "--no-first-run",
            "--no-default-browser-check",
            google_url,
            gemini_url,
            bulk_canvas_url,
        ]

        try:
            subprocess.Popen(cmd)
            return True, f"Opened Chrome for profile '{name}'. Sign into Google, then close the window."
        except Exception as e:
            return False, str(e)

    @classmethod
    def open_all_profiles(cls) -> Tuple[bool, str]:
        """Opens all configured Chrome profiles sequentially for one-time setup."""
        profiles = cls.get_all_profiles()
        opened = 0
        for p in profiles:
            ok, _ = cls.open_browser_profile(p["name"])
            if ok:
                opened += 1
            time.sleep(1.0)
        return True, f"Opened {opened} Chrome profiles for one-time Google login."

    @classmethod
    def get_signed_in_profiles(cls) -> List[str]:
        """Returns a list of profile names that currently have active Google sign-ins."""
        return [p["name"] for p in cls.get_all_profiles() if p["is_signed_in"]]
