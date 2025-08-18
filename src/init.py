import os
from mastodon import Mastodon

import src.db as db

from . import __APP_NAME__
from . import __VERSION__
from . import __WEBSITE__
from . import ACCOUNTS
from . import PREFS


APP_SCOPES = ['read']


def check_folders():
    dirs = ['creds', 'data', 'logs']
    ud = f"{PREFS['user_dir']}"
    for dir in dirs:
        d = f"{ud}/{dir}"
        if not os.path.exists(d):
            os.makedirs(d)
            print(f"Folder '{d}' created")


def register_app(account):
    print("\nRegistering the app")
    client_cred = f"{PREFS['user_dir']}/creds/{account['safe']}_clientcred.secret"

    if os.path.isfile(client_cred):
        print(f"   File '{client_cred}' already present on disk. Skipping this step.")
    else:
        Mastodon.create_app(
            __APP_NAME__,
            website=__WEBSITE__,
            scopes=APP_SCOPES,
            api_base_url=account['instance'],
            to_file=f"{client_cred}"
        )
        print(f"   OK - File '{client_cred}' successfully created.")


def authorize_app(account):
    print("\nAuthorizing the app")
    user_cred = f"{PREFS['user_dir']}/creds/{account['safe']}_usercred.secret"

    if os.path.isfile(user_cred):
        print(f"   File '{user_cred}' already present on disk. Skipping this step.")
    else:
        print("   Open the following URL in your brower, then copy the code you get.")
        print(f"   ⚠️ Make sure your are logged in with the correct account ({account['text']}).")
        mastodon = Mastodon(client_id=f"{PREFS['user_dir']}/creds/{account['safe']}_clientcred.secret",)
        print("\n   " + mastodon.auth_request_url(scopes=APP_SCOPES) + "\n")
        mastodon.log_in(
            scopes=APP_SCOPES,
            code=input("Enter the OAuth authorization code: "),
            to_file=f"{user_cred}"
        )
        print(f"   OK - File '{user_cred}' successfully created.")


def main():
    nb = len(ACCOUNTS)
    print(f"\n⚙️ running {__APP_NAME__} v.{__VERSION__}, init mode\n")
    print(f"Initialiazing app with {nb} account{'s' if nb > 1 else ''}.")

    check_folders()
    db.init_db()

    for account in ACCOUNTS:
        print(f"\nAccount: {account['text']}")
        register_app(account)
        authorize_app(account)

    print("\nAnd we're done! :)\n")


if __name__ == "__main__":
    main()

