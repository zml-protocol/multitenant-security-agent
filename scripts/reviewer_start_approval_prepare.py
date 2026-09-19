import argparse

from reviewer.start_approval import validate_prepared_package, write_package


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare or validate the closed formal reviewer start approval package."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the existing package without changing it",
    )
    args = parser.parse_args()
    if args.check:
        validate_prepared_package()
        print("The formal-start approval package is valid and execution remains unauthorized.")
    else:
        write_package()
        print("Prepared the closed formal-start approval package; execution remains unauthorized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
