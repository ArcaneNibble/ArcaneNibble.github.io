AUTHOR = 'ArcaneNibble'
SITENAME = 'ArcaneNibble\'s site'
SITEURL = ''

PATH = 'content'

TIMEZONE = 'Etc/UTC'

DEFAULT_LANG = 'en'

# Don't want these pages
AUTHOR_SAVE_AS = ''
CATEGORY_SAVE_AS = ''

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

# Blogroll
LINKS = (('My CV', '/cv.html'),)

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

PLUGINS = ['i18n_subsites']
JINJA_ENVIRONMENT = {'extensions': ['jinja2.ext.i18n']}
THEME = "pelican-bootstrap3-fork"

DISPLAY_CATEGORIES_ON_MENU = False
DISPLAY_CATEGORIES_ON_SIDEBAR = True
DISPLAY_ARTICLE_INFO_ON_INDEX = True

CUSTOM_LICENSE = 'Unless otherwise stated, all articles are published under the <a href="https://creativecommons.org/publicdomain/zero/1.0/legalcode">CC0</a> license.'
