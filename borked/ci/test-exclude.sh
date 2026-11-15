#!/bin/bash
# A bad exclude must fail the solve. Run inside the Fedora container.
set -euo pipefail
# shellcheck disable=SC1091
source /src/image/lib.sh

dnf_build -y install python3 >/dev/null
root=/tmp/borked-exclude-test
rm -rf "$root"
mkdir -p "$root"
set +e
output="$(dnf_build --installroot="$root" --use-host-config --assumeno install --exclude=glibc bash 2>&1)"
status=$?
set -e
printf '%s\n' "$output"
if [[ "$status" -eq 0 ]]; then
    echo "exclude test: dnf accepted an uninstallable transaction" >&2
    exit 1
fi
if printf '%s\n' "$output" | grep -q "Transaction Summary"; then
    echo "exclude test: bash solved while glibc was excluded" >&2
    exit 1
fi
if ! printf '%s\n' "$output" | grep -Eqi 'glibc|problem|nothing provides'; then
    echo "exclude test: failure was not a glibc dependency problem" >&2
    exit 1
fi
grep -qx 'nginx' /src/packages/exclude.list
if grep -Eq '^glibc($|[[:space:]])' /src/packages/exclude.list; then
    echo "exclude test: glibc must not be in the real exclude list" >&2
    exit 1
fi
echo "exclude test: bad exclude failed the solve"
