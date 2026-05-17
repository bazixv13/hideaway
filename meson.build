project('hideaway',
          version: '1.4.1',
    meson_version: '>= 0.62.0',
  default_options: [ 'warning_level=2', 'werror=false', ],
)

dependency('gtk4', version: '>= 4.10')
dependency('libadwaita-1', version: '>= 1.4')
dependency('pygobject-3.0', version: '>= 3.40')

python = import('python')

subdir('src')
subdir('data')
subdir('po')
