# Check the "is this section filled in" points from criteria.json in plain
# Python, so they give the same answer on every run and cost no tokens.
#
# CHECKS maps a point id to a function that takes the PR description and
# returns (passed, explanation, requested_change). Points without an entry here
# still go to Claude, also when criteria.json marks them "check": "script".


import re

HEADING = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t#]*$", re.MULTILINE)
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
PLACEHOLDER_LINES = {"", "-", "*", ">"}


def sections(body):
    """Map each Markdown heading in the description, lowercased, to the text
    under it. HTML comments are dropped, since the template's hints live there."""
    text = COMMENT.sub("", body or "")
    headings = list(HEADING.finditer(text))
    found = {}
    for heading, following in zip(headings, [*headings[1:], None]):
        end = following.start() if following else len(text)
        found.setdefault(heading.group(1).strip().lower(), text[heading.end() : end])
    return found


def _has_content(text):
    return any(line.strip() not in PLACEHOLDER_LINES for line in text.splitlines())


def _section_filled(names, label):
    shown = " or ".join(f"'## {name.title()}'" for name in names)

    def check(body):
        found = sections(body)
        name = next((n for n in names if n in found), None)
        if name is None:
            return False, f"The description has no {shown} section.", f"Add a {shown} section and fill it in."
        if not _has_content(found[name]):
            return False, f"The '## {name.title()}' section only holds the template placeholder.", f"Replace the placeholder with {label}."
        return True, f"The '## {name.title()}' section has content.", ""

    return check


def _first_quote(text):
    """The first block of '>' lines. Bots such as Macroscope append their own
    quoted summary further down, which is not the contributor's prompt."""
    block = []
    for line in text.splitlines():
        if line.lstrip().startswith(">"):
            block.append(line)
        elif block:
            break
    return block


def _prompt_filled(body):
    found = sections(body)
    if "synthetic prompt" not in found:
        return False, "The description has no '## Synthetic prompt' section.", "Add a '## Synthetic prompt' section with the request as a '> ...' quote."
    if not any(line.lstrip()[1:].strip() for line in _first_quote(found["synthetic prompt"])):
        return False, "The '## Synthetic prompt' section has no filled-in '> ...' quote line.", "Write the request a coding agent would need for this change after the '>'."
    return True, "The '## Synthetic prompt' section has a quoted prompt.", ""


CHECKS = {
    "summary_filled": _section_filled(["summary", "solution"], "what the change does"),
    "verification_filled": _section_filled(["verification"], "how you checked the change"),
    "prompt_filled": _prompt_filled,
}


def run(parts, body):
    """Return (results, llm_parts): a result for each point checked here, by
    id, and criteria.json without those points, for Claude to judge."""
    results = {}
    llm_parts = []
    for part in parts:
        remaining = []
        for point in part["points"]:
            check = CHECKS.get(point["id"])
            if check is None:
                remaining.append(point)
                continue
            passed, explanation, requested_change = check(body)
            results[point["id"]] = {
                "id": point["id"],
                "status": "pass" if passed else "fail",
                "explanation": explanation,
                "requested_change": requested_change,
            }
        if remaining:
            llm_parts.append({**part, "points": remaining})
    return results, llm_parts


def merge(parts, script_results, llm_results):
    """Combine both result lists into one per point, in criteria.json order."""
    by_id = {**{r["id"]: r for r in llm_results}, **script_results}
    return [by_id[point["id"]] for part in parts for point in part["points"]]
