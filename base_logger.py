import os
import sys
import logging
import traceback
from datetime import datetime

def crash_stack(e):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    logger.error('{} {}'.format(timestamp(), repr(traceback.format_tb(exc_traceback))))

def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class My_logger:

    def __init__(self):
        self.logger = logging.getLogger("")
        self.logger.setLevel(logging.INFO)

    def set_asset(self, asset):
        formatter = logging.Formatter("%(asctime)s [{}] %(message)s".format(asset), "%Y-%m-%d %H:%M:%S")
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        self.logger.addHandler(console_handler)
        
        stLogfile = logging.FileHandler(log_dir + '/' + asset + '.log')
        stLogfile.setFormatter(formatter)
        stLogfile.setLevel(logging.DEBUG)
        self.logger.addHandler(stLogfile)

work_dir = os.getcwd()

log_dir = os.path.join(work_dir, "logs")
if not os.path.isdir(log_dir):
    os.mkdir(log_dir)
my_logger = My_logger()
logger = my_logger.logger
