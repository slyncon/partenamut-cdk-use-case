"""Compatibility wrapper around the installed platform validation command."""

import sys

from cdk_launchpad.cli import main

if __name__ == "__main__":
    sys.exit(main())
