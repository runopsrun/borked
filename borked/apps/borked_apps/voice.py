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

That's the list. It will get longer. Unfortunately.
"""


def say(lines: tuple[str, ...], **fmt: str) -> str:
    return random.choice(lines).format(**fmt)
