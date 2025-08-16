import re
import json
import filetype
from bs4 import BeautifulSoup


def get_account_handle(account, safe=False):
    """Returns a full handle for an account as configured in prefs.json

    Output: username@domain.tld or username_domaintld (if safe)
    """

    username = account['username'].replace('@', '')
    instance = account['instance'].replace('https://', '').replace('http://', '')

    if safe:
        username = ''.join(e for e in username if e.isalnum())
        instance = ''.join(e for e in instance if e.isalnum())
        return f"{username}_{instance}"

    return f"{username}@{instance}"


def get_username(uri, safe=False):
    """Returns username (without @) from URI

    Input: https://domain.tld/users/username or https://domain.tld/@username
    Output: username
    If safe, all non alphanumeric characters are removed from output
    """

    username = uri.split('/')[-1].replace('@', '')
    if safe:
        username = ''.join(e for e in username if e.isalnum())
    return username


def get_instance(uri, safe=False):
    """Returns instance name ("domain.tld", without "https://") from URI

    Input: https://domain.tld/users/username or https://domain.tld/@username
    Output: domain.tld
    If safe, all non alphanumeric characters are removed from output
    """

    instance = uri.replace('https://', '').replace('http://', '').split('/')[0]
    if safe:
        instance = ''.join(e for e in instance if e.isalnum())
    return instance


def get_handle(uri, safe=False):
    """Returns full author handle (username@domain.tld) from URI

    Input: https://domain.tld/users/username (uri) or https://domain.tld/@username (url)
    Output: username@domain.tld, or username_domaintld (if safe)

    Note: for accounts on bsky.brid.gy (Bluesky Bridge, https://fed.brid.gy/),
    'url' is better suited than 'uri'. Example:

    "url": "https://bsky.brid.gy/r/https://bsky.app/profile/username",
    "uri": "https://bsky.brid.gy/ap/did:plc:twpze4qqf6gtxz43ct52wlnl",
    """

    # special treatment for posts imported from Bluesky Bridge
    if 'brid.gy' in uri and uri.count('https://') > 1:
        bsky_parts = uri.split('https://')
        # ["bsky.brid.gy/r/", "bsky.app/profile/username"]
        if len(bsky_parts) > 1 and 'profile' in bsky_parts[1]:
            uri = f"https://{bsky_parts[1].replace('/profile/', '/users/')}"

    username = get_username(uri, safe)
    instance = get_instance(uri, safe)
    handle = f"{username}_{instance}" if safe else f"{username}@{instance}"
    return handle


def post_is_mine(account, status_author_uri):
    """Checks if the author of a post is the same as the logged-in account"""
    return True if account['handle'] == get_handle(status_author_uri) else False


def is_link_mastodon_post(url):
    """Detect if a URL is a link to a Mastodon post.

    Common patterns:
    - https://instance.com/@username/1234567890
    - https://instance.com/users/username/statuses/1234567890
    - https://instance.com/web/statuses/1234567890
    """
    mastodon_post_patterns = [
        r'https?://[^/]+/@[^/]+/\d+',
        r'https?://[^/]+/users/[^/]+/statuses/\d+',
        r'https?://[^/]+/web/statuses/\d+',
    ]

    for pattern in mastodon_post_patterns:
        if re.match(pattern, url):
            return True

    return False


def strip_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    return soup.get_text()


def extract_links(html):
    """Extract links from HTML content."""

    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    links = []

    for link in soup.find_all('a', href=True):
        url = link['href']

        # skip hashtags or mentions (class="mention" or class="u-url mention")
        if 'mention' in link.get('class', []):
            continue
        if 'hashtag' in link.get('class', []):
            continue
        # if link.get_text(strip=True).startswith('@'):
        #     continue
        # if link.get_text(strip=True).startswith('#'):
        #     continue

        text = link.get_text(strip=True)
        if text == url:
            text = ''

        mastodon = 1 if is_link_mastodon_post(url) else 0

        links.append({
            'url': url,
            'text': text,
            'mastodon': mastodon
        })

    return links


def extract_tags(tags):
    return [tag['name'] for tag in tags]


def extract_mentions(mentions):
    # mention['acct'] does not always contain the full handle
    # in particular for user sharing the same instance as "me"
    # so we cannot use it; instead we extract the full handle
    # from the url
    return [get_handle(mention['url']) for mention in mentions]


def extract_poll_options(poll):
    if poll and poll['options']:
        return [option['title'] for option in poll['options']]
    else:
        return []


def guess_file_extension(path):
    kind = filetype.guess(path)
    if kind is None:
        return 'undefined'
    return kind.extension


def to_json(data, ind=False):
    if ind:
        return json.dumps(data, default=str, ensure_ascii=False, indent=4)
    else:
        return json.dumps(data, default=str, ensure_ascii=False)

