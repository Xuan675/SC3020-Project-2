import re

SCAN_NODE_TYPES = {"Seq Scan", "Index Scan", "Index Only Scan", "Bitmap Heap Scan"}
JOIN_NODE_TYPES = {"Hash Join", "Merge Join", "Nested Loop"}

def walk_plan_with_path(node, path=()):
    nodes = [(node, path)]
    for child_index, child in enumerate(node.get("Plans", [])):
        nodes.extend(walk_plan_with_path(child, path + (child_index,)))
    return nodes

def get_root_plan(plan):
    return plan[0]["Plan"]

def get_top_total_cost(plan):
    return get_root_plan(plan).get("Total Cost")

def _get_join_condition(node):
    return node.get("Hash Cond") or node.get("Merge Cond") or node.get("Join Filter")

def _get_scan_condition(node):
    return (
        node.get("Index Cond")
        or node.get("Recheck Cond")
        or node.get("Filter")
        or node.get("TID Cond")
    )

def _get_relation_name(node):
    return node.get("Relation Name") or node.get("Alias") or "unknown table"

def _collect_relations(node):
    relations = set()
    for current, _ in walk_plan_with_path(node):
        if current.get("Node Type") in SCAN_NODE_TYPES:
            relations.add(_get_relation_name(current))
    return tuple(sorted(relations))

def _to_operator_record(node, path):
    node_type = node.get("Node Type")
    if node_type in JOIN_NODE_TYPES:
        kind = "join"
        predicate = _get_join_condition(node) or "join condition"
        subject = predicate
    elif node_type in SCAN_NODE_TYPES:
        kind = "scan"
        predicate = _get_scan_condition(node) or "no explicit predicate"
        subject = _get_relation_name(node)
    else:
        return None

    return {
        "kind": kind,
        "node_type": node_type,
        "path": path,
        "subject": subject,
        "relation": _get_relation_name(node),
        "predicate": predicate,
        "relations_in_subtree": _collect_relations(node),
        "startup_cost": node.get("Startup Cost"),
        "total_cost": node.get("Total Cost"),
        "plan_rows": node.get("Plan Rows"),
    }

def _extract_operator_records(plan):
    root = get_root_plan(plan)
    records = []
    for node, path in walk_plan_with_path(root):
        record = _to_operator_record(node, path)
        if record is not None:
            records.append(record)
    return records

def _similarity_score(selected, candidate):
    score = 0
    if selected["kind"] == candidate["kind"]:
        score += 5
    if selected["relation"] == candidate["relation"]:
        score += 4
    if selected["predicate"] == candidate["predicate"]:
        score += 4
    if selected["path"] == candidate["path"]:
        score += 2
    overlap = set(selected["relations_in_subtree"]) & set(candidate["relations_in_subtree"])
    score += len(overlap)
    return score

def _find_best_match(selected_operator, alternative_operators):
    candidates = [op for op in alternative_operators if op["kind"] == selected_operator["kind"]]
    if not candidates:
        return None

    best_candidate = None
    best_score = -1
    for candidate in candidates:
        score = _similarity_score(selected_operator, candidate)
        if score > best_score:
            best_candidate = candidate
            best_score = score

    if best_score <= 5:
        return None
    return best_candidate

def _build_explanations(qep, aqps):
    qep_operators = _extract_operator_records(qep)
    qep_total_cost = get_top_total_cost(qep)
    alternative_operator_map = {
        aqp["disabled_option"]: _extract_operator_records(aqp["plan"])
        for aqp in aqps
        if "plan" in aqp
    }

    explanations = []
    for selected in qep_operators:
        alternatives = []
        unavailable = []

        for aqp in aqps:
            disabled_option = aqp["disabled_option"]
            if "error" in aqp:
                unavailable.append(f"{disabled_option} ({aqp['error']})")
                continue

            matched = _find_best_match(selected, alternative_operator_map[disabled_option])
            if matched is None:
                alternatives.append(
                    {
                        "disabled_option": disabled_option,
                        "status": "no_match",
                    }
                )
                continue

            method_changed = matched["node_type"] != selected["node_type"]
            cost_delta = None
            cost_ratio = None
            if selected["total_cost"] is not None and matched["total_cost"] is not None:
                cost_delta = matched["total_cost"] - selected["total_cost"]
                if selected["total_cost"] > 0:
                    cost_ratio = matched["total_cost"] / selected["total_cost"]

            alternatives.append(
                {
                    "disabled_option": disabled_option,
                    "status": "matched",
                    "method": matched["node_type"],
                    "method_changed": method_changed,
                    "startup_cost": matched["startup_cost"],
                    "total_cost": matched["total_cost"],
                    "plan_rows": matched["plan_rows"],
                    "cost_delta": cost_delta,
                    "cost_ratio": cost_ratio,
                }
            )

        explanations.append(
            {
                "selected": selected,
                "alternatives": alternatives,
                "unavailable": unavailable,
                "qep_total_cost": qep_total_cost,
            }
        )
    return explanations

def _format_ratio_text(alternative):
    if alternative["cost_ratio"] is None:
        return f"{alternative['method']}"
    return f"{alternative['method']} (~{alternative['cost_ratio']:.2f}x operator cost)"

