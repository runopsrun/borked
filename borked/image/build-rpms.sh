#!/bin/bash
# Build and sign the three branding RPMs inside the Fedora container.
set -euo pipefail
# shellcheck disable=SC1091
source /src/image/lib.sh

variant="${BORKED_VARIANT:-Development}"
keydir=/src/out/keys
gnupg="$keydir/gnupg"
top=/src/out/rpmbuild

dnf_build -y install rpm-build rpm-sign createrepo_c gnupg2 python3

if [[ ! -f /src/branding/wallpaper.png ]]; then
    python3 /src/branding/gen_wallpaper.py
fi

install -d -m 0700 "$gnupg"
export GNUPGHOME="$gnupg"
if [[ -n "${BORKED_RELEASE_KEY:-}" ]]; then
    gpg --batch --import "$BORKED_RELEASE_KEY"
    gpg --batch --export --armor "$(gpg --batch --with-colons --list-secret-keys | awk -F: '/^uid:/ {print substr($10,1); exit}')" \
        >"$keydir/RPM-GPG-KEY-borked" || true
    if [[ ! -s "$keydir/RPM-GPG-KEY-borked" ]]; then
        gpg --batch --export --armor >"$keydir/RPM-GPG-KEY-borked"
    fi
elif [[ ! -s "$keydir/RPM-GPG-KEY-borked" ]]; then
    gpg --batch --pinentry-mode loopback --passphrase '' \
        --quick-gen-key "Borked OS Dev <dev@borked.invalid>" default default never
    gpg --batch --export --armor "Borked OS Dev <dev@borked.invalid>" >"$keydir/RPM-GPG-KEY-borked"
fi
printf 'allow-loopback-pinentry\n' >"$gnupg/gpg-agent.conf"
printf 'pinentry-mode loopback\n' >"$gnupg/gpg.conf"
chmod 700 "$gnupg"
gpgconf --kill gpg-agent >/dev/null 2>&1 || true

identity_evr="$(dnf_build -q repoquery --latest-limit=1 --queryformat '%{version}-%{release}' fedora-release-common | tail -n 1)"
if [[ ! "$identity_evr" =~ ^[0-9]+- ]]; then
    echo "could not read fedora-release-common EVR: ${identity_evr}" >&2
    exit 1
fi
echo "fedora-release-identity provide = ${identity_evr}"

rm -rf "$top"
install -d "$top"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
cp /src/branding/issue "$top/SOURCES/issue"
cp /src/branding/borked-selfcheck "$top/SOURCES/borked-selfcheck"
cp /src/packages/exclude.list "$top/SOURCES/exclude.list"
cp "$keydir/RPM-GPG-KEY-borked" "$top/SOURCES/RPM-GPG-KEY-borked"
cp /src/branding/wallpaper.png "$top/SOURCES/wallpaper.png"
cp /src/branding/accent_palette_dark "$top/SOURCES/accent_palette_dark"
cp /src/branding/accent_palette_light "$top/SOURCES/accent_palette_light"
cp /src/specs/*.spec "$top/SPECS/"

defines=(
    --define "_topdir $top"
    --define "dist .fc${RELEASE}"
    --define "fedora_release ${RELEASE}"
    --define "borked_variant ${variant}"
    --define "identity_evr ${identity_evr}"
    --define "_gpg_name Borked OS Dev <dev@borked.invalid>"
    --define "_gpg_path ${gnupg}"
    --define "__gpg /usr/bin/gpg"
    --define "_gpg_sign_cmd_extra_args --batch --pinentry-mode loopback --passphrase ''"
)

for spec in borked-release borked-repos borked-defaults; do
    rpmbuild "${defines[@]}" -bb "$top/SPECS/${spec}.spec"
done

install -d /src/out/repo
rm -f /src/out/repo/*.rpm
cp -a "$top"/RPMS/noarch/*.rpm /src/out/repo/
rpm --addsign "${defines[@]}" /src/out/repo/*.rpm
createrepo_c /src/out/repo
rpm --import "$keydir/RPM-GPG-KEY-borked" || true
borked_chown /src/out
echo "borked repo ready: $(ls /src/out/repo/*.rpm | wc -l) packages"
