import os
import re
import shutil
import subprocess
import threading
import unicodedata
from gi.repository import Gtk, Adw, Gio, GLib, GObject

try:
    from i18n import _
except ImportError:
    from .i18n import _

# Allowed base directories — paths must resolve within these
_SAFE_FILENAME_RE = re.compile(r'^[\w][\w\-. ]*\.desktop$', re.UNICODE)


class AppItem(GObject.Object):
    """GObject wrapper for a single app entry, used in the ListStore model."""
    __gtype_name__ = 'AppItem'

    name     = GObject.Property(type=str, default='')
    filename = GObject.Property(type=str, default='')
    icon     = GObject.Property(type=str, default='application-x-executable')
    status   = GObject.Property(type=str, default='installed')  # installed | hidden | backed_up

    def __init__(self, name, filename, icon, status):
        super().__init__()
        self.name     = name
        self.filename = filename
        self.icon     = icon
        self.status   = status


@Gtk.Template(filename=os.path.join(os.path.dirname(__file__), 'window.ui'))
class HideawayWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'HideawayWindow'

    app_listbox  = Gtk.Template.Child()
    search_bar   = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.in_flatpak = os.path.exists('/.flatpak-info')

        default_usr = '/var/run/host/usr/share/applications' if self.in_flatpak else '/usr/share/applications'

        if self.in_flatpak:
            real_home = os.environ.get('HOME', '')
            if '.var/app' in real_home:
                real_home = real_home.split('.var/app')[0].rstrip('/')
            default_local  = os.path.join(real_home, '.local/share/applications')
            default_backup = os.path.join(real_home, '.local/share/hideaway/backups')
        else:
            default_local  = os.path.expanduser('~/.local/share/applications')
            default_backup = os.path.expanduser('~/.local/share/hideaway/backups')

        self.usr_dir    = self._validated_dir(os.environ.get('APP_MANAGER_USR_DIR'),    default_usr)
        self.local_dir  = self._validated_dir(os.environ.get('APP_MANAGER_LOCAL_DIR'),  default_local)
        self.backup_dir = self._validated_dir(os.environ.get('APP_MANAGER_BACKUP_DIR'), default_backup)

        os.makedirs(self.local_dir,  exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)

        # Model
        self.store = Gio.ListStore(item_type=AppItem)

        # Filter wraps the store; only items passing _filter_func are shown
        self._filter = Gtk.CustomFilter.new(self._filter_func, None)
        self._filter_model = Gtk.FilterListModel.new(self.store, self._filter)
        self.app_listbox.bind_model(self._filter_model, self._create_row)

        # Search
        self.search_entry.connect('search-changed', self._on_search_changed)
        # Pressing Escape collapses the bar and clears the query
        self.search_entry.connect('stop-search', self._on_stop_search)

        # Load app list off the main thread so the window opens instantly
        threading.Thread(target=self._load_apps_bg, daemon=True).start()

    # Security helpers

    @staticmethod
    def _validated_dir(env_val, default):
        """Accept an env-var override only if it's an absolute path with no
        null bytes. Falls back to the safe default otherwise."""
        if env_val and env_val.startswith('/') and '\x00' not in env_val:
            return os.path.normpath(env_val)
        return default

    def _safe_join(self, base: str, filename: str) -> str | None:
        """Join base + filename and verify the result stays inside base.
        Returns None if the resolved path escapes (path-traversal guard)."""
        if not _SAFE_FILENAME_RE.match(filename):
            return None
        joined = os.path.normpath(os.path.join(base, filename))
        if not joined.startswith(os.path.normpath(base) + os.sep):
            return None
        return joined

    # Background loading

    def _load_apps_bg(self):
        """Scan desktop dirs on a worker thread, then push results to UI."""
        apps = {}

        if os.path.exists(self.usr_dir):
            for filename in os.listdir(self.usr_dir):
                if not _SAFE_FILENAME_RE.match(filename):
                    continue  # skip files with suspicious names
                path = self._safe_join(self.usr_dir, filename)
                if not path:
                    continue
                info = self._parse_desktop(path)
                if info:
                    info['status'] = 'installed'
                    apps[filename] = info

        for filename, info in apps.items():
            if self._check_is_hidden(filename):
                info['status'] = 'hidden'

        if os.path.exists(self.backup_dir):
            for filename in os.listdir(self.backup_dir):
                if not _SAFE_FILENAME_RE.match(filename):
                    continue
                path = self._safe_join(self.backup_dir, filename)
                if not path:
                    continue
                info = self._parse_desktop(path)
                if info:
                    info['status'] = 'backed_up'
                    apps[filename] = info

        sorted_apps = sorted(apps.values(), key=lambda x: x['name'].lower())
        GLib.idle_add(self._populate_store, sorted_apps)

    def _populate_store(self, app_list):
        self.store.remove_all()
        items = [
            AppItem(a['name'], a['filename'], a['icon'], a['status'])
            for a in app_list
        ]
        self.store.splice(0, 0, items)
        return GLib.SOURCE_REMOVE

    # Search & filtering

    @staticmethod
    def _sanitise(text: str) -> str:
        # Normalise, truncate, and strip special characters to prevent regex backtracking
        text = unicodedata.normalize('NFC', text)
        text = text.strip()[:100]
        text = re.sub(r'[^\w\s.\-]', '', text, flags=re.UNICODE)
        return text.lower()

    def _filter_func(self, item, _user_data):
        """Return True if the item should be visible."""
        query = self._sanitise(self.search_entry.get_text())
        if not query:
            return True
        # Match against normalised name and filename
        name     = unicodedata.normalize('NFC', item.name).lower()
        filename = item.filename.lower()
        return query in name or query in filename

    def _on_search_changed(self, _entry):
        """Called every keystroke — tell GTK the filter needs re-evaluation."""
        self._filter.changed(Gtk.FilterChange.DIFFERENT)

    def _on_stop_search(self, _entry):
        """Escape pressed: clear the query and collapse the search bar."""
        self.search_entry.set_text('')
        self.search_bar.set_search_mode(False)

    # Row factory

    def _create_row(self, item):
        row = Adw.ActionRow(title=item.name, subtitle=item.filename)

        # Icon — just set the name; GTK resolves it lazily when painting
        icon_widget = Gtk.Image(icon_name=item.icon, pixel_size=32)
        row.add_prefix(icon_widget)

        btn = self._make_button_for_status(item.status, item, row)
        row.add_suffix(btn)

        return row

    def _make_button_for_status(self, status, item, row):
        if status == 'backed_up':
            btn = Gtk.Button(label=_("Restore (Moved)"), valign=Gtk.Align.CENTER)
            btn.add_css_class("suggested-action")
            btn.connect("clicked", self.on_restore_moved, item, row)
        elif status == 'hidden':
            btn = Gtk.Button(label=_("Restore"), valign=Gtk.Align.CENTER)
            btn.add_css_class("suggested-action")
            btn.connect("clicked", self.on_restore_hidden, item, row)
        else:
            btn = Gtk.Button(label=_("Remove"), valign=Gtk.Align.CENTER)
            btn.add_css_class("destructive-action")
            btn.connect("clicked", self.on_remove, item, row)
        return btn

    # Desktop file parsing helpers

    def _parse_desktop(self, path):
        keyfile = GLib.KeyFile.new()
        try:
            keyfile.load_from_file(path, GLib.KeyFileFlags.NONE)
            if not keyfile.has_group("Desktop Entry"):
                return None
            try:
                if keyfile.get_boolean("Desktop Entry", "NoDisplay"):
                    return None
            except GLib.Error:
                pass
            try:
                name = keyfile.get_string("Desktop Entry", "Name")
            except GLib.Error:
                name = os.path.basename(path)
            try:
                icon = keyfile.get_string("Desktop Entry", "Icon")
            except GLib.Error:
                icon = "application-x-executable"
            return {"name": name, "icon": icon, "filename": os.path.basename(path), "path": path}
        except GLib.Error:
            return None

    def _check_is_hidden(self, filename):
        local_path = os.path.join(self.local_dir, filename)
        if os.path.exists(local_path):
            keyfile = GLib.KeyFile.new()
            try:
                keyfile.load_from_file(local_path, GLib.KeyFileFlags.NONE)
                if keyfile.get_boolean("Desktop Entry", "NoDisplay"):
                    return True
            except GLib.Error:
                pass
        return False

    # UI helpers

    def show_error(self, message):
        dialog = Gtk.AlertDialog(message=message)
        dialog.show(self)

    def _swap_button(self, row, old_btn, new_label, new_css, new_handler, item):
        row.remove(old_btn)
        new_btn = Gtk.Button(label=new_label, valign=Gtk.Align.CENTER)
        new_btn.add_css_class(new_css)
        new_btn.connect("clicked", new_handler, item, row)
        row.add_suffix(new_btn)

    # Actions

    def on_remove(self, button, item, row):
        use_deletion = self.get_application().use_file_deletion

        if use_deletion:
            src  = self._safe_join(self.usr_dir, item.filename)
            dest = self._safe_join(self.backup_dir, item.filename)
            if not src or not dest:
                self.show_error(_("Invalid filename — operation aborted."))
                return
            if not os.path.exists(dest):
                self._move_file_async(
                    src, dest,
                    on_success=lambda: self._swap_button(row, button, _("Restore (Moved)"), "suggested-action", self.on_restore_moved, item),
                    on_error=lambda msg: self.show_error(msg),
                )
        else:
            src  = self._safe_join(self.usr_dir, item.filename)
            dest = self._safe_join(self.local_dir, item.filename)
            if not src or not dest:
                self.show_error(_("Invalid filename — operation aborted."))
                return
            try:
                # TOCTOU fix: use O_EXCL via open() instead of exists()-then-copy
                try:
                    fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    os.close(fd)
                    shutil.copy2(src, dest)
                except FileExistsError:
                    pass  # already copied from a previous hide; just update NoDisplay
                keyfile = GLib.KeyFile.new()
                keyfile.load_from_file(dest, GLib.KeyFileFlags.NONE)
                keyfile.set_boolean("Desktop Entry", "NoDisplay", True)
                keyfile.save_to_file(dest)
            except Exception as e:
                self.show_error(_("Failed to hide app: {}").format(e))
                return
            self._swap_button(row, button, _("Restore"), "suggested-action", self.on_restore_hidden, item)

    def on_restore_hidden(self, button, item, row):
        dest = self._safe_join(self.local_dir, item.filename)
        if not dest:
            self.show_error(_("Invalid filename — operation aborted."))
            return
        try:
            if os.path.exists(dest):
                os.remove(dest)
        except Exception as e:
            self.show_error(_("Failed to restore: {}").format(e))
            return
        self._swap_button(row, button, _("Remove"), "destructive-action", self.on_remove, item)

    def on_restore_moved(self, button, item, row):
        src  = self._safe_join(self.backup_dir, item.filename)
        dest = self._safe_join(self.usr_dir, item.filename)
        if not src or not dest:
            self.show_error(_("Invalid filename — operation aborted."))
            return
        self._move_file_async(
            src, dest,
            on_success=lambda: self._swap_button(row, button, _("Remove"), "destructive-action", self.on_remove, item),
            on_error=lambda msg: self.show_error(msg),
        )

    # Privileged file moves

    def _move_file_async(self, src, dest, on_success, on_error):
        needs_root = '/usr/share' in src or '/usr/share' in dest \
                  or '/var/run/host/usr' in src or '/var/run/host/usr' in dest

        if needs_root:
            def worker():
                try:
                    if self.in_flatpak:
                        host_src  = src.replace('/var/run/host', '')  if src.startswith('/var/run/host')  else src
                        host_dest = dest.replace('/var/run/host', '') if dest.startswith('/var/run/host') else dest
                        cmd = ['flatpak-spawn', '--host', 'pkexec', 'mv', host_src, host_dest]
                    else:
                        cmd = ['pkexec', 'mv', src, dest]
                    subprocess.run(cmd, check=True)
                    GLib.idle_add(on_success)
                except subprocess.CalledProcessError:
                    GLib.idle_add(on_error, _("Authentication failed or was cancelled."))
                except Exception as e:
                    GLib.idle_add(on_error, _("Error moving file: {}").format(e))
            threading.Thread(target=worker, daemon=True).start()
        else:
            try:
                shutil.move(src, dest)
                on_success()
            except Exception as e:
                on_error(_("Error moving file: {}").format(e))
