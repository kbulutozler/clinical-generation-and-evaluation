import argparse
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

from utils import load_config


REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / "configs/config.yaml"
DEFAULT_EVAL_PROMPT_PATH = REPO_ROOT / "prompts/evaluation/eval_prompt_template.json"
HALLUCINATION_TYPES = ("fabrication", "negation", "causality", "contextual")
OMISSION_TYPES = ("current_issues", "pmfs", "plan")
SEVERITIES = ("major", "minor")
HALLUCINATION_EXPLANATIONS = {
    "fabrication": "Information stated in the generated note but not mentioned in the dialogue.",
    "negation": "The generated note reverses or contradicts a clinical fact from the dialogue.",
    "causality": "The generated note speculates about a cause without explicit support in the dialogue.",
    "contextual": "The generated note mixes in unrelated or mismatched clinical context.",
}
OMISSION_EXPLANATIONS = {
    "current_issues": "Details about the current presentation, symptoms, exam, or results were dropped.",
    "pmfs": "Past medical history, medications, allergies, family history, or social history were dropped.",
    "plan": "Management plan, prescriptions, follow-up, referrals, or patient instructions were dropped.",
}
DEDUCTIONS = {
    ("hallucinations", "major"): 0.25,
    ("hallucinations", "minor"): 0.05,
    ("omissions", "major"): 0.10,
    ("omissions", "minor"): 0.02,
}
STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "been",
    "being",
    "from",
    "have",
    "into",
    "that",
    "their",
    "there",
    "these",
    "this",
    "were",
    "with",
    "would",
}


MODEL_SIZE_B = {
    "Qwen3.5-2B": 2.274,
    "Qwen3.5-4B": 4.660,
    "gemma-4-E2B-it": 5.123,
    "gemma-4-E4B-it": 7.996,
    "Qwen3.5-9B": 9.653,
    "gemma-4-26B-A4B-it": 26.544,
    "medgemma-27b-text-it": 27.000,
    "Qwen3.5-27B": 27.781,
    "gemma-4-31B-it": 32.682,
}


def model_size_b(model_name):
    if model_name in MODEL_SIZE_B:
        return MODEL_SIZE_B[model_name]
    matches = re.findall(r"(\d+(?:\.\d+)?)b\b", model_name.lower())
    return float(matches[-1]) if matches else float("inf")


def shot_number(exp):
    match = re.search(r"_(\d+)shot$", exp)
    return int(match.group(1)) if match else 999


def run_sort_key(key):
    gen_model, exp = key
    return (model_size_b(gen_model), gen_model.lower(), shot_number(exp), exp)


def run_label(gen_model, exp):
    if exp.endswith("_0shot"):
        shot = "0-shot"
    elif exp.endswith("_1shot"):
        shot = "1-shot"
    elif exp.endswith("_2shot"):
        shot = "2-shot"
    else:
        shot = exp
    return f"{gen_model} {shot}"


def fmt_float(value, digits=3):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "NA"
    return f"{value:.{digits}f}"


def mean(values):
    return sum(values) / len(values) if values else float("nan")


def stdev(values):
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def markdown_table(headers, rows):
    lines = [
        "| " + " | ".join(md_cell(x) for x in headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(md_cell(x) for x in row) + " |")
    return "\n".join(lines)


def md_cell(value):
    return str(value).replace("\n", "<br>").replace("|", "\\|")


def compact_text(text, limit=520):
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def normalize_text(text):
    text = re.sub(r"n['’]t\b", " n t", str(text).lower())
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def content_tokens(text):
    return {
        token
        for token in normalize_text(text).split()
        if len(token) >= 4 and token not in STOPWORDS
    }


def compute_manual_score(hallucinations, omissions):
    score = 1.0
    for item in hallucinations:
        score -= DEDUCTIONS.get(("hallucinations", item.get("severity")), 0.0)
    for item in omissions:
        score -= DEDUCTIONS.get(("omissions", item.get("severity")), 0.0)
    return max(0.0, min(1.0, round(score, 10)))


def load_evaluation_system_prompt(path=DEFAULT_EVAL_PROMPT_PATH):
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        return f"Could not load evaluation system prompt from `{path}`: {exc}"
    for message in data.get("messages", []):
        if message.get("role") == "system":
            return message.get("content", "")
    return f"No system message found in `{path}`."


def parse_eval_json(text):
    text = str(text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        return json.loads(fence_match.group(1).strip())

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])

    return json.loads(text)


