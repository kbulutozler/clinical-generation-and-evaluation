import json
import sys
import time
from datetime import datetime
from pathlib import Path

from vllm import LLM, SamplingParams

from utils import load_config, extract_thinking

CONFIG_PATH = Path("configs/config.yaml")

SYSTEM_PROMPT = """\
# Clinician Evaluation Guide: LLM-Generated Clinical Note Review

## Your Role
You are reviewing an AI-generated clinical note. Your job is to identify errors that could impact patient care. You will be given three documents:

- **Source Document** — the original doctor-patient conversation or clinical record
- **Reference Note** — a gold standard note written by a clinician
- **AI-Generated Note** — the note produced by the AI system you are evaluating

Your evaluation has two parts: (1) checking the AI note for **fabrications and negations**, and (2) checking for **omissions**.

---

## PART 1: Hallucination Review
### Task
Read the AI-Generated Note sentence by sentence. For each sentence, check whether it is fully supported by the Source Document.

### Error Types to Look For

| Error Type | Definition | Example |
|---|---|---|
| **Fabrication** | The AI states something that was never mentioned in the source document | Source says patient has a cough. AI note says patient has a cough and fever — fever was never mentioned |
| **Negation** | The AI contradicts a fact stated in the source document | Source says patient IS allergic to penicillin. AI note says patient has NO known allergies |
| **Causality** | The AI implies a cause-effect relationship not explicitly stated in the source | Source says patient has diabetes and fatigue. AI note says fatigue is caused by diabetes — this was not stated |

### For Each Sentence in the AI Note, Ask:
> "Is every claim in this sentence directly supported by the source document?"

- If **yes** → mark as correct, move on
- If **no** → flag the sentence, identify the error type, and note what is wrong

### Severity Rating
For every flagged sentence, rate the severity:

| Rating | Definition |
|---|---|
| **Major** | If left uncorrected, this error could change the diagnosis, treatment plan, or directly harm the patient |
| **Minor** | The error is inaccurate but would not meaningfully change clinical management |

### Recording Your Findings — Part 1

For each error found, fill in the following:

```
Sentence flagged: [copy the problematic sentence here]
Error type: [Fabrication / Negation / Causality]
What is wrong: [explain in one or two sentences what the AI got wrong]
Severity: [Major / Minor]
Supporting evidence: [quote or reference the part of the source document that contradicts or fails to support the AI sentence]
```

---

## PART 2: Omission Review
### Task
Now read the Source Document sentence by sentence. For each clinically relevant piece of information, check whether it appears in the AI-Generated Note.

### What Counts as Clinically Relevant?
Include the following if mentioned in the source:
- Current symptoms, complaints, or reason for visit
- Past medical history, medications, allergies
- Family history, social history (smoking, alcohol, occupation)
- Examination findings
- Diagnoses or clinical impressions
- Treatment plans, prescriptions, referrals, follow-up instructions

### For Each Relevant Sentence in the Source, Ask:
> "Is this information captured somewhere in the AI note?"

- If **yes** → mark as present, move on
- If **no** → flag it as an omission

### Severity Rating
Use the same scale:

| Rating | Definition |
|---|---|
| **Major** | The missing information could change the diagnosis, treatment, or continuity of care if a colleague read only this note |
| **Minor** | The missing information is relevant but its absence would not meaningfully affect clinical management |

### Recording Your Findings — Part 2

For each omission found, fill in the following:

```
Information omitted: [copy or summarize the missing information from the source]
Section it should appear in: [History / Medications / Examination / Assessment / Plan / Other]
Severity: [Major / Minor]
Why it matters: [briefly explain the clinical significance of this omission]
```

---

## PART 3: Overall Assessment
After completing both parts, provide a brief overall judgment:

```
Total hallucinations found: ___
  - Major: ___
  - Minor: ___

Total omissions found: ___
  - Major: ___
  - Minor: ___

Overall safety rating:
[ ] Safe for clinical use as-is
[ ] Safe with minor corrections
[ ] Requires significant revision before clinical use
[ ] Unsafe — do not use without complete review

Additional comments:
[Any patterns you noticed, sections that were consistently problematic, or anything else relevant]
```

---

## Important Reminders
- **Only use the Source Document** to judge hallucinations — do not rely on your own clinical knowledge to fill in gaps
- **Do not penalize the AI** for paraphrasing or summarizing, as long as the meaning is preserved and nothing is added or contradicted
- **If you are unsure** whether something is an error, mark it as flagged with a note explaining your uncertainty — a senior clinician will review these cases
- **Focus on meaning, not wording** — a sentence can be phrased differently from the source and still be correct

---

## Quick Reference Card

| Question | If Yes | If No |
|---|---|---|
| Is this AI sentence fully supported by the source? | Mark correct | Flag as hallucination |
| Is this a fabricated claim? | Fabrication error | — |
| Does the AI contradict the source? | Negation error | — |
| Is this clinically relevant source information in the AI note? | Mark present | Flag as omission |
| Could this error change patient management? | Major | Minor |"""

