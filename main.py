import sys
import src.fetch as f
import src.init as init
import src.log as log

from src import __APP_NAME__
from src import __VERSION__
from src import ACCOUNTS

def init_app():
    nb = len(ACCOUNTS)
    print(f"Initialiazing app with {nb} account{'s' if nb > 1 else ''}.")
    init.main()
    quit()


def main():
    args = sys.argv[1:]
    if args and args[0] == 'init':
        print(f"\n⚙️ running {__APP_NAME__} v.{__VERSION__}, init mode\n")
        init_app()
        return

    print("")
    nb = len(ACCOUNTS)
    log.info(f"Starting {__APP_NAME__} v.{__VERSION__} ---- {nb} account{'(s)' if nb > 1 else ''} configured", True)

    for account in ACCOUNTS:
        print("")
        log.info(f"ACCOUNT: {account['text']}\n", True)

        if not f.validate_username(account):
            log.err("❌ Mismatch between configured username and authenticated username. Skipping this account.", True)
            continue

        f.fetch_all(account)

    print("")
    log.info("✅ End of script \\o/\n", True)


if __name__ == "__main__":
    log.purge_logs()
    main()

