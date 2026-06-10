# SeekUI Failure Case Analysis

This note summarizes the qualitative failure cases mined from the completed follow-up predictions.

## Artifacts Reviewed

Local failure visualization pack:

```text
/home/perzival/HCI_Research/seekui_failure_visuals
```

CHPC source directory:

```text
$SEEKUI_WORK/outputs/failure_cases
```

Failure bundles:

| Bundle | Failure Type | Count |
|---|---|---:|
| SeekUI_present_absent_absent_false_present | absent false-present | 30 |
| SeekUI_present_absent_present_false_absent | present false-absent | 30 |
| SeekUI_sft_present_absent_absent_false_present | absent false-present | 30 |
| SeekUI_sft_present_absent_present_false_absent | present false-absent | 30 |
| SeekUI_image_cue_far_from_target | image-cue far from target | 30 |
| SeekUI_sft_image_cue_far_from_target | image-cue far from target | 30 |
| SeekUI_semantic_association_predicted_absent | association predicted absent | 14 |
| SeekUI_semantic_association_far_from_target | association far from target | 18 |
| SeekUI_semantic_one_fixation_present | one-fixation present | 30 |
| SeekUI_sft_semantic_association_predicted_absent | association predicted absent | 12 |
| SeekUI_sft_semantic_association_far_from_target | association far from target | 20 |
| SeekUI_sft_semantic_one_fixation_present | one-fixation present | 30 |

## Main Qualitative Patterns

### 1. False-Present Behavior Often Lands on Plausible But Wrong UI Elements

The absent-target failures are not random blank failures. In many cases, the model still produces a plausible search path toward a semantically or visually salient UI element, even though the requested target is absent.

Representative example:

```text
SeekUI_absent_false_present/0004_3ea9d8_12a222_txt_QxcdksfMUj_cb0bf5_30b73f_txt_QxcdksfMUj_absent.png
Target: Search
Status: absent
Prediction: present
```

The screenshot contains file-conversion controls such as `Select your file` and `Convert Now`. The model generates a multi-fixation path around the central conversion button area. This is useful as a paper/slide example because it shows the forced-choice behavior clearly: when the exact target is absent, the model still grounds the request to a salient action region.

Interpretation:

```text
The model behaves like a forced-choice localizer rather than a stopping/search-decision model.
```

### 2. Synthetic Absent Cases Need Careful Validation

Some absent examples are genuinely ambiguous. For example:

```text
SeekUI_sft_absent_false_present/0008_a9793b_152086_txt_F4gfyigqWx_ba9073_0ebc10_txt_F4gfyigqWx_absent.png
Target: Search
Status: absent
```

The screenshot visibly contains a `Search GymShark` search field. This is not a clean absent example, even if the exact source target ID was absent by annotation. This matches the manual review finding that the synthetic absent benchmark is useful but not fully clean without visual validation.

Interpretation:

```text
Synthetic absent negatives are valuable for stress testing, but they can contain semantically valid targets that are missing from the source annotation.
```

This should be described as a benchmark caveat, not hidden.

### 3. Associative Queries Expose Semantic Grounding Weakness

The association subset gives some of the cleanest qualitative evidence for semantic brittleness.

Representative example:

```text
SeekUI_association_predicted_absent/0000_b45744_d325c0_txt_-J_W8-zy9x_query1_association_mapping.png
Original target: Delete
Query: remove
Predicted status: absent
```

The delete/trash icon is visible in the top-right toolbar, and the target bounding box is around that icon. With the exact target `Delete`, the model can produce a gaze path toward the icon. But with the associative query `remove`, the model is marked as predicted absent and the scanpath drifts away from the target.

This is a strong case-study candidate because it contrasts exact text/icon grounding with functional wording.

Interpretation:

```text
The model can associate visible UI labels/icons with exact targets more easily than with functionally equivalent descriptions.
```

Another useful case:

```text
SeekUI_association_predicted_absent/0005_ba9073_148945_txt_F4gfyigqWx_query1_association_mapping.png
Original target: Search
Query: type a query
Predicted status: absent
```

The search box is visibly present in the top navigation, but the model fails under the functional wording. This is a clean demonstration that exact text is still central to model behavior.

### 4. Image-Cue Failures Often Follow Salient Text or Layout Instead of the Target Crop

Representative example:

```text
SeekUI_image_cue_far_from_target/0000_4d17b7_fdbc2d_txt_KW8rNyyeWp.png
Target: Speak with a Clio expert
Failure type: far from target
```

The target button is at the bottom of a mobile landing page, but the predicted scanpath is pulled toward large central hero text and the URL/header region before ending far from the target. This is useful for the multimodal proxy story: even when given a target crop, the model may still follow global saliency or text hierarchy instead of grounding the visual cue.

Interpretation:

```text
Target-crop image cues are not enough to guarantee visual grounding; the model can still be dominated by screen saliency and layout priors.
```

### 5. SeekUI-SFT Often Collapses Search Into One Fixation

Representative example:

```text
SeekUI_sft_one_fixation_present/0018_2c9c76_152086_txt_6ecWykuqSJ_query0_exact.png
Target: Settings
Prediction length: 1
```

The target is visible in a menu, and the human scanpath moves through the menu before landing near settings. The SFT prediction is a single point far from the target. This visually supports the aggregate finding that SeekUI-SFT produces much shorter paths and often lands farther from the target.

Interpretation:

```text
SFT appears to compress scanpath behavior rather than improve robust target grounding.
```

## Best Candidate Figures

Recommended examples for slides or paper figures:

1. Forced-choice absent failure:

```text
visualizations/SeekUI_absent_false_present/0004_3ea9d8_12a222_txt_QxcdksfMUj_cb0bf5_30b73f_txt_QxcdksfMUj_absent.png
```

Use to show the model grounding an absent `Search` target to an unrelated central action area.

2. Associative semantic failure:

```text
visualizations/SeekUI_association_predicted_absent/0000_b45744_d325c0_txt_-J_W8-zy9x_query1_association_mapping.png
```

Use to show `Delete -> remove` failing despite a visible delete icon.

3. Functional search-box failure:

```text
visualizations/SeekUI_association_predicted_absent/0005_ba9073_148945_txt_F4gfyigqWx_query1_association_mapping.png
```

Use to show `Search -> type a query` failing despite a visible search box.

4. Image-cue grounding failure:

```text
visualizations/SeekUI_image_cue_far_from_target/0000_4d17b7_fdbc2d_txt_KW8rNyyeWp.png
```

Use to show target-crop search being pulled toward salient hero text rather than the target button.

5. SFT one-fixation failure:

```text
visualizations/SeekUI_sft_one_fixation_present/0018_2c9c76_152086_txt_6ecWykuqSJ_query0_exact.png
```

Use to illustrate SFT's short-path behavior.

## Implications For Next Experiments

1. Improve absent-target validation.

The visual audit confirms that some synthetic absent examples are ambiguous or invalid. We should use OCR/VLM-assisted validation or a larger manual audit before making strong benchmark claims.

2. Build a stronger association-first benchmark.

The current association subset is small but qualitatively strong. The next v3 benchmark should increase association coverage and avoid shallow templates.

3. Add a cognitive stopping model.

The false-present examples show exactly why a stopping model is needed. A useful next method should output:

```text
present / absent / uncertain
```

rather than always producing a forced grounding.

4. Treat image-cue as a proxy, not a final non-text benchmark.

The image-cue failures are useful, but the cue is derived from ground-truth crops. A stronger non-text experiment would need native icon/image cue trials or curated external cue images.

