import argparse
import json

from reviewer.start_approval import approve_manual_launch, validate_prepared_package, write_package


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare or validate the closed formal reviewer start approval package."
    )
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument(
        "--check",
        action="store_true",
        help="validate the existing package without changing it",
    )
    operation.add_argument(
        "--approve-manual-launch",
        action="store_true",
        help="bind the prepared handoff for Security Engineer manual launch",
    )
    parser.add_argument("--approver", help="Security Engineer identifier for manual-launch approval")
    args = parser.parse_args()
    if args.approve_manual_launch:
        if not args.approver:
            parser.error("--approve-manual-launch requires --approver")
        print(json.dumps(approve_manual_launch(args.approver), indent=2))
    elif args.check:
        validate_prepared_package()
        print("The formal-start approval package is valid.")
    else:
        write_package()
        print("Prepared the closed formal-start approval package; execution remains unauthorized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
