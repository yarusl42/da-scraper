def has_meta_description(soup):
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    return bool(meta_desc and meta_desc.get('content', '').strip())