def parse_eval_path(base, path):
    rel = path.relative_to(base)
    parts = rel.parts
    # <dataset>/<encounter>/<gen_model>/<testsplit_nshot>/evals/<eval_model>/eval_output.txt
    if len(parts) != 7 or parts[4] != "evals":
        raise ValueError(f"Unexpected eval path shape: {path}")
    return {
        "dataset": parts[0],
        "encounter": parts[1],
        "gen_model": parts[2],
        "exp": parts[3],
        "eval_model": parts[5],
    }


def load_rows(base, evaluator):
    rows = []
    bad = []
    pattern = f"*/*/*/*/evals/{evaluator}/eval_output.txt"
    for path in sorted(base.glob(pattern)):
        meta = parse_eval_path(base, path)
        try:
            data = parse_eval_json(path.read_text())
            reported_score = data.get("score")
            if not isinstance(reported_score, (int, float)):
                raise ValueError(f"Score is not numeric: {reported_score!r}")
            hallucinations = data.get("hallucinations") or []
            omissions = data.get("omissions") or []
            manual_score = compute_manual_score(hallucinations, omissions)
            row = {
                **meta,
                "path": path,
                "score": manual_score,
                "reported_score": float(reported_score),
                "score_diff": manual_score - float(reported_score),
                "hallucinations": hallucinations,
                "omissions": omissions,
                "h_total": len(hallucinations),
                "o_total": len(omissions),
            }
            for err_type in HALLUCINATION_TYPES:
                row[f"h_{err_type}"] = sum(1 for x in hallucinations if x.get("type") == err_type)
            for err_type in OMISSION_TYPES:
                row[f"o_{err_type}"] = sum(1 for x in omissions if x.get("type") == err_type)
            for severity in SEVERITIES:
                row[f"h_{severity}"] = sum(1 for x in hallucinations if x.get("severity") == severity)
                row[f"o_{severity}"] = sum(1 for x in omissions if x.get("severity") == severity)
            rows.append(row)
        except Exception as exc:
            bad.append({
                **meta,
                "path": path,
                "error": str(exc),
                "preview": path.read_text()[:240].replace("\n", " "),
            })
    return rows, bad


def group_rows(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["gen_model"], row["exp"])].append(row)
    return grouped


def sorted_group_keys(grouped):
    return sorted(grouped, key=run_sort_key)


def score_summary_rows(grouped, bad):
    bad_counts = Counter((x["gen_model"], x["exp"]) for x in bad)
    table = []
    for key in sorted_group_keys(grouped):
        vals = grouped[key]
        scores = [x["score"] for x in vals]
        table.append([
            run_label(*key),
            len(vals),
            bad_counts[key],
            fmt_float(mean(scores)),
            fmt_float(statistics.median(scores)),
            fmt_float(min(scores)),
            fmt_float(max(scores)),
            fmt_float(stdev(scores)),
            sum(x >= 0.8 for x in scores),
            sum(x >= 0.7 for x in scores),
            sum(x >= 0.5 for x in scores),
            sum(x < 0.3 for x in scores),
            sum(x == 0.0 for x in scores),
        ])
    for key, count in sorted(bad_counts.items(), key=lambda item: run_sort_key(item[0])):
        if key not in grouped:
            table.append([run_label(*key), 0, count, "NA", "NA", "NA", "NA", "NA", 0, 0, 0, 0, 0])
    return table


def count_summary_rows(grouped):
    rows = []
    for key in sorted_group_keys(grouped):
        vals = grouped[key]
        n = len(vals)
        rows.append([
            run_label(*key),
            sum(x["h_total"] for x in vals),
            fmt_float(mean([x["h_total"] for x in vals]), 2),
            sum(x["h_major"] for x in vals),
            sum(x["h_minor"] for x in vals),
            sum(x["o_total"] for x in vals),
            fmt_float(mean([x["o_total"] for x in vals]), 2),
            sum(x["o_major"] for x in vals),
            sum(x["o_minor"] for x in vals),
            n,
        ])
    return rows


