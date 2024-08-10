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

# This file manages all the downloading.
# It will pass json to the classes in gumroad_library.py

r'''
TODO Nice to have: show download progress bar (see Gumload)
TODO Nice to have: add parallel download (see Gumload)
TODO? sort download order by creator
TODO create .url file for any external links found
TODO Download files to temp location before replacing existing in case of download error
TODO Catch Ctrl+Z and exit cleanly
TODO Generate a simple html file with a list of authors and products with the downloaded thumbnail (much like library page)
TODO Could try to check if any files were removed from gumroad but have been safely saved locally
TODO Firefox knows what extension to use, e.g. lowercase .unitypackage, but where does it get that full filename?
TODO track product download sizes and meta-data download sizes separately
'''

import logging
import shutil
import os
import mimetypes

import requests
from unidecode import unidecode

from gumroad_library import *

# TODO what browser is this for?
DEFAULT_USER_AGENT = r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.0"
LIBRARY_URL = 'https://app.gumroad.com/library'
GIT_IGNORE_FILE = "for-output_dir.gitignore"


PRODUCT_RAW_JSON = "product-raw.json"
PRODUCT_JSON = "product.json"
PRODUCT_PAGE_HTML = "product-page.html"
PRODUCT_PAGE_URL = "product-page.url"
LIBRARY_HTML = "library.html"
LIBRARY_JSON = "library.json"
LIBRARY_RAW_JSON = "library-raw.json"


def create_dir_with_log(dir_path) -> None:
    exists = os.path.exists(dir_path)
    if (exists):
        logging.debug('Directory already exists "%s"', dir_path)
    else:
        logging.debug('Creating directory "%s"', dir_path)
        os.makedirs(dir_path, exist_ok=True)

def write_file_with_log(file_path, mode : str, contents, encoding=None) -> None:
    exists = os.path.exists(file_path)
    logging.debug('Writing file "%s" exists=%s', file_path, exists)
    with open(file_path, mode, encoding=encoding) as out_file:
        out_file.write(contents)

# ---------------------------------------------------------------------------------

