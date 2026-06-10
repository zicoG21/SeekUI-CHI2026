# Small Manual / Realistic Absent Validation Protocol

Last updated: 2026-06-10

## Goal

Reduce the main threat to validity: current absent examples are synthetic target swaps. A small manually verified benchmark can test whether the same findings hold for realistic target-present and target-absent UI queries.

## Minimal Dataset

Target size:

```text
100-200 GUI-target pairs
50% present
50% absent
```

Recommended first version:

```text
100 examples total
50 present
50 absent
```

## Sampling

Present examples:

- Sample from existing VSGUI examples.
- Prefer a mix of small, medium, large targets.
- Include edge/corner targets and cluttered pages.

Absent examples:

- Do not only use random target swaps.
- Create realistic user queries for each screen, such as:
  - a common action missing from the current screen,
  - a menu item that might exist on a neighboring screen,
  - a semantically related but absent function,
  - a target that appears in another app or page but not this one.

Examples:

```text
Screen: login page
Absent query: "create account" if no sign-up control is visible

Screen: product page
Absent query: "checkout" if only add-to-cart or product details are visible

Screen: settings page
Absent query: "change language" if no language option is visible
```

## Annotation Fields

Use a CSV with:

| Field | Meaning |
|---|---|
| `image` | screenshot path |
| `query_text` | target/query |
| `gold_status` | present or absent |
| `target_bbox` | optional bbox for present cases |
| `target_visible` | yes/no |
| `query_realistic` | yes/no |
| `ambiguity_level` | low/medium/high |
| `notes` | short explanation |

## Evaluation

Run:

1. SeekUI prompt-only.
2. Combined AND best-F1 thresholds from dev/image split.
3. Direct VLM yes/no.
4. Best VLM prompt from GL ablation.

Metrics:

- accuracy,
- absent precision,
- absent recall,
- absent F1,
- present false-absent count,
- absent false-present count.

## Success Criteria

This manual validation is useful if:

- combined AND remains better than prompt-only by absent F1,
- VLM prompt baselines do not trivially solve all absent cases,
- the main failure taxonomy appears again: small/edge/OCR-missed present targets and strong distractor absent targets.

## Scope Control

Do not start with a large annotation effort. The first goal is a credibility check, not a new benchmark paper.
