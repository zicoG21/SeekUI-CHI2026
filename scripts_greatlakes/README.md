# Great Lakes Setup

These scripts mirror the Utah helpers but use University of Michigan Great Lakes defaults.

Default GPU settings:

```text
account:   engin1
partition: spgpu
gres:      gpu:a40:1
```

Use an Engineering scratch/project directory for data and model cache:

```bash
export SEEKUI_WORK=/scratch/engin_root/engin1/zicong/seekui
mkdir -p "$SEEKUI_WORK"/{data,models,outputs,hf_cache}
sed -i '/SEEKUI_WORK=/d' ~/.bashrc
echo "export SEEKUI_WORK=$SEEKUI_WORK" >> ~/.bashrc
```

After copying `vsgui10k-images.zip` into `$SEEKUI_WORK/data`, unpack and flatten:

```bash
unzip -q "$SEEKUI_WORK/data/vsgui10k-images.zip" -d "$SEEKUI_WORK/data/vsgui10k-images"
find "$SEEKUI_WORK/data/vsgui10k-images" -mindepth 2 -type f -name '*.png' -exec mv -n {} "$SEEKUI_WORK/data/vsgui10k-images/" \;
find "$SEEKUI_WORK/data/vsgui10k-images" -maxdepth 1 -type f -name '*.png' | wc -l
```

Create the environment on a login node:

```bash
module avail python

module load python3.10-anaconda/2023.03
conda create -n seekui python=3.10.12 -y
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui
bash scripts_greatlakes/setup_env.sh
```

If `conda activate` fails, the important line is:

```bash
source "$(conda info --base)/etc/profile.d/conda.sh"
```

Download models:

```bash
conda activate seekui
bash scripts_utah/download_models.sh
```

Build offline follow-up datasets:

```bash
sbatch scripts_greatlakes/offline_research_prep.slurm
```

Run a smoke test:

```bash
sbatch scripts_greatlakes/inference_demo.slurm
```

Run a reviewer-risk VLM yes/no baseline pilot:

```bash
VLM_LIMIT=200 sbatch scripts_greatlakes/vlm_presence_baseline.slurm
```

Run the full VLM yes/no baseline:

```bash
sbatch scripts_greatlakes/vlm_presence_baseline.slurm
```

Run VLM prompt ablations in parallel:

```bash
VLM_LIMIT=200 bash scripts_greatlakes/submit_vlm_prompt_ablation.sh

# Full run after the pilot looks sane:
bash scripts_greatlakes/submit_vlm_prompt_ablation.sh

# Override the allocation/account when needed:
SBATCH_ACCOUNT=jaabell0 bash scripts_greatlakes/submit_vlm_prompt_ablation.sh
```

Run the semantic v3 association-first jobs:

```bash
MODEL_NAME=SeekUI \
SEMANTIC_JSON="$SEEKUI_WORK/data/semantic_queries_1362_v3_assocfirst.json" \
OUTPUT_PATH="$SEEKUI_WORK/outputs/semantic_query_predictions_SeekUI_1362_v3_assocfirst.json" \
SEMANTIC_MAPPING=scripts_research/associative_query_mapping.json \
SEMANTIC_SELECTION_POLICY=association_first \
sbatch scripts_greatlakes/semantic_query_inference.slurm

MODEL_NAME=SeekUI_sft \
SEMANTIC_JSON="$SEEKUI_WORK/data/semantic_queries_1362_v3_assocfirst.json" \
OUTPUT_PATH="$SEEKUI_WORK/outputs/semantic_query_predictions_SeekUI_sft_1362_v3_assocfirst.json" \
SEMANTIC_MAPPING=scripts_research/associative_query_mapping.json \
SEMANTIC_SELECTION_POLICY=association_first \
sbatch scripts_greatlakes/semantic_query_inference.slurm
```

You can override account/partition/GPU at submission time:

```bash
sbatch --account=jaabell0 --partition=gpu_mig40 --gres=gpu:nvidia_a100_80gb_pcie_3g.40gb:1 scripts_greatlakes/inference_demo.slurm
```

Use `jaabell0` only when you intentionally want to spend that allocation; the
checked-in defaults use `engin1`.
