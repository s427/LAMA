import sqlite3

import src.log as log
import src.save as save
import src.utils as utils
import src.fetch as f

from . import __APP_NAME__
from . import __VERSION__
from . import PREFS


def open_con():
    db_path = f"{PREFS['user_dir']}/data/app.db"
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    return (con, cur)


def init_db():
    (con, cur) = open_con()

    tables = ['posts', 'activities', 'states']
    for table in tables:
        res = cur.execute(
            f"SELECT name FROM sqlite_master WHERE name='{table}'")
        if res.fetchone() is None:
            log.info(f"   Table '{table}' not found - initializing", True)

    cur.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_uri TEXT UNIQUE NOT NULL,
            post_id INTEGER NOT NULL,

            author TEXT,
            visibility TEXT,
            content TEXT,
            hashtags TEXT,
            mentions TEXT,
            links TEXT,
            attachments TEXT,
            poll_options TEXT,
            reblog TEXT,

            created_at TEXT,
            edited_at TEXT,
            fetched_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),

            json TEXT NOT NULL,
            note TEXT DEFAULT ""
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account TEXT NOT NULL,
            post_uri TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            activity_id INTEGER NOT NULL,
            archived_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),

            FOREIGN KEY (post_uri) REFERENCES posts(post_uri),
            UNIQUE(account, post_uri, activity_type, activity_id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account TEXT NOT NULL,
            name TEXT NOT NULL,
            value TEXT NOT NULL,

            UNIQUE(account, name)
        )
    ''')

    con.commit()

    save_app_state(__APP_NAME__, 'app_version', __VERSION__)
    con.close()


def save_status(account, data, activity_type):
    """Save one post to the database

    Note: if activity_type == mention or poll, the structure is different
    """

    if activity_type in {'mention', 'poll'}:
        status = data.status
    else:
        status = data

    post_uri = status.uri

    # avoid saving posts or activities twice
    save_post = True
    save_activity = True

    saved_activity = get_unique_activity(account, post_uri, activity_type)
    if saved_activity:
        log.info(f"🟰 Activity {activity_type} by {account['handle']} for {post_uri}is already present in database with the same 'edited_at value; skipping.'")
        save_activity = False

    saved_post = get_post_last_edited(post_uri)
    if saved_post:
        db_edited_at, = saved_post
        if db_edited_at == status.edited_at:
            log.info(f"🟰 Post {post_uri} ({activity_type}) already present in database with the same 'edited_at value; skipping.'")
            save_post = False
        else:
            log.warn(f"🆕 Post {post_uri} ({activity_type}) already present in database, with different 'edited_at' values (this post: {status.edited_at}; db post: {db_edited_at}); we proceed and update the data.")

    (con, cur) = open_con()

    if save_post:
        post_id =      status.id
        author =       utils.get_handle(status.account.url)
        visibility =   status.get('visibility', None)
        content =      utils.strip_html(status.get('content', ''))
        hashtags =     utils.extract_tags(status.get('tags', []))
        mentions =     utils.extract_mentions(status.get('mentions', []))
        links =        utils.extract_links(status.get('content', ''))
        attachments =  save.save_attachments(account, status)
        poll_options = utils.extract_poll_options(status.get('poll', []))
        js =           utils.to_json(status.__dict__)

        reblog_uri = None
        if status.reblog and status.reblog.uri:
            # this is a reblog
            reblog_uri = status.reblog.uri

            if PREFS['fetch_reblogs']:
                # we also save its embedded content as a distinct post
                save.save_fetched_status(account, status.reblog, 'reblog')
            else:
                # we do not want to save reblogs...
                if content or attachments or poll_options:
                    # ...but the post has some content of its own. Maybe a quote-post?
                    # therefore we still save the post itself
                    # (but not status.reblog as a distinct post)
                    pass
                else:
                    # it doesn't have a content of its own (pure reblog)
                    # therefore we save nothing (because PREFS)
                    return

        post_data = {
            'post_uri':     post_uri,
            'post_id':      post_id,
            'author':       author,
            'visibility':   visibility,
            'content':      content,
            'hashtags':     utils.to_json(hashtags)     if hashtags     else None,
            'mentions':     utils.to_json(mentions)     if mentions     else None,
            'links':        utils.to_json(links)        if links        else None,
            'attachments':  utils.to_json(attachments)  if attachments  else None,
            'poll_options': utils.to_json(poll_options) if poll_options else None,
            'reblog':       reblog_uri,
            'created_at':   status['created_at'],
            'edited_at':    status['edited_at'],
            'json':         js
        }

        cur.execute("""
            INSERT OR REPLACE INTO posts (
                post_uri, post_id, author, visibility,
                content, hashtags, mentions, links, attachments, poll_options,
                reblog, created_at, edited_at, json
            ) VALUES (
                :post_uri, :post_id, :author, :visibility,
                :content, :hashtags, :mentions, :links, :attachments, :poll_options,
                :reblog, :created_at, :edited_at, :json
            )
        """, post_data)
        con.commit()

    if save_activity:
        activity_id = data.id if activity_type in {'mention', 'poll'} else status.id

        log.debug(f"Saving activity {activity_id}: {activity_type} by {account['handle']} for {post_uri}")

        activity_data = {
            'account': account['handle'],
            'post_uri': post_uri,
            'activity_type': activity_type,
            'activity_id': activity_id,
        }
        cur.execute("""
            INSERT OR REPLACE INTO activities (
                account, post_uri, activity_type, activity_id
            ) VALUES (
                :account, :post_uri, :activity_type, :activity_id
            )
        """, activity_data)
        con.commit()

    con.close()

    # fetch related posts:
    #
    # - Mastodon links found in the post body will be fetched as a "X.link" activity
    # - parent of a post (in_reply_to)        will be fetched as a "X.parent" activity
    #
    # in both cases X is the name of the base activity
    # (e.g. bookmark.link == a post that was linked in a bookmark)
    #
    # We also allow each type (parent or link) to trigger the same type of activity
    # recursively (e.g. a parent of a parent of a parent..., OR a link in a link in a link)
    # because it makes sense to get the full context; however we do not mix the two,
    # ie. we do NOT fetche a link found in a parent, or a parent of a link.

    if save_post:

        if activity_type.count('.') >= PREFS['recursion_limit']:
            log.warn(f"⛔ STOP. We don't want to go any deeper than that (PREFS['recursion_limit'] is {PREFS['recursion_limit']}).", True)
            log.warn(f"  {activity_type}")
            return

        is_reply = status.in_reply_to_id
        if is_reply and PREFS['fetch_reply_parents']:
            if '.link' in activity_type:
                # don't fetch the parent of a quoted post
                pass
            else:
                # "bookmark"          becomes "bookmark.parent"
                # "bookmark.parent"   becomes "bookmark.parent#2"
                # "bookmark.parent#2" becomes "bookmark.parent#3" etc
                if activity_type.endswith('.parent'):
                    new_activity = f'{activity_type}#2'
                elif '.parent#' in activity_type:
                    act, count = activity_type.split('.parent#')
                    new_activity = f'{act}.parent#{int(count) + 1}'
                else:
                    new_activity = f'{activity_type}.parent'

                f.fetch_post_from_id(account, is_reply, new_activity)

        if links and PREFS['fetch_linked_posts']:
            if '.parent' in activity_type:
                # don't fetch a post quoted in a parent
                pass
            else:
                # same logic as above: X.link, X.link#2, X.link#3...
                if activity_type.endswith('.link'):
                    new_activity = f'{activity_type}#2'
                elif '.link#' in activity_type:
                    act, count = activity_type.split('.link#')
                    new_activity = f'{act}.link#{int(count) + 1}'
                else:
                    new_activity = f'{activity_type}.link'
                for link in links:
                    if (link['mastodon']):
                        f.fetch_post_by_url(account, link['url'], new_activity)


def get_last_fetched_id(account, activity_type='post'):
    """Get the ID of the most recent {activity_type} for a specific account"""

    (con, cur) = open_con()
    cur.execute("""
        SELECT activity_id
        FROM activities
        WHERE account = ?
            AND activity_type = ?
        ORDER BY archived_at DESC
        LIMIT 1
    """, (account['handle'], activity_type))
    result = cur.fetchone()
    con.close()

    return result[0] if result and result[0] else None


def get_post_last_edited(uri):
    """Get the edited_at date for a post, if it exists in the database

    Used to determine whether a post that is fetched a second time (e.g from
    a different account or related to a different activity type) should be saved again
    (and his attachmens downloaded again), or not.
    """

    (con, cur) = open_con()
    cur.execute("""
        SELECT edited_at FROM posts WHERE post_uri = ?
    """, (uri,))
    result = cur.fetchone()
    con.close()

    return result if result else False


def get_unique_activity(account, post_uri, activity_type):
    """Get the id of a specific activity (account + post URI + activity type)

    Used to determines whether an activity has already been saved to the database.
    """

    (con, cur) = open_con()
    cur.execute("""
        SELECT id FROM activities WHERE
        account = ? AND
        post_uri = ? AND
        activity_type = ?
    """, (account['handle'], post_uri, activity_type))
    result = cur.fetchone()
    con.close()

    return result if result else False


def save_app_state(handle, name, value):
    """Save app-related states

    E.g. pagination data for the favourites of a specific account, allowing
    to fetch only the newest favourites the next time the app is run.
    """

    data = {
        'account': handle,
        'name': name,
        'value': value,
    }

    (con, cur) = open_con()
    cur.execute("""
        INSERT INTO states (
            account, name, value
        ) VALUES (
            :account, :name, :value
        )
        ON CONFLICT(account, name) DO UPDATE SET
            value = excluded.value;
    """, data)
    con.commit()
    con.close()


def get_app_state(handle, name):
    """Get app-related states (e.g pagination data for favourites)"""

    (con, cur) = open_con()
    cur.execute(f"""
        SELECT value FROM states WHERE
        account = ? AND
        name = ?
    """, (handle, name))
    result = cur.fetchone()
    con.close()

    return result[0] if result and result[0] else None

