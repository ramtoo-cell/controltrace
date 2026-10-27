Preliminary runs, INVALIDATED and excluded from all reported numbers.
Two benchmark defects were found by error analysis of these runs:
 1. The prompt did not define the four conclusion labels (26/31 Opus errors were control_deficiency vs violation_confirmed).
 2. Generated dates were inconsistent with stated durations (e.g. "lapsed 2026-01-05, 53 months before 2026-10-15").
Both were fixed in the generator/prompt and the evaluation was rerun from scratch.
