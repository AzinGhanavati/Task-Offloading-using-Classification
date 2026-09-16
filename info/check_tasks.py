import os
import xml.etree.ElementTree as ET

def find_max_task_requirements(tasks_dir: str) -> None:
    max_data_raw = 0.0
    max_workload_raw = 0.0
    max_deadline_relative = 0.0
    total_tasks = 0

    if not os.path.exists(tasks_dir):
        print(f"Directory not found: {tasks_dir}")
        return

    print(f"Scanning task XML files in {tasks_dir}...")
    
    for filename in os.listdir(tasks_dir):
        if not filename.endswith(".xml"):
            continue
            
        filepath = os.path.join(tasks_dir, filename)
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            
            # Iterate through each timestep to get the current 'step' time
            for timestep in root.findall('timestep'):
                step_time = float(timestep.get('time', 0.0))
                
                # Iterate through all tasks in this timestep
                for task in timestep.findall('task'):
                    total_tasks += 1
                    
                    # Extract raw values from XML
                    data_size = float(task.get("dataSize", 0.0))
                    cycles_per_bit = float(task.get("cycles_per_bit", 0.0))
                    abs_deadline = float(task.get("deadline", 0.0))
                    
                    # Calculate real values
                    workload = data_size * cycles_per_bit
                    relative_deadline = abs_deadline - step_time  # (exec_time + free_time)
                    
                    if data_size > max_data_raw: max_data_raw = data_size
                    if workload > max_workload_raw: max_workload_raw = workload
                    if relative_deadline > max_deadline_relative: max_deadline_relative = relative_deadline
                    
        except Exception as e:
            print(f"Error parsing XML in file {filename}: {e}")

    print("\nTask Feature Analysis Complete:")
    print(f"Total tasks checked: {total_tasks}")
    print(f"Maximum Data Size (Raw XML): {max_data_raw:.2f}")
    print(f"Maximum Workload multiplier (Raw XML): {max_workload_raw:.2f}")
    print(f"Maximum Relative Deadline (s): {max_deadline_relative:.2f}")
    
    # Apply the math from your generator comments:
    # dataSize is *10^6 (Megabits)
    # cycles_per_bit is *10^3 (Kilocyles)
    # Total workload = dataSize * cycles_per_bit * 10^9
    real_max_data_bits = max_data_raw * 1e6
    real_max_workload_cycles = max_workload_raw * 1e9

    print("\n========================================================")
    print("Recommended Hyperparameters for NormalizationConfig")
    print("(Includes a 10% safety margin for stability)")
    print("========================================================")
    
    print(f"max_data_size_bits: float = {real_max_data_bits * 1.1:.1e}")
    print(f"max_workload_cycles: float = {real_max_workload_cycles * 1.1:.1e}")
    print(f"max_deadline_s: float = {max_deadline_relative * 1.1:.1f}")
    print("========================================================")

if __name__ == "__main__":
    tasks_directory = "../data/chunks/tasks"
    find_max_task_requirements(tasks_directory)