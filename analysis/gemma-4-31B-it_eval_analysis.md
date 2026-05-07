# gemma-4-31B-it Evaluation Analysis

Base directory: `outputs/final`

This report uses only `evals/gemma-4-31B-it/eval_output.txt` files under the final output layout.

## Evaluation System Prompt

The gemma-4-31B-it evaluator used this system prompt:

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

- Parsed eval outputs: `360`
- Malformed eval outputs: `0`
- Evaluator score arithmetic failures: `8` of `360` valid outputs had a self-reported `score` that did not match the rubric score recomputed from its own listed errors.
- Plot: `analysis/gemma-4-31B-it_eval_analysis.png`

## Score Summary

| Run | Valid N | Bad JSON | Mean | Median | Min | Max | Std | >=0.8 | >=0.7 | >=0.5 | <0.3 | Zeros |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3.5-2B 0-shot | 40 | 0 | 0.217 | 0.165 | 0.000 | 0.660 | 0.211 | 0 | 0 | 6 | 26 | 12 |
| Qwen3.5-4B 0-shot | 40 | 0 | 0.615 | 0.615 | 0.030 | 0.900 | 0.208 | 11 | 16 | 31 | 4 | 0 |
| gemma-4-E2B-it 0-shot | 40 | 0 | 0.786 | 0.830 | 0.460 | 0.980 | 0.121 | 24 | 32 | 39 | 0 | 0 |
| gemma-4-E4B-it 0-shot | 40 | 0 | 0.836 | 0.850 | 0.600 | 0.960 | 0.092 | 31 | 35 | 40 | 0 | 0 |
| Qwen3.5-9B 0-shot | 40 | 0 | 0.640 | 0.650 | 0.200 | 0.950 | 0.160 | 10 | 15 | 34 | 1 | 0 |
| gemma-4-26B-A4B-it 0-shot | 40 | 0 | 0.906 | 0.930 | 0.650 | 1.000 | 0.073 | 36 | 39 | 40 | 0 | 0 |
| medgemma-27b-text-it 0-shot | 40 | 0 | 0.676 | 0.650 | 0.430 | 0.900 | 0.144 | 14 | 18 | 36 | 0 | 0 |
| medgemma-27b-text-it 1-shot | 40 | 0 | 0.682 | 0.715 | 0.230 | 0.950 | 0.157 | 12 | 24 | 35 | 1 | 0 |
| Qwen3.5-27B 0-shot | 40 | 0 | 0.705 | 0.740 | 0.350 | 0.900 | 0.128 | 11 | 28 | 37 | 0 | 0 |

## Error Totals

| Run | Hallucinations | Hallucinations / case | Major H | Minor H | Omissions | Omissions / case | Major O | Minor O | Valid N |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3.5-2B 0-shot | 333 | 8.32 | 82 | 251 | 43 | 1.07 | 7 | 36 | 40 |
| Qwen3.5-4B 0-shot | 223 | 5.58 | 20 | 203 | 13 | 0.33 | 0 | 13 | 40 |
| gemma-4-E2B-it 0-shot | 92 | 2.30 | 11 | 81 | 47 | 1.18 | 10 | 37 | 40 |
| gemma-4-E4B-it 0-shot | 106 | 2.65 | 3 | 103 | 30 | 0.75 | 1 | 29 | 40 |
| Qwen3.5-9B 0-shot | 220 | 5.50 | 16 | 204 | 10 | 0.25 | 0 | 10 | 40 |
| gemma-4-26B-A4B-it 0-shot | 63 | 1.57 | 1 | 62 | 20 | 0.50 | 0 | 20 | 40 |
| medgemma-27b-text-it 0-shot | 224 | 5.60 | 7 | 217 | 14 | 0.35 | 1 | 13 | 40 |
| medgemma-27b-text-it 1-shot | 210 | 5.25 | 9 | 201 | 21 | 0.53 | 0 | 21 | 40 |
| Qwen3.5-27B 0-shot | 214 | 5.35 | 5 | 209 | 5 | 0.12 | 0 | 5 | 40 |

## Hallucinations by Type

