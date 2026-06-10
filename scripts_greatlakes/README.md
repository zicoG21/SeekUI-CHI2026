# Great Lakes Setup

These scripts mirror the Utah helpers but use University of Michigan Great Lakes defaults.

Default GPU settings:

```text
account:   jaabell0
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
module avail miniconda
module avail python

module load miniconda3
conda create -n seekui python=3.10.12 -y
conda activate seekui
bash scripts_utah/install_inference_deps.sh
```

If the `miniconda3` module name differs, load the local Great Lakes module and then run the same conda commands.

Download models:

```bash
conda activate seekui
bash scripts_utah/download_models.sh
```

Run a smoke test:

```bash
sbatch scripts_greatlakes/inference_demo.slurm
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
