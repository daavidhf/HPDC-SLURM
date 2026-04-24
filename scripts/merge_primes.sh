#!/bin/bash

# Set the job name for easier identification in the queue
#SBATCH --job-name=merge_primes

# Output and error files
# $j is the job ID assigned by SLURM to this job, we use it to differentiate the logs.
#SBATCH --output=/home/master/mhedas/mhedas-39/project/logs/merge_%j.out
#SBATCH --error=/home/master/mhedas/mhedas-39/project/logs/merge_%j.err

# Run our auxiliary Python script to merge the results
python /home/master/mhedas/mhedas-39/project/scripts/consolidate_results.py /home/master/mhedas/mhedas-39/project/results
