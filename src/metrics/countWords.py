import re
def count_words(soup):
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()

    text = soup.get_text(" ", strip=True)
    words = re.findall(r'\b\w+\b', text)
    num_words = len(words)
    return num_words