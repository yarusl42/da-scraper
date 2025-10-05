def count_images(soup):
    img_tags = soup.find_all('img')
    num_images = len(img_tags)
    return num_images