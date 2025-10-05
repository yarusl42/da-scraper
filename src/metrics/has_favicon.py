def has_favicon(html_string):
    icon_link = html_string.find('<link rel="icon"')
    return icon_link != -1