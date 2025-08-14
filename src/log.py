import logging
import os
import time

from . import __APP_NAME__
from . import PREFS

LOG_PREFIX = f'{__APP_NAME__}-run'

def purge_logs():
    limit = int(PREFS['log_history_limit']) - 1
    if limit < 0:
        return

    all_files = os.listdir(f"{PREFS['user_dir']}/logs")
    app_logs = [f"{PREFS['user_dir']}/logs/{file}" for file in all_files if file.startswith(LOG_PREFIX)]
    app_logs = [file for file in app_logs if os.path.isfile(file)]

    if len(app_logs) > limit:
        info("Purging old log files")
        delete_files = sorted([os.path.abspath(log) for log in app_logs], key=os.path.getctime)[0:(0-limit)]

        for delete_file in delete_files:
            try:
                os.remove(delete_file)
                info(f"  '{delete_file}' deleted")
            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                err(f"❌ Failed to delete expired log file ({delete_file})", True)
                err(f"  {error_msg}", True)


def log(txt, type='info', also_print=False):
    logger = logging.getLogger(__name__)

    lv = logging.WARNING
    match PREFS['log_level']:
        case 'debug':
            lv = logging.DEBUG
        case 'info':
            lv = logging.INFO
        case 'warning':
            lv = logging.WARNING
        case 'critical':
            lv = logging.CRITICAL

    timestr = time.strftime("%Y%m%d-%H%M%S")
    logging.basicConfig(
        filename=f"{PREFS['user_dir']}/logs/{LOG_PREFIX}-{timestr}.log",
        level=lv,
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        encoding='utf-8'
    )

    match type:
        case 'debug':
            logger.debug(txt)
        case 'info':
            logger.info(txt)
        case 'warning':
            logger.warning(txt)
        case 'error':
            logger.error(txt)

    if also_print:
        print(txt)


def debug(txt, also_print=False):
    log(txt, 'debug', also_print)

def info(txt, also_print=False):
    log(txt, 'info', also_print)

def warn(txt, also_print=False):
    log(txt, 'warning', also_print)

def err(txt, also_print=False):
    log(txt, 'error', also_print)

