import argparse

def main():
    parser = argparse.ArgumentParser(prog="hermes")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="Run the full intelligence pipeline")
    sub.add_parser("status", help="Show last run summary")
    args = parser.parse_args()

    if args.command == "run":
        from hermes.pipeline.run import run
        run()
    elif args.command == "status":
        from hermes.pipeline.run import status
        status()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
