#!/bin/bash
# Launch Cytrence Kiwi inside its distrobox. The binary is SDL/X11.
# COSMIC is Wayland, so the video driver stays on X11 (Xwayland) unless
# the environment already picked something else.
# ~/.config/borked/kiwi.env is sourced when it exists. That is where a
# machine-specific workaround goes, such as SDL_AUDIO_DRIVER=dummy when
# nouveau's HDMI sink blanks a display.

if [ -f "${HOME}/.config/borked/kiwi.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "${HOME}/.config/borked/kiwi.env"
    set +a
fi

export LD_LIBRARY_PATH="/opt/cytrence/kiwi/bin${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export SDL_VIDEO_DRIVER="${SDL_VIDEO_DRIVER:-x11}"
export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-x11}"
export SDL_VIDEO_X11_XRANDR="${SDL_VIDEO_X11_XRANDR:-0}"
export SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR="${SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR:-0}"
export SDL_VIDEO_ALLOW_SCREENSAVER="${SDL_VIDEO_ALLOW_SCREENSAVER:-1}"
export EGL_PLATFORM="${EGL_PLATFORM:-x11}"

exec /opt/cytrence/kiwi/bin/CytrenceKiwi "$@"
