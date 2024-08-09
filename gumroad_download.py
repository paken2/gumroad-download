#
# Copyright (C) 2024 packentu
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# 

## Edit these before running the script ##

# Make sure this is right
OUTPUT_DIR = r'Z:\output\path'

# Open browser dev tools and look for "_gumroad_app_session" cookie, paste value here
_gumroad_app_session = r"""value of _gumroad_app_session cookie"""

#=================================================


# Custom packages
import requests
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename
from requests.adapters import HTTPAdapter

# Standard packages
import json
import shutil
import mimetypes
import urllib
import pathlib
import sys
import logging
import os
from datetime import datetime

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] {%(filename)s:%(lineno)d} %(message)s",
    handlers=[
        logging.FileHandler("debug.log", encoding='utf8'),
        logging.StreamHandler()
    ]
)

# To pipe to a file
sys.stdout.reconfigure(encoding='utf-8')

def handle_exception(exc_type, exc_value, exc_traceback):
    logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

#################################################################################################################

class MySession:
    a_session = None
    cookies = { "_gumroad_app_session" : _gumroad_app_session }
    http_adapter = HTTPAdapter(max_retries=5)
    
    def head(self, url):
        if not self.a_session:
            self.a_session = requests.Session()
            self.a_session.mount('https://', self.http_adapter)
            response = self.a_session.head(url, allow_redirects=True, cookies=self.cookies)
        else:
            response = self.a_session.head(url, allow_redirects=True)
        return response


    def get(self, url, stream=None, ok_404=False):

        if not self.a_session:
            self.a_session = requests.Session()
            self.a_session.mount('https://', self.http_adapter)
            response = self.a_session.get(url, stream=stream, cookies=self.cookies)
        else:
            response = self.a_session.get(url, stream=stream)

        if response.status_code != 200:
            if response.status_code == 404 and ok_404:
                logging.warn("URL %s returned 404, but it's ok", url)
            else:
                raise Exception(f"Failed to download the file. Status code: {response.status_code}")
        
        return response

#################################################################################################################

def download_LibraryPage_json(my_session):
    lib_url = 'https://app.gumroad.com/library'
    logging.info('Loading library from %s', lib_url)
    response = my_session.get(lib_url)

    #save html
    with open("library.html", 'wb') as myresult:
        myresult.write(str(response.content).encode('utf-8'))

    # Find the json data for all the downloads
    soup = BeautifulSoup(response.content, 'html.parser')
    results = soup.find_all('script', class_='js-react-on-rails-component', attrs={'data-component-name':'LibraryPage'})

    # Should be only 1
    if len(results) != 1:
        raise Exception('%s results' % len(results))

    result = results[0]

    result_txt = result.text
    with open(pathlib.Path(OUTPUT_DIR, "library.json"), 'wb') as myresult:
        myresult.write(result_txt.encode('utf-8'))
    
    return result_txt


def parse_library_json(json_text):
    myJson = json.loads(json_text)

    gumroad_results = []

    for athing in myJson['results']:
        gri = GumroadItem()
        gri.name = athing['product']['name']
        creator = athing['product']['creator']
        if creator:
            gri.creator_name = creator['name']
        else:
            logging.warn('Creator name is missing with id %s for product "%s"', athing['product']['creator_id'], gri.name)
            gri.creator_name = '[id %s]' % athing['product']['creator_id']

        logging.info('Found product "%s" by %s', gri.name, gri.creator_name)
        gri.thumbnail = athing['product']['thumbnail_url']
        gri.images = []

        if 'covers' in athing['product']:
            for cover in athing['product']['covers']:
                cover_url = cover['url']
                gri.images.append(cover_url)
        else:
            logging.warn('No covers found for product "%s"', gri.name)

        gri.download_url = athing['purchase']['download_url']
        gri.purchase_id = athing['purchase']['id']

        gumroad_results.append(gri)
    return gumroad_results

