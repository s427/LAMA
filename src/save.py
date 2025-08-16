import os
import urllib.request

import src.db as db
import src.log as log
import src.utils as utils

from . import PREFS


def save_fetched_status(account, data, activity_type):
    log.info(f"save_fetched_data {data['id']} ({activity_type}) for {account['text']}")
    log.debug(f"  {utils.to_json(data.__dict__)}")

    # a reblog is simply a subset of an already saved post (post['reblog']),
    # so we avoid saving it again
    if PREFS['save_json'] and activity_type != 'reblog':
        save_to_json(account, data, activity_type)

    db.save_status(account, data, activity_type)


def save_to_json (account, data, activity_type):
    """Save raw fetched data to JSON file"""

    id = data.id
    created_year = data.created_at.year
    created_month = data.created_at.strftime("%m")
    author = utils.get_handle(data.account.url, True)

    if '.parent' in activity_type:
        activity_type = 'parent'
    if '.link' in activity_type:
        activity_type = 'link'

    filename = f"{PREFS['user_dir']}/data/json/{account['safe']}/{activity_type}s/{created_year}/{created_month}/{author}_{id}.json"
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    js = utils.to_json(data.__dict__, True)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(js)


def save_attachments(account, status):

    if utils.post_is_mine(account, status.account.url):
        if not PREFS['download_own_attachments']:
            return []

    elif not PREFS['download_others_attachments']:
        return []

    r = []
    if status.get('media_attachments'):
        for idx, att in enumerate(status.get('media_attachments', [])):
            att_data = save_attachment(att, idx, status)
            r.append(att_data)
    return r


def save_attachment(att, idx, status):
    urls = []
    if att['url']:
        urls.append(att['url'])
    if att['remote_url']:
        urls.append(att['remote_url'])

    dl_ok = False

    errors = []

    for i, url in enumerate(urls):
        log.info(f"  save_attachment, attempt {i+1} - {url}")

        id = status.id
        instance = utils.get_instance(status.uri, True)
        author = utils.get_username(status.account.uri, True)
        created_year = status.created_at.year
        created_month = status.created_at.strftime("%m")

        # we will guess the file extension after the file has been downloaded,
        # as some URL schemes don't include it
        local_path = f"{PREFS['user_dir']}/data/media/{instance}/{author}/{created_year}/{created_month}/{author}_{id}_{idx:02d}"

        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        ok, txt = fetch_file(url, local_path)

        if ok:
            ext = utils.guess_file_extension(local_path)
            txt = f"{txt}.{ext}"
            dl_ok = True

            try:
                os.rename(local_path, txt)
            except FileExistsError as e:
                error_msg = f"{e.code}: {e.reason}"
                log.err(f"    ❌ Failed to rename '{local_path}' to '{txt}': {error_msg}", True)
            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                log.err(f"    ❌ Failed to rename '{local_path}' to '{txt}': {error_msg}", True)
            finally:
                # make the path relative to the database
                txt = txt.replace(f"{PREFS['user_dir']}/data/", '')
                break
        else:
            errors.append(txt)

    if not dl_ok:
        log.err(f"  ❌ Failed to download attachment (post: {status.uri})", True)
        txt = utils.to_json(errors)
        for err in errors:
            print(f"    {err})")

    desc = att['description'] if att['description'] else ""

    return [txt, desc]


def fetch_file(url, local_path):
        try:
            urllib.request.urlretrieve(url, local_path)
            log.info(f"    OK, saved as {local_path}")
            return (True, local_path)

        except urllib.error.HTTPError as e:
            error_msg = f"HTTP {e.code}: {e.reason}"
            log.err(f"    Failed to download {url}: {error_msg}")
            return (False, error_msg)

        except urllib.error.URLError as e:
            error_msg = f"URL Error: {e.reason}"
            log.err(f"    Failed to download {url}: {error_msg}")
            return (False, error_msg)

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            log.err(f"    Failed to download {url}: {error_msg}")
            return (False, error_msg)

