pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
moduledir = join_paths(pkgdatadir, 'hideaway')

python.find_installation('python3').install_sources(
  'main.py',
  'window.py',
  'preferences.py',
  'i18n.py',
  subdir: 'hideaway'
)

# In a real app we'd configure main.py to point to installed UI files,
# but for simplicity in this example we can install the UI files next to the python files.
install_data(
  'window.ui',
  'preferences.ui',
  install_dir: python.find_installation('python3').get_install_dir(subdir: 'hideaway')
)

# Generate a wrapper script
wrapper_conf = configuration_data()
wrapper_conf.set('pkgdatadir', pkgdatadir)
wrapper_conf.set('moduledir', moduledir)

configure_file(
  input: 'hideaway.in',
  output: 'hideaway',
  configuration: wrapper_conf,
  install_dir: get_option('bindir')
)