| Run | fabrication | negation | causality | contextual |
| --- | --- | --- | --- | --- |
| Qwen3.5-2B 0-shot | 261 (6.53/case) | 45 (1.12/case) | 9 (0.23/case) | 18 (0.45/case) |
| Qwen3.5-4B 0-shot | 180 (4.50/case) | 20 (0.50/case) | 12 (0.30/case) | 11 (0.28/case) |
| gemma-4-E2B-it 0-shot | 67 (1.68/case) | 18 (0.45/case) | 1 (0.03/case) | 6 (0.15/case) |
| gemma-4-E4B-it 0-shot | 93 (2.33/case) | 4 (0.10/case) | 5 (0.12/case) | 4 (0.10/case) |
| Qwen3.5-9B 0-shot | 184 (4.60/case) | 14 (0.35/case) | 12 (0.30/case) | 10 (0.25/case) |
| gemma-4-26B-A4B-it 0-shot | 53 (1.32/case) | 2 (0.05/case) | 6 (0.15/case) | 2 (0.05/case) |
| medgemma-27b-text-it 0-shot | 209 (5.22/case) | 6 (0.15/case) | 7 (0.17/case) | 2 (0.05/case) |
| medgemma-27b-text-it 1-shot | 197 (4.92/case) | 7 (0.17/case) | 4 (0.10/case) | 2 (0.05/case) |
| Qwen3.5-27B 0-shot | 193 (4.83/case) | 4 (0.10/case) | 12 (0.30/case) | 5 (0.12/case) |

## Omissions by Type

| Run | current_issues | pmfs | plan |
| --- | --- | --- | --- |
| Qwen3.5-2B 0-shot | 20 (0.50/case) | 6 (0.15/case) | 17 (0.42/case) |
| Qwen3.5-4B 0-shot | 5 (0.12/case) | 6 (0.15/case) | 2 (0.05/case) |
| gemma-4-E2B-it 0-shot | 24 (0.60/case) | 14 (0.35/case) | 9 (0.23/case) |
| gemma-4-E4B-it 0-shot | 15 (0.38/case) | 7 (0.17/case) | 8 (0.20/case) |
| Qwen3.5-9B 0-shot | 4 (0.10/case) | 3 (0.07/case) | 3 (0.07/case) |
| gemma-4-26B-A4B-it 0-shot | 10 (0.25/case) | 7 (0.17/case) | 3 (0.07/case) |
| medgemma-27b-text-it 0-shot | 6 (0.15/case) | 2 (0.05/case) | 6 (0.15/case) |
| medgemma-27b-text-it 1-shot | 11 (0.28/case) | 6 (0.15/case) | 4 (0.10/case) |
| Qwen3.5-27B 0-shot | 3 (0.07/case) | 2 (0.05/case) | 0 (0.00/case) |

## Negation Examples

Examples where a selected generated note says something contradicted by the source dialogue. The reference comes from the matched line in `sourcedoc.txt`; only the reference words are bolded.

