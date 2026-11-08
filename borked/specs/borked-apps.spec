Name:           borked-apps
Version:        1
Release:        2%{?dist}
Summary:        Borked optional software picker
License:        MIT
URL:            https://projectborked.com
BuildArch:      noarch

Source0:        borked-apps.tar

Requires:       python3
Requires:       dnf

%description
TUI for software that is not part of the base image. The catalog is a
text file under /usr/share/borked/apps.

%install
install -d -m 0755 %{buildroot}/usr/share/borked/apps
tar -C %{buildroot}/usr/share/borked/apps -xf %{SOURCE0}
install -d -m 0755 %{buildroot}/usr/bin
cat > %{buildroot}/usr/bin/borked << 'EOF'
#!/usr/bin/python3
import sys
sys.path.insert(0, "/usr/share/borked/apps")
from borked_apps.__main__ import main
raise SystemExit(main())
EOF
chmod 0755 %{buildroot}/usr/bin/borked
install -d -m 0755 %{buildroot}/usr/share/applications
install -m 0644 %{buildroot}/usr/share/borked/apps/borked-apps.desktop \
    %{buildroot}/usr/share/applications/borked-apps.desktop

%files
/usr/bin/borked
/usr/share/borked/apps
/usr/share/applications/borked-apps.desktop

%changelog
* Sat Nov 07 2026 Borked <dev@borked.invalid> - 1-2
- The command is borked. apps is the first subcommand.
* Sat Nov 07 2026 Borked <dev@borked.invalid> - 1-1
- Optional software picker.
