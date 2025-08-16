__APP_NAME__ = "LAMA"
__VERSION__ = "1.0.1"
__WEBSITE__ = "https://github.com/s427/LAMA"

import src.config

PREFS, ACCOUNTS = src.config.load()


# full "account" object structure:

# {
#   "username": "username",                     # used to build self.handle, self.safe, self.text
#   "instance": "https://domain.tld",           # same as username; also used for app registration

#   "handle": "username@domain.tld",            # used as account identifier in database (activities)
#   "safe": "username_domaintld",               # used in files or folders names
#   "text": "@username on https://domain.tld"   # used in printed messages or logs
# },