| Run | Encounter | Severity | Model said | Reference in dialog | Evaluator explanation |
| --- | --- | --- | --- | --- | --- |
| Qwen3.5-2B 0-shot | D2N095 | major | Uncontrolled hypertensive disorder | L34: [doctor] okay ? hey , dragon , show me the vital signs . so good- you know , here in the office , your vital signs look great . your blood pressure's **really well controlled** , which is good . so that's a good job . so i'm going to take a listen to your heart and lungs . i'm going to examine your back , and i'm going to let you know what i find . okay ? | The dialogue explicitly states the patient's blood pressure is 'really well controlled' and 'looking great'. |
| Qwen3.5-2B 0-shot | D2N098 | major | pain levels decrease with mild lifting (<15–20 lbs) | L9: [patient] well , i've always hit the gym and lifted weights . i've been trying to keep with my routine of two days a week , but it's been hard . **the pain is worse when i lift** , and i have n't been able to lift more than 15 or 20 pounds which is very frustrating . | The patient explicitly stated that 'the pain is worse when i lift' and that he has been unable to lift more than 15-20 pounds. The note incorrectly states that pain decreases with this activity. |
| Qwen3.5-4B 0-shot | D2N098 | minor | schedule PT appointments at 2-day intervals | L22: [doctor] well , we have a few options you can try . first option would be to start with physical therapy . i would recommend **two sessions per week** as well as any other exercises they give you to do at home . we can start there and if that does n't improve your pain , then we could try a cortisone injection . | The doctor specifically recommended 'two sessions per week', whereas '2-day intervals' would result in 3-4 sessions per week. |
| Qwen3.5-4B 0-shot | D2N101 | minor | Expresses interest in breastfeeding but acknowledges uncertainty about capacity after surgery | L64: [patient] yeah . **i do n't know if i'm interested in breastfeeding** . | The patient explicitly stated, 'i don't know if i'm interested in breastfeeding,' which contradicts the note's claim that she 'expresses interest'. |
| gemma-4-E2B-it 0-shot | D2N090 | minor | Heart sounds normal. | L56: [doctor] okay . so , on your physical exam , everything looks really good . um , you do n't appear in any distress at this time . i do n't appreciate any carotid bruits . your heart , on your heart exam , i do hear that **slight 2/6 systolic ejection murmur** , but we heard that in the past . | This contradicts the statement in the previous sentence of the note stating that a 'Slight 2/6 systolic ejection murmur' was noted. |
| gemma-4-E2B-it 0-shot | D2N096 | minor | Tylenol provided temporary, but ineffective, relief | L10: [patient] no , i did not take any pain medications . actually , i did . i did take a tylenol for two or three days , but then that **did n't help at all** . so , uh , the reason why it started or when it started to happen is- | The patient explicitly stated that Tylenol 'did n't help at all,' which contradicts the note's claim that it provided 'temporary' relief. |
| gemma-4-E4B-it 0-shot | D2N103 | major | non-exertional chest discomfort | L7: [patient] no , not really . but , you know , i'm still getting some chest pains sometimes , and my breathing gets shallow . but , i guess i'm learning what i can and ca n't do . uh , so if i feel like that , if i'm , like , **exerting myself** , i slow down a bit which helps , and then when i go back to it later , i can usually finish whatever i was doing . | The patient explicitly states that the chest pain and shallow breathing occur when she is 'exerting myself' and that 'slowing down' helps, meaning the symptoms are exertional. |
| gemma-4-E4B-it 0-shot | D2N127 | minor | Side-to-Side/Rotation: Limited/Negative | L53: [doctor] okay so pain on palpation both on the bony process and on the muscle can you move your neck from side to side can you move your neck can you swive it side to side no no alright so i'm i'm seeing i'm seeing some range of movement **moderate range of movement** that's fine okay i so when can you bend your neck forward that that's your whole body just just the neck are you capable of bending up | The doctor explicitly stated he saw 'moderate range of movement' and that it was 'fine' for side-to-side movement. |
| Qwen3.5-9B 0-shot | D2N099 | major | Backup Prescription (Antibiotics) | L62: [doctor] all right . so , he's just kind of getting started with this , and i think we're seeing something viral right now . often sinus infections will start out as a virus and then will become bacterial infections if left alone and does n't go away . but , **i do n't think he needs any antibiotics , at least not at this point in time** . um , keep up with the fluids , rest , and i would watch him very carefully for a barking cough . if he does get a barky cough , then that tends to be a little bit more significant and a little more severe . so , if he develops a barky cough , i want you to give him a half a teaspoon of his sister's medicine . | The note identifies the standby medication as an antibiotic. However, the doctor explicitly states, 'i don't think he needs any antibiotics, at least not at this point in time,' and prescribes the medication specifically for a 'barky cough' (suggestive of croup/laryngotracheitis, typically treated with steroids, not antibiotics). |
| Qwen3.5-9B 0-shot | D2N108 | minor | inconsistent medication compliance | L20: [patient] **i take my medication** but i do n't check my sugar all the time | The patient explicitly stated, 'i take my medication,' although he admitted to not checking his sugar regularly. |
| gemma-4-26B-A4B-it 0-shot | D2N104 | minor | bruises appear frequently without any known trauma or significant impact | L18: [patient] well , i just wanted to know why i was getting all these bruises here , so like **when i bump myself** . i do n't know where they're coming from . | The patient explicitly mentioned the bruises happen 'when i bump myself,' which contradicts the note's statement that they occur without known trauma. |
| medgemma-27b-text-it 0-shot | D2N101 | minor | Inspection reveals symmetrical breasts | L43: [doctor] okay , that's great . all right . so what we'll do is we'll go ahead and take a look . i'm gon na take a couple of measurements . and we'll kinda talk about the surgery afterwards . um , so go ahead and stand up for me , julia . okay . so , looking at the measurements , it looks like **one breast is a little lower than the other** . | The doctor explicitly noted during the exam that 'one breast is a little lower than the other' and his internal note described them as 'asymmetrical'. |
| medgemma-27b-text-it 0-shot | D2N110 | major | Foot Exam (Left Foot): Normal inspection. Palpable DP and PT pulses. | L31: ...is ninety eight . one your vital signs look good your heart rate is seventy two respirations sixteen blood pressure is one ten over sixty five okay so on your foot exam let's see there is a one by two inch circular wound on the dorsal aspect of the lateral right foot it is just proximal to the right fifth to the fifth mtp joint and there is some yellow slough present with minimal granulation tissue there's no surrounding erythema or cellulitis and there's no evidence of fluid collection there's no necrosis there is no odor i do not appreciate any bony exposure on on vascular exam there are palpable bilateral femoral and popliteal pulses there are **no palpable dp or pt pulses** but doppler signs are present okay so does this hurt when i touch it here | The doctor explicitly stated in the dialogue that there were 'no palpable dp or pt pulses' (plural), implying both feet were affected. The note contradicts this by stating the left foot pulses were palpable. |
| medgemma-27b-text-it 1-shot | D2N099 | major | Randy Gutierrez is a 1 year old male | L69: [doctor] okay . we'll do the same thing with him , as long as nothing gets worse , and we'll see him back in one week . so , it wo n't get rid of a regular cough . he can use zarbee's , but use the dose for kids **under a year of age** . so , if you wan na get some of that , you can definitely try that for him , it can help out a little bit with the regular cough . | The doctor explicitly mentions using doses for kids 'under a year of age' and avoiding honey for kids 'under a year,' indicating the patient is an infant under 12 months. Stating he is 1 year old contradicts this clinical status, which is critical for medication dosing and safety. |
| medgemma-27b-text-it 1-shot | D2N108 | major | 1 x 2 cm circular wound | L25: ...that's definitely pretty high yeah you definitely if your if your pcp has n't gotten created treatment plan for you definitely need to go back and see them so you can get that controlled alright so let me do a quick physical exam on your foot here today your vital signs look normal you do n't have a fever so let me just take a look at your foot so on your foot exam there is a **one by two inch** circular wound on the dorsal aspect of the lateral right foot so it's just proximal to the fifth mtp joint there is some redness some drainage present you have some edema around it there is fluid like you said that's coming out of it i do n't see any necrosis you do n't have any odor and i do n't appreciate any bony exposure so it pretty much is like you sai... | The doctor explicitly stated the wound was 'one by two inch'. 1x2 cm is significantly smaller than 1x2 inches (approx 2.5 x 5 cm), which is a major clinical discrepancy. |
| Qwen3.5-27B 0-shot | D2N104 | minor | Spontaneous ecchymoses (bruising) | L18: [patient] well , i just wanted to know why i was getting all these bruises here , so like **when i bump myself** . i do n't know where they're coming from . | The note describes the bruising as 'spontaneous,' but the patient explicitly stated that the bruises occur 'when i bump myself,' indicating they are trauma-induced, not spontaneous. |
| Qwen3.5-27B 0-shot | D2N111 | minor | Daily PRN | L61: ...r an x-ray and when you come back we can have that discussion alright so i reviewed the results of your right knee x-ray which showed no evidence of fracture or bony abnormality so let's talk about my assessment and plan alright so for your first problem of right knee pain i think you have a lateral a lateral ligament strain i wan na prescribe some meloxicam which is gon na be **fifteen milligrams daily** for pain and swelling i'm gon na refer you to physical therapy to help strengthen the muscles around the area and to prevent further injury if you're still having pain we can do further imaging imaging but like this is a common injury that tends to heal on its own for your second problem with hypertension i wan na continue the lisinopril at twenty m... | The doctor prescribed Meloxicam 'fifteen milligrams daily', whereas 'PRN' means as needed, which contradicts a daily scheduled dosage. |