def mismatch_rows(rows, tolerance=1e-9):
    mismatches = [row for row in rows if abs(row["score_diff"]) > tolerance]
    grouped = defaultdict(list)
    for row in mismatches:
        grouped[(row["gen_model"], row["exp"])].append(row)

    summary = []
    for key in sorted(grouped, key=run_sort_key):
        vals = grouped[key]
        diffs = [x["score_diff"] for x in vals]
        summary.append([
            run_label(*key),
            len(vals),
            fmt_float(mean(diffs)),
            fmt_float(mean([abs(x) for x in diffs])),
            fmt_float(min(diffs)),
            fmt_float(max(diffs)),
        ])

    details = []
    for row in sorted(mismatches, key=lambda x: (run_sort_key((x["gen_model"], x["exp"])), x["encounter"])):
        details.append([
            run_label(row["gen_model"], row["exp"]),
            row["encounter"],
            fmt_float(row["score"]),
            fmt_float(row["reported_score"]),
            fmt_float(row["score_diff"]),
            row["h_major"],
            row["h_minor"],
            row["o_major"],
            row["o_minor"],
        ])
    return summary, details


def type_rows(grouped, prefix, types):
    rows = []
    for key in sorted_group_keys(grouped):
        vals = grouped[key]
        row = [run_label(*key)]
        for err_type in types:
            total = sum(x[f"{prefix}_{err_type}"] for x in vals)
            per_case = total / len(vals) if vals else float("nan")
            row.append(f"{total} ({per_case:.2f}/case)")
        rows.append(row)
    return rows


def quoted_phrases(text):
    phrases = []
    for match in re.finditer(r"(?<!\w)'((?:[^']|(?<=\w)'(?=\w)){8,180})'(?!\w)|\"([^\"]{8,180})\"", str(text or "")):
        phrase = match.group(1) or match.group(2)
        phrases.append(phrase)
    return phrases


def candidate_phrases(issue):
    explanation = issue.get("explanation", "")
    candidates = quoted_phrases(explanation)
    return [candidate for candidate in candidates if len(normalize_text(candidate)) >= 15]


def nonempty_lines(path):
    if not path.exists():
        return []
    lines = []
    for line_no, text in enumerate(path.read_text().splitlines(), start=1):
        stripped = text.strip()
        if stripped:
            lines.append((line_no, stripped))
    return lines


def match_source_line(lines, candidates):
    normalized_lines = [(line_no, text, normalize_text(text)) for line_no, text in lines]
    for candidate in candidates:
        normalized_candidate = normalize_text(candidate)
        if len(normalized_candidate) < 8:
            continue
        for idx, (_, _, normalized_line) in enumerate(normalized_lines):
            if normalized_candidate in normalized_line or (
                len(normalized_line) >= 20 and normalized_line in normalized_candidate
            ):
                return idx, candidate

    return None, None


def token_spans(text):
    return [(normalize_text(match.group(0)), match.start(), match.end()) for match in re.finditer(r"[a-zA-Z0-9]+", text)]


def bold_reference(line, reference):
    ref_words = normalize_text(reference).split()
    if ref_words:
        pattern = r"\b" + r"\W+".join(re.escape(word) for word in ref_words) + r"\b"
        match = re.search(pattern, line, flags=re.IGNORECASE)
        if match:
            start_char, end_char = match.span()
            return f"{line[:start_char]}**{line[start_char:end_char]}**{line[end_char:]}"

    line_tokens = token_spans(line)
    ref_tokens = [token for token, _, _ in token_spans(reference)]
    if not line_tokens or not ref_tokens:
        return line

    for start in range(0, len(line_tokens) - len(ref_tokens) + 1):
        candidate_tokens = [token for token, _, _ in line_tokens[start:start + len(ref_tokens)]]
        if candidate_tokens == ref_tokens:
            start_char = line_tokens[start][1]
            end_char = line_tokens[start + len(ref_tokens) - 1][2]
            return f"{line[:start_char]}**{line[start_char:end_char]}**{line[end_char:]}"

    ref_content = content_tokens(reference)
    if not ref_content:
        return line
    parts = []
    last = 0
    for token, start_char, end_char in line_tokens:
        if token in ref_content:
            parts.append(line[last:start_char])
            parts.append(f"**{line[start_char:end_char]}**")
            last = end_char
    parts.append(line[last:])
    return "".join(parts)


