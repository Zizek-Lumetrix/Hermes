import argparse


def main():
    parser = argparse.ArgumentParser(prog="hermes")
    parser.add_argument("-c", "--config", help="Path to config file", default=None)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("run", help="Run the full intelligence pipeline")
    sub.add_parser("cron", help="Run pipeline silently (for cron/scheduled execution)")
    sub.add_parser("status", help="Show last run summary")

    web_parser = sub.add_parser("web", help="Start the web server")
    web_parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    web_parser.add_argument("--port", type=int, default=8000, help="Bind port")

    sub.add_parser("health", help="Send weekly health check email")

    audit_parser = sub.add_parser("audit", help="Audit LLM analysis quality")
    audit_parser.add_argument("-n", type=int, default=5, help="Number of items to audit (default: 5)")

    args = parser.parse_args()

    if args.command == "run":
        from hermes.pipeline.run import run
        run(args.config)
    elif args.command == "cron":
        from hermes.pipeline.run import run
        run(args.config)
    elif args.command == "status":
        from hermes.pipeline.run import status
        status()
    elif args.command == "web":
        import uvicorn
        uvicorn.run("hermes.web.app:app", host=args.host, port=args.port, reload=False)
    elif args.command == "health":
        import os
        from hermes.config import load_config
        from hermes.db import Database
        from hermes.health import send_health_check

        config_path = args.config or os.path.expanduser("~/.hermes/config.yaml")
        config = load_config(config_path)
        db = Database(config.db_url)
        conclusions = db.get_all_conclusions()
        send_health_check(
            config,
            ingest_count=len(db.get_items_by_status("incorporated")),
            new_conclusions=len(conclusions),
            errors=[],
        )
        print("Health check email sent.")
    elif args.command == "audit":
        import os
        from hermes.config import load_config
        from hermes.db import Database
        from hermes.audit import run_audit

        config_path = args.config or os.path.expanduser("~/.hermes/config.yaml")
        config = load_config(config_path)
        db = Database(config.db_url)
        run_audit(db, n=args.n)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
