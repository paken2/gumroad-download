import os
import glob
from urllib.request import pathname2url

from jinja2 import Template 

from gumroad_library import Library, LibraryProduct, GumroadProduct
from download_manager import PRODUCT_RAW_JSON, PRODUCT_PAGE_HTML, LIBRARY_HTML
from main import OUTPUT_DIR

def find_thumbnail_file(dir_path : str):
    thumbnail_files = glob.glob('thumbnail.*', root_dir=dir_path)
    if not thumbnail_files:
        return None
    if len(thumbnail_files) != 1:
        print('Unexpected %s thumbnail files in %s: %s' % (len(thumbnail_files), dir_path, thumbnail_files))
    return thumbnail_files[0]



def render_library_html(download_root : str):

    with open(os.path.join(download_root, LIBRARY_HTML), 'rb') as f:
        lib = Library(f.read()) # TODO

    products = lib.get_products()

    data = []

    for product in products:
        relative_product_path = product.get_creator_product_path()
        product_path = os.path.join(download_root, relative_product_path)

        with open(os.path.join(product_path, PRODUCT_RAW_JSON), 'r', encoding='UTF-8') as f:
            gumroad_product = GumroadProduct(json_raw_text=f.read()) # TODO

        thumbnail = find_thumbnail_file(product_path)
        if thumbnail:
            thumbnail_path = pathname2url(os.path.join(relative_product_path, thumbnail))
        else:
            thumbnail_path = '.'

        local_path_link = pathname2url(relative_product_path)

        dat = dict(
            thumbnail_path  = thumbnail_path,
            name            = product.get_product_name(),
            creator         = product.get_creator_name(),
            creator_page    = product.get_creator_profile_url(),
            local_path      = relative_product_path,
            local_path_link = local_path_link,
            product_page    = gumroad_product.get_store_page_url(),
            local_copy_link = os.path.join(relative_product_path, PRODUCT_PAGE_HTML),
            download_page   = product.get_page_download_url(),
            date_updated    = product.get_updated_at(),
            date_purchased  = gumroad_product.get_purchase_date()
        )
        data.append(dat)

    # Create one external form_template html page and read it 
    with open('local-library-template.html', 'r') as f:
        content = f.read() 
    
    # Render the template and pass the variables 
    template = Template(content) 
    rendered_form = template.render(data=data) 
    
    # save the txt file in the form.html 
    with open(os.path.join(download_root, "index.html"), 'w', encoding='UTF-8') as f:
        f.write(rendered_form) 

render_library_html(OUTPUT_DIR)
