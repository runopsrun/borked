Name:           borked-defaults
Version:        1
Release:        1%{?dist}
Summary:        Borked OS COSMIC theme seed and wallpaper
License:        MIT
URL:            https://borked.invalid
BuildArch:      noarch

Source0:        wallpaper.png
Source1:        accent_palette_dark
Source2:        accent_palette_light

%description
Wallpaper and a COSMIC accent-palette seed. Nothing is copied into /etc/skel.

%install
install -d -m 0755 %{buildroot}/usr/share/backgrounds/borked
install -d -m 0755 %{buildroot}/usr/share/borked/cosmic
install -m 0644 %{SOURCE0} %{buildroot}/usr/share/backgrounds/borked/default.png
install -m 0644 %{SOURCE1} %{buildroot}/usr/share/borked/cosmic/accent_palette_dark
install -m 0644 %{SOURCE2} %{buildroot}/usr/share/borked/cosmic/accent_palette_light

%files
/usr/share/backgrounds/borked/default.png
/usr/share/borked/cosmic/accent_palette_dark
/usr/share/borked/cosmic/accent_palette_light

%changelog
* Fri Nov 06 2026 Borked OS <dev@borked.invalid> - 1-1
- Initial wallpaper and COSMIC accent seed.
