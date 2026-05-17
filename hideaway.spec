Name:           hideaway
Version:        0.1.0
Release:        1%{?dist}
Summary:        A Libadwaita application to manage GNOME overview applications

License:        GPL-3.0-or-later
URL:            https://example.com/hideaway
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  meson
BuildRequires:  gcc
BuildRequires:  pkgconfig(gtk4) >= 4.10
BuildRequires:  pkgconfig(libadwaita-1) >= 1.4
BuildRequires:  python3-devel

Requires:       gtk4 >= 4.10
Requires:       libadwaita >= 1.4
Requires:       python3-gobject
Requires:       polkit

%description
Hideaway is a small GNOME utility that allows you to view and hide
(or remove) applications from your GNOME overview directory.

%prep
%autosetup

%build
%meson
%meson_build

%install
%meson_install

%files
%license LICENSE
%{_bindir}/hideaway
%{_datadir}/hideaway/