def compact_around_bold(text, limit=760):
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    marker = text.find("**")
    if marker == -1:
        return compact_text(text, limit)
    start = max(0, marker - limit // 2)
    end = min(len(text), start + limit)
    start = max(0, end - limit)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end].strip() + suffix


def find_negation_excerpt(row, issue):
    encounter_dir = row["path"].parents[2]
    source_name = "sourcedoc.txt"
    source_path = encounter_dir / source_name
    lines = nonempty_lines(source_path)
    if not lines:
        return None
    idx, matched = match_source_line(lines, candidate_phrases(issue))
    if idx is None:
        return None
    line_no, line = lines[idx]
    return f"L{line_no}: {compact_around_bold(bold_reference(line, matched))}"


def negation_example_rows(rows, max_per_run=2):
    examples = []
    counts = Counter()
    sorted_rows = sorted(
        rows,
        key=lambda row: (run_sort_key((row["gen_model"], row["exp"])), row["encounter"]),
    )
    for row in sorted_rows:
        run = run_label(row["gen_model"], row["exp"])
        if counts[run] >= max_per_run:
            continue
        issues = [item for item in row["hallucinations"] if item.get("type") == "negation"]
        for issue in issues:
            excerpt = find_negation_excerpt(row, issue)
            if not excerpt:
                continue
            examples.append([
                run,
                row["encounter"],
                issue.get("severity", ""),
                compact_text(issue.get("text_in_note", ""), 260),
                excerpt,
                compact_text(issue.get("explanation", ""), 360),
            ])
            counts[run] += 1
            break
    return examples


def medgemma_shot_rows(grouped):
    zero_key = ("medgemma-27b-text-it", "clinicalnlp_taskB_test1_0shot")
    one_key = ("medgemma-27b-text-it", "clinicalnlp_taskB_test1_1shot")
    if zero_key not in grouped or one_key not in grouped:
        return [], []
    zero = {x["encounter"]: x for x in grouped[zero_key]}
    one = {x["encounter"]: x for x in grouped[one_key]}
    rows = []
    for enc in sorted(set(zero) & set(one)):
        diff = one[enc]["score"] - zero[enc]["score"]
        rows.append([enc, fmt_float(zero[enc]["score"]), fmt_float(one[enc]["score"]), fmt_float(diff)])
    improvements = sorted(rows, key=lambda x: float(x[3]), reverse=True)[:8]
    regressions = sorted(rows, key=lambda x: float(x[3]))[:8]
    return improvements, regressions


def plot_run_label(label):
    for shot in ("0-shot", "1-shot", "2-shot"):
        suffix = f" {shot}"
        if label.endswith(suffix):
            return f"{label[:-len(suffix)]}\n{shot}"
    return label


def set_run_xticks(ax, x_positions, labels):
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels, rotation=30, ha="right", rotation_mode="anchor")
    ax.margins(x=0.04)


