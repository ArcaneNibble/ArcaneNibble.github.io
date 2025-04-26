import pygments.styles
from pygments.formatters import get_formatter_by_name
from pygments.style import Style
from pygments.token import Token, Comment, Keyword, Name, String, \
     Error, Generic, Number, Operator

class FairyFlossStyle(Style):
    background_color = "#5A5475"
    highlight_color = "#716799"

    styles = {
        Token:          "#F8F8F2",
        Comment:        "#E6C000",
        String:         "#FFEA00",
        Number:         "#C5A3FF",
        Keyword:        "#FFB8D1",
        Operator:       "#FFB8D1",
        # fixme what is storage, storage type?
        Name.Class:     "#FFF352",
        Name.Function:  "#FFF352",
        # function args???
        Name.Tag:       "#FFB8D1",
        Name.Attribute: "#FFF352",
        Name.Builtin:   "#C2FFDF",
    }

def hooked(name):
    print("HOOKED!")
    return FairyFlossStyle
pygments.styles.get_style_by_name = hooked

fmter = get_formatter_by_name('html', style='default')
print(fmter.get_style_defs('.highlight'))