def _extract_query_components(query):
    normalized = " ".join(query.strip().rstrip(";").split())
    from_match = re.search(
        r"\bFROM\b\s+(.*?)(?=\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|$)",
        normalized,
        flags=re.IGNORECASE,
    )
    where_match = re.search(
        r"\bWHERE\b\s+(.*?)(?=\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|$)",
        normalized,
        flags=re.IGNORECASE,
    )
    
    join_matches = re.findall(
        r"\b(?:(INNER|LEFT|RIGHT|FULL|CROSS)\s+)?JOIN\s+\w+(?:\s+\w+)?\s+ON\s+(.*?)(?=\b(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\b|\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|$)",
        normalized,
        flags=re.IGNORECASE,
    )
    components = []

    if from_match:
        for table_text in from_match.group(1).split(","):
            parts = table_text.strip().split()
            if not parts or "join" in [part.lower() for part in parts]:
                continue

            relation = parts[0]
            alias = relation
            if len(parts) >= 3 and parts[1].lower() == "as":
                alias = parts[2]
            elif len(parts) >= 2:
                alias = parts[1]

            components.append({
                "type": "table",
                "fragment": table_text.strip(),
                "relation": relation,
                "alias": alias,
            })

    for join_keyword, on_condition in join_matches:
        components.append({
            "type": "join",
            "fragment": on_condition.strip(),
            "join_keyword": (join_keyword or "INNER").upper(),   # NEW
        })

    if where_match:
        predicates = re.split(r"\bAND\b", where_match.group(1), flags=re.IGNORECASE)
        for predicate in predicates:
            predicate = predicate.strip()
            if not predicate:
                continue

            component_type = "join" if re.match(r"^\w+\.\w+\s*=\s*\w+\.\w+$", predicate) else "filter"
            components.append({
                "type": component_type,
                "fragment": predicate,
            })

    return components

def _normalize_condition(condition):
    if not condition:
        return ""
    return " ".join(condition.lower().replace("(", " ").replace(")", " ").split())

def _same_equality(left_condition, right_condition):
    left_parts = [part.strip() for part in _normalize_condition(left_condition).split("=")]
    right_parts = [part.strip() for part in _normalize_condition(right_condition).split("=")]
    if len(left_parts) != 2 or len(right_parts) != 2:
        return False
    return set(left_parts) == set(right_parts)

def _strip_aliases(condition):
    return " ".join(part.split(".")[-1] for part in _normalize_condition(condition).split())

def _find_scan(component, explanations):
    names = {component.get("relation", "").lower(), component.get("alias", "").lower()}
    for explanation in explanations:
        selected = explanation["selected"]
        if selected["kind"] == "scan" and selected["relation"].lower() in names:
            return explanation
    return None

def _find_join(component, explanations):
    for explanation in explanations:
        selected = explanation["selected"]
        if selected["kind"] == "join" and _same_equality(component["fragment"], selected["subject"]):
            return explanation
    return None

def _find_filter(component, explanations):
    target = _strip_aliases(component["fragment"])
    for explanation in explanations:
        selected = explanation["selected"]
        if selected["kind"] != "scan" or selected["predicate"] == "no explicit predicate":
            continue
        predicate = _strip_aliases(selected["predicate"])
        if target == predicate or target in predicate:
            return explanation
    return None

def _changed_alternatives(explanation):
    return [
        alt for alt in explanation["alternatives"]
        if alt["status"] == "matched" and alt["method_changed"]
    ]

def generate_annotations(query, qep, aqps):
    annotations = []
    explanations = _build_explanations(qep, aqps)
    components = _extract_query_components(query)

    if not components:
        annotations.append("No simple SQL components were extracted; showing plan-level annotations instead.")
        components = []

    for component in components:
        if component["type"] == "table":
            explanation = _find_scan(component, explanations)
            if explanation is None:
                annotations.append(f"[FROM {component['fragment']}] No matching scan node was found.")
                continue

            selected = explanation["selected"]
            annotations.append(
                f"[FROM {component['fragment']}] Read using {selected['node_type']} "
                f"(total={selected['total_cost']}, rows={selected['plan_rows']})."
            )
            if selected["node_type"] == "Seq Scan" and selected["predicate"] == "no explicit predicate":
                annotations.append(
                    f"[FROM {component['fragment']}] Full-table read: no filter/index condition appears in this scan node."
                )

        elif component["type"] == "join":
            explanation = _find_join(component, explanations)
            if explanation is None:
                annotations.append(f"[ON {component['fragment']}] No matching join node was found.")
                continue

            selected = explanation["selected"]
            join_keyword = component.get("join_keyword", "INNER")   # NEW
            join_text = selected["node_type"]
            if join_keyword != "INNER":
                join_text = f"{selected['node_type']} for {join_keyword} JOIN semantics"   # NEW

            annotations.append(
                f"[ON {component['fragment']}] Executed using {join_text} "
                f"(total={selected['total_cost']}, rows={selected['plan_rows']})."
            )

            alternatives = _changed_alternatives(explanation)
            if alternatives:
                alternatives.sort(
                    key=lambda alt: alt["cost_ratio"] if alt["cost_ratio"] is not None else 0,
                    reverse=True,
                )
                annotations.append(
                    f"[ON {component['fragment']}] Representative AQP alternative: "
                    + ", ".join(_format_ratio_text(alt) for alt in alternatives[:2])
                    + "."
                )

        elif component["type"] == "filter":
            explanation = _find_filter(component, explanations)
            if explanation is None:
                annotations.append(f"[WHERE {component['fragment']}] No matching filter condition was found.")
                continue

            selected = explanation["selected"]
            annotations.append(
                f"[WHERE {component['fragment']}] Applied during {selected['node_type']} on {selected['relation']}."
            )

    return annotations

def format_annotated_query(query, annotations):
    lines = [query.strip(), ""]
    for annotation in annotations:
        lines.append(f"-- {annotation}")
    return "\n".join(lines)