def make_plot(grouped, output_path):
    keys = sorted_group_keys(grouped)
    labels = [plot_run_label(run_label(*key)) for key in keys]
    x_positions = list(range(len(keys)))
    scores = [[x["score"] for x in grouped[key]] for key in keys]
    means = [mean(values) for values in scores]

    fig, axes = plt.subplots(3, 2, figsize=(20, 17))
    ax = axes[0][0]
    ax.boxplot(scores, positions=x_positions, widths=0.55, showmeans=True)
    ax.set_title("Evaluator Score Distribution")
    ax.set_ylabel("Score")
    ax.set_ylim(0, 1)
    set_run_xticks(ax, x_positions, labels)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[0][1]
    bars = ax.bar(x_positions, means, width=0.72, color="#4C78A8")
    ax.set_title("Mean Score")
    ax.set_ylabel("Mean score")
    ax.set_ylim(0, 1.08)
    ax.bar_label(bars, labels=[fmt_float(value) for value in means], padding=3, fontsize=9)
    set_run_xticks(ax, x_positions, labels)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1][0]
    bottom = [0] * len(keys)
    colors = ["#E45756", "#F58518", "#72B7B2", "#54A24B"]
    for err_type, color in zip(HALLUCINATION_TYPES, colors):
        vals = [sum(x[f"h_{err_type}"] for x in grouped[key]) / len(grouped[key]) for key in keys]
        ax.bar(x_positions, vals, width=0.72, bottom=bottom, label=err_type, color=color)
        bottom = [a + b for a, b in zip(bottom, vals)]
    ax.set_title("Hallucinations by Type (per Encounter)")
    ax.set_ylabel("Count per encounter")
    set_run_xticks(ax, x_positions, labels)
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1][1]
    bottom = [0] * len(keys)
    colors = ["#B279A2", "#9D755D", "#FF9DA6"]
    for err_type, color in zip(OMISSION_TYPES, colors):
        vals = [sum(x[f"o_{err_type}"] for x in grouped[key]) / len(grouped[key]) for key in keys]
        ax.bar(x_positions, vals, width=0.72, bottom=bottom, label=err_type, color=color)
        bottom = [a + b for a, b in zip(bottom, vals)]
    ax.set_title("Omissions by Type (per Encounter)")
    ax.set_ylabel("Count per encounter")
    set_run_xticks(ax, x_positions, labels)
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    ax = axes[2][0]
    bottom = [0] * len(keys)
    for severity, color in (("major", "#B23A48"), ("minor", "#F4A261")):
        vals = [sum(x[f"h_{severity}"] for x in grouped[key]) / len(grouped[key]) for key in keys]
        ax.bar(x_positions, vals, width=0.72, bottom=bottom, label=severity, color=color)
        bottom = [a + b for a, b in zip(bottom, vals)]
    ax.set_title("Hallucinations by Severity (per Encounter)")
    ax.set_ylabel("Count per encounter")
    set_run_xticks(ax, x_positions, labels)
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    ax = axes[2][1]
    bottom = [0] * len(keys)
    for severity, color in (("major", "#7B2CBF"), ("minor", "#C77DFF")):
        vals = [sum(x[f"o_{severity}"] for x in grouped[key]) / len(grouped[key]) for key in keys]
        ax.bar(x_positions, vals, width=0.72, bottom=bottom, label=severity, color=color)
        bottom = [a + b for a, b in zip(bottom, vals)]
    ax.set_title("Omissions by Severity (per Encounter)")
    ax.set_ylabel("Count per encounter")
    set_run_xticks(ax, x_positions, labels)
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def write_report(base, report_path, plot_path, rows, bad, evaluator):
    grouped = group_rows(rows)
    score_rows = score_summary_rows(grouped, bad)
    count_rows = count_summary_rows(grouped)
    h_type_rows = type_rows(grouped, "h", HALLUCINATION_TYPES)
    o_type_rows = type_rows(grouped, "o", OMISSION_TYPES)
    negation_rows = negation_example_rows(rows)
    improvements, regressions = medgemma_shot_rows(grouped)
    _, mismatch_details = mismatch_rows(rows)
    evaluation_system_prompt = load_evaluation_system_prompt()

    lines = [
        f"# {evaluator} Evaluation Analysis",
        "",
        f"Base directory: `{base}`",
        "",
        f"This report uses only `evals/{evaluator}/eval_output.txt` files under the final output layout.",
        "",
        "## Evaluation System Prompt",
        "",
        f"The {evaluator} evaluator used this system prompt:",
        "",
        "```text",
        evaluation_system_prompt,
        "```",
        "",
        "## Evaluation Rubric",
        "",
        "The evaluator compares each generated note against the doctor-patient dialogue and reference note. It returns hallucinations, omissions, and a score.",
        "",
        "Hallucination types: `fabrication`, `negation`, `causality`, `contextual`.",
        "",
        markdown_table(
            ["Hallucination Type", "Meaning"],
            [[key, value] for key, value in HALLUCINATION_EXPLANATIONS.items()],
        ),
        "",
        "Omission types: `current_issues`, `pmfs`, `plan`.",
        "",
        markdown_table(
            ["Omission Type", "Meaning"],
            [[key, value] for key, value in OMISSION_EXPLANATIONS.items()],
        ),
        "",
        "Scoring starts at 1.0, then deducts 0.25 per major hallucination, 0.05 per minor hallucination, 0.10 per major omission, and 0.02 per minor omission. Scores are clamped to [0.0, 1.0].",
        "",
        "All score statistics below use a deterministic manual recomputation from the evaluator's listed hallucinations and omissions, not the evaluator's self-reported `score` field.",
        "",
        "## Data Quality",
        "",
        f"- Parsed eval outputs: `{len(rows)}`",
        f"- Malformed eval outputs: `{len(bad)}`",
        f"- Evaluator score arithmetic failures: `{len(mismatch_details)}` of `{len(rows)}` valid outputs had a self-reported `score` that did not match the rubric score recomputed from its own listed errors.",
        f"- Plot: `{plot_path}`",
        "",
        "## Score Summary",
        "",
        markdown_table(
            ["Run", "Valid N", "Bad JSON", "Mean", "Median", "Min", "Max", "Std", ">=0.8", ">=0.7", ">=0.5", "<0.3", "Zeros"],
            score_rows,
        ),
        "",
        "## Error Totals",
        "",
        markdown_table(
            ["Run", "Hallucinations", "Hallucinations / case", "Major H", "Minor H", "Omissions", "Omissions / case", "Major O", "Minor O", "Valid N"],
            count_rows,
        ),
        "",
        "## Hallucinations by Type",
        "",
        markdown_table(["Run", *HALLUCINATION_TYPES], h_type_rows),
        "",
        "## Omissions by Type",
        "",
        markdown_table(["Run", *OMISSION_TYPES], o_type_rows),
        "",
        "## Negation Examples",
        "",
        "Examples where a selected generated note says something contradicted by the source dialogue. The reference comes from the matched line in `sourcedoc.txt`; only the reference words are bolded.",
        "",
        markdown_table(
            ["Run", "Encounter", "Severity", "Model said", "Reference in dialog", "Evaluator explanation"],
            negation_rows,
        ) if negation_rows else "No negation examples could be matched to `sourcedoc.txt`.",
        "",
    ]
    if improvements or regressions:
        lines.extend([
            "",
            "## MedGemma 1-Shot vs 0-Shot",
            "",
            f"Both are evaluated by {evaluator}.",
            "",
            "Largest 1-shot improvements:",
            "",
            markdown_table(["Encounter", "0-shot", "1-shot", "Delta"], improvements),
            "",
            "Largest 1-shot regressions:",
            "",
            markdown_table(["Encounter", "0-shot", "1-shot", "Delta"], regressions),
        ])
    report_path.write_text("\n".join(lines))


def default_evaluator():
    try:
        config = load_config(CONFIG_PATH)
        eval_model_name = config["active_eval_model"]
        return config["models"][eval_model_name]["modelname"]
    except Exception:
        return "Qwen3.5-27B"


def safe_prefix(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default="outputs/final")
    parser.add_argument("--evaluator", default=None)
    parser.add_argument("--output-dir", default="analysis")
    parser.add_argument("--prefix", default=None)
    args = parser.parse_args()

    base = Path(args.base_dir)
    evaluator = args.evaluator or default_evaluator()
    prefix = args.prefix or f"{safe_prefix(evaluator)}_eval_analysis"
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{prefix}.md"
    plot_path = output_dir / f"{prefix}.png"

    rows, bad = load_rows(base, evaluator)
    grouped = group_rows(rows)
    if not rows:
        raise SystemExit(f"No valid eval rows found under {base} for evaluator {evaluator}")

    make_plot(grouped, plot_path)
    write_report(base, report_path, plot_path, rows, bad, evaluator)

    print(f"Wrote {report_path}")
    print(f"Wrote {plot_path}")
    print(f"Parsed {len(rows)} valid eval outputs; malformed {len(bad)}")


if __name__ == "__main__":
    main()
