A scuffed Python script to download all your digital products you purchased from Gumroad, with an emphasis on also keeping a history of changes to those products.

Disclaimers:
* This assumes you have some basic understanding of the Python language.
* I'm not a Python pro, so some of this could probably be improved.
* The design expects the user will use Git to track the history of html and json files (otherwise that history will be lost upon each run of the app).
* This doesn't use any Gumroad API. It scrapes the web pages you see manually. It will definitely break if Gumroad changes anything.
* Creators can put just about anything in your library product download page, and links to external sites. I've been adding some exceptions for the variations I've come across, but some are too complicated to be worth implementing. So this may miss downloads for other odd cases which you'll have to handle manually.


# How to use

1. Download dependencies in requirements.txt

2. Edit `main.py` with these values:

    * Set the `OUTPUT_DIR` to a directory path where everything will be written
    * When logged into Gumroad in your browser, find and copy the value of these cookies:
        *  `_gumroad_app_session`
        * `_gumroad_guid`

3. Create a git repo at the `OUTPUT_DIR` location

4. Run the script

5. After each run, you'll want to commit the changes

# Protect your purchases

Your Gumroad library can change in several ways

* You purchase a new product
* A product is refunded and removed
* **A creator can remove a download from a product**
* A creator can change a product's name
* A creator can change the creator's name
* The store page for the product can be deleted (but it looks like you still keep your purchases)
* The creator can close their store (but it looks like you still keep your purchases (unlike Payhip and Booth...))
* Other important meta-data about your product can change or be removed

Notice that creators can remove the files of the product your purchased at any time. Usually it's to improve the content you paid for. But you can lose all old versions, and worst case, you could lose everything. And there's probably other ways I haven't experienced (yet).

It's a real **"buyer beware"** in the world of VRChat assets. The only way to be safe is to back them up yourself.

But it's not all bad. At least the creator got your money (passive aggressive :)

# Weird cases

Gumroad has so many strange cases that this script may or may not support.

* Links to "cover" images are intermittently included in the .json
* "cover" images can link to Youtube videos, or even a Sketchfab 3D model viewer
* Thumbnails and "cover" images file sizes will randomly change in size each time your download them. Sometimes the sizes changes in the middle of a download.
* A creator can add a new download to a product, which may have the same name as the prior version
* There can be more than one download with the same file name at the same time
* A product can be purchased multiple times
* Downloads can be to anywhere like Dropbox, Google Drive, Mediafire
* Creators can rename their name or product names
* Creator names, product names, and file names can have any strange Unicode characters you can think of
* Other important metadata can exist in your library product page like additional links, explanations, license keys, etc.
* Creators can change the text in your library product page

# How it works

Your Gumroad Library page (app.gumroad.com/library) contains a block of JSON with all the information about your assets. It then dynamically renders the page from that information. Likewise, the download page for a product you purchased is also a block of JSON that is rendered into html.

```html
<script class="js-react-on-rails-component" ... >{"json" : "here"}</script>
```

It then dynamically renders the page from that information. Likewise, the download page for a product you purchased has a similar block of JSON that is rendered into html.

What the script does:

1. It copies a pre-made `.gitignore` to the output directory to just track the html and json files
2. It downloads your Library page and captures the JSON. It saves the full Library page as an .html file. This will overwrite any existing library.html, so if you want to keep this history, use Git or other VCS.
3. It then iterates through all your product download pages. For each product download page:
    1. It creates a directory structure of *`<product creator>/<product name>`*
    2. It downloads the thumbnail and "cover" images found on the original product page (these seem to be intermittently available)
    3. It downloads the product download page html and captures its JSON.
    4. It saves the JSON to a file (both raw and formatted). Again, this will overwrite any existing product.json, so use Git or other VCS.
    5. For each file
        * It checks if a local file exists with the same name and id
        * It gets the size of the file on the Gumroad server
        * It compares the two sizes
        * If the Gumroad file size is the same as the local file size, it skips the download
        * Otherwise it downloads the file under a directory of its unique id\
        *`<product creator>/<product name>/<file id>/<file name>`*\
        The id directory is important because multiple files can have the same name.
    6. It creates a .url shortcut to the original product page.
    7. It downloads the original product page and saves it as a .html file (which may be a 404 page). Again, this will overwrite any existing html. This html can be useful because it may list dependencies and instructions on how to use. They also contain credits and ToS, but those probably aren't very important since creators never include them in the product downloads.
4. It generates log files of everything it does

There's a work-in-progress script that generates a local searchable .html page that lists all of your downloaded products with thumbnails.

**!! Note: this skips any files or URLs that point outside of the gumroad.com domain, so you'll need to download them separately if you want them (you'll need to search the logs).** It doesn't download any "Download All" option for files. This just searches for individual files located under the gumroad.com domain.

Since this script first checks if the file is already downloaded, it can save a lot of bandwidth, and should (hopefully) be safe to re-run anytime to just get new library items.

This script has evolved over several months and has been used multiple times to download over 400 digital purchases. But I have to continually tweak it to handle weird cases as I find them.

# Other

The [Gumload](https://github.com/InfiniteCanvas/gumload) project takes the same approach of scraping the web pages for the .json and downloading what it finds after first checking if the download exists. It also has a nicer presentation with progress bars and is mult-threaded. And it was clearly written by someone with more Python experience. But it only downloads the product downloads and doesn't have any checks for some of the weird cases listed above. If you have a small library, without any weird cases, and just want your product files, then it could be a practical alternative.