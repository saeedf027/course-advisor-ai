# Preferences are the default

The Course Advisor AI learner can specify desired budget, language, and class format without losing potentially useful courses.

- Soft preferences affect the estimated match percentage, rather than disqualifying an otherwise source-backed course.
- Budget preference contributes up to -7 points (unknown price: -3; known nonfree when free preferred: -7).
- Language preference contributes up to -4 points (unknown language: -2).
- Delivery format contributes up to -4 points (unknown format: -2).
- The base pedagogical fit still uses topic 35%, learning level 25%, intent 25%, pedagogy 15%. Soft deductions are subsequently applied, with minimum score zero.
- A learner can explicitly mark a constraint mandatory in `settings.hard_constraints` (e.g. accessibility or strict budget). Then Python applies strict filtering; the model must not silently override it.
- The real data analysis fixture now specifies `budget.mode = free` and `hard_constraints = []`. The previous hard-budget configuration prevented every course with undisclosed tuition from being considered.
- This is a heuristically calculated suitability indicator, not a scientific probability of success.
- Source-grounded course identity and HTTPS links are still mandatory; no fabricated courses are allowed.

Automated tests cover scoring, unknown costs, other soft preferences, and explicitly hard budget behavior.
