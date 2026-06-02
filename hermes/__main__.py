import argparse
import re


def _classify_conclusion(text: str) -> str:
    """Heuristic classification of a conclusion statement."""
    predictive = [
        r"将(会|在|导致|成为|取代|推动|引发|改变|显著|大幅)?",
        r"预计", r"预期", r"预测", r"未来\d*[年个月内]",
        r"趋势.*持续", r"持续.*增长", r"面临.*风险",
        r"\d+年.*将", r"在.*年.*将",
        r"走向", r"预示", r"可能(会|导致|造成|引发)?",
    ]
    evaluative = [
        r"(被)?(低估|高估|忽视|夸大|误解)",
        r"(是|不是).*(关键|核心|最重要|决定性|瓶颈)",
        r"(有效|无效|成功|失败|不足|不够|过度)",
        r"值得(关注|警惕|怀疑|商榷|反思)",
        r"需要.*(更|根本|彻底|完全|重新)",
        r"应(该)?.*(转向|放弃|采取|改变)",
        r"风险在于", r"问题在于",
    ]

    for pat in predictive:
        if re.search(pat, text):
            return "predictive"
    for pat in evaluative:
        if re.search(pat, text):
            return "evaluative"
    return "descriptive"


def backfill_conclusion_types(db) -> None:
    """Classify existing conclusions that lack a conclusion_type."""
    nulls = db._query(
        "SELECT id, statement FROM conclusions "
        "WHERE conclusion_type IS NULL AND status = 'active'"
    )
    if not nulls:
        print("All conclusions already have a type. Nothing to do.")
        return

    counts = {"predictive": 0, "evaluative": 0, "descriptive": 0}
    for row in nulls:
        ctype = _classify_conclusion(row["statement"])
        db.execute(
            "UPDATE conclusions SET conclusion_type = %s WHERE id = %s",
            (ctype, row["id"]),
        )
        counts[ctype] += 1

    db.conn.commit()
    print(f"Backfilled {len(nulls)} conclusions:")
    for ctype, n in sorted(counts.items()):
        print(f"  {ctype}: {n}")
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

    sub.add_parser("backfill", help="Backfill conclusion_type for existing conclusions")

    audit_parser = sub.add_parser("audit", help="Audit LLM analysis quality")
    audit_parser.add_argument("-n", type=int, default=5, help="Number of items to audit (default: 5)")

    pt_parser = sub.add_parser("test-prompts", help="Run prompt regression tests against fixtures")
    pt_parser.add_argument("-n", type=int, default=None, help="Number of fixtures to test (default: all)")
    pt_parser.add_argument("--threshold", type=int, default=4, help="Pass threshold 0-5 (default: 4)")
    pt_parser.add_argument("--synthesize", action="store_true", help="Test synthesize prompt instead of assess")

    args = parser.parse_args()

    if args.command == "run":
        from hermes.pipeline.run import run
        run(args.config, trigger_type="manual")
    elif args.command == "cron":
        from hermes.pipeline.run import run
        run(args.config, trigger_type="cron")
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
    elif args.command == "test-prompts":
        import os
        from openai import OpenAI
        from hermes.config import load_config

        config_path = args.config or os.path.expanduser("~/.hermes/config.yaml")
        config = load_config(config_path)
        client = OpenAI(api_key=config.llm_api_key, base_url=config.llm_base_url)

        if args.synthesize:
            from hermes.pipeline.test_prompts import run_synthesize_tests, format_synthesize_test_report
            report = run_synthesize_tests(client, limit=args.n, threshold=args.threshold)
            print(format_synthesize_test_report(report))
        else:
            from hermes.pipeline.test_prompts import run_prompt_tests, format_prompt_test_report
            report = run_prompt_tests(client, config.domains,
                                      limit=args.n, threshold=args.threshold)
            print(format_prompt_test_report(report))
    elif args.command == "backfill":
        import os
        import re
        from hermes.config import load_config
        from hermes.db import Database

        config_path = args.config or os.path.expanduser("~/.hermes/config.yaml")
        config = load_config(config_path)
        db = Database(config.db_url)
        backfill_conclusion_types(db)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
