from datetime import datetime
from mastodon import Mastodon, MastodonError

import src.db as db
import src.log as log
import src.save as save
import src.utils as utils

from . import __APP_NAME__
from . import __VERSION__
from . import ACCOUNTS
from . import PREFS


def connect_api(account):
    return Mastodon(access_token = f"{PREFS['user_dir']}/creds/{account['safe']}_usercred.secret", request_timeout = 10)


def validate_username(account):
    api = connect_api(account)
    user_data = api.account_verify_credentials()
    authenticated_username = user_data.username

    if authenticated_username != account['username']:
        msg = f"⚠️ WARNING for account {account['text']}: the username declared in 'prefs.json' ({account['username']}) does not match the authenticated username ({authenticated_username}). This will lead to inaccurate information saved in the database (activities attributed to the wrong account). You should either:\n\nFix your 'prefs.json' file by filling {authenticated_username} instead of {account['username']},\n\nOr restart the whole app initialization process, by deleting the 'creds/{account['safe']}*.secret' files and running app_init.py again. Make sure your are logged in with the correct account on {account['instance']} when authorizing the app.\n\nYou can revoke the app authorization on your {authenticated_username} account on the web by visiting 'Preferences > Account > Authorized apps' and clicking 'revoke' for {__APP_NAME__}."
        log.err(msg, True)
        return False

    return True


def api_limit(account):
    """Displays information about API rate limit"""

    api = connect_api(account)
    reset = datetime.fromtimestamp(api.ratelimit_reset)
    lastcall = datetime.fromtimestamp(api.ratelimit_lastcall)

    log.debug(f"rate limit: {api.ratelimit_limit} - remaining: {api.ratelimit_remaining} - fetching: {PREFS['fetch_limit']}")
    log.debug(f"  reset {reset}")
    log.debug(f"  last call {lastcall}")


def fetch_post_from_id(account, post_id, activity_type):
    log.info(f"fetch_post_from_id ({activity_type}): {post_id} - account {account['text']}")
    api = connect_api(account)

    try:
        status = api.status(post_id)

    except MastodonError as e:
        log.err(f"  ERROR: {e}", True)
        return

    log.debug(status)
    save.save_fetched_status(account, status, activity_type)


def fetch_post_by_url(account, post_url, activity_type):
    log.info(f"fetch_post_by_url ({activity_type}): {post_url} - account {account['text']}")
    api = connect_api(account)

    try:
        result = api.search_v2(q = post_url, result_type = 'statuses')

    except MastodonError as e:
        log.err(f"  ERROR: {e}", True)
        return

    if result.statuses:
        save.save_fetched_status(account, result.statuses[0], activity_type)


