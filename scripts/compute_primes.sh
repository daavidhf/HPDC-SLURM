#!/bin/bash

# Set the job name for easier identification in the queue
#SBATCH --job-name=calc_primes

# Set the array to run from 1 to the number of tasks (intervals) we have at the same time.
# SLURM will automatically set the environment variable SLURM_ARRAY_TASK_ID to the current index (1-based).
#SBATCH --array=1-5

# Output and error files for each task in the array, using the task ID to differentiate them.
# %A is the job ID and %a is the array index. Each task will have its own log files.
#SBATCH --output=/home/master/mhedas/mhedas-39/project/logs/compute_%A_%a.out
#SBATCH --error=/home/master/mhedas/mhedas-39/project/logs/compute_%A_%a.err

# Extract start and end of the interval corresponding to this task:
# sed "stream editor" gets the line corresponding to the current task ID from the tasks file.
# -n silent mode, only print what we explicitly ask for.
# p explicitly print the line that matches the task ID.
LINE=$(sed -n "${SLURM_ARRAY_TASK_ID}p" /home/master/mhedas/mhedas-39/project/results/all_intervals.txt)

# awk search for witespaces to split the line and print field 1 and 2 (start and end).
START=$(echo $LINE | awk '{print $1}')
END=$(echo $LINE | awk '{print $2}')

# Run the count_tot_primes script, filter the total, and save the partial results
# grep: selects the line that contains the total count, so we only save the primes found in the interval.
# -v option: inverts the match, so it prints all lines that do NOT contain "TOTAL:".
python /home/master/mhedas/mhedas-39/project/scripts/count_tot_primes.py $START $END | grep -v "TOTAL:"
