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

# This file provides a nice interface to the json found in the Gumroad pages.

import json
import logging
import re
import os

from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename
import unicodedata

DOWNLOAD_URL_PREFIX = 'https://app.gumroad.com'


class ProductCover:
    """
    This is an image or other content that you see on the product's store page.
    It's referred to as a 'cover' in the json.

    What I've observed from my library
    id            - Probably UUID
    url           - link to file hosted on gumroad, or youtube link
                    if image, I think this is the optimized one
    original_url  - link to file hosted on gumroad, or youtube link
                    if image, I think this is the original uploaded one
    thumbnail     - null for images hosted by gumroad. Set to youtube thumbnail for youtube urls
    type          - "image", "video", "oembed", others?
    filetype      - null for youtube links. "png", "gif", "mp4", "jpg", others?
    width, height - Media dimensions, even for mp4 and youtube videos
    native_width, native_height
    """
    def __init__(self, cover_item_data : dict) -> None:
        self.cover_item_data = cover_item_data
    
    def get_id(self) -> str:
        return self.cover_item_data['id']
    
    def get_url(self) -> str:
        return self.cover_item_data['original_url']
    
    def is_external(self) -> bool:
        # Could also check if the thumbnail is gumroad url and use that instead
        if self.cover_item_data['type'] == 'oembed':
            pass # probably external

        url = self.get_url()
        if url and 'gumroad.com' in url:
            return False
        
        return True

    def get_file_name_and_extension(self) -> tuple:
        file_name = self.get_id() # Hopefully this is very constant
        extension = self.cover_item_data['filetype']
        return (file_name, extension)


class LibraryProduct:
    """
    This is the description of the product as found on the Library page.
    Most importantly it as the link to the product download page.
    This is different than the description of the product on the product's download page
    and doesn't contain the links to the files.
    """
    def __init__(self, library_result : dict) -> None:
        self.library_result = library_result
        
    def get_product_name(self) -> str:
        return self.library_result['product']['name']

    def get_sanitized_product_name(self) -> str:
        return heavily_sanitize_filename(self.get_product_name())
    
    def get_creator_product_path(self) -> str:
        return os.path.join(self.get_creator_dir_name(), self.get_sanitized_product_name())

    def get_thumbnail_url(self) -> str | None:
        return self.library_result['product']['thumbnail_url']

    def get_updated_at(self) -> str | None:
        return self.library_result['product']['updated_at']

    def get_page_download_url(self) -> str:
        return self.library_result['purchase']['download_url']
    
    def get_creator_profile_url(self) -> str:
        creator = self.library_result['product']['creator']
        profile_url = None
        if creator:
            profile_url = creator['profile_url']
        return profile_url

    def get_creator_name(self) -> str:
        creator = self.library_result['product']['creator']
        if creator:
            creator_name = creator['name']
        else:
            creator_id = self.library_result['product']['creator_id']
            logging.warn('The creator with ID %s for product "%s" has no name ', creator_id, self.get_product_name())
            creator_name = f'[id {creator_id}]'
        return creator_name

    def get_creator_dir_name(self) -> str:
        """
        The creator name can have any length and use any kind of wacky unicode characters.
        Instead of using that string, we'll use the creator's sub-domain name.
        But fall back to creator's string name if that fails.
        """
        creator = self.library_result['product']['creator']
        creator_dir_name = None

        if creator:
            profile_page_url = creator['profile_url']
            url_match = re.search(r'://([^\.]+).', profile_page_url)
            if url_match:
                creator_dir_name = url_match.group(1)
            else:
                # I haven't ever seen this happen, so if it does, there can easily be more problems in later steps
                logging.warn("Was unable to find the creator sub-domain in URL %s", profile_page_url)

        if not creator_dir_name:
            creator_dir_name = self.get_creator_name()

        return heavily_sanitize_filename(creator_dir_name)
    
    def get_covers(self) -> list[ProductCover]:
        product = self.library_result['product']
        # I haven't seen one without any covers, but maybe possible?
        if 'covers' not in product:
            return None
        covers = []
        for cover_data in product['covers']:
            product_cover = ProductCover(cover_data)
            covers.append(product_cover)
        return covers


class Library:
    # TODO Add constructor just for the json
    def __init__(self, library_page_contents : bytes) -> None:
        self.library_page_contents = library_page_contents

        be_soup = BeautifulSoup(self.library_page_contents, "lxml")

        json_elements = be_soup.find_all('script', 
                                        class_='js-react-on-rails-component', 
                                        attrs={'data-component-name':'LibraryPage'})
        # Should be only 1
        if len(json_elements) != 1:
            raise Exception('Found %s json blocks, expected 1' % len(json_elements))

        self.json_text = json_elements[0].text
        self.library_data = json.loads(self.json_text)
    
    def get_raw_json_text(self) -> str:
        return self.json_text

    def get_formatted_json(self) -> str:
        json_string = json.dumps(self.library_data, indent=2, ensure_ascii=False)
        return json_string

    def get_products(self) -> list[LibraryProduct]:
        products = []
        for result in self.library_data['results']:
            products.append(LibraryProduct(result))
        return products
        

class ContentItem:
    """ 
    This is information about an individual file to download. 
    In the json it is referred to as a 'content_item'
    """
    def __init__(self, content_item_data : dict) -> None:
        self.content_item_data = content_item_data
        external_link = self.get_external_link_url()
        if external_link:
            logging.warn('Download "%s" has an external link %s', self.get_file_name(), external_link)
        if not self.is_file():
            logging.critical('Download "%s" is not a file: %s', self.get_file_name(), self.content_item_data['type'])

    def get_id(self) -> str:
        return self.content_item_data['id']
    
    def is_file(self) -> bool:
        # I haven't seen any other value
        return self.content_item_data['type'] == 'file'

    def get_external_link_url(self) -> str | None:
        return self.content_item_data['external_link_url']
    
    def is_external(self) -> bool:
        url = self.content_item_data['download_url']
        if url and 'gumroad.com' in url:
            return False
        
        return True

    def get_full_download_url(self) -> str | None:
        dl_url = self.content_item_data['download_url']
        if dl_url:
            return DOWNLOAD_URL_PREFIX + dl_url
        else:
            return None
    
    def get_file_size(self) -> int:
        return self.content_item_data['file_size']
    
    def get_file_name(self) -> str:
        return self.content_item_data['file_name']
    
    def get_sanitized_filename(self) -> str:
        return sanitize_filename(self.get_file_name())

    def get_file_name_and_extension(self) -> tuple:
        # In theory, if the creator uploaded the file with its filename
        # we shouldn't need to sanitize at all.
        # But just in case, do a minimal amount of sanitization
        file_name = self.get_sanitized_filename()
        extension = self.content_item_data['extension']
        return (file_name, extension)


def heavily_sanitize_filename(file_name) -> str:
    s = unicodedata.normalize('NFKC', file_name) # replace stylized unicode char with normal
    s = re.sub(r'[^\x00-\x7F]+',' ', s) # limit to ascii
    s = sanitize_filename(s) # remove invalid filename chars
    s = re.sub(r'\s+', ' ', s) # remove redundant spaces
    s = s.strip() # trim ends
    return s

class GumroadProduct:
    """ This holds the json that is found on the product's download page. """

    # TODO This is a weird way to overload
    def __init__(self, 
                 product_download_page_contents : bytes = None,
                 json_raw_text : str = None) -> None:
        if product_download_page_contents:
            if json_raw_text:
                raise Exception('Only 1 parameter must be non-null')
            be_soup = BeautifulSoup(product_download_page_contents, "lxml")
            json_elements = be_soup.find_all('script', class_='js-react-on-rails-component', attrs={'data-component-name':'DownloadPageWithContent'})
            # Should be only 1
            if len(json_elements) != 1:
                raise Exception('%s results' % len(json_elements))
            self.json_raw_text = json_elements[0].text
        elif json_raw_text:
            self.json_raw_text = json_raw_text # TODO if created with the raw json, don't need to save it again later
        else:
            raise Exception('Both args are null')

        self.product_data = json.loads(self.json_raw_text)

    def get_content_items(self) -> list[ContentItem]:
        content_items = []

        for content_item_data in self.product_data['content']['content_items']:
            ci = ContentItem(content_item_data)
            if ci.is_file():
                content_items.append(ci)
            else:
                logging.info('Skipping non-file content')

        return content_items
    
    def get_raw_json_text(self) -> str:
        return self.json_raw_text

    def get_formatted_json(self) -> str:
        json_string = json.dumps(self.product_data, indent=2, ensure_ascii=False)
        return json_string

    def get_product_name(self) -> str:
        return self.product_data['purchase']['product_name']

    def get_store_page_url(self) -> str:
        return self.product_data['purchase']['product_long_url']

    def get_purchase_date(self) -> str:
        return self.product_data['purchase']['created_at']

