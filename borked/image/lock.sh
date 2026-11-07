#!/bin/bash
# Build the local repo, then write packages/lock.
set -euo pipefail
# shellcheck disable=SC1091
source /src/image/lib.sh

/src/image/build-rpms.sh
write_borked_repo
dnf_build -y install python3
python3 /src/image/solve.py
borked_chown /src/out /src/packages/lock
