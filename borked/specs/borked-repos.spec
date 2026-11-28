Name:           borked-repos
Version:        1
Release:        2%{?dist}
Summary:        Borked package repository
License:        MIT
URL:            https://projectborked.com
BuildArch:      noarch

%{!?fedora_release:%{error:pass --define "fedora_release N"}}

Source0:        RPM-GPG-KEY-borked

Requires:       fedora-repos

%description
Repository definition for the Borked package set. Fedora repositories stay
in place and are checked with Fedora's keys. This repo is a higher priority
only for packages Borked actually ships.

%install
install -d -m 0755 %{buildroot}/etc/yum.repos.d
install -d -m 0755 %{buildroot}/etc/pki/rpm-gpg
install -m 0644 %{SOURCE0} %{buildroot}/etc/pki/rpm-gpg/RPM-GPG-KEY-borked
cat > %{buildroot}/etc/yum.repos.d/borked.repo << EOF
[borked]
name=Borked OS %{fedora_release} - x86_64
baseurl=https://repo.borked.invalid/%{fedora_release}/x86_64
enabled=1
gpgcheck=1
repo_gpgcheck=0
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-borked
priority=90
skip_if_unavailable=1
countme=0
EOF

%files
/etc/yum.repos.d/borked.repo
/etc/pki/rpm-gpg/RPM-GPG-KEY-borked

%changelog
* Sat Nov 28 2026 Borked <dev@borked.invalid> - 1-2
- Update package URL and summary.
* Fri Nov 06 2026 Borked OS <dev@borked.invalid> - 1-1
- Initial Borked repository definition.
