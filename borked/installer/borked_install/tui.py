"""Full-screen installer. Unattended installs never reach this."""

from __future__ import annotations

import curses
import os
import re
import subprocess
import sys
from pathlib import Path

from borked_install.config import Config, resolve_disk

# English is the locale pack shipped in the image. More choices need a
# glibc-langpack-* entry in packages/include.list.
LANGUAGES = (
    ("en_US.UTF-8", "English (United States)"),
    ("en_GB.UTF-8", "English (United Kingdom)"),
    ("en_CA.UTF-8", "English (Canada)"),
    ("en_AU.UTF-8", "English (Australia)"),
)

# Console keymap, xkb layout, label. The xkb name is what COSMIC reads.
KEYBOARDS = (
    ("us", "us", "English (US)"),
    ("uk", "gb", "English (UK)"),
    ("de-latin1", "de", "German"),
    ("fr-latin1", "fr", "French"),
    ("es", "es", "Spanish"),
    ("it", "it", "Italian"),
    ("pt-latin1", "pt", "Portuguese"),
    ("sv-latin1", "se", "Swedish"),
    ("fi-latin1", "fi", "Finnish"),
    ("no-latin1", "no", "Norwegian"),
    ("dk-latin1", "dk", "Danish"),
    ("nl", "nl", "Dutch"),
    ("pl", "pl", "Polish"),
    ("br-abnt2", "br", "Portuguese (Brazil)"),
    ("ru", "ru", "Russian"),
    ("jp106", "jp", "Japanese"),
)

USER_RE = re.compile(r"[a-z_][a-z0-9_-]{0,31}")
HOST_RE = re.compile(r"[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?")

# Two rows, wide enough to read on an 80-column console.
LOGO = (
    "█▀▄ █▀█ █▀█ █▄▀ █▀▀ █▀▄",
    "█▄▀ █▄█ █▀▄ █ █ ██▄ █▄▀",
)

# Title, then the line under it. The welcome screen uses the first pair.
COPY = (
    ("Beautifully broken.", "Stop ricing. Start using it. Probably."),
    ("Keyboard", "The layout you'll blame later."),
    ("Language", "English. The rest can wait."),
    ("Account", "A name. Regret is optional."),
    ("Password", "You'll forget it. Don't write it here."),
    ("Hostname", "What it calls itself when it misbehaves."),
    ("Timezone", "Wrong on purpose, if you insist."),
    ("Disk", "This one gets erased. No takebacks."),
    ("Encryption", "Blank means unencrypted. Reversible-ish."),
    ("Install", "Enter erases the disk. Esc if you flinched."),
)