class DownloadSession(requests.Session):
    bytes_read : int = 0
    bytes_skipped : int = 0
    files_downloaded : int = 0
    files_skipped : int = 0

    def __init__(self, app_session: str, guid: str, user_agent: str = DEFAULT_USER_AGENT) -> None:
        super().__init__()
        self.cookies.set("_gumroad_app_session", app_session)
        self.cookies.set("_gumroad_guid", guid)
        self.headers["User-Agent"] = user_agent

    def __do_get(self, session : requests.Session, url : str, is404_ok : bool = False) -> requests.Response:
        logging.debug('Downloading %s', url)
        response = session.get(url, stream=True, allow_redirects=True)
        if is404_ok and response.status_code == 404:
            pass # 404 is ok
        else:
            response.raise_for_status()
        return response
    
    def get_size_and_content_type(self, url : str) -> tuple:
        logging.debug('Getting HEAD from %s', url)
        head_response = self.head(url, allow_redirects=True)
        content_type = head_response.headers.get('content-type')
        content_length = head_response.headers.get('content-length')

        download_size = None
        try:
            download_size = int(content_length)
        except:
            pass

        return download_size, content_type
    
    def get_content_no_session(self, url : str, is404_ok : bool = False) -> bytes:
        no_session = requests.Session()
        content = self.__do_get(no_session, url, is404_ok=is404_ok).content
        self.bytes_read += len(content)
        self.files_downloaded += 1
        return content

    def get_content(self, url : str, is404_ok : bool = False) -> bytes:
        content = self.__do_get(self, url, is404_ok=is404_ok).content
        self.bytes_read += len(content)
        self.files_downloaded += 1
        return content
    
    def stream_download(self, url : str, output_file_path : str):
        total_bytes_written = 0
        with open(output_file_path, 'wb') as out_file:
            for data in self.__do_get(self, url).iter_content(chunk_size=None):
                bytes_written = out_file.write(data)
                self.bytes_read += bytes_written
                total_bytes_written += bytes_written
        self.files_downloaded += 1
        return total_bytes_written

    def download_if_not_exists(self, url : str, 
                               output_path : str,
                               file_name : str, 
                               extension : str | None, 
                               size : int | None = None, 
                               is_cover : bool = False) -> bool:
        """
        Most complicated part of downloading.
        If an extension is provided, it will use it.
        Otherwise it will figure out the extension based on the mimetype of the download.
        is_cover is to handle the very strange download behavior of the thumbnail and cover image.
        Returns if the file was actually downloaded.

        TODO somehow check if the downloaded file, when smaller, isn't smaller because the download failed in a prior run.
        """

        # Note: This content length is of the compressed data if it is compressed,
        # which won't match the size of the file on the disk
        download_size, content_type = self.get_size_and_content_type(url)
        if size:
            if size != download_size:
                logging.debug('content-length=%s expected size=%s', download_size, size)
            download_size = size

        if extension:
            extension = '.' + extension
        elif content_type:
            extension = mimetypes.guess_extension(content_type)

        if extension:
            file_name = f'{file_name}{extension}'

        output_file_path = os.path.join(output_path, file_name)

        if not os.path.exists(output_file_path):
            logging.debug('File "%s" does not exist', output_file_path)
        else:
            existing_size = os.path.getsize(output_file_path)
            logging.debug('File "%s" exists with size %s', output_file_path, format(existing_size, ','))
            if download_size:
                if existing_size == 0:
                    logging.info('File is empty, downloading')
                elif existing_size == download_size:
                    logging.info('File "%s" exists with matching size %s, assuming unchanged, skipping download', output_file_path, download_size)
                    self.bytes_skipped += download_size
                    self.files_skipped += 1
                    return False
                else:
                    # File size has changed, pray it does not change further...
                    logging.warn('Size of file "%s" has changed from %s to %s', output_file_path, existing_size, download_size)

                    # This could happen if the size came from the content-length and the data is compressed.
                    # Also the value cannot always be trusted, but so far Gumroad seems reliable.
                    # TODO? It may be worthwhile to download to a temp location and compare the file sizes after that.
                    # Could optimize by checking if the response is compressed.
                    if not is_cover:
                        error_file = 'error-'+file_name
                        bytes_written = self.stream_download(url, error_file)
                        raise Exception(
                            f'Size of file "{output_file_path}" is {existing_size}, content-length says {download_size}, actual bytes downloaded {bytes_written} to {error_file}')
                    
                    if download_size >= existing_size:
                        logging.warn('The existing file is smaller, so keeping it')
                        self.bytes_skipped += download_size
                        self.files_skipped += 1
                        return False
                    logging.warn('New file is smaller, so downloading it')
            else:
                # Download size unknown, so don't know if it has changed.

                # Biggest design weakness here:
                # The design assumes that only files tracked by git can change and be overwritten.
                # This will be a file that isn't tracked by git, so all file history will be lost by this download.
                # TODO Do something about this
                # Possibly download the file to a temp location and compare.
                # If different then blow up. The user needs to decide what to do.
                logging.critical('Unknown download size of url %s, overwriting existing file "%s" with size %s', url, output_file_path, format(existing_size, ','))

        logging.info('Saving download to "%s" with size %s', output_file_path, format(download_size, ','))

        retry = is_cover
        while True:
            try:
                bytes_written = self.stream_download(url, output_file_path)
                break
            except requests.exceptions.ChunkedEncodingError:
                if retry:
                    logging.warn("Error during download, but it's a thumbnail/cover, so will try once more")
                    retry = False
                else:
                    raise

        logging.debug('Downloaded %d bytes to file "%s"', bytes_written, output_file_path)

        if download_size and bytes_written != download_size:
            # This will be a file that isn't tracked by git, so all file history will be lost by this download.
            logging.critical('Size of file "%s" has changed from %s to %s', output_file_path, existing_size, bytes_written)

        return True



# ---------------------------------------------------------------------------------


class LibraryDownloader:
    def __init__(self, session : DownloadSession, output_root_dir : str) -> None:
        self.session = session
        self.output_root_dir = output_root_dir

        create_dir_with_log(self.output_root_dir)

        '''
        TODO Find replace these to make .html more same
            "csp_nonce":"[^"]+"
            "ProductPage-react-component-[^"]+"
            ^<meta name="csrf-token" .+/>$
        Still other things can change (rating, purchases, other wacky things)
        '''

        library_page_html = self.session.get_content(LIBRARY_URL)
        write_file_with_log(os.path.join(self.output_root_dir, LIBRARY_HTML), 'wb', library_page_html)

        self.library = Library(library_page_html)
        write_file_with_log(os.path.join(self.output_root_dir, LIBRARY_RAW_JSON), 'w', self.library.get_raw_json_text(), encoding='UTF-8')
        write_file_with_log(os.path.join(self.output_root_dir, LIBRARY_JSON), 'w', self.library.get_formatted_json(), encoding='UTF-8')

    def get_products(self) -> list[LibraryProduct]:
        return self.library.get_products()


