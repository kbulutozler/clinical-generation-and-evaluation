# Qwen Evaluation Analysis

Base directory: `outputs/aces/20260501`

This report uses only `evals/Qwen3.5-27B/eval_output.txt` files. MedGemma evaluator outputs are intentionally ignored.

## Evaluation System Prompt

The Qwen evaluator used this system prompt:

```text
You are a clinical documentation expert evaluating AI-generated clinical notes for
accuracy and completeness.

---
HALLUCINATION TYPES (information in the note NOT supported by the dialogue):
- fabrication: stated something not mentioned in the dialogue at all
- negation: reversed or contradicted a clinical fact from the dialogue
- causality: speculated a cause for a condition without explicit support in the dialogue
- contextual: mixed in unrelated clinical information

OMISSION TYPES (relevant information from the dialogue MISSING from the note):
- current_issues: details about the current presentation were dropped
- pmfs: past medical history, medications, allergies, family or social history were dropped
- plan: management plan, prescriptions, follow-up, or patient instructions were dropped

SEVERITY:
- major: if left uncorrected, could change the diagnosis or management of the patient
- minor: inaccurate or incomplete but unlikely to change clinical decision-making

---
SCORING:
Start at 1.0. Deduct:
- 0.25 per major hallucination
- 0.05 per minor hallucination
- 0.10 per major omission
- 0.02 per minor omission
Clamp final score to [0.0, 1.0]. Never return a value below 0.0.

---
Return ONLY valid JSON in this exact format:

{
  "hallucinations": [
    {
      "type": "<fabrication|negation|causality|contextual>",
      "severity": "<major|minor>",
      "text_in_note": "<exact phrase from generated note>",
      "explanation": "<why this is a hallucination>"
    }
  ],
  "omissions": [
    {
      "type": "<current_issues|pmfs|plan>",
      "severity": "<major|minor>",
      "text_in_dialogue": "<what was said in the dialogue>",
      "explanation": "<why this omission matters clinically>"
    }
  ],
  "score": <float 0.0-1.0>
}
```

## Evaluation Rubric

The evaluator compares each generated note against the doctor-patient dialogue and reference note. It returns hallucinations, omissions, and a score.

Hallucination types: `fabrication`, `negation`, `causality`, `contextual`.

| Hallucination Type | Meaning |
| --- | --- |
| fabrication | Information stated in the generated note but not mentioned in the dialogue. |
| negation | The generated note reverses or contradicts a clinical fact from the dialogue. |
| causality | The generated note speculates about a cause without explicit support in the dialogue. |
| contextual | The generated note mixes in unrelated or mismatched clinical context. |

Omission types: `current_issues`, `pmfs`, `plan`.

| Omission Type | Meaning |
| --- | --- |
| current_issues | Details about the current presentation, symptoms, exam, or results were dropped. |
| pmfs | Past medical history, medications, allergies, family history, or social history were dropped. |
| plan | Management plan, prescriptions, follow-up, referrals, or patient instructions were dropped. |

Scoring starts at 1.0, then deducts 0.25 per major hallucination, 0.05 per minor hallucination, 0.10 per major omission, and 0.02 per minor omission. Scores are clamped to [0.0, 1.0].

All score statistics below use a deterministic manual recomputation from the evaluator's listed hallucinations and omissions, not the evaluator's self-reported `score` field.

## Data Quality

- Parsed Qwen eval outputs: `239`
- Malformed Qwen eval outputs: `1`
- Evaluator score arithmetic failures: `31` of `239` valid outputs had a self-reported `score` that did not match the rubric score recomputed from its own listed errors.
- Plot: `analysis/qwen_eval_analysis_20260501.png`

## Score Summary

