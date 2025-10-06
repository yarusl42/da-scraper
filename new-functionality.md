right now it uses gmb everywhere to find the categories selected for a gmb listings. 
I want to expand the functionality of it to include more fields witch the gmb everywhere plugin can't find. 
We're going to be using PlePer. Upside of gmb everywhere was that you could simply scroll all the way down to the bottom of the google maps listings and then extract the data. PlePer is a bit more complex and you have to click on the listings once by one and scrape a panel that would appear on the page. 

0. Make the scrolling down routine first, get all the items, then follow the plan listed below
1. How to select a listing. In my browser i do it like so:
listings[0].querySelector(".hfpxzc").click()
We have a listings array in the code, so we can use it to select the listing. My code is obviosly in python, the snippet is in js
2. The PlePer side panel has class "single_listing_info_window", but every time i select a different listing it changes its id attribute for the same dev element. It's important because we can detect if the panel actualy loaded. We're going to be clicking listings one by one and we need to make sure that the panel loaded before we try to scrape it. 
3. For now, let's scrape just if the business if verified or not, query selector is just "small". Text content will say either "Verified" or "Not Verified", make sure it's text content cuz there is an image as well which we don't need. 
4. Add it as a new column "gbp_is_verified" to the output file. 