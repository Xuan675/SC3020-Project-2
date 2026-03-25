def walk_plan(node):
    nodes = [node]
    for child in node.get("Plans", []):
        nodes.extend(walk_plan(child))
    return nodes


def get_root_plan(plan):
    return plan[0]["Plan"]


def get_top_total_cost(plan):
    return get_root_plan(plan).get("Total Cost")


def get_join_condition(node):
    return (
        node.get("Hash Cond")
        or node.get("Merge Cond")
        or node.get("Join Filter")
        or "join condition"
    )


def get_scan_nodes(plan):
    root = get_root_plan(plan)
    nodes = walk_plan(root)
    return [
        node for node in nodes
        if node.get("Node Type") in {"Seq Scan", "Index Scan", "Index Only Scan", "Bitmap Heap Scan"}
    ]


def get_join_nodes(plan):
    root = get_root_plan(plan)
    nodes = walk_plan(root)
    return [
        node for node in nodes
        if node.get("Node Type") in {"Hash Join", "Merge Join", "Nested Loop"}
    ]


def get_join_alternatives(aqps, join_index, selected_method):
    alternatives = []
    for aqp in aqps:
        if "error" in aqp:
            continue

        alt_join_nodes = get_join_nodes(aqp["plan"])
        if join_index >= len(alt_join_nodes):
            continue

        alt_method = alt_join_nodes[join_index].get("Node Type")
        alt_cost = get_top_total_cost(aqp["plan"])
        if alt_method and alt_method != selected_method:
            alternatives.append(
                f"with {aqp['disabled_option']} off, PostgreSQL used {alt_method} with estimated plan cost {alt_cost}"
            )
    return alternatives


def generate_annotations(_query, qep, aqps):
    annotations = []

    for scan in get_scan_nodes(qep):
        table_name = scan.get("Relation Name", "unknown table")
        method = scan.get("Node Type")
        annotations.append(f"{table_name} is accessed using {method}.")

    join_nodes = get_join_nodes(qep)
    for join_index, join_node in enumerate(join_nodes):
        join_method = join_node.get("Node Type")
        join_condition = get_join_condition(join_node)
        annotations.append(
            f"The condition {join_condition} is executed using {join_method}."
        )

        alternatives = get_join_alternatives(aqps, join_index, join_method)

        if alternatives:
            annotations.append(
                f"{join_method} was chosen because representative alternatives were more expensive or less preferred: "
                + "; ".join(alternatives) + "."
            )

    return annotations


def format_annotated_query(query, annotations):
    lines = [query.strip(), ""]
    for annotation in annotations:
        lines.append(f"-- {annotation}")
    return "\n".join(lines)