| Run | Valid N | Bad JSON | Mean | Median | Min | Max | Std | >=0.8 | >=0.7 | >=0.5 | <0.3 | Zeros |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3.5-2B 0-shot | 40 | 0 | 0.165 | 0.120 | 0.000 | 0.550 | 0.177 | 0 | 0 | 3 | 31 | 14 |
| Qwen3.5-4B 0-shot | 39 | 1 | 0.533 | 0.550 | 0.000 | 0.900 | 0.226 | 7 | 9 | 27 | 7 | 1 |
| Qwen3.5-9B 0-shot | 40 | 0 | 0.584 | 0.600 | 0.150 | 0.850 | 0.184 | 4 | 15 | 29 | 4 | 0 |
| Qwen3.5-27B 0-shot | 40 | 0 | 0.670 | 0.700 | 0.280 | 0.850 | 0.155 | 10 | 23 | 35 | 1 | 0 |
| medgemma-27b-text-it 0-shot | 40 | 0 | 0.634 | 0.660 | 0.080 | 0.850 | 0.155 | 4 | 18 | 34 | 1 | 0 |
| medgemma-27b-text-it 1-shot | 40 | 0 | 0.659 | 0.720 | 0.130 | 0.900 | 0.172 | 8 | 23 | 35 | 3 | 0 |

## Error Totals

| Run | Hallucinations | Hallucinations / case | Major H | Minor H | Omissions | Omissions / case | Major O | Minor O | Valid N |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3.5-2B 0-shot | 270 | 6.75 | 101 | 169 | 87 | 2.17 | 13 | 74 | 40 |
| Qwen3.5-4B 0-shot | 210 | 5.38 | 33 | 177 | 43 | 1.10 | 4 | 39 | 39 |
| Qwen3.5-9B 0-shot | 208 | 5.20 | 26 | 182 | 36 | 0.90 | 4 | 32 | 40 |
| Qwen3.5-27B 0-shot | 188 | 4.70 | 16 | 172 | 29 | 0.72 | 0 | 29 | 40 |
| medgemma-27b-text-it 0-shot | 184 | 4.60 | 21 | 163 | 46 | 1.15 | 4 | 42 | 40 |
| medgemma-27b-text-it 1-shot | 192 | 4.80 | 15 | 177 | 44 | 1.10 | 2 | 42 | 40 |

## Hallucinations by Type

| Run | fabrication | negation | causality | contextual |
| --- | --- | --- | --- | --- |
| Qwen3.5-2B 0-shot | 176 (4.40/case) | 55 (1.38/case) | 13 (0.33/case) | 26 (0.65/case) |
| Qwen3.5-4B 0-shot | 156 (4.00/case) | 24 (0.62/case) | 6 (0.15/case) | 24 (0.62/case) |
| Qwen3.5-9B 0-shot | 156 (3.90/case) | 20 (0.50/case) | 7 (0.17/case) | 25 (0.62/case) |
| Qwen3.5-27B 0-shot | 158 (3.95/case) | 7 (0.17/case) | 8 (0.20/case) | 15 (0.38/case) |
| medgemma-27b-text-it 0-shot | 155 (3.88/case) | 12 (0.30/case) | 5 (0.12/case) | 12 (0.30/case) |
| medgemma-27b-text-it 1-shot | 161 (4.03/case) | 11 (0.28/case) | 2 (0.05/case) | 18 (0.45/case) |

## Omissions by Type

| Run | current_issues | pmfs | plan |
| --- | --- | --- | --- |
| Qwen3.5-2B 0-shot | 38 (0.95/case) | 17 (0.42/case) | 32 (0.80/case) |
| Qwen3.5-4B 0-shot | 16 (0.41/case) | 13 (0.33/case) | 14 (0.36/case) |
| Qwen3.5-9B 0-shot | 11 (0.28/case) | 12 (0.30/case) | 13 (0.33/case) |
| Qwen3.5-27B 0-shot | 8 (0.20/case) | 7 (0.17/case) | 14 (0.35/case) |
| medgemma-27b-text-it 0-shot | 13 (0.33/case) | 15 (0.38/case) | 18 (0.45/case) |
| medgemma-27b-text-it 1-shot | 15 (0.38/case) | 14 (0.35/case) | 15 (0.38/case) |

## Negation Examples

Examples where a selected generated note says something contradicted by the source dialogue. This table is limited to Qwen3.5-4B, Qwen3.5-9B, Qwen3.5-27B, and MedGemma 0/1-shot. The reference comes from the matched line in `sourcedoc.txt`; only the reference words are bolded.

