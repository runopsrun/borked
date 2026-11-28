Name:           borked-defaults
Version:        1
Release:        7%{?dist}
Summary:        Borked wallpaper, theme seed, and Quickshell bar
License:        MIT
URL:            https://projectborked.com
BuildArch:      noarch

Source0:        wallpaper.png
Source1:        accent_palette_dark
Source2:        accent_palette_light
Source3:        shell.qml
Source4:        borked-quickshell.service
Source5:        hyprland.conf
Source6:        hyprpaper.conf

%description
Wallpaper, a COSMIC accent-palette seed, the Quickshell top bar, and
Hyprland session defaults the installer copies for that desktop choice.
The COSMIC panel list keeps the dock. Nothing is copied into /etc/skel.

%install
install -d -m 0755 %{buildroot}/usr/share/backgrounds/borked
install -d -m 0755 %{buildroot}/usr/share/borked/cosmic
install -d -m 0755 %{buildroot}/usr/share/borked/quickshell
install -d -m 0755 %{buildroot}/usr/share/borked/hypr
install -d -m 0755 %{buildroot}/usr/lib/systemd/user/cosmic-session.target.wants
install -m 0644 %{SOURCE0} %{buildroot}/usr/share/backgrounds/borked/default.png
install -m 0644 %{SOURCE1} %{buildroot}/usr/share/borked/cosmic/accent_palette_dark
install -m 0644 %{SOURCE2} %{buildroot}/usr/share/borked/cosmic/accent_palette_light
install -m 0644 %{SOURCE3} %{buildroot}/usr/share/borked/quickshell/shell.qml
install -m 0644 %{SOURCE4} %{buildroot}/usr/lib/systemd/user/borked-quickshell.service
install -m 0644 %{SOURCE5} %{buildroot}/usr/share/borked/hypr/hyprland.conf
install -m 0644 %{SOURCE6} %{buildroot}/usr/share/borked/hypr/hyprpaper.conf
ln -s ../borked-quickshell.service %{buildroot}/usr/lib/systemd/user/cosmic-session.target.wants/borked-quickshell.service

%files
/usr/share/backgrounds/borked/default.png
/usr/share/borked/cosmic/accent_palette_dark
/usr/share/borked/cosmic/accent_palette_light
/usr/share/borked/quickshell/shell.qml
/usr/share/borked/hypr/hyprland.conf
/usr/share/borked/hypr/hyprpaper.conf
/usr/lib/systemd/user/borked-quickshell.service
/usr/lib/systemd/user/cosmic-session.target.wants/borked-quickshell.service

%transfiletriggerin -- /usr/share/cosmic/com.system76.CosmicPanel/v1
entries=/usr/share/cosmic/com.system76.CosmicPanel/v1/entries
if [ -f "$entries" ]; then
    printf '%%s\n' '["Dock"]' >"$entries" || :
fi

%changelog
* Sat Nov 28 2026 Borked <dev@borked.invalid> - 1-7
- Share the nmcli link probe across screens and terminate only the current session on logout.
* Thu Nov 26 2026 Borked OS <dev@borked.invalid> - 1-6
- Ship Hyprland session defaults the installer can copy.
* Sun Nov 15 2026 Borked OS <dev@borked.invalid> - 1-5
- Point Quickshell at the Cosmic icon theme so status glyphs are not missing.
* Mon Nov 09 2026 Borked OS <dev@borked.invalid> - 1-4
- The bar floats, and the status icons share one control center.
* Mon Nov 09 2026 Borked OS <dev@borked.invalid> - 1-3
- The bar shows sound, network, Bluetooth, battery, the tray, and power.
* Mon Nov 09 2026 Borked OS <dev@borked.invalid> - 1-2
- Quickshell draws the top bar. The COSMIC panel list keeps the dock.
* Fri Nov 06 2026 Borked OS <dev@borked.invalid> - 1-1
- Initial wallpaper and COSMIC accent seed.
