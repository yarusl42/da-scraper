def has_favicon(soup):
    icon_link = soup.find('link', rel=lambda x: x and 'icon' in x.lower())
    return bool(icon_link)