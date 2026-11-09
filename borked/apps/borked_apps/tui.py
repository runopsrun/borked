"""Picker. Space marks an app. Enter installs the marks."""

from __future__ import annotations

import curses
import os

from borked_apps.catalog import App, categories
from borked_apps.install import InstallError, install, is_installed
from borked_apps.voice import ALREADY, DONE, EMPTY, FAIL, MARK, MIXED, OK, START, UNMARK, WORKING, say

LOGO = (
    "█▄█ █▀█ █▀█ █▄▀ █▀▀ █▀▄",
    "█▀█ █▄█ █▀▄ █ █ ██▄ █▄▀",
)


def _add(win, y: int, x: int, text: str, attr: int = 0) -> None:
    height, width = win.getmaxyx()
    if y < 0 or y >= height - 1 or x >= width - 1:
        return
    try:
        win.addnstr(y, x, text, max(1, width - x - 1), attr)
    except curses.error:
        return


def _origin(win) -> tuple[int, int]:
    _height, width = win.getmaxyx()
    panel = min(72, max(20, width - 4))
    return max(1, (width - panel) // 2), panel


class Picker:
    def __init__(self, apps: list[App]) -> None:
        self.groups = categories(apps)
        self.apps = [app for _name, group in self.groups for app in group]
        self.installed = {app.id for app in self.apps if is_installed(app)}
        self.marked: set[str] = set()
        self.cursor = 0
        self.note = "Space marks one. Enter tempts fate."

    def run(self, win) -> list[App] | None:
        curses.curs_set(0)
        curses.start_color()
        try:
            curses.use_default_colors()
            bg = -1
        except curses.error:
            bg = curses.COLOR_BLACK
        curses.init_pair(1, curses.COLOR_RED, bg)
        curses.init_pair(2, curses.COLOR_WHITE, bg)
        curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLUE)
        self.accent = curses.color_pair(1) | curses.A_BOLD
        self.body = curses.color_pair(2)
        self.mark = curses.color_pair(3) | curses.A_BOLD
        self.dim = curses.A_DIM
        while True:
            self._draw(win)
            key = win.getch()
            if key == curses.KEY_RESIZE:
                continue
            if key in (27, ord("q")):
                return None
            if key in (curses.KEY_UP, curses.KEY_BTAB):
                self.cursor = (self.cursor - 1) % len(self.apps)
            elif key in (curses.KEY_DOWN, 9):
                self.cursor = (self.cursor + 1) % len(self.apps)
            elif key == ord(" "):
                self._toggle()
            elif key in (10, 13, curses.KEY_ENTER):
                chosen = [app for app in self.apps if app.id in self.marked]
                if not chosen:
                    self.note = say(EMPTY)
                    continue
                return chosen

    def _toggle(self) -> None:
        app = self.apps[self.cursor]
        if app.id in self.installed:
            self.note = say(ALREADY)
            return
        if app.id in self.marked:
            self.marked.remove(app.id)
            self.note = say(UNMARK)
        else:
            self.marked.add(app.id)
            self.note = say(MARK)

    def _draw(self, win) -> None:
        win.erase()
        height, _width = win.getmaxyx()
        if height < 16 or win.getmaxyx()[1] < 60:
            _add(win, 0, 0, "Make the window at least 60x16")
            win.refresh()
            return
        x, panel = _origin(win)
        y = 1
        for line in LOGO:
            _add(win, y, x, line, self.accent)
            y += 1
        _add(win, y, x, "Beautifully broken.", self.dim)
        y += 2
        _add(win, y, x, "Apps.", self.body | curses.A_BOLD)
        y += 1
        _add(win, y, x, "Optional. The base image stays boring.", self.dim)
        y += 2
        rows = self._rows()
        selected_row = next(i for i, row in enumerate(rows) if row[0] == "app" and row[1] == self.cursor)
        room = max(1, height - y - 3)
        start = max(0, min(selected_row - room // 2, len(rows) - room))
        for row in rows[start : start + room]:
            if row[0] == "head":
                _add(win, y, x, row[1][:panel], self.dim)
            else:
                app = self.apps[row[1]]
                box = "x" if app.id in self.marked or app.id in self.installed else " "
                text = f"[{box}] {app.label}"
                blurb_at = 28
                if len(text) < blurb_at:
                    text = text.ljust(blurb_at) + app.blurb
                attr = self.mark if row[1] == self.cursor else self.body
                _add(win, y, x, text[:panel].ljust(panel), attr)
            y += 1
        if self.note:
            _add(win, height - 3, x, self.note[:panel], self.accent)
        _add(win, height - 2, x, "space  mark    enter  tempt fate    esc  flee", self.dim)
        win.refresh()

    def _rows(self) -> list[tuple]:
        rows = []
        index = 0
        for name, group in self.groups:
            rows.append(("head", name))
            for _app in group:
                rows.append(("app", index))
                index += 1
        return rows


def pick(apps: list[App]) -> list[App] | None:
    if os.environ.get("TERM") == "linux":
        try:
            os.write(1, b"\033]P00b0a12\033]P1ff3d81\033]P42a2540\033]P7f4f0ff\033]P89a93b5")
        except OSError:
            pass
    return curses.wrapper(lambda stdscr: Picker(apps).run(stdscr))


def run_install(chosen: list[App]) -> int:
    failed = False
    print(say(START))
    print("System packages ask for sudo. Agents install into your home.")
    for app in chosen:
        print(f"\n-- {say(WORKING, label=app.label)}")
        try:
            install(app, print)
            print(say(OK, label=app.label))
        except InstallError as exc:
            failed = True
            print(f"{say(FAIL, label=app.label)} ({exc})")
    print()
    print(say(MIXED if failed else DONE))
    return 1 if failed else 0