class LibraryProductDownloader:
    def __init__(self, session : DownloadSession, output_root_dir : str, library_product : LibraryProduct) -> None:
        self.session = session
        self.output_root_dir = output_root_dir
        self.library_product = library_product
        
        self.product_dir_path = os.path.join(self.output_root_dir, self.library_product.get_creator_product_path())

        logging.debug('Initializing product "%s" by "%s"', 
                     self.library_product.get_product_name(), self.library_product.get_creator_name())
        
        self.download()

    def download(self):
        create_dir_with_log(self.product_dir_path)

        self.__download_thumbnail()
        self.__download_covers()

    def __download_thumbnail(self) -> None:
        thumbnail_url = self.library_product.get_thumbnail_url()
        if thumbnail_url:
            # Thumbnails have the same problem with cover files, they'll randomly change size
            self.session.download_if_not_exists(thumbnail_url, self.product_dir_path, 'thumbnail', None, is_cover=True)
    
    def __download_covers(self) -> None:
        '''
        Move cover images to subfolder?
            keep thumbnail in root
            except if they have no thumbnail...
            move a cover image into root?
            starts getting weird
            May doesn't matter since covers seem to be removed
        '''
        covers = self.library_product.get_covers()
        if covers is None:
            logging.warn('No covers block for product "%s"', self.library_product.get_product_name())
            return
        logging.info('Found %s covers for product "%s"', len(covers), self.library_product.get_product_name())
        download_count = 0
        for cover in covers:
            if cover.is_external():
                logging.info('Skipping external cover url %s', cover.get_url())
            else:
                # Cover images will randomly change size for no reason, but the image has no visual difference.
                # It is almost always smaller. So... download the smaller one?
                # And in some cases, it will change size in the middle of download?!?
                fn, ext = cover.get_file_name_and_extension()
                downloaded = self.session.download_if_not_exists(cover.get_url(), self.product_dir_path, fn, ext, is_cover=True)
                if downloaded:
                    download_count += 1
        logging.info('Downloaded %s covers for product "%s"', download_count, self.library_product.get_product_name())


class GumroadProductDownloader:
    def __init__(self, session : DownloadSession, product_dir : str, product_page_url : str) -> None:
        self.session = session
        self.product_dir = product_dir
        self.product_page_url = product_page_url
        self.gumroad_product : GumroadProduct = None

        product_download_page_html = self.session.get_content(self.product_page_url)
        self.gumroad_product = GumroadProduct(product_download_page_contents=product_download_page_html)

        self.__save_product_json()
        self.__write_store_page_url()
        self.__download_store_page()

    def __save_product_json(self) -> None:
        json_raw_path = os.path.join(self.product_dir, PRODUCT_RAW_JSON)
        json_path = os.path.join(self.product_dir, PRODUCT_JSON)
        write_file_with_log(json_raw_path, 'w', self.gumroad_product.get_raw_json_text(), encoding='UTF-8')
        write_file_with_log(json_path, 'w', self.gumroad_product.get_formatted_json(), encoding='UTF-8')

    def __write_store_page_url(self) -> None:
        store_page_url = self.gumroad_product.get_store_page_url()
        url_file_contents = f'[InternetShortcut]\nURL={store_page_url}'
        write_file_with_log(os.path.join(self.product_dir, PRODUCT_PAGE_URL), 'w', url_file_contents)
    
    def __download_store_page(self) -> None:
        store_page_url = self.gumroad_product.get_store_page_url()
        store_page_html_path = os.path.join(self.product_dir, PRODUCT_PAGE_HTML)
        logging.debug('Downloading product store page %s to %s', store_page_url, store_page_html_path)
        store_page_html = self.session.get_content_no_session(store_page_url, is404_ok=True)
        write_file_with_log(store_page_html_path, 'wb', store_page_html)

    def get_content_items(self) -> list[ContentItem]:
        return self.gumroad_product.get_content_items()