class GumroadItem():
    name = None
    thumbnail = None
    images = None
    download_url = None
    purchase_id = None
    creator_name = None

    def do_download(self, my_session):
        logging.info('Downloading files for creator "%s" product "%s"', self.creator_name, self.name)
        dir_name = sanitize_filename(self.name)
        creator_part = sanitize_filename(self.creator_name)
        pl_path = pathlib.Path(OUTPUT_DIR, creator_part, dir_name)
        pl_path.mkdir(exist_ok=True, parents=True)
        download_count = 0
        if self.thumbnail:
            if download_file(my_session, self.thumbnail, pl_path, 'thumbnail'):
                download_count += 1
        for image in self.images:
            if 'https://public-files.gumroad.com' in image:
                if download_file(my_session, image, pl_path):
                    download_count += 1
        
        product_json = download_product_page(my_session, self.download_url)
        with open(pl_path / "product.json", 'wb') as myresult:
            myresult.write(product_json.encode('utf-8'))

        downloads, product_url = parse_product_json(product_json)

        # Create shortcut link to product page
        with open(pl_path / ('product page.url'), 'w') as win_shortcut:
            win_shortcut.write('[InternetShortcut]\n')
            win_shortcut.write('URL=%s' % product_url)

        if download_file(my_session, product_url, pl_path, 'product page.html', backup_if_different=True, ok_404=True):
            download_count += 1
        
        for dl_url in downloads:
            if download_file(my_session, dl_url, pl_path, backup_if_different=True):
                download_count += 1

        logging.info('Downloaded %s files for creator "%s" product "%s"', download_count, self.creator_name, self.name)



#################################################################################################################

def download_product_page(my_session, url):
    logging.info('Loading product page %s',url)
    response = my_session.get(url)

    # Find the json data for all the downloads
    soup = BeautifulSoup(response.content, 'html.parser')
    results = soup.find_all('script', class_='js-react-on-rails-component', attrs={'data-component-name':'DownloadPageWithContent'})

    # Should be only 1
    if len(results) != 1:
        raise Exception('%s results' % len(results))

    result = results[0]

    result_txt = result.text

    return result_txt

def parse_product_json(json_text):
    myJson = json.loads(json_text)
    
    product_url = myJson['purchase']['product_long_url']
    
    download_urls = []
    for item in myJson['content']['content_items']:
        logging.info('Found item to download %s', item['file_name'])
        external_url = item['external_link_url']
        dl_url = item['download_url']
        if external_url:
            logging.warn('Has external link url %s', external_url)
        if dl_url:
            download_urls.append('https://app.gumroad.com' + dl_url)
        else:
            logging.warn('No download url, skipping')

    return download_urls, product_url

#################################################################################################################

def download_file(my_session, url, pl_path, file_base_name=None, backup_if_different=False, ok_404=False):
    
    logging.info('Requesting %s',url)

    # TODO the product.json contains the file_size of the main downloads, could use that instead (but still need HEAD for images)
    # TODO it's possible for one product to have 2 downloads with the same name

    head_response = my_session.head(url)
    content_type = head_response.headers.get('content-type')
    content_length = head_response.headers.get('content-length')
    logging.info('Head response Content type "%s" size %s url %s', content_type, content_length, head_response.url)
    file_extension = mimetypes.guess_extension(content_type)
    if not file_extension or file_extension == '.bin':
        file_extension = ''    

    if not file_base_name:
        parsed_url = urllib.parse.urlparse(head_response.url)
        file_base_name = pathlib.Path(parsed_url.path).name
        file_base_name = urllib.parse.unquote(file_base_name, encoding='utf-8', errors='replace')

    if file_base_name.endswith(file_extension):
        final_path = pl_path / file_base_name
    else:
        final_path = pl_path / (file_base_name +file_extension)
    
    logging.info('Will save as %s',final_path)

    if final_path.exists():
        if content_length:
            existing_size = final_path.stat().st_size
            if content_length == str(existing_size):
                logging.info('File "%s" already exists with the same size, skipping', final_path)
                return False
            else:
                logging.error('File "%s" already exists with a DIFFERENT size %s != %s', final_path, content_length, existing_size)
        logging.warn('File "%s" already exists but content-length is missing, will download again', final_path)
        
        if backup_if_different:
            now = datetime.now()
            now_str = now.strftime("%d-%m-%Y.%H.%M.%S")
            new_path = final_path.parent / (final_path.name + now_str)
            logging.warn('Renaming existing file "%s" to "%s"', final_path, new_path)
            os.rename(final_path, new_path)

    response = my_session.get(url, stream=True, ok_404=ok_404)
    response.raw.decode_content = True

    if url != response.url:
        logging.info('Downloading %s',response.url)

    with open(final_path, 'wb') as out_file:
        shutil.copyfileobj(response.raw, out_file)
    del response
    
    return True


#################################################################################################################


my_session = MySession()

library_json = download_LibraryPage_json(my_session)
gumroad_items =  parse_library_json(library_json)
logging.info('Found total %s products', len(gumroad_items))

count = 5 # for testing
for gr_item in gumroad_items:
    gr_item.do_download(my_session)
    count -= 1
    #if count < 1:
    #    break
