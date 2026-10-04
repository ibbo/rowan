"""Published SCDDB grades and explicitly labelled legacy estimates.

Labels verified against SCDDB dance pages 5525, 2821, 803 and 15435.
Intensity is an activity measure, not an official difficulty scale.
"""

GRADE_LABELS = {
    1: 'Suitable for everyone (one ghillie)',
    2: 'An experienced partner would be helpful (two ghillies)',
    3: 'For more confident dancers (three ghillies)',
    4: 'Expert-level or unusual dance unsuitable for most programmes',
}


def with_difficulty(dance):
    """Annotate a result without ever overriding a published grade."""
    grade = dance.get('rscds_grade')
    grade = grade if grade in GRADE_LABELS else None
    dance['rscds_grade'] = grade
    dance['rscds_grade_label'] = GRADE_LABELS.get(grade)
    dance['difficulty_source'] = 'SCDDB rscds_grade' if grade else 'unassessed'
    dance['difficulty_estimate'] = None
    intensity = dance.get('intensity')
    if grade is None and intensity is not None and intensity > 0:
        # Preserve the historical bands only as a weak fallback. They are
        # not a conversion to ghillies and need corroboration from the crib.
        band = 'easy' if intensity <= 40 else 'medium' if intensity < 70 else 'hard'
        dance['difficulty_source'] = 'ChatSCD legacy estimate from SCDDB intensity (not an RSCDS grade)'
        dance['difficulty_estimate'] = {
            'level': band,
            'basis': 'SCDDB intensity',
            'caveat': 'Activity-based proxy only; check formations, transitions and dancer familiarity.',
        }
    return dance


DIFFICULTY_GUIDANCE = """
DIFFICULTY AND DANCE SELECTION:
- Prefer the rscds_grade returned by tools over any intensity-based estimate.
  SCDDB labels: 1 = suitable for everyone (one ghillie); 2 = an experienced
  partner would be helpful (two ghillies); 3 = for more confident dancers
  (three ghillies); 4 = expert-level or unusual dance unsuitable for most programmes.
  Do NOT call grade 4 "four ghillies": SCDDB supplies no such ghillie label.
- Use min_rscds_grade/max_rscds_grade and sort_by_rscds_grade on find_dances
  for published-grade searches. For one-ghillie dances use max_rscds_grade=1.
  These filters exclude ungraded dances. Preserve RSCDS publication filters
  separately: a grade is not proof of publication by RSCDS.
- For dances without a grade (including non-RSCDS dances), use
  has_rscds_grade=False and, if useful, the legacy min_intensity/max_intensity
  filters (historical easy <=40, medium >40 and <70, hard >=70). Inspect the
  crib/formations/transitions and consider the dancers' familiarity before
  recommending them. Always call this a ChatSCD estimate, never an official
  rating or a difficulty rating supplied by SCDDB. SCDDB supplies the raw
  intensity; ChatSCD supplies the historical easy/medium/hard interpretation.
  A null, -1 or 0 grade means ungraded, never easier than grade 1.
- Intensity measures activity, not cognitive difficulty. Never use it to
  override a published grade or convert it into ghillies. When neither grade
  nor useful evidence exists, say difficulty is unassessed.
- A one-ghillie grade is a programme guide, not a guarantee that absolute
  beginners can dance it without teaching. Retain the source label in answers.
"""
