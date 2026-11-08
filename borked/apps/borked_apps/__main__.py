"""borked: the command. apps is the first thing it does."""

from __future__ import annotations

import sys

from borked_apps.catalog import load
from borked_apps.tui import pick, run_install
from borked_apps.voice import USAGE


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE, end="")
        return 0
    command, rest = args[0], args[1:]
    if command == "apps":
        return _apps(rest)
    print(f"borked: '{command}' is not a thing. Try `borked apps`, or don't.")
    return 2


def _apps(args: list[str]) -> int:
    apps = load()
    if args[:1] == ["--list"]:
        print("The menu. None of this is in the base image. On purpose.")
        for app in apps:
            print(f"{app.category}\t{app.id}\t{app.label}")
        return 0
    if args[:1] == ["--install"]:
        wanted = set(args[1:])
        known = {app.id for app in apps}
        missing = wanted - known
        if not wanted or missing:
            names = ", ".join(sorted(missing or {"(none)"}))
            print(f"borked apps: never heard of {names}.")
            return 2
        return run_install([app for app in apps if app.id in wanted])
    if args:
        print("usage: borked apps [--list | --install id...]")
        return 2
    if not sys.stdin.isatty():
        print("borked apps wants a terminal. `--list` works without one. You don't.")
        return 2
    chosen = pick(apps)
    if not chosen:
        from borked_apps.voice import QUIT, say

        print(say(QUIT))
        return 0
    return run_install(chosen)


if __name__ == "__main__":
    raise SystemExit(main())
