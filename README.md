A quick and dirty Python script to download all your digital assets you purchased from Gumroad. 

Disclaimers:
* This assumes you have some basic understanding of the Python language and ecosystem.
* This isn't ready for quick distributing. It's just the script. You'll need to get the dependencies yourself and edit the script with some information.
* I'm not a Python pro, so some of this could probably be improved.
* This may miss some downloads if they don't follow the assumptions made when writing this script.
* This will probably break if Gumroad changes anything.

Feel free to fork or create PRs to improve.

# How to use

1. Download dependencies
* `requests`
* `BeautifulSoup4`
* `pathvalidate`

2. Edit the script to set the `OUTPUT_DIR`

3. When logged into Gumroad in your browser, copy the value of the cookie `_gumroad_app_session` and paste it into the script.

4. Run the script

# Protect your purchases

You can lose access to the files you paid for. Creators can change or remove the files of the asset your purchased at any time. Usually it's to improve the content you paid for. But you can lose all old versions, and worst case, you could lose everything. And there's probably other ways I haven't experienced (yet).

Note that Booth and Payhip have even worse customer protections than Gumroad.

It's a real **"buyer beware"** in the world of VRChat assets. The only way to be safe is to back them up yourself.

But it's not all bad. At least the creator got your money (passive aggressive :)

# How it works

Your Gumroad Library page (app.gumroad.com/library) contains a block of JSON with all the information about your assets. It then dynamically renders the page from that information. Likewise, the download page for a product you purchased is also a block of JSON that is rendered into html.

1. This downloads the Library page and captures the JSON. It saves the full Library page as an .html file
2. It then iterates through all your product download pages and downloads them and captures their JSON. 
3. For each product download page
    1. It creates a directory structure of *`<asset creator>/<product name>`*
    2. It downloads the thumbnail and all other "cover" images found on the original product page
    3. It saves the JSON to a file
    4. It downloads all the assets found on the product download page. If there's assets with the same name, it may make a time-stamped copy of the file.
    5. It creates a .url shortcut to the original product page
    6. It downloads the original product page and saves it as a .html file (assuming it still exists)

!! Note this skips any files or URLs that point outside of the gumroad.com domain, so you'll need to download them separately if you want them. It doesn't download the "Download All" option for some assets. This just searches for files. 

This script tries to be smart and not re-download something that already exists. It's designed to be safely run at any time to just get what's new. But it's not perfect.