def fetch_posts(account, activity_type='posts'):
    """Fetch various types of posts (activity_type) and saves them individually"""
    log.info(f"fetch_posts ({activity_type}) - account {account['text']}", True)
    api = connect_api(account)

    if activity_type == 'mention':
        try:
            start_from = db.get_last_fetched_id(account, activity_type)
            start_from = 0 if start_from is None else start_from
            log.info(f"  start_from: {start_from}")
            statuses = api.notifications(limit=PREFS['fetch_limit'], types=['mention'], min_id=start_from)
        except MastodonError as e:
            log.err(f"fetch_posts ({activity_type}) - ERROR: {e}", True)
            return

    elif activity_type == 'poll':
        try:
            start_from = db.get_last_fetched_id(account, activity_type)
            start_from = 0 if start_from is None else start_from
            log.info(f"  start_from: {start_from}")
            statuses = api.notifications(limit=PREFS['fetch_limit'], types=['poll'], min_id=start_from)
        except MastodonError as e:
            log.err(f"fetch_posts ({activity_type}) - ERROR: {e}", True)
            return

    elif activity_type == 'bookmark':
        try:
            start_from = db.get_app_state(account['handle'], 'bookmarks_pagination_prev')
            start_from = 0 if start_from is None else start_from
            log.info(f"  start_from: {start_from}")
            statuses = api.bookmarks(limit=PREFS['fetch_limit'], min_id=start_from)
        except MastodonError as e:
            log.err(f"fetch_posts ({activity_type}) - ERROR: {e}", True)
            return

    elif activity_type == 'favourite':
        try:
            start_from = db.get_app_state(account['handle'], 'favourites_pagination_prev')
            start_from = 0 if start_from is None else start_from
            log.info(f"  start_from: {start_from}")
            statuses = api.favourites(limit=PREFS['fetch_limit'], min_id=start_from)
        except MastodonError as e:
            log.err(f"fetch_posts ({activity_type}) - ERROR: {e}", True)
            return

    else:
        activity_type = 'post'
        try:
            start_from = db.get_last_fetched_id(account)
            start_from = 0 if start_from is None else start_from
            log.info(f"  start_from: {start_from}")
            statuses = api.account_statuses(api.me(), limit=PREFS['fetch_limit'], min_id=start_from)
        except MastodonError as e:
            log.err(f"fetch_posts ({activity_type}) - ERROR: {e}", True)
            return

    count = 0
    notifications_no_content = 0
    for i in __import__('itertools').count():
        log.info(f"LOOP {i}")
        api_limit(account)

        if not statuses:
            break

        parse_statuses = reversed(statuses) if activity_type in {'post', 'mention', 'poll'} else statuses

        for status in parse_statuses:
            if activity_type in {'mention', 'poll'} and not status.status:
                notification_author = utils.get_handle(status.account.url) if status.account and status.account.url else '[unknown author]'
                log.warn(f"  Post {status.id} ({activity_type}) by {notification_author} has no content (expired from instance cache?); skipping.")
                log.debug(f"  Full JSON: {utils.to_json(status.__dict__)}")
                notifications_no_content += 1
                continue

            save.save_fetched_status(account, status, activity_type)
            count += 1

        log.debug(f"=> api.fetch_previous ({i})")
        statuses = api.fetch_previous(statuses)

    if activity_type == 'bookmark':
        pagination_prev = api.bookmarks()._pagination_prev["min_id"]
            # see https://github.com/halcy/Mastodon.py/issues/417
        log.info(f'  pagination_prev: {pagination_prev}')
        db.save_app_state(account['handle'], 'bookmarks_pagination_prev', pagination_prev)

    if activity_type == 'favourite':
        pagination_prev = api.favourites()._pagination_prev["min_id"]
            # see https://github.com/halcy/Mastodon.py/issues/417
        log.info(f'  pagination_prev: {pagination_prev}')
        db.save_app_state(account['handle'], 'favourites_pagination_prev', pagination_prev)

    msg_notifications = f"\n  {notifications_no_content} notifications{'s were' if notifications_no_content > 1 else ' was'} (mentions or polls) skipped (no content)." if notifications_no_content else ''

    log.info(f"Done. {count} {activity_type}{'s' if count > 1 else ''} fetched.{msg_notifications}\n", True)


def fetch_all():
    print("")
    nb = len(ACCOUNTS)
    log.info(f"Starting {__APP_NAME__} v.{__VERSION__} ---- {nb} account{'(s)' if nb > 1 else ''} configured", True)

    for account in ACCOUNTS:
        print("")
        log.info(f"ACCOUNT: {account['text']}\n", True)

        if not validate_username(account):
            log.err("❌ Mismatch between configured username and authenticated username. Skipping this account.", True)
            continue

        fetch_posts(account)

        if PREFS['fetch_favourites']:
            fetch_posts(account, 'favourite')
        if PREFS['fetch_bookmarks']:
            fetch_posts(account, 'bookmark')
        if PREFS['fetch_mentions']:
            fetch_posts(account, 'mention')
        if PREFS['fetch_polls']:
            fetch_posts(account, 'poll')

    print("")
    log.info("✅ End of script \\o/\n", True)

