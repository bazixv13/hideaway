import os
import gettext
import locale

try:
    locale.setlocale(locale.LC_ALL, '')
except Exception:
    pass

LOCALEDIR = os.environ.get('HIDEAWAY_LOCALE_DIR')
if not LOCALEDIR:
    if os.path.exists('/.flatpak-info'):
        LOCALEDIR = '/app/share/locale'
    else:
        LOCALEDIR = '/usr/share/locale'

gettext.bindtextdomain('hideaway', LOCALEDIR)
gettext.textdomain('hideaway')
_ = gettext.gettext
