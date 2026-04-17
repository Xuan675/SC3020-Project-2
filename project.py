import argparse
import sys
from pathlib import Path

from preprocessing import connect_db, get_qep, get_representative_aqps
from annotation import generate_annotations, format_annotated_query


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate query-plan annotations for a SQL query."
    )
    parser.add_argument(
        "-q",
        "--query",
        help="SQL query text.",
    )
    parser.add_argument(
        "-f",
        "--query-file",
        help="Path to a file containing a SQL query.",
    )
    return parser.parse_args()


def _read_query_from_prompt():
    print("Enter SQL query (end with an empty line):")
    lines = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line)
    return "\n".join(lines).strip()


def resolve_query(args):
    if args.query and args.query_file:
        raise ValueError("Use either --query or --query-file, not both.")

    if args.query:
        return args.query.strip()

    if args.query_file:
        query_path = Path(args.query_file)
        return query_path.read_text(encoding="utf-8").strip()

    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

    return _read_query_from_prompt()


def main():
    args = parse_args()
    query = resolve_query(args)
    if not query:
        raise ValueError("No SQL query provided.")

    conn = connect_db()
    try:
        qep = get_qep(conn, query)
        aqps = get_representative_aqps(conn, query)

        annotations = generate_annotations(query, qep, aqps)
        annotated_query = format_annotated_query(query, annotations)

        print(annotated_query)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
