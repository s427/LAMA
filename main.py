import sys
import src.fetch as f
import src.init as init
import src.log as log


def main():
    args = sys.argv[1:]
    if args and args[0] == 'init':
        init.main()
        quit()

    f.fetch_all()


if __name__ == "__main__":
    log.purge_logs()
    main()