## MedGemma 1-Shot vs 0-Shot

Both are evaluated by gemma-4-31B-it.

Largest 1-shot improvements:

| Encounter | 0-shot | 1-shot | Delta |
| --- | --- | --- | --- |
| D2N107 | 0.500 | 0.850 | 0.350 |
| D2N097 | 0.500 | 0.830 | 0.330 |
| D2N103 | 0.430 | 0.730 | 0.300 |
| D2N114 | 0.430 | 0.730 | 0.300 |
| D2N100 | 0.580 | 0.830 | 0.250 |
| D2N115 | 0.500 | 0.700 | 0.200 |
| D2N126 | 0.580 | 0.750 | 0.170 |
| D2N119 | 0.580 | 0.740 | 0.160 |

Largest 1-shot regressions:

| Encounter | 0-shot | 1-shot | Delta |
| --- | --- | --- | --- |
| D2N106 | 0.850 | 0.450 | -0.400 |
| D2N121 | 0.550 | 0.230 | -0.320 |
| D2N118 | 0.800 | 0.530 | -0.270 |
| D2N116 | 0.850 | 0.600 | -0.250 |
| D2N099 | 0.550 | 0.380 | -0.170 |
| D2N089 | 0.550 | 0.400 | -0.150 |
| D2N117 | 0.850 | 0.700 | -0.150 |
| D2N120 | 0.900 | 0.800 | -0.100 |