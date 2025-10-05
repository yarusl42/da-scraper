import re

def guess_last_update(head, soup):
    try:        
        last_mod = head.headers.get('Last-Modified')
        # 3. Look for meta updated dates
        meta_date = soup.find('meta', attrs={'property': 'article:modified_time'}) \
                    or soup.find('meta', attrs={'name': 'last-modified'})
        meta_date = meta_date['content'] if meta_date else None

        # 4. Find visible “Updated” or copyright years
        text = soup.get_text(" ", strip=True)
        years = re.findall(r'(20[1-3][0-9])', text)  # e.g. 2010–2039
        updated = re.search(r'updated\s*(on|:)?\s*\w*\s*\d{4}', text, re.I)

        # Pick the latest year found
        latest_year = max(map(int, years)) if years else None

        return {
            "last_modified_header": last_mod,
            "meta_date": meta_date,
            "latest_year_in_text": latest_year,
            "has_updated_phrase": bool(updated),
        }

    except Exception as e:
        return {"error": str(e)}
