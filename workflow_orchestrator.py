import os
import sys
import glob
from datetime import datetime

import subprocess

def main():
    # 1. Detect the project path (pass it as an argument or use the current one)
    # If an argument is provided, we use it as the base directory
    if len(sys.argv) > 1:
        base_dir = os.path.abspath(sys.argv[1])
    # If no argument is provided, we assume the script must be ran using the directory where it is located
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    # Define the relative paths based on the statement
    data_dir = os.path.join(base_dir, 'data')
    logs_dir = os.path.join(base_dir, 'logs')
    results_dir = os.path.join(base_dir, 'results')
    scripts_dir = os.path.join(base_dir, 'scripts')

    # 2. Configure the logging system (ORCHEST_LOG.txt)
    log_file = os.path.join(logs_dir, 'ORCHEST_LOG.txt')
    with open(log_file, 'w') as f: # 'w' for write mode, which will overwrite the file if it already exists
        title = " STARTING ORCHESTRATOR "
        f.write(f"{title.center(100, '=')}\n")
    
    def register_log(message):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_message = f"[{current_time}] {message}"
        print(full_message)  # Print to console as well
        with open(log_file, 'a') as f: # 'a' for append mode without overwriting
            f.write(full_message + '\n')
    
    register_log(f"Base directory: {base_dir}")

    # 3. Explore the "sample" folders and extract intervals
    intervals = []
    
    # Search for all folders that start with "sample_" inside data/
    print(glob.glob(os.path.join(data_dir, 'sample_*')))
    sample_folders = sorted(glob.glob(os.path.join(data_dir, 'sample_*')))
    
    if not sample_folders:
        register_log("WARNING: No sample folders found.")
        return

    for folder in sample_folders:
        folder_name = os.path.basename(folder)
        register_log(f"Visiting sample folder: {folder_name}")
        
        # Search for ranges_x.txt inside the current folder
        range_files = sorted(glob.glob(os.path.join(folder, 'ranges_*.txt')))
        
        for rf in range_files:
            file_name = os.path.basename(rf)
            register_log(f"  -> Reading range file: {file_name}")
            
            with open(rf, 'r') as file:
                for line in file:
                    # Strip to remove leading/trailing whitespace and split by spaces
                    parts = line.strip().split()
                    # If the line has two numbers, we save it
                    if len(parts) == 2:
                        intervals.append(f"{parts[0]} {parts[1]}")

    register_log(f"Exploration completed. {len(intervals)} intervals found in total.")
    
    # 4. Save all intervals in a master temporary file for SLURM
    tasks_file = os.path.join(results_dir, 'all_intervals.txt')
    with open(tasks_file, 'w') as f:
        f.write('\n'.join(intervals) + '\n')
    
    register_log(f"Tasks file generated at: {tasks_file}")

    with open(log_file, 'a') as f: # 'a' for append mode without overwriting
        title = " END OF EXPLORATION PHASE "
        f.write(f"{title.center(100, '=')}\n")


    # ===========================================
    # PHASE 2: GENERATION AND SUBMISSION TO SLURM
    # ===========================================
    fase_slurm = " STARTING SLURM PHASE "
    register_log(fase_slurm.center(100, '='))

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
                #SBATCH --job-name=calc_primes
                #SBATCH --array=1-{num_tasks}
                #SBATCH --output={logs_dir}/compute_%A_%a.out
                #SBATCH --error={logs_dir}/compute_%A_%a.err

                # Extract start and end of the interval corresponding to this task
                LINE=$(sed -n "${{SLURM_ARRAY_TASK_ID}}p" {tasks_file})
                START=$(echo $LINE | awk '{{print $1}}')
                END=$(echo $LINE | awk '{{print $2}}')

                # Run the original script, filter the total, and save the partial results
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
                #SBATCH --job-name=merge_primes
                #SBATCH --output={logs_dir}/merge_%j.out
                #SBATCH --error={logs_dir}/merge_%j.err

                # Run our auxiliary Python script to merge the results
                python {scripts_dir}/consolidate_results.py {results_dir}
            """
        )

    register_log(f"Generated consolidation script: {merge_sh}")

    # 3. Submit the jobs to SLURM (Protected in case we are on local)
    try:
        # Submit the first job (Array)
        res1 = subprocess.run(['sbatch', compute_sh], capture_output=True, text=True, check=True)
        # sbatch returns something like "Submitted batch job 12345", we extract the ID:
        job1_id = res1.stdout.strip().split()[-1]
        register_log(f"Job Array submitted to SLURM successfully. Job ID: {job1_id}")

        # Submit the second job (Dependent on the first)
        # We use --dependency=afterok:ID so it waits for the Array to finish successfully before starting
        dependency = f"--dependency=afterok:{job1_id}"
        res2 = subprocess.run(['sbatch', dependency, merge_sh], capture_output=True, text=True, check=True)
        job2_id = res2.stdout.strip().split()[-1]
        register_log(f"Consolidation job submitted to SLURM. Job ID: {job2_id} (Depends on {job1_id})")

    except FileNotFoundError:
        register_log("WARNING: The command 'sbatch' does not exist in this system.")
        register_log("This is normal if you are testing on your local computer (WSL).")
        register_log("The .sh files have been generated correctly for when you upload the code to the cluster.")
    except subprocess.CalledProcessError as e:
        register_log(f"ERROR: Failed to communicate with SLURM. Details: {e.stderr}")

    fase_fin = " END OF ORCHESTRATION "
    register_log(fase_fin.center(80, '='))

if __name__ == '__main__':
    main()