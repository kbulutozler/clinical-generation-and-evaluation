import argparse
import json
from pathlib import Path


DEDUCTIONS = {
    ("hallucinations", "major"): 0.25,
    ("hallucinations", "minor"): 0.05,
    ("omissions", "major"): 0.10,
    ("omissions", "minor"): 0.02,
}


def compute_score(data):
    score = 1.0
    counts = {
        "major_hallucinations": 0,
        "minor_hallucinations": 0,
        "major_omissions": 0,
        "minor_omissions": 0,
    }

    for item in data.get("hallucinations") or []:
        severity = item.get("severity")
        score -= DEDUCTIONS.get(("hallucinations", severity), 0.0)
        if severity == "major":
            counts["major_hallucinations"] += 1
        elif severity == "minor":
            counts["minor_hallucinations"] += 1

    for item in data.get("omissions") or []:
        severity = item.get("severity")
        score -= DEDUCTIONS.get(("omissions", severity), 0.0)
        if severity == "major":
            counts["major_omissions"] += 1
        elif severity == "minor":
            counts["minor_omissions"] += 1

    return max(0.0, min(1.0, round(score, 10))), counts


def iter_eval_files(paths, evaluator=None):
    for path in paths:
        path = Path(path)
        if path.is_dir():
            if evaluator:
                yield from sorted(path.glob(f"**/evals/{evaluator}/eval_output.txt"))
            else:
                yield from sorted(path.glob("**/eval_output.txt"))
        else:
            if evaluator and f"/evals/{evaluator}/" not in path.as_posix():
                continue
            else:
                yield path


def main():
    parser = argparse.ArgumentParser(
        description="Recompute eval scores from hallucination/omission severities."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Eval JSON file(s) or directory/directories containing eval_output.txt files.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1e-9,
        help="Allowed absolute difference from the score stored in the JSON.",
    )
    parser.add_argument(
        "--evaluator",
        help="Only score eval_output.txt files under evals/<evaluator>/.",
    )
    args = parser.parse_args()

    checked = 0
    mismatches = 0
    malformed = 0

    for path in iter_eval_files(args.paths, args.evaluator):
        checked += 1
        try:
            data = json.loads(path.read_text())
        except Exception as exc:
            malformed += 1
            print(f"MALFORMED\t{path}\t{exc}")
            continue

        manual_score, counts = compute_score(data)
        reported_score = data.get("score")
        diff = None
        status = "OK"

        if isinstance(reported_score, (int, float)):
            diff = manual_score - float(reported_score)
            if abs(diff) > args.tolerance:
                status = "MISMATCH"
                mismatches += 1
        else:
            status = "MISSING_SCORE"
            mismatches += 1

        print(
            "\t".join(
                [
                    status,
                    str(path),
                    f"manual={manual_score:.10g}",
                    f"reported={reported_score}",
                    f"diff={diff:.10g}" if diff is not None else "diff=NA",
                    f"major_h={counts['major_hallucinations']}",
                    f"minor_h={counts['minor_hallucinations']}",
                    f"major_o={counts['major_omissions']}",
                    f"minor_o={counts['minor_omissions']}",
                ]
            )
        )

    print(
        "\t".join(
            [
                "SUMMARY",
                f"checked={checked}",
                f"mismatches={mismatches}",
                f"malformed={malformed}",
            ]
        )
    )


if __name__ == "__main__":
    main()
