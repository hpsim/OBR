# OBR - OpenFOAM Benchmark Runner

This repository is used to easily create benchmark cases to evaluate the
performance of the OpenFOAM Ginkgo Layer.

## Dependencies

    1. docopt

## Usage

The benchmark runnner is split into several layers:
    1. case generation
    2. case decomposition
    3. case run

### 1. Creating a tree

To create a tree of case variation run


    python obr_create_tree.py \
         --parameters lidDrivenCavity3DFull.json \
         --folder lidDrivenCavity3DFull

### 2. Running a tree

    python obr_benchmark_cases.py \
         --results_folder lidDrivenCavity3DFull
         --filter MPI # dont run cases with mpi in name

