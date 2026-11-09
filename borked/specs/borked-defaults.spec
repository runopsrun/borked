Name:           borked-defaults
Version:        1
Release:        3%{?dist}
Summary:        Borked wallpaper, theme seed, and Quickshell bar
License:        MIT
URL:            https://borked.invalid
BuildArch:      noarch

Source0:        wallpaper.png
Source1:        accent_palette_dark
Source2:        accent_palette_light
Source3:        shell.qml
Source4:        borked-quickshell.service

%description
Wallpaper, a COSMIC accent-palette seed, and the Quickshell top bar.
The COSMIC panel list keeps the dock. Nothing is copied into /etc/skel.

%install
install -d -m 0755 %{buildroot}/usr/share/backgrounds/borked
install -d -m 0755 %{buildroot}/usr/share/borked/cosmic
install -d -m 0755 %{buildroot}/usr/share/borked/quickshell
install -d -m 0755 %{buildroot}/usr/lib/systemd/user/cosmic-session.target.wants
install -m 0644 %{SOURCE0} %{buildroot}/usr/share/backgrounds/borked/default.png
install -m 0644 %{SOURCE1} %{buildroot}/usr/share/borked/cosmic/accent_palette_dark
install -m 0644 %{SOURCE2} %{buildroot}/usr/share/borked/cosmic/accent_palette_light
install -m 0644 %{SOURCE3} %{buildroot}/usr/share/borked/quickshell/shell.qml
install -m 0644 %{SOURCE4} %{buildroot}/usr/lib/systemd/user/borked-quickshell.service
ln -s ../borked-quickshell.service %{buildroot}/usr/lib/systemd/user/cosmic-session.target.wants/borked-quickshell.service

%files
/usr/share/backgrounds/borked/default.png
/usr/share/borked/cosmic/accent_palette_dark
/usr/share/borked/cosmic/accent_palette_light
/usr/share/borked/quickshell/shell.qml
/usr/lib/systemd/user/borked-quickshell.service
/usr/lib/systemd/user/cosmic-session.target.wants/borked-quickshell.service

%transfiletriggerin -- /usr/share/cosmic/com.system76.CosmicPanel/v1
entries=/usr/share/cosmic/com.system76.CosmicPanel/v1/entries
if [ -f "$entries" ]; then
    printf '%%s\n' '["Dock"]' >"$entries" || :
fi

%changelog
* Mon Nov 09 2026 Borked OS <dev@borked.invalid> - 1-3
- The bar shows sound, network, Bluetooth, battery, the tray, and power.
* Mon Nov 09 2026 Borked OS <dev@borked.invalid> - 1-2
- Quickshell draws the top bar. The COSMIC panel list keeps the dock.
* Fri Nov 06 2026 Borked OS <dev@borked.invalid> - 1-1
- Initial wallpaper and COSMIC accent seed.
