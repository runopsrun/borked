Name:           borked-release
Version:        1
Release:        4%{?dist}
Summary:        Borked release identity
License:        MIT
URL:            https://projectborked.com
BuildArch:      noarch

%{!?fedora_release:%{error:pass --define "fedora_release N"}}
%{!?identity_evr:%{error:pass --define "identity_evr VER-REL"}}
%{!?borked_variant:%global borked_variant Development}

Source0:        issue
Source1:        borked-selfcheck
Source2:        exclude.list

# Matched to fedora-release-common's require at build time.
Provides:       fedora-release-identity = %{identity_evr}
Provides:       borked-release

Requires:       bash
Requires:       rpm
Requires:       systemd

%description
Release files for Borked OS, a Fedora remix. This package provides
fedora-release-identity so Fedora's identity packages are not installed
over /usr/lib/os-release.

%install
install -d -m 0755 %{buildroot}/usr/lib
install -d -m 0755 %{buildroot}/usr/bin
install -d -m 0755 %{buildroot}/usr/share/borked
install -d -m 0755 %{buildroot}/etc/dnf/protected.d

variant="%{borked_variant}"
case "$variant" in
    COSMIC|cosmic) variant_id=cosmic; variant=COSMIC ;;
    *) variant_id=development; variant=Development ;;
esac

cat > %{buildroot}/usr/lib/os-release << EOF
NAME="Borked"
VERSION="%{fedora_release}"
ID=borked
ID_LIKE=fedora
VERSION_ID=%{fedora_release}
PRETTY_NAME="Borked"
ANSI_COLOR="0;38;2;232;80;70"
CPE_NAME="cpe:/o:borked:borked:%{fedora_release}"
HOME_URL="https://projectborked.com"
VARIANT="$variant"
VARIANT_ID=$variant_id
EOF

install -m 0644 %{SOURCE0} %{buildroot}/usr/share/borked/issue
install -m 0755 %{SOURCE1} %{buildroot}/usr/bin/borked-selfcheck
install -m 0644 %{SOURCE2} %{buildroot}/usr/share/borked/exclude.list
printf '%s\n' borked-release borked-repos borked-defaults borked-apps > %{buildroot}/etc/dnf/protected.d/borked.conf

%post
if [ -d /usr/lib ]; then
    ln -sfn ../usr/lib/os-release /etc/os-release
fi
if [ -f /usr/share/borked/issue ]; then
    cp -f /usr/share/borked/issue /etc/issue
    cp -f /usr/share/borked/issue /usr/lib/issue
fi

%files
/usr/lib/os-release
/usr/bin/borked-selfcheck
/usr/share/borked/issue
/usr/share/borked/exclude.list
/etc/dnf/protected.d/borked.conf

%changelog
* Sat Nov 28 2026 Borked <dev@borked.invalid> - 1-4
- Require getenforce=Enforcing in borked-selfcheck and update package URL.
* Thu Nov 26 2026 Borked OS <dev@borked.invalid> - 1-3
- The boot check requires both COSMIC and Hyprland session files.
* Mon Nov 09 2026 Borked OS <dev@borked.invalid> - 1-2
- The boot check looks for BlueZ, UPower, and bluetooth.service.
* Fri Nov 06 2026 Borked OS <dev@borked.invalid> - 1-1
- Initial Borked OS release identity.
