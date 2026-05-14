#!/usr/bin/env python3
"""Create PNG plots and a Markdown summary for a GEPA run directory."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

import matplotlib.pyplot as plt


ERROR_KEYS = [
    ("hallucinations", "major", "Major hallucinations"),
    ("hallucinations", "minor", "Minor hallucinations"),
    ("omissions", "major", "Major omissions"),
    ("omissions", "minor", "Minor omissions"),
]
ERROR_COLORS = {
    ("hallucinations", "major"): "#C44E52",
    ("hallucinations", "minor"): "#E17C05",
    ("omissions", "major"): "#4C78A8",
    ("omissions", "minor"): "#72B7B2",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def fmt_float(value: Any, digits: int = 3) -> str:
    if value is None:
        return "NA"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "NA"
    if math.isnan(number):
        return "NA"
    return f"{number:.{digits}f}"


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(item).replace("|", "\\|") for item in row) + " |")
    return "\n".join(lines)


def compact_text(text: Any, limit: int = 900) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def score(row: dict[str, Any]) -> float:
    return float(row.get("manual_score", row.get("score", 0.0)) or 0.0)


def reported_score(row: dict[str, Any]) -> float | None:
    value = row.get("reported_score")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def eval_payload(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("evaluation") or {}


def count_errors(row: dict[str, Any]) -> dict[tuple[str, str], int]:
    data = eval_payload(row)
    counts: dict[tuple[str, str], int] = {}
    for category, severity, _ in ERROR_KEYS:
        counts[(category, severity)] = sum(
            1 for item in data.get(category, []) or [] if item.get("severity") == severity
        )
    return counts


def group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key, ""))].append(row)
    return dict(grouped)


def savefig(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def plot_score_progression(rows: list[dict[str, Any]], out: Path) -> None:
    plt.figure(figsize=(11, 6))
    for encounter, vals in sorted(group_by(rows, "encounter_id").items()):
        vals = sorted(vals, key=lambda row: row["call_index"])
        plt.plot(
            [row["call_index"] for row in vals],
            [score(row) for row in vals],
            marker="o",
            linewidth=1.8,
            label=encounter,
        )
    for row in rows:
        plt.text(row["call_index"], score(row) + 0.025, str(row["candidate_prompt_hash"])[:6], fontsize=7, ha="center")
    plt.ylim(-0.05, 1.08)
    plt.xlabel("Rollout call index")
    plt.ylabel("Manual rubric score")
    plt.title("GEPA Score Progression by Encounter")
    plt.grid(axis="y", alpha=0.25)
    plt.legend(title="Encounter")
    savefig(out / "01_score_progression.png")


def plot_candidate_scores(rows: list[dict[str, Any]], out: Path) -> None:
    grouped = group_by(rows, "candidate_prompt_hash")
    labels = sorted(grouped)
    data = [[score(row) for row in grouped[label]] for label in labels]
    plt.figure(figsize=(10, 6))
    positions = list(range(1, len(labels) + 1))
    plt.boxplot(data, positions=positions, widths=0.5, showmeans=True)
    for x, label in zip(positions, labels):
        ys = data[x - 1]
        plt.scatter([x] * len(ys), ys, s=32, alpha=0.7)
    plt.xticks(positions, [label[:8] for label in labels])
    plt.ylim(-0.05, 1.08)
    plt.xlabel("Candidate prompt hash")
    plt.ylabel("Manual rubric score")
    plt.title("Candidate Score Distribution")
    plt.grid(axis="y", alpha=0.25)
    savefig(out / "02_candidate_scores.png")


def plot_errors_by_rollout(rows: list[dict[str, Any]], out: Path) -> None:
    sorted_rows = sorted(rows, key=lambda row: row["call_index"])
    x = [row["call_index"] for row in sorted_rows]
    bottoms = [0] * len(sorted_rows)
    plt.figure(figsize=(12, 6))
    for category, severity, label in ERROR_KEYS:
        values = [count_errors(row)[(category, severity)] for row in sorted_rows]
        plt.bar(x, values, bottom=bottoms, label=label, color=ERROR_COLORS[(category, severity)])
        bottoms = [a + b for a, b in zip(bottoms, values)]
    plt.xlabel("Rollout call index")
    plt.ylabel("Listed error count")
    plt.title("Evaluator-Listed Errors by Rollout")
    plt.xticks(x)
    plt.legend()
    plt.grid(axis="y", alpha=0.25)
    savefig(out / "03_error_counts_by_rollout.png")


def plot_errors_by_candidate(rows: list[dict[str, Any]], out: Path) -> None:
    grouped = group_by(rows, "candidate_prompt_hash")
    labels = sorted(grouped)
    x = list(range(len(labels)))
    bottoms = [0.0] * len(labels)
    plt.figure(figsize=(10, 6))
    for category, severity, label in ERROR_KEYS:
        values = []
        for candidate in labels:
            vals = [count_errors(row)[(category, severity)] for row in grouped[candidate]]
            values.append(mean(vals) if vals else 0.0)
        plt.bar(x, values, bottom=bottoms, label=label, color=ERROR_COLORS[(category, severity)])
        bottoms = [a + b for a, b in zip(bottoms, values)]
    plt.xticks(x, [label[:8] for label in labels])
    plt.xlabel("Candidate prompt hash")
    plt.ylabel("Mean listed errors per rollout")
    plt.title("Mean Error Counts by Candidate")
    plt.legend()
    plt.grid(axis="y", alpha=0.25)
    savefig(out / "04_error_counts_by_candidate.png")


def plot_final_scores(summary: dict[str, Any], out: Path) -> None:
    final_outputs = summary.get("final_outputs") or []
    labels = [row["encounter_id"] for row in final_outputs]
    values = [float(row.get("score", 0.0) or 0.0) for row in final_outputs]
    plt.figure(figsize=(9, 5.5))
    bars = plt.bar(labels, values, color="#4C78A8")
    plt.bar_label(bars, labels=[fmt_float(value) for value in values], padding=3)
    plt.ylim(0, 1.08)
    plt.xlabel("Encounter")
    plt.ylabel("Manual rubric score")
    plt.title("Final Scores by Encounter")
    plt.grid(axis="y", alpha=0.25)
    savefig(out / "05_final_scores_by_encounter.png")


def plot_reported_vs_manual(rows: list[dict[str, Any]], out: Path) -> None:
    points = [(reported_score(row), score(row), row) for row in rows if reported_score(row) is not None]
    plt.figure(figsize=(6.5, 6.5))
    if points:
        plt.scatter([x for x, _, _ in points], [y for _, y, _ in points], s=45, alpha=0.75)
    plt.plot([0, 1], [0, 1], linestyle="--", color="#888888", linewidth=1)
    plt.xlim(-0.05, 1.05)
    plt.ylim(-0.05, 1.05)
    plt.xlabel("Evaluator-reported score")
    plt.ylabel("Manual recomputed score")
    plt.title("Reported vs Manual Score")
    plt.grid(alpha=0.25)
    savefig(out / "06_reported_vs_manual_score.png")


def plot_prompt_length_vs_score(rows: list[dict[str, Any]], out: Path) -> None:
    plt.figure(figsize=(9, 6))
    for candidate, vals in sorted(group_by(rows, "candidate_prompt_hash").items()):
        plt.scatter(
            [len(row.get("candidate_prompt") or "") for row in vals],
            [score(row) for row in vals],
            s=55,
            alpha=0.75,
            label=candidate[:8],
        )
    plt.ylim(-0.05, 1.08)
    plt.xlabel("Candidate prompt length (characters)")
    plt.ylabel("Manual rubric score")
    plt.title("Prompt Length vs Score")
    plt.legend(title="Candidate")
    plt.grid(alpha=0.25)
    savefig(out / "07_prompt_length_vs_score.png")


def write_summary(run_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any], candidates: list[dict[str, Any]], out: Path) -> None:
    grouped = group_by(rows, "candidate_prompt_hash")
    candidate_rows = []
    for candidate, vals in sorted(grouped.items()):
        scores = [score(row) for row in vals]
        candidate_rows.append([
            candidate,
            len(vals),
            fmt_float(mean(scores)),
            fmt_float(min(scores)),
            fmt_float(max(scores)),
            sorted({row["encounter_id"] for row in vals}),
            len(vals[0].get("candidate_prompt") or "") if vals else 0,
        ])

    final_rows = []
    for row in summary.get("final_outputs") or []:
        ev = row.get("evaluation") or {}
        final_rows.append([
            row.get("encounter_id"),
            fmt_float(row.get("score")),
            fmt_float(ev.get("reported_score")),
            ev.get("score_source", ""),
            len(ev.get("hallucinations") or []),
            len(ev.get("omissions") or []),
        ])

    lines = [
        "# GEPA Run Plots",
        "",
        f"Run directory: `{run_dir}`",
        f"Metric calls: `{summary.get('metric_calls')}`",
        f"Trace records: `{len(rows)}`",
        f"Candidates: `{len(candidates)}`",
        "",
        "## Candidate Summary",
        "",
        markdown_table(
            ["candidate_hash", "rollouts", "mean", "min", "max", "encounters", "prompt_chars"],
            candidate_rows,
        ),
        "",
        "## Final Outputs",
        "",
        markdown_table(
            ["encounter", "manual_score", "reported_score", "score_source", "hallucinations", "omissions"],
            final_rows,
        ),
        "",
        "## Plots",
        "",
        "- `01_score_progression.png`",
        "- `02_candidate_scores.png`",
        "- `03_error_counts_by_rollout.png`",
        "- `04_error_counts_by_candidate.png`",
        "- `05_final_scores_by_encounter.png`",
        "- `06_reported_vs_manual_score.png`",
        "- `07_prompt_length_vs_score.png`",
        "- `encounter_reports/<encounter_id>.md`",
    ]
    (out / "summary.md").write_text("\n".join(lines) + "\n")


def error_summary(eval_json: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for category in ("hallucinations", "omissions"):
        for item in eval_json.get(category, []) or []:
            rows.append([
                category[:-1],
                item.get("type", ""),
                item.get("severity", ""),
                compact_text(item.get("text_in_note") or item.get("text_in_dialogue") or "", 220),
                compact_text(item.get("explanation") or "", 280),
            ])
    return rows


def write_encounter_reports(run_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any], out: Path) -> None:
    report_dir = out / "encounter_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    final_by_encounter = {
        row.get("encounter_id"): row
        for row in summary.get("final_outputs") or []
    }
    for encounter, vals in sorted(group_by(rows, "encounter_id").items()):
        vals = sorted(vals, key=lambda row: row["call_index"])
        final = final_by_encounter.get(encounter) or {}
        final_eval = final.get("evaluation") or {}
        rollout_rows = [
            [
                row["call_index"],
                row["candidate_prompt_hash"],
                fmt_float(row.get("manual_score")),
                fmt_float(row.get("reported_score")),
                len(eval_payload(row).get("hallucinations") or []),
                len(eval_payload(row).get("omissions") or []),
                compact_text(row.get("reflector_feedback"), 260),
            ]
            for row in vals
        ]
        lines = [
            f"# GEPA Encounter Report: {encounter}",
            "",
            f"Run directory: `{run_dir}`",
            "",
            "## Rollouts",
            "",
            markdown_table(
                ["call", "candidate", "manual", "reported", "hallucinations", "omissions", "feedback"],
                rollout_rows,
            ),
            "",
            "## Final Selected Output",
            "",
            f"Manual score: `{fmt_float(final.get('score'))}`",
            f"Score source: `{final_eval.get('score_source', '')}`",
            "",
            "Generated note excerpt:",
            "",
            "```text",
            compact_text(final.get("generated_target"), 1800),
            "```",
            "",
            "## Final Listed Errors",
            "",
        ]
        error_rows = error_summary(final_eval)
        if error_rows:
            lines.append(markdown_table(["kind", "type", "severity", "text", "explanation"], error_rows))
        else:
            lines.append("No hallucinations or omissions listed.")
        lines.extend(["", "## Candidate Prompt Excerpts", ""])
        seen: set[str] = set()
        for row in vals:
            candidate = row["candidate_prompt_hash"]
            if candidate in seen:
                continue
            seen.add(candidate)
            lines.extend([
                f"### {candidate}",
                "",
                "```text",
                compact_text(row.get("candidate_prompt"), 1800),
                "```",
                "",
            ])
        (report_dir / f"{encounter}.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", help="GEPA run directory containing summary.json and traces/rollouts.jsonl")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    summary_path = run_dir / "summary.json"
    traces_path = run_dir / "traces" / "rollouts.jsonl"
    candidates_path = run_dir / "gepa_state" / "candidates.json"

    if not summary_path.exists():
        raise SystemExit(f"Missing {summary_path}")
    if not traces_path.exists():
        raise SystemExit(f"Missing {traces_path}")
    if not candidates_path.exists():
        raise SystemExit(f"Missing {candidates_path}")

    summary = load_json(summary_path)
    rows = load_jsonl(traces_path)
    candidates = load_json(candidates_path)
    out = run_dir / "plots"
    out.mkdir(parents=True, exist_ok=True)

    plot_score_progression(rows, out)
    plot_candidate_scores(rows, out)
    plot_errors_by_rollout(rows, out)
    plot_errors_by_candidate(rows, out)
    plot_final_scores(summary, out)
    plot_reported_vs_manual(rows, out)
    plot_prompt_length_vs_score(rows, out)
    write_summary(run_dir, rows, summary, candidates, out)
    write_encounter_reports(run_dir, rows, summary, out)

    print(out)
    print(8)


if __name__ == "__main__":
    main()
