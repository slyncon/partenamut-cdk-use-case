"""Validate synthesized application stacks; fail on violations or missing output."""

import argparse
import sys
from pathlib import Path

from cdk_launchpad.security import validate_assembly


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directories", nargs="+", type=Path, help="CDK cloud assembly directories")
    args = parser.parse_args()
    try:
        count = sum(validate_assembly(directory) for directory in args.directories)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"Security validation failed: {error}", file=sys.stderr)
        return 1
    print(f"Security validation passed: {count} application stack templates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
