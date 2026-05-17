import os
from gi.repository import Gtk, Adw

@Gtk.Template(filename=os.path.join(os.path.dirname(__file__), 'preferences.ui'))
class HideawayPreferences(Adw.PreferencesWindow):
    __gtype_name__ = 'HideawayPreferences'
    
    behavior_switch = Gtk.Template.Child()

    def __init__(self, parent, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent)
        app = parent.get_application()
        self.behavior_switch.set_active(app.use_file_deletion)
        self.behavior_switch.connect("notify::active", self.on_switch_changed)

    def on_switch_changed(self, switch, param):
        app = self.get_transient_for().get_application()
        app.use_file_deletion = switch.get_active()
        app.save_config()
