GENERIC_TITLES = [
    "home", "welcome", "index", "my website", "untitled", "new site", "default title"
]

def check_generic_title(soup):
    try:
        title_tag = soup.find('title')
        title_text = title_tag.text.strip() if title_tag else ""
        
        # Check against generic list
        is_generic = title_text.lower() in GENERIC_TITLES
        
        return {
            "title": title_text,
            "is_generic": is_generic
        }
    except Exception as e:
        return {"error": str(e)}
