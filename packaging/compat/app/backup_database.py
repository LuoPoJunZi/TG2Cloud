"""Installed consistent database backup command compatibility."""
from tg2cloud.persistence.backup import main

if __name__ == "__main__":
    raise SystemExit(main())
