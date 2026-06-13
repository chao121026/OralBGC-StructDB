import re


def short_id(value: str | None) -> str:
    if not value:
        return "Not available"
    text = str(value)
    match = re.search(r"(region\d+)_cds(\d+)$", text)
    if match:
        if "|" in text:
            return f"{text.split('|', 1)[0]}|...|{match.group(1)}|cds{match.group(2)}"
        return f"{match.group(1)} · cds{match.group(2)}"
    region_match = re.search(r"(region\d+)", text)
    if "|" in text and region_match:
        return f"{text.split('|', 1)[0]}|...|{region_match.group(1)}"
    if "|" in text:
        return text.split("|", 1)[0] + "|" + text.split("|", 1)[1][:18] + "..."
    if len(text) > 28:
        return text[:12] + "..." + text[-10:]
    return text


def human_label(value: str | None) -> str:
    if value in {None, ""}:
        return "Not available"
    text = str(value).replace("_", " ").strip()
    replacements = {"pdb": "PDB", "af3": "AF3", "qc": "QC", "tm": "TM"}
    words = [replacements.get(word.lower(), word.capitalize()) for word in text.split()]
    return " ".join(words)


def fmt_measure(value, digits: int = 1) -> str:
    if value in {None, ""}:
        return "Not available"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.{digits}f}"


def register_template_filters(templates) -> None:
    templates.env.filters["short_id"] = short_id
    templates.env.filters["human_label"] = human_label
    templates.env.filters["humanize_label"] = human_label
    templates.env.filters["fmt_measure"] = fmt_measure