USER_PROMPT_TEMPLATE = """\
Here are the three documents for your evaluation:

**Source Document:**
{sourcedoc}

**Reference Note:**
{sourcetarget}

**AI-Generated Note:**
{generated_note}"""


def fmt_time(seconds):
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}m {s}s"


def main():
    if len(sys.argv) not in (2, 3):
        print("Usage: python3 evaluate_outputs.py <exp_dir> [encounter_id]")
        print("  e.g. python3 evaluate_outputs.py outputs/20260423/Qwen3.5-4B/aci_bench/clinicalnlp_taskB_test1_0shot")
        sys.exit(1)

    exp_dir = Path(sys.argv[1])
    encounter_id_filter = sys.argv[2] if len(sys.argv) == 3 else None

    if encounter_id_filter:
        target = exp_dir / encounter_id_filter
        if not target.is_dir():
            print(f"No directory found for encounter_id '{encounter_id_filter}' in {exp_dir}")
            sys.exit(1)
        enc_dirs = [target]
    else:
        enc_dirs = sorted([d for d in exp_dir.iterdir() if d.is_dir()])

    if not enc_dirs:
        print(f"No encounter directories found in {exp_dir}")
        sys.exit(1)

    config = load_config(CONFIG_PATH)
    eval_model_name = config["active_eval_model"]
    eval_model_cfg = config["models"][eval_model_name]
    enable_thinking = config.get("active_model_thinking", False)
    gen = eval_model_cfg["generation"]["thinking" if enable_thinking else "non_thinking"]

    # build messages for all encounters
    all_messages = []
    valid_dirs = []
    for enc_dir in enc_dirs:
        sourcedoc_path = enc_dir / "sourcedoc.txt"
        sourcetarget_path = enc_dir / "sourcetarget.txt"
        output_path = enc_dir / "output.txt"

        if not sourcedoc_path.exists() or not sourcetarget_path.exists() or not output_path.exists():
            print(f"[WARN] {enc_dir.name}: missing required files — skipping")
            continue

        user_content = USER_PROMPT_TEMPLATE.format(
            sourcedoc=sourcedoc_path.read_text().strip(),
            sourcetarget=sourcetarget_path.read_text().strip(),
            generated_note=output_path.read_text().strip(),
        )
        all_messages.append([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ])
        valid_dirs.append(enc_dir)

    if not valid_dirs:
        print("No valid encounters to evaluate.")
        sys.exit(1)

    load_start = time.time()
    llm = LLM(
        model=eval_model_cfg["path"],
        dtype=eval_model_cfg["load"]["dtype"],
        tensor_parallel_size=eval_model_cfg["load"]["tensor_parallel_size"],
        gpu_memory_utilization=eval_model_cfg["load"]["gpu_memory_utilization"],
        max_model_len=eval_model_cfg["load"]["max_model_len"],
    )
    load_time = fmt_time(time.time() - load_start)

    sampling_params = SamplingParams(
        temperature=gen["temperature"],
        top_p=gen["top_p"],
        top_k=gen["top_k"],
        min_p=gen["min_p"],
        presence_penalty=gen["presence_penalty"],
        repetition_penalty=gen["repetition_penalty"],
        max_tokens=gen["max_tokens"],
    )

    infer_start = time.time()
    outputs = llm.chat(all_messages, sampling_params,
                       chat_template_kwargs={"enable_thinking": enable_thinking})
    infer_time = fmt_time(time.time() - infer_start)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    batch_metadata = {
        "timestamp": timestamp,
        "eval_model": eval_model_name,
        "thinking": enable_thinking,
        "load": eval_model_cfg["load"],
        "generation": gen,
        "num_evaluated": len(valid_dirs),
        "model_load_time": load_time,
        "inference_time": infer_time,
    }
    (exp_dir / "_eval_batch_metadata.json").write_text(json.dumps(batch_metadata, indent=2))

    for i, (enc_dir, output) in enumerate(zip(valid_dirs, outputs)):
        output_text, thinking_text = extract_thinking(output.outputs[0].text or "")

        if thinking_text:
            (enc_dir / "eval_thinking.txt").write_text(thinking_text)
        (enc_dir / "eval_output.txt").write_text(output_text)

        print(f"[{i+1}/{len(valid_dirs)}] {enc_dir.name}")

    print(f"Done. Evaluated {len(valid_dirs)} encounters.")
    print(f"Model load: {load_time} | Inference: {infer_time}")


if __name__ == "__main__":
    main()