def disks() -> list[tuple[str, str]]:
    try:
        out = subprocess.check_output(
            ["lsblk", "-dn", "-o", "NAME,SIZE,TYPE"], text=True
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    found = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == "disk":
            found.append((f"/dev/{parts[0]}", parts[1]))
    return found


def timezones() -> list[str]:
    found = ["UTC"]
    tab = Path("/usr/share/zoneinfo/zone.tab")
    if tab.is_file():
        for line in tab.read_text(errors="replace").splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 3 and parts[2] not in found:
                found.append(parts[2])
    return found


def _loadkeys(keymap: str) -> None:
    if not keymap:
        return
    subprocess.run(["loadkeys", keymap], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class _Log:
    def __init__(self, redraw) -> None:
        self.redraw = redraw
        self.last = "Preparing the disk"
        self.lines: list[str] = []

    def write(self, data: str) -> None:
        for line in str(data).splitlines():
            text = line.strip()
            if not text:
                continue
            self.lines.append(text)
            self.last = _phase(text)
            self.redraw(self.last)
        self.redraw(self.last)

    def flush(self) -> None:
        return


def _phase(line: str) -> str:
    text = line.lower()
    if "cryptsetup" in text:
        return "Encrypting the disk"
    if "mkfs" in text or "parted" in text or "sfdisk" in text:
        return "Partitioning the disk"
    if "btrfs" in text:
        return "Copying the system"
    if "useradd" in text or "chpasswd" in text:
        return "Creating the account"
    if any(word in text for word in ("grub", "shim", "kernel", "dracut", "setfiles")):
        return "Installing the bootloader"
    if line.startswith("+"):
        return "Installing"
    return line


def _add(win, y: int, x: int, text: str, attr: int = 0) -> None:
    height, width = win.getmaxyx()
    if y < 0 or y >= height - 1 or x >= width - 1:
        return
    try:
        win.addnstr(y, x, text, max(1, width - x - 1), attr)
    except curses.error:
        return


def _center(win, y: int, text: str, attr: int = 0) -> None:
    _, width = win.getmaxyx()
    _add(win, y, max(0, (width - len(text)) // 2), text, attr)


class Installer:
    def __init__(self, stdscr, stream: str) -> None:
        self.win = stdscr
        self.stream = stream
        self.step = 0
        self.error = ""
        self.filter = ""
        self.cursor = 0
        self.field = 0
        self.username = ""
        self.full_name = ""
        self.password = ""
        self.again = ""
        self.hostname = "borked"
        self.luks = ""
        self.luks_again = ""
        self.disk_i = 0
        self.lang_i = 0
        self.key_i = 0
        self.zone_i = 0
        self.disks = disks()
        self.zones = timezones()
        curses.curs_set(0)
        bg = _colors()
        curses.init_pair(1, curses.COLOR_RED, bg)
        curses.init_pair(2, curses.COLOR_WHITE, bg)
        curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLUE)
        self.accent = curses.color_pair(1) | curses.A_BOLD
        self.dim = curses.A_DIM
        self.body = curses.color_pair(2)
        self.mark = curses.color_pair(3) | curses.A_BOLD

    def run(self) -> Config:
        steps = (
            self._welcome,
            self._keyboard,
            self._language,
            self._user,
            self._password,
            self._hostname,
            self._timezone,
            self._disk,
            self._encrypt,
            self._confirm,
        )
        while True:
            self.win.erase()
            if self.win.getmaxyx()[0] < 16 or self.win.getmaxyx()[1] < 60:
                _center(self.win, 0, "Make the window at least 60x16")
                self.win.refresh()
                self.win.getch()
                continue
            steps[self.step]()
            self._footer()
            self.win.refresh()
            key = self.win.getch()
            if key == curses.KEY_RESIZE:
                continue
            if key == 27 and self.step > 0:
                self.error = ""
                self.filter = ""
                self.step -= 1
                continue
            if key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE, 9, curses.KEY_BTAB):
                self._move(key)
                continue
            if key in (curses.KEY_BACKSPACE, 127, 8):
                self._backspace()
                continue
            if key in (10, 13, curses.KEY_ENTER):
                if self._enter():
                    return self._config()
                continue
            if 32 <= key <= 126:
                self._type(chr(key))

    def _config(self) -> Config:
        keymap, xkb, _label = KEYBOARDS[self.key_i]
        disk, _size = self.disks[self.disk_i]
        zone = self._visible_zones()[self.zone_i]
        return Config(
            disk=resolve_disk(disk),
            luks_passphrase=self.luks or None,
            username=self.username,
            full_name=self.full_name or self.username,
            password=self.password,
            hostname=self.hostname,
            timezone=zone,
            stream=self.stream,
            locale=LANGUAGES[self.lang_i][0],
            keymap=keymap,
            xkb_layout=xkb,
        )

    def _origin(self) -> tuple[int, int]:
        return _origin(self.win)

    def _frame(self) -> int:
        title, snark = COPY[self.step]
        return _frame(self.win, title, snark, self.accent, self.dim, self.body)

    def _footer(self) -> None:
        height, _width = self.win.getmaxyx()
        x, _panel = self._origin()
        if self.error:
            _add(self.win, height - 3, x, self.error[:_panel], self.accent)
        _add(self.win, height - 2, x, "enter  continue    tab  next    esc  back", self.dim)

    def _welcome(self) -> None:
        y = self._frame()
        self._bar(y, "  Enter", True)

    def _keyboard(self) -> None:
        y = self._frame()
        self._choices(y, [item[2] for item in KEYBOARDS], self.key_i)

    def _language(self) -> None:
        y = self._frame()
        self._choices(y, [item[1] for item in LANGUAGES], self.lang_i)

    def _user(self) -> None:
        y = self._frame()
        self._field_row(y, "Username", self.username, self.field == 0)
        self._field_row(y + 3, "Full name", self.full_name, self.field == 1)

    def _password(self) -> None:
        y = self._frame()
        self._field_row(y, "Password", "•" * len(self.password), self.field == 0)
        self._field_row(y + 3, "Again", "•" * len(self.again), self.field == 1)

    def _hostname(self) -> None:
        y = self._frame()
        self._field_row(y, "Name", self.hostname, True)

    def _timezone(self) -> None:
        y = self._frame()
        self._field_row(y, "Search", self.filter, True)
        self._choices(y + 3, self._visible_zones(), self.zone_i)

    def _disk(self) -> None:
        y = self._frame()
        if not self.disks:
            x, _panel = self._origin()
            _add(self.win, y, x, "No disks found. Awkward.", self.accent)
            return
        rows = [f"  {path}    {size}" for path, size in self.disks]
        self._choices(y, rows, self.disk_i)

    def _encrypt(self) -> None:
        y = self._frame()
        self._field_row(y, "Passphrase", "•" * len(self.luks), self.field == 0)
        self._field_row(y + 3, "Again", "•" * len(self.luks_again), self.field == 1)

    def _confirm(self) -> None:
        y = self._frame()
        disk = self.disks[self.disk_i][0] if self.disks else "?"
        rows = (
            f"  Disk        {disk}",
            f"  Encryption  {'LUKS' if self.luks else 'off'}",
            f"  User        {self.username}",
            f"  Hostname    {self.hostname}",
            f"  Language    {LANGUAGES[self.lang_i][1]}",
            f"  Keyboard    {KEYBOARDS[self.key_i][2]}",
            f"  Timezone    {self._visible_zones()[self.zone_i] if self._visible_zones() else 'UTC'}",
        )
        for row in rows:
            self._bar(y, row, False)
            y += 1

    def _field_row(self, y: int, label: str, value: str, active: bool) -> None:
        x, panel = self._origin()
        _add(self.win, y, x, label, self.accent if active else self.dim)
        shown = value[: max(0, panel - 2)]
        self._bar(y + 1, " " + shown, active)

    def _bar(self, y: int, text: str, selected: bool) -> None:
        x, panel = self._origin()
        shown = text[:panel].ljust(panel)
        _add(self.win, y, x, shown, self.mark if selected else self.body)

    def _choices(self, y: int, rows: list[str], selected: int) -> None:
        height = self.win.getmaxyx()[0]
        x, _panel = self._origin()
        room = max(1, height - y - 4)
        if not rows:
            _add(self.win, y, x, "No matches.", self.dim)
            return
        selected = max(0, min(selected, len(rows) - 1))
        start = max(0, selected - room + 1)
        for offset, row in enumerate(rows[start : start + room]):
            self._bar(y + offset, row if row.startswith("  ") else "  " + row, start + offset == selected)

    def _visible_zones(self) -> list[str]:
        query = self.filter.lower()
        if not query:
            return self.zones
        return [zone for zone in self.zones if query in zone.lower()]

    def _move(self, key: int) -> None:
        delta = -1 if key in (curses.KEY_UP, curses.KEY_PPAGE, curses.KEY_BTAB) else 1
        if self.step == 1:
            self.key_i = (self.key_i + delta) % len(KEYBOARDS)
            _loadkeys(KEYBOARDS[self.key_i][0])
        elif self.step == 2:
            self.lang_i = (self.lang_i + delta) % len(LANGUAGES)
        elif self.step in (3, 4, 8):
            self.field = (self.field + delta) % 2
        elif self.step == 6:
            rows = self._visible_zones()
            if rows:
                self.zone_i = (self.zone_i + delta) % len(rows)
        elif self.step == 7 and self.disks:
            self.disk_i = (self.disk_i + delta) % len(self.disks)

    def _backspace(self) -> None:
        target = self._editor()
        if target is None:
            return
        value = getattr(self, target)
        setattr(self, target, value[:-1])
        if target == "filter":
            self.zone_i = 0

    def _type(self, char: str) -> None:
        target = self._editor()
        if target is None:
            return
        value = getattr(self, target)
        if len(value) < 64:
            setattr(self, target, value + char)
        if target == "filter":
            self.zone_i = 0

    def _editor(self) -> str | None:
        if self.step == 3:
            return "username" if self.field == 0 else "full_name"
        if self.step == 4:
            return "password" if self.field == 0 else "again"
        if self.step == 5:
            return "hostname"
        if self.step == 6:
            return "filter"
        if self.step == 8:
            return "luks" if self.field == 0 else "luks_again"
        return None

    def _enter(self) -> bool:
        self.error = ""
        if self.step == 3:
            if not USER_RE.fullmatch(self.username):
                self.error = "Username: lowercase, digits, _ or -, starting with a letter."
                return False
        elif self.step == 4:
            if not self.password or self.password != self.again:
                self.error = "Passwords were empty or did not match."
                return False
        elif self.step == 5:
            if not HOST_RE.fullmatch(self.hostname):
                self.error = "Hostname may use letters, digits, and interior hyphens."
                return False
        elif self.step == 6:
            if not self._visible_zones():
                self.error = "No timezone matches that search."
                return False
        elif self.step == 7:
            if not self.disks:
                self.error = "No disks found."
                return False
        elif self.step == 8:
            if self.luks != self.luks_again:
                self.error = "Encryption passphrases did not match."
                return False
        self.field = 0
        self.step += 1
        return self.step >= 10


def _origin(win) -> tuple[int, int]:
    _height, width = win.getmaxyx()
    panel = min(56, max(20, width - 4))
    return max(1, (width - panel) // 2), panel


def _frame(win, title: str, snark: str, accent: int, dim: int, body: int) -> int:
    x, _panel = _origin(win)
    y = 1
    for line in LOGO:
        _add(win, y, x, line, accent | curses.A_BOLD)
        y += 1
    _add(win, y, x, "Beautifully broken.", dim)
    y += 2
    if title and title != "Beautifully broken.":
        _add(win, y, x, title, body | curses.A_BOLD)
        y += 1
    _add(win, y, x, snark, dim)
    return y + 2


def _paint_palette() -> None:
    # The Linux console only has 16 colors. Match the site: near-black
    # field, pink mark, light text, and a quiet surface for the selection.
    colors = {
        "0": "0b0a12",
        "1": "ff3d81",
        "4": "2a2540",
        "7": "f4f0ff",
        "8": "9a93b5",
    }
    seq = "".join(f"\033]P{key}{value}" for key, value in colors.items())
    try:
        os.write(1, (seq + "\033[40m\033[37m\033[2J").encode())
    except OSError:
        return


def _attach_console() -> None:
    # live-init tees stdout through a fifo so the serial log can see it.
    # curses runs cbreak on that fd, and a fifo is not a terminal.
    os.environ["TERM"] = "linux"
    os.environ.setdefault("ESCDELAY", "25")
    try:
        fd = os.open("/dev/tty0", os.O_RDWR)
    except OSError:
        return
    try:
        os.dup2(fd, 0)
        os.dup2(fd, 1)
        os.dup2(fd, 2)
    finally:
        if fd > 2:
            os.close(fd)
    _paint_palette()


def ask(stream: str) -> Config:
    _attach_console()
    return curses.wrapper(lambda stdscr: Installer(stdscr, stream).run())


def present_install(cfg: Config) -> None:
    _attach_console()
    curses.wrapper(lambda stdscr: _present(stdscr, cfg))


def _colors() -> int:
    curses.start_color()
    try:
        curses.use_default_colors()
    except curses.error:
        return curses.COLOR_BLACK
    return -1


def _present(stdscr, cfg: Config) -> None:
    os.environ["BORKED_QUIET"] = "1"
    curses.curs_set(0)
    bg = _colors()
    curses.init_pair(1, curses.COLOR_RED, bg)
    curses.init_pair(2, curses.COLOR_WHITE, bg)
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLUE)
    accent = curses.color_pair(1) | curses.A_BOLD
    status = {"line": "Preparing the disk"}

    def redraw(line: str) -> None:
        status["line"] = line
        stdscr.erase()
        y = _frame(
            stdscr,
            "Installing",
            "Breaking it in. This is a feature.",
            accent,
            curses.A_DIM,
            curses.color_pair(2),
        )
        x, panel = _origin(stdscr)
        _add(stdscr, y, x, line[:panel].ljust(panel), accent)
        stdscr.refresh()

    redraw(status["line"])
    log = _Log(redraw)
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = log  # type: ignore[assignment]
    sys.stderr = log  # type: ignore[assignment]
    failed: str | None = None
    try:
        from borked_install.install import install

        install(cfg)
    except SystemExit as exc:
        if exc.code not in (0, None):
            failed = exc.code if isinstance(exc.code, str) else "Install failed."
    except Exception as exc:  # noqa: BLE001 — show it on the boot screen
        failed = str(exc)
    finally:
        sys.stdout = old_out
        sys.stderr = old_err

    stdscr.erase()
    if failed:
        y = _frame(
            stdscr,
            "Slightly borked.",
            "This was not the feature.",
            accent,
            curses.A_DIM,
            curses.color_pair(2),
        )
        x, panel = _origin(stdscr)
        _add(stdscr, y, x, failed[:panel], accent)
        for offset, line in enumerate(log.lines[-6:]):
            _add(stdscr, y + 2 + offset, x, line[:panel], curses.A_DIM)
        stdscr.refresh()
        while True:
            stdscr.getch()
    y = _frame(
        stdscr,
        "It's on the disk.",
        "Remove the media, then Enter. Try to look sure.",
        accent,
        curses.A_DIM,
        curses.color_pair(2),
    )
    x, panel = _origin(stdscr)
    _add(stdscr, y, x, "  Enter".ljust(panel), curses.color_pair(3) | curses.A_BOLD)
    stdscr.refresh()
    while True:
        key = stdscr.getch()
        if key in (10, 13, curses.KEY_ENTER):
            return
