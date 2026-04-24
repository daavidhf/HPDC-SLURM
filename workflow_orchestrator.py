import os
import sys
import glob
from datetime import datetime

import subprocess

def main():
    # ==========================================================
    # PHASE 1: ANALYSIS OF DATA FOLDERS AND PREPARATION OF TASKS
    # ==========================================================

    # 1. Detect the project path (pass it as an argument or use the current one)
    # If an argument is provided, we use it as the base directory
    code_dir = os.path.dirname(os.path.abspath(__file__))
    if len(sys.argv) > 1:
        base_dir = os.path.abspath(sys.argv[1])
    # If no argument is provided, script uses the directory where it is located
    else:
        base_dir = code_dir

    # Define the relative paths
    data_dir = os.path.join(base_dir, 'data')
    logs_dir = os.path.join(base_dir, 'logs')
    results_dir = os.path.join(base_dir, 'results')
    scripts_dir = os.path.join(base_dir, 'scripts')


    # 2. Configure the logging system (ORCHEST_LOG.txt)
    log_file = os.path.join(logs_dir, 'ORCHEST_LOG.txt')
    with open(log_file, 'w') as f: # 'w' for write mode, which will overwrite the file if it already exists
        title = " STARTING PHASE 1: EXPLORATION AND TASKS PREPARATION "
        f.write(f"{title.center(100, '=')}\n")

    def register_log(message):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_message = f"[{current_time}] {message}";
        with open(log_file, 'a') as f: # 'a' for append mode without overwriting
            f.write(full_message + '\n')
    
    register_log(f"Project directory: {base_dir}")


    # 3. Explore the "sample" folders and extract intervals
    intervals = []
    
    # Search for all folders that start with "sample_" inside data/
    sample_folders = sorted(glob.glob(os.path.join(data_dir, 'sample_*')))
    
    if not sample_folders:
        register_log("WARNING: No sample folders found.")
        return

    for folder in sample_folders:
        folder_name = os.path.basename(folder)
        register_log(f"Visiting sample folder: {folder_name}")
        
        # Search for ranges_x.txt inside the current folder
        range_files = sorted(glob.glob(os.path.join(folder, 'ranges_*.txt')))
        
        for file in range_files:
            file_name = os.path.basename(file)
            register_log(f"  -> Reading range file: {file_name}")
            
            with open(file, 'r') as f:
                for line in f:
                    # Strip to remove leading whitespace and split by spaces
                    parts = line.strip().split()
                    # If the line has two numbers, we save it
                    if len(parts) == 2:
                        intervals.append(f"{parts[0]} {parts[1]}")

    register_log(f"Exploration completed. {len(intervals)} intervals found in total.")
    

    # 4. Save all intervals in a temporary file for SLURM
    tasks_file = os.path.join(results_dir, 'all_intervals.txt')
    with open(tasks_file, 'w') as f:
        f.write('\n'.join(intervals) + '\n')
    
    register_log(f"Tasks file generated at: {tasks_file}")

    with open(log_file, 'a') as f: # 'a' for append mode without overwriting
        title = " END OF PHASE 1: EXPLORATION AND TASKS PREPARATION "
        f.write(f"{title.center(100, '=')}\n")



    # ===========================================
    # PHASE 2: GENERATION AND SUBMISSION TO SLURM
    # ===========================================
    with open(log_file, 'a') as f: # 'w' for write mode, which will overwrite the file if it already exists
        title = " STARTING PHASE 2: SLURM FILES GENERATION AND JOBS SUBMISSION "
        f.write(f"{title.center(100, '=')}\n")

    num_tasks = len(intervals)
    if num_tasks == 0:
        register_log("No tasks to execute. Aborting SLURM phase.")
        return


    # 1. Create the Bash script for the Job Array calculation
    compute_sh = os.path.join(scripts_dir, 'compute_primes.sh')
    with open(compute_sh, 'w') as f:
        f.write(
            f"""
                #!/bin/bash

                # Set the job name for easier identification in the queue
                #SBATCH --job-name=calc_primes

                # Set the array to run from 1 to the number of tasks (intervals) we have at the same time.
                # SLURM will automatically set the environment variable SLURM_ARRAY_TASK_ID to the current index (1-based).
                #SBATCH --array=1-{num_tasks}

                # Output and error files for each task in the array, using the task ID to differentiate them.
                # %A is the job ID and %a is the array index. Each task will have its own log files.
                #SBATCH --output={logs_dir}/compute_%A_%a.out
                #SBATCH --error={logs_dir}/compute_%A_%a.err

                # Extract start and end of the interval corresponding to this task:
                # sed "stream editor" gets the line corresponding to the current task ID from the tasks file.
                # -n silent mode, only print what we explicitly ask for.
                # p explicitly print the line that matches the task ID.
                LINE=$(sed -n "${{SLURM_ARRAY_TASK_ID}}p" {tasks_file})

                # awk search for witespaces to split the line and print field 1 and 2 (start and end).
                START=$(echo $LINE | awk '{{print $1}}')
                END=$(echo $LINE | awk '{{print $2}}')

                # Run the count_tot_primes script, filter the total, and save the partial results
                # grep: selects the line that contains the total count, so we only save the primes found in the interval.
                # -v option: inverts the match, so it prints all lines that do NOT contain "TOTAL:".
                python {scripts_dir}/count_tot_primes.py $START $END | grep -v "TOTAL:" > {results_dir}/primes_${{SLURM_ARRAY_TASK_ID}}.txt
            """
        )

    register_log(f"Generated computing script: {compute_sh}")


    # 2. Create the Bash script for the consolidation
    merge_sh = os.path.join(scripts_dir, 'merge_primes.sh')
    with open(merge_sh, 'w') as f:
        f.write(
            f""" 
                #!/bin/bash

                # Set the job name for easier identification in the queue
                #SBATCH --job-name=merge_primes

                # Output and error files
                # $j is the job ID assigned by SLURM to this job, we use it to differentiate the logs.
                #SBATCH --output={logs_dir}/merge_%j.out
                #SBATCH --error={logs_dir}/merge_%j.err

                # Run our auxiliary Python script to merge the results
                python {code_dir}/scripts/consolidate_results.py {results_dir}
            """
        )

    register_log(f"Generated consolidation script: {merge_sh}")


    # 3. Submit the jobs to SLURM
    try:
        # Submit the first job (Array)
        res1 = subprocess.run(['sbatch', compute_sh], # call sbatch with the compute_sh script to submit the job to SLURM
                                stdout=subprocess.PIPE, # Not printing the output directly, save it in res1.stdout
                                stderr=subprocess.PIPE, # Not printing the error directly, save it in res1.stderr
                                universal_newlines=True, # Interpret the output as text (string) instead of bytes
                                check=True # If command fails (non-zero exit code), raise a CalledProcessError exception
                                )
        
        # sbatch returns something like "Submitted batch job 12345", we extract the ID:
        job1_id = res1.stdout.strip().split()[-1]
        register_log(f"Job Array submitted to SLURM successfully. Job ID: {job1_id}")

        # Submit the second job (Dependent on the first one)
        dependency = f"--dependency=afterok:{job1_id}" # wait for the Array (first job) to finish successfully before starting
        res2 = subprocess.run(['sbatch', dependency, merge_sh],
                                stdout=subprocess.PIPE, # Not printing the output directly, save it in res2.stdout
                                stderr=subprocess.PIPE, # Not printing the error directly, save it in res2.stderr
                                universal_newlines=True, # Interpret the output as text (string) instead of bytes
                                check=True # If command fails (non-zero exit code), raise a CalledProcessError exception
                                )
        
        job2_id = res2.stdout.strip().split()[-1]
        register_log(f"Consolidation job submitted to SLURM. Job ID: {job2_id} (Depends on {job1_id})")

    except subprocess.CalledProcessError as e:
        register_log(f"Error submitting jobs to SLURM: {e.stderr}")
        return

    title = " END OF PHASE 2: SLURM FILES GENERATION AND JOBS SUBMISSION "
    register_log(title.center(100, '='))


if __name__ == '__main__':
    main()