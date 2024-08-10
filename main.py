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

# This file contains the main entry function to the program.
# It sets up logging
# and contains the variables that the user should edit.

#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

## Edit these before running the script!

# Make sure this is right
OUTPUT_DIR = r"your desired output directory"

# Open browser dev tools and look for "_gumroad_app_session" cookie, paste value here
_gumroad_app_session = r"""get from browser cookies"""
# Open browser dev tools and look for "_gumroad_guid" cookie, paste value here
_gumroad_guid = r"""get from browser cookies"""

#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


r'''
TODO collect information the user should manually check and show at end
TODO cleanup dependencies, they were initially based on Gumload dependencies
TODO Print total time
'''

import logging
import logging.handlers
import os
import sys

from download_manager import DownloadManager


def setup_logging() -> None:
    filename = "debug.log"

    should_roll_over = os.path.isfile(filename)
    rotate_handler = logging.handlers.RotatingFileHandler(filename, encoding='utf8', delay=True, backupCount=20, mode='w')

    stream_handle = logging.StreamHandler()
    stream_handle.setLevel(logging.INFO)
    stream_handle.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] {%(filename)s:%(lineno)d} %(message)s",
        handlers=[
            rotate_handler,
            stream_handle
        ]
    )

    if should_roll_over:  # log already exists, roll over!
        rotate_handler.doRollover()

setup_logging()

def handle_exception(exc_type, exc_value, exc_traceback) -> None:
    logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
sys.excepthook = handle_exception

if __name__ == '__main__':
    dlm = DownloadManager(output_root_dir=OUTPUT_DIR, 
                          _gumroad_guid = _gumroad_guid,
                          _gumroad_app_session = _gumroad_app_session)
    dlm.download()

    logging.info('Total downloads: %s files, %s bytes', 
                 dlm.get_files_downloaded(),
                 format(dlm.get_bytes_downloaded(), ',')), 

    logging.info('Total skipped:  %s files, %s bytes', 
                 dlm.get_files_skipped(),
                 format(dlm.get_bytes_skipped(), ','))

