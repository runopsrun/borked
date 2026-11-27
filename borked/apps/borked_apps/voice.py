"""Lines for when the user does something. Keep it short. Keep it mean, fondly."""

from __future__ import annotations

import random

MARK = (
    "Well, I hope this doesn't break it.",
    "Bold. We'll see.",
    "Sure. What could go wrong. Probably.",
    "Noted. This is a feature until it isn't.",
    "Adding that. Emotionally.",
)

UNMARK = (
    "Changed your mind. Growth.",
    "Fine. It stays off the disk.",
    "Second thoughts. The disk thanks you.",
)

ALREADY = (
    "That's already here. Try to look surprised.",
    "Installed. Doing it twice will not make it love you.",
)

EMPTY = (
    "You marked nothing. Commitment issues.",
    "Space first. Enter is for people who have decided.",
)

QUIT = (
    "Leaving already. The software will cope.",
    "Esc. The coward's deploy.",
)

START = (
    "Alright. Well, I hope this doesn't break it.",
    "Installing. If it catches fire, the wallpaper still looks good.",
    "Here we go. Reversible-ish.",
)

WORKING = (
    "Fetching {label}. Try to look sure.",
    "{label}. No takebacks. Only history.",
    "Putting {label} on the machine. Emotionally prepared. Barely.",
)

OK = (
    "Motherfucker. Oh wait, never mind. It worked.",
    "{label} landed. Weirdly fine.",
    "It worked. I'm as shocked as you are.",
    "Done. Something is slightly borked. This one isn't.",
)

FAIL = (
    "{label} faceplanted. The rest can still try.",
    "That one broke. The others are pretending not to know it.",
    "{label} failed. At least it failed with style.",
)

DONE = (
    "All of it worked. Don't tell anyone. They'll expect this.",
    "Clean run. Suspicious, but I'll take it.",
)

MIXED = (
    "Some of it worked. The rest is a conversation.",
    "Partial success. The traditional kind.",
)

VIRT = (
    "{user} is in libvirt. Log out once. virt-manager can wait.",
    "Group's on. Log out before you open virt-manager, hotshot.",
)

USAGE = """Borked. Beautifully broken.

  borked apps     optional software. hope you're sure.
  borked duo      write Duo Unix keys. optionally wire SSH.

That's the list. It will get longer. Unfortunately.
"""

DUO_USAGE = """borked duo — Cisco Duo Unix after the packages land.

  borked duo
  borked duo --ikey=KEY --skey=SECRET --host=api-XXXX.duosecurity.com
  borked duo --ssh
  borked duo --failmode=secure

Install with `borked apps` first if needed. Keys go in /etc/duo/login_duo.conf.
`--ssh` drops ForceCommand into /etc/ssh/sshd_config.d/50-borked-duo.conf.
failmode defaults to safe so a Duo outage does not lock you out. On purpose.
"""

DUO_MISS = (
    "Duo Unix is not installed. Fixing that first. Emotionally prepared. Barely.",
    "No duo_unix yet. Installing it so the secrets have somewhere to live.",
)

DUO_START = (
    "Pulling Duo Unix from Fedora. Hope the admin panel is open.",
    "Installing Duo. Your phone will hate you later.",
)

DUO_DONE = (
    "Keys written to {path}. Mode 600. Don't screenshot that.",
    "{path} has the secrets. Fail open until you say otherwise.",
)

DUO_SSH = (
    "SSH now runs through login_duo. Drop-in at {path}. Don't lose your phone.",
    "ForceCommand is live. Remove {path} if you want the old kind of broken.",
)


def say(lines: tuple[str, ...], **fmt: str) -> str:
    return random.choice(lines).format(**fmt)