| Run | Encounter | Severity | Model said | Reference in dialog | Evaluator explanation |
| --- | --- | --- | --- | --- | --- |
| Qwen3.5-4B 0-shot | D2N090 | minor | DOB: 61-Years Old | L5: [doctor] so , albert is a **62-year-old male** , with a past medical history significant for depression , type 2 diabetes , and kidney transplant , who is here today for emergency room follow-up . | The dialogue explicitly states the patient is a "62-year-old male". Recording age as 61 contradicts the verified clinical fact provided by the physician. |
| Qwen3.5-4B 0-shot | D2N098 | minor | Acute fracture, dislocation, or neuropathic involvement ruled out clinically. | L20: [doctor] okay . left shoulder and elbow , tender sa space , no warmth , erythema or deformity . positive hawkins-kennedy and neer's test . normal proximal and distar , distal upper extremity strength . intact median radial ulnar sensation and abduction to 90 degrees . normal empty tan , can test . okay , mr . james , w-what i think you are dealing with is impingement syndrome of your left shoulder . **i do n't think there's an additional injury** or issue with your wrist , but because everything is connected , you're experiencing pain in your wrist because of your shoulder . we do see this type of issue when someone has a fall , so it's good you came to see us , you came in to see us so we could help . | The dialogue expresses uncertainty ('I don't think there's an additional injury') rather than definitively ruling out fractures/dislocations without imaging data. |
| Qwen3.5-9B 0-shot | D2N093 | minor | When questioned about orthopnea, the patient reported no current inability to lie flat. | L16: [patient] um , i'm **a little uncomfortable when i wake up in the morning** and i feel pretty stiff . and , and , like , it takes me a little while to adjust to walking when i get up . | The patient stated he is 'a little uncomfortable when i wake up in the morning', suggesting some degree of orthopnea/discomfort. The note characterizes this as 'no current inability', which minimizes the patient's reported symptom. |
| Qwen3.5-9B 0-shot | D2N094 | minor | if symptoms persist or improve. | L38: [doctor] okay . um ... so with your x-ray , and with your exam , looks like you have a sprain of your distar- distal interphalangeal joint . it's called your dip joint , of your right index finger , and so what we're gon na do for that is we're gon na put a splint on that right finger . i'm gon na give you a strong antiinflammatory called mobic . you'll take 15 milligrams once a day . i'll prescribe 14 of those for you . and i want you to come back and see me in two weeks , and let's **make sure it's all healed up** and if we need to start any hand therapy at that point , then we can . do you have any questions for me ? | The dialogue states therapy consideration depends on healing ('make sure it's all healed up'), and the reference note specifies 'if she is unimproved'. Stating 'if symptoms... improve' as a trigger for therapy contradicts standard clinical logic and the dialogue's intent. |
| Qwen3.5-27B 0-shot | D2N100 | major | Start Retin-A 0.1% topical gel | L27: [doctor] yes . i would like to start with a topical therapy first . every morning , you will wash your face with a mild cleanser then use a moisturizer labeled , " noncomedogenic , " with sunscreen spf 30 or higher . this means it wo n't clog your pores . now , in the evening , wash your face with the same cleanser and allow it to dry . apply **adapalene , 0.1 % cream** , in a thin layer to the areas you generally get acne . i want you to start off using this a few nights a week and slowly work up to using it every night . if it is ... excuse me , if it is very expensive or not covered by insurance , you can try different gel over the counter . you can follow that with clean and clear persa-gel in a thin layer , or where you generally get acne . and... | While the Pharmacotherapy section correctly identifies 'Adapalene', the Instructions section incorrectly specifies 'Retin-A' (Tretinoin). The dialogue explicitly prescribes 'adapalene, 0.1% cream'. This contradiction creates a medication error risk in the discharge instructions. |
| Qwen3.5-27B 0-shot | D2N103 | minor | Cardiovascular: Regular rate, irregularly irregular rhythm | L24: [doctor] okay then . i'm going to be using my status post template , ms. sanchez , please lie down on the table here and we'll get started . all right . can you turn your head to the left . head and neck no jvd detected . you can turn back now and just take a couple of deep breaths for me please . okay , that's good . and lungs have reduced breath , but auscultation and percussion are clear . okay . breath normally , i'm just going to listen to your heart . rhythm is **irregularly irregular** . | The dialogue describes the rhythm as 'irregularly irregular' consistent with AFib. Describing the rate as 'Regular' contradicts the inherent variability of AFib rhythm described in the dialogue ('doesn't have a pattern'). |
| medgemma-27b-text-it 0-shot | D2N089 | minor | Protonix 40 mg PO daily (*dose assumed based on standard practice, not explicitly stated*) | L37: [doctor] hey dragon , order a referral to cardiology . and for your last problem , the reflux , you know , i wanna- i want you to just **continue on the protonix , 40 mg a day** . continue with your dietary modifications , you know , avoiding coffee and spicy foods , that type of thing . okay ? and then let me know if you have any other issues with that , okay ? | The dialogue explicitly states the doctor's plan to 'continue on the protonix , 40 mg a day'. Claiming the dose was not explicitly stated contradicts the dialogue. |
| medgemma-27b-text-it 0-shot | D2N098 | minor | The referred elbow pain is likely secondary to the shoulder pathology. | L20: [doctor] okay . left shoulder and elbow , tender sa space , no warmth , erythema or deformity . positive hawkins-kennedy and neer's test . normal proximal and distar , distal upper extremity strength . intact median radial ulnar sensation and abduction to 90 degrees . normal empty tan , can test . okay , mr . james , w-what i think you are dealing with is impingement syndrome of your left shoulder . i do n't think there's an additional injury or issue with your wrist , but because everything is connected , you're experiencing pain in your **wrist because of your shoulder** . we do see this type of issue when someone has a fall , so it's good you came to see us , you came in to see us so we could help . | The doctor explicitly explained in the dialogue that the patient is experiencing pain in their 'wrist because of your shoulder', whereas the note attributes the referred pain to the elbow, contradicting the provider's specific clinical reasoning in the conversation. |
| medgemma-27b-text-it 1-shot | D2N099 | minor | Randy Gutierrez is a 1 year old male | L71: [doctor] yes , that's a great question . you **do n't give honey to kids under a year** , instead , you can give them agave , which is a different type of nectar . um , now you can give honey to his older sister , that is okay , but for him , it would not be very good because his stomach acid's not good enough to break down the botulism spores . so , it'd cause him harm . um , you should look at the package of say , honey nut cheerios . it says right on there to not give it to a baby . | While the DOB is correct, the doctor's counseling regarding honey ('don't give honey to kids under a year') and Zarbee's dosage ('under a year') strongly implies the patient is under 1 year old. Stating '1 year old' contradicts the clinical context provided in the dialogue. |
| medgemma-27b-text-it 1-shot | D2N101 | major | Denies interest in breastfeeding. | L64: [patient] yeah . **i do n't know if i'm interested in breastfeeding** . | In the dialogue, the patient explicitly states 'i do n't know if I'm interested in breastfeeding', indicating uncertainty. The note falsely documents this as a definitive denial, which misrepresents patient preferences regarding a key surgical risk (loss of lactation capability). |

## MedGemma 1-Shot vs 0-Shot

Both are evaluated by Qwen3.5-27B.

Largest 1-shot improvements:

| Encounter | 0-shot | 1-shot | Delta |
| --- | --- | --- | --- |
| D2N097 | 0.380 | 0.830 | 0.450 |
| D2N122 | 0.580 | 0.900 | 0.320 |
| D2N100 | 0.530 | 0.790 | 0.260 |
| D2N091 | 0.330 | 0.550 | 0.220 |
| D2N105 | 0.590 | 0.810 | 0.220 |
| D2N126 | 0.530 | 0.730 | 0.200 |
| D2N094 | 0.700 | 0.880 | 0.180 |
| D2N107 | 0.600 | 0.780 | 0.180 |

Largest 1-shot regressions:

| Encounter | 0-shot | 1-shot | Delta |
| --- | --- | --- | --- |
| D2N088 | 0.790 | 0.350 | -0.440 |
| D2N108 | 0.530 | 0.130 | -0.400 |
| D2N127 | 0.490 | 0.290 | -0.200 |
| D2N104 | 0.700 | 0.510 | -0.190 |
| D2N093 | 0.730 | 0.580 | -0.150 |
| D2N121 | 0.650 | 0.510 | -0.140 |
| D2N110 | 0.800 | 0.680 | -0.120 |
| D2N111 | 0.700 | 0.580 | -0.120 |