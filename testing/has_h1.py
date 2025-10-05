def has_h1(soup):
    h1_tag = soup.find('h1')
    return bool(h1_tag)