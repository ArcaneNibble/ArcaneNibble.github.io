AUTHOR = 'ArcaneNibble'
SITENAME = 'ArcaneNibble\'s site'
SITEURL = ''

PATH = 'content'

TIMEZONE = 'Etc/UTC'

DEFAULT_LANG = 'en'

# Don't want these pages
AUTHOR_SAVE_AS = ''
CATEGORY_SAVE_AS = ''
DIRECT_TEMPLATES = ['index', 'archives']

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

NAVLINKS = (('My CV', '/cv.html'),)

# Social widget
SOCIAL = (('Mastodon', 'https://glauca.space/@r', 'home'),
          ('GitHub', 'https://github.com/ArcaneNibble/'),
          ('Email', 'mailto:rqou@berkeley.edu', 'envelope'),
          ('Ko-fi', 'https://ko-fi.com/arcanenibble', 'dollar'))

DEFAULT_PAGINATION = False

# Uncomment following line if you want document-relative URLs when developing
#RELATIVE_URLS = True

STATIC_PATHS = [
    'images',
    'extra',
]
ARTICLE_EXCLUDES = [
    'extra',
]
EXTRA_PATH_METADATA = {
    'extra/new-cv.html': {'path': 'cv.html'}
}

THEME = "arcanenibble-theme"

DISPLAY_CATEGORIES_ON_MENU = False
DISPLAY_CATEGORIES_ON_SIDEBAR = True
DISPLAY_ARTICLE_INFO_ON_INDEX = True
