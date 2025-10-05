from countWords import count_words
def check_if_js_is_used(soup, soup_unloaded):
    words = count_words(soup)
    words_unloaded = count_words(soup_unloaded)
    return words > words_unloaded
    