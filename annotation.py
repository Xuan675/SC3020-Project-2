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


def generate_annotations(_query, qep, aqps):
    annotations = []

    for explanation in _build_explanations(qep, aqps):
        selected = explanation["selected"]
        matched_alternatives = [
            alt for alt in explanation["alternatives"] if alt["status"] == "matched"
        ]
        changed_alternatives = [
            alt for alt in matched_alternatives if alt["method_changed"]
        ]

        if selected["kind"] == "scan":
            base = (
                f"{selected['subject']} is read using {selected['node_type']} "
                f"(startup={selected['startup_cost']}, total={selected['total_cost']}, rows={selected['plan_rows']})."
            )
            annotations.append(base)

            if selected["node_type"] == "Seq Scan":
                if selected["predicate"] == "no explicit predicate":
                    annotations.append(
                        f"This is a full-table read for {selected['subject']} (no filter/index condition in this operator)."
                    )
                elif any("Index" in alt["method"] for alt in changed_alternatives):
                    better = [
                        _format_ratio_text(alt)
                        for alt in changed_alternatives
                        if "Index" in alt["method"]
                    ]
                    annotations.append(
                        "Alternative index-based access paths exist but were not estimated cheaper in the selected plan: "
                        + ", ".join(better)
                        + "."
                    )
                else:
                    annotations.append(
                        "The optimizer retained sequential access under representative planner variations."
                    )
        else:
            annotations.append(
                f"The condition {selected['subject']} is executed using {selected['node_type']} "
                f"(startup={selected['startup_cost']}, total={selected['total_cost']}, rows={selected['plan_rows']})."
            )

            if changed_alternatives:
                changed_alternatives.sort(
                    key=lambda alt: alt["cost_ratio"]
                    if alt["cost_ratio"] is not None
                    else float("-inf"),
                    reverse=True,
                )
                top_changed = ", ".join(
                    _format_ratio_text(alt) for alt in changed_alternatives[:3]
                )
                annotations.append(
                    f"{selected['node_type']} was preferred because representative alternatives were costlier: {top_changed}."
                )
            elif matched_alternatives:
                annotations.append(
                    f"{selected['node_type']} stayed preferred across representative planner variations."
                )

        if explanation["unavailable"]:
            annotations.append(
                "Some alternative plans could not be generated: "
                + "; ".join(explanation["unavailable"])
                + "."
            )

    return annotations


def format_annotated_query(query, annotations):
    lines = [query.strip(), ""]
    for annotation in annotations:
        lines.append(f"-- {annotation}")
    return "\n".join(lines)
