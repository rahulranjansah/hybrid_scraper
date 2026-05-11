# LLM-as-a-Judge Pipeline

Goal: benchmark `combined_scraper/ai_scorer.py` against human labels, then
train an LLM judge that matches the human.

## Stages

```
  Google Sheet (human labels)                     combined_scraper results
        |                                               |
        v                                               v
  [Step 1] parse_human_labels  ..............  [Step 2] align_ai_scores
        |   IO/step1_parse/                            |   IO/step2_align/
        v                                               v
              +-------- join on LinkedIn URL / name --------+
                                   |
                                   v
                      IO/step3_benchmark/ai_vs_human.csv
                                   |
                       (inspect disagreements, iterate)
                                   |
                                   v
              [Step 4] llm_judge    (new prompt, grounded
                       IO/step4_judge/   in real human remarks)
                                   |
                                   v
              [Step 5] confusion matrix, agreement metrics
                       IO/step5_report/
```

## Conventions

- **Plans/** — plans, backlogs, open questions, design notes. No data.
- **IO/** — every stage gets a folder `IO/stepN_<name>/` holding its
  input artifacts, intermediate files, and outputs. A stage should be
  re-runnable from what's in its folder.
- **step*.py** — one runnable script per stage at the `judge/` root.
- **Baby steps.** One script per commit. Verify output before moving on.