# ----------------------------------------------------------------------------

def copy_git_ignore(directory : str) -> None:
    git_ignore_path = os.path.join(directory, ".gitignore")
    # Always overwrite?
    # Yes if the default .gitignore is ever changed
    # No if the existing .gitignore was customized
    # So...?
    logging.info("Copying %s to %s", GIT_IGNORE_FILE, git_ignore_path)
    shutil.copyfile(GIT_IGNORE_FILE, git_ignore_path)

def compare_product_names(name_from_library : str, name_from_product : str) -> None:
    # These should be identical
    if name_from_library != name_from_product:
        logging.warn('Product name on Library page "%s" is different from the product name on the product page "%s"',
                    name_from_library, name_from_product)

class DownloadManager:
    # Will be created when the downloading begins
    session : DownloadSession = None

    def __init__(self, _gumroad_app_session : str, _gumroad_guid : str, output_root_dir : str) -> None:
        self._gumroad_app_session = _gumroad_app_session
        self._gumroad_guid = _gumroad_guid
        self.output_root_dir = output_root_dir
    
    def get_bytes_downloaded(self) -> int:
        return self.session.bytes_read
    
    def get_bytes_skipped(self) -> int:
        return self.session.bytes_skipped
    
    def get_files_downloaded(self) -> int:
        return self.session.files_downloaded

    def get_files_skipped(self) -> int:
        return self.session.files_skipped

    def download(self) -> None:
        self.session = DownloadSession(self._gumroad_app_session, self._gumroad_guid)

        create_dir_with_log(self.output_root_dir)
        copy_git_ignore(self.output_root_dir)

        library_downloader = LibraryDownloader(self.session, self.output_root_dir)
        library_products = library_downloader.get_products()

        product_count = len(library_products)
        logging.info('Found %s products', product_count)

        for lib_prod_idx, library_product in enumerate(library_products): #[:3]):  # for testing
            logging.info('[%s/%s] Downloading "%s" by "%s"', 
                         lib_prod_idx+1, product_count, 
                         library_product.get_product_name(), 
                         library_product.get_creator_name())

            lib_prod_downloader = LibraryProductDownloader(self.session, self.output_root_dir, library_product)
            product_dir_path = lib_prod_downloader.product_dir_path

            gum_prod_downloader = GumroadProductDownloader(self.session, product_dir_path, library_product.get_page_download_url())

            compare_product_names(library_product.get_product_name(), gum_prod_downloader.gumroad_product.get_product_name())

            content_items = gum_prod_downloader.get_content_items()

            content_item_count = len(content_items)
            logging.info('Downloading %s files for product "%s" by "%s"', 
                         content_item_count, 
                         library_product.get_product_name(), 
                         library_product.get_creator_name())

            for cnt_itm_idx, content_item in enumerate(content_items):
                download_url = content_item.get_full_download_url()
                external_url = content_item.get_external_link_url()
                file_name = content_item.get_file_name()

                if download_url:
                    if external_url:
                        logging.warn('File "%s" also has an external URL you should check %s', file_name, external_url)
                        
                    if 'gumroad.com' not in download_url:
                        logging.warn('File "%s" appears to have an external url you will need to check %s', file_name, download_url)
                        continue
                else:
                    if external_url:
                        logging.warn('File "%s" has an external url you will need to download manually %s', file_name, external_url)
                    else:
                        logging.warn('File "%s" has no download url, skipping', file_name)
                    continue

                # Save the actual files under a directory of the ID of the file.
                # This avoids having 2+ files with the same name, or a file
                # that was replaced with the same name.
                content_item_dir = os.path.join(product_dir_path, content_item.get_id())
                create_dir_with_log(content_item_dir)

                logging.info('[%s/%s] (%s/%s) Downloading file "%s" for "%s" by "%s"', 
                             lib_prod_idx+1, product_count, 
                             cnt_itm_idx+1, content_item_count, 
                             content_item.get_sanitized_filename(),
                             library_product.get_product_name(), 
                             library_product.get_creator_name())

                fn, ext = content_item.get_file_name_and_extension()
                self.session.download_if_not_exists(download_url, content_item_dir, 
                                                    fn, ext, size=content_item.get_file_size())

