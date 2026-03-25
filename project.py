from preprocessing import connect_db, get_qep, get_representative_aqps
from annotation import generate_annotations, format_annotated_query


def main():
    query = """
SELECT *
FROM customer c, orders o
WHERE c.c_custkey = o.o_custkey
""".strip()

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