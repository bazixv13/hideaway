import sys
import os
import json
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, Gio, GLib, Gdk
try:
    from window import HideawayWindow
    from preferences import HideawayPreferences
    from i18n import _
except ImportError:
    from .window import HideawayWindow
    from .preferences import HideawayPreferences
    from .i18n import _

CONFIG_DIR = os.path.expanduser('~/.config/hideaway')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

class HideawayApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id='io.github.bazixv13.Hideaway',
                         flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.create_action('preferences', self.on_preferences_action)
        self.create_action('about', self.on_about_action)
        self.use_file_deletion = False
        self.load_config()
        self.win = None

    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
            # Schema validation — only accept known keys with correct types
            if isinstance(data, dict):
                val = data.get('use_file_deletion', False)
                self.use_file_deletion = bool(val) if isinstance(val, bool) else False
        except Exception:
            pass

    def save_config(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            # Write to temp file then atomically rename to avoid partial writes
            tmp = CONFIG_FILE + '.tmp'
            with open(tmp, 'w') as f:
                json.dump({'use_file_deletion': bool(self.use_file_deletion)}, f)
            os.replace(tmp, CONFIG_FILE)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def do_activate(self):
        display = Gdk.Display.get_default()
        if display:
            icon_theme = Gtk.IconTheme.get_for_display(display)
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            icon_theme.add_search_path(os.path.join(base_dir, 'data', 'icons'))
            
            if os.path.exists('/.flatpak-info'):
                icon_theme.add_search_path('/var/run/host/usr/share/icons')
                icon_theme.add_search_path('/var/run/host/usr/share/pixmaps')
                
                real_home = os.environ.get('HOME', '')
                if '.var/app' in real_home:
                    real_home = real_home.split('.var/app')[0].rstrip('/')
                icon_theme.add_search_path(os.path.join(real_home, '.local/share/icons'))
                icon_theme.add_search_path(os.path.join(real_home, '.icons'))

        if not self.win:
            self.win = HideawayWindow(application=self)
        self.win.present()

    def create_action(self, name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)

    def on_preferences_action(self, widget, param):
        pref_window = HideawayPreferences(parent=self.win)
        pref_window.present()

    def on_about_action(self, widget, param):
        about = Adw.AboutWindow(
            application_name=_("Hideaway"),
            application_icon="io.github.bazixv13.Hideaway",
            developer_name=_("bazixv13"),
            version="1.1.2",
            website="https://github.com/bazixv13/hideaway"
        )
        about.add_credit_section(_("Contributors"), ["bazixv13"])
        about.add_acknowledgement_section(_("Special Thanks"), ["GNOME Foundation"])
        about.set_transient_for(self.win)
        about.present()

def main():
    app = HideawayApplication()
    return app.run(sys.argv)

if __name__ == '__main__':
    # Initialize icon theme locally if testing (optional, Libadwaita usually handles basic ones)
    sys.exit(main())
