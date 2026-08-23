import csv
import os
import random
import xml.etree.ElementTree as Et
from collections import defaultdict
from dataclasses import dataclass
import numpy as np
import matplotlib.pyplot as plt
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

import config.config as CNF
class Config:
    CHUNK_SIZE = 3600  # Chunk size in seconds

    class TaskConfig:
        MIN_POWER_CONSUMPTION: float = 1.0
        MAX_POWER_CONSUMPTION: float = 3.5
        DEADLINE_MIN_FREE_TIME: float = 3.0
        DEADLINE_MAX_FREE_TIME: float = 15.0
        MIN_CYCLE_PER_BIT: float = 1  # *10^3
        MAX_CYCLE_PER_BIT: float = 2
        MIN_DATASIZE: float = 0.25  # *10^6
        MAX_DATASIZE: float = 1.5

    class VehicleConfig:
        TASK_GENERATION_RATE: float = 0.35
        FUCKED_UP_TASK_GENERATION_RATE: float = 0.55
        TRAFFIC_MIN_SPEED_THRESHOLD: float = 10.5
        LANE_TRAFFIC_THRESHOLD: int = 15
        MAX_COMPUTATION_POWER: float = 6  
        MIN_COMPUTATION_POWER: float = 2
        COMPUTATION_POWER_ROUND_DIGIT: int = 2
        HIGH_TRANSMISSION_POWER = 30
        
        # Parameters for Poisson lambda and Gaussian noise
        MIN_BASE_LAMBDA: float = 1.0
        MAX_BASE_LAMBDA: float = 5.0
        NOISE_GAUSS_MEAN: float = 2.0
        NOISE_GAUSS_STD: float = 1.0

    class MobileFogConfig:
        MAX_COMPUTATION_POWER: float = 12.0
        MIN_COMPUTATION_POWER: float = 7.0
        COMPUTATION_POWER_ROUND_DIGIT: int = 2


@dataclass
class Vehicle:
    id: str
    x: float
    y: float
    angle: float
    speed: float
    power: float
    type: str
    lane: str
    frequency: float
    weather: float
    base_lambda: float  # Stores the unique task generation rate of this vehicle


@dataclass
class Task:
    id: str
    deadline: float
    exec_time: float  
    power: float  
    creator: str  
    cycles_per_bit: float
    dataSize: float


class Generator:
    def __init__(self):
        self.current_chunk = 0
        self.current_vehicles = []
        self.current_tasks = []
        self.soft_task_counters = defaultdict(int)
        
        self.tasks_count_per_step = defaultdict(int)
        self.average_speed_per_step = defaultdict(float)
        self.total_task_power_per_step = defaultdict(float)

        # Dictionary to persist the assigned lambda for each unique vehicle
        self.vehicle_lambdas: dict[str, float] = {}

        os.makedirs("./data/chunks/vehicles", exist_ok=True)
        os.makedirs("./data/chunks/tasks", exist_ok=True)

    @staticmethod
    def get_chunk_number(step: int) -> int:
        return step // Config.CHUNK_SIZE

    def save_current_chunk(self, step: int):
        chunk_num = self.get_chunk_number(step)
        if chunk_num > self.current_chunk and (self.current_vehicles or self.current_tasks):
            self._save_vehicles_chunk()
            self._save_tasks_chunk()
            self.current_vehicles = []
            self.current_tasks = []
            self.current_chunk = chunk_num

    def _save_vehicles_chunk(self):
        root = Et.Element('fcd-export')
        root.set("version", "1.0")

        for time_data in self.current_vehicles:
            time_elem = Et.SubElement(root, 'timestep')
            time_elem.set('time', f"{time_data['step']}")
            for vehicle in time_data['vehicles']:
                v_elem = Et.SubElement(time_elem, 'vehicle')
                v_elem.set('id', vehicle.id)
                v_elem.set('x', f"{vehicle.x:.2f}")
                v_elem.set('y', f"{vehicle.y:.2f}")
                v_elem.set('angle', f"{vehicle.angle:.2f}")
                v_elem.set('speed', f"{vehicle.speed:.2f}")
                v_elem.set('lane', vehicle.lane)
                v_elem.set('type', vehicle.type)
                v_elem.set('power', f"{vehicle.power:.2f}")
                v_elem.set('frequency', f"{vehicle.frequency:.2f}")
                v_elem.set('weather', f"{vehicle.weather}")
                
                # ADD THIS LINE: Save base_lambda to the XML output
                v_elem.set('base_lambda', f"{vehicle.base_lambda:.4f}")

        Et.indent(root, space="    ", level=0)
        tree = Et.ElementTree(root)
        tree.write(f"./data/chunks/vehicles/chunk_{self.current_chunk}.xml", encoding='utf-8', xml_declaration=True)

    def _save_tasks_chunk(self):
        root = Et.Element('fcd-export')
        root.set("version", "1.0")

        for time_data in self.current_tasks:
            time_elem = Et.SubElement(root, 'timestep')
            time_elem.set('time', f"{time_data['step']}")
            for task in time_data['tasks']:
                t_elem = Et.SubElement(time_elem, 'task')
                t_elem.set('id', task.id)
                t_elem.set('deadline', f"{task.deadline:.2f}")
                t_elem.set('exec_time', f"{task.exec_time:.2f}")
                t_elem.set('power', f"{task.power:.2f}")
                t_elem.set('creator', task.creator)
                t_elem.set('cycles_per_bit', f"{task.cycles_per_bit:.2f}")
                t_elem.set('dataSize', f"{task.dataSize:.2f}")

        Et.indent(root, space="    ", level=0)
        tree = Et.ElementTree(root)
        tree.write(f"./data/chunks/tasks/chunk_{self.current_chunk}.xml", encoding='utf-8', xml_declaration=True)

    def calculate_metrics(self, step: float, vehicles: list[Vehicle], tasks: list[Task]):
        self.tasks_count_per_step[step] = len(tasks)
        if vehicles:
            avg_speed = sum(v.speed for v in vehicles) / len(vehicles)
            self.average_speed_per_step[step] = round(avg_speed, 2)
        else:
            self.average_speed_per_step[step] = 0.0

        self.total_task_power_per_step[step] = round(sum(task.power for task in tasks), 2)

    def generate_one_step_tasks(self, step, vehicle, lane_counter):
        """Generate tasks using vehicle's unique lambda and Gaussian noise during bad conditions."""
        
        traffic_high = (
                lane_counter > Config.VehicleConfig.LANE_TRAFFIC_THRESHOLD
                or vehicle.speed < Config.VehicleConfig.TRAFFIC_MIN_SPEED_THRESHOLD
        )
        
        current_lambda = vehicle.base_lambda

        if traffic_high:
            noise = random.gauss(
                Config.VehicleConfig.NOISE_GAUSS_MEAN, 
                Config.VehicleConfig.NOISE_GAUSS_STD
            )
            current_lambda += abs(noise)

        num_tasks = np.random.poisson(lam=current_lambda)
        
        tasks = []
        for _ in range(num_tasks):
            deadline_free = round(
                random.uniform(
                    Config.TaskConfig.DEADLINE_MIN_FREE_TIME,
                    Config.TaskConfig.DEADLINE_MAX_FREE_TIME,
                ),
                2
            )
            power = round(
                random.uniform(
                    Config.TaskConfig.MIN_POWER_CONSUMPTION,
                    Config.TaskConfig.MAX_POWER_CONSUMPTION
                ),
                2
            )
            cycles_per_bit = round(
                random.uniform(
                    Config.TaskConfig.MIN_CYCLE_PER_BIT,
                    Config.TaskConfig.MAX_CYCLE_PER_BIT
                ),
                2
            )
            dataSize = round(random.uniform(Config.TaskConfig.MIN_DATASIZE, Config.TaskConfig.MAX_DATASIZE), 2)

            exec_time = (dataSize * cycles_per_bit) / CNF.Config.UserNodeConfig.USER_NODE_FREQUENCY
            deadline = round(exec_time + deadline_free) + step

            task_index = self.soft_task_counters[vehicle.id]
            self.soft_task_counters[vehicle.id] += 1

            tasks.append(Task(
                id=f"{vehicle.id}_S_{step}_{task_index}",
                deadline=deadline,
                exec_time=exec_time,
                power=power,
                creator=vehicle.id,
                cycles_per_bit=cycles_per_bit,
                dataSize=dataSize
            ))

        return tasks

    def generate_one_step(self, step, time_data, seen_ids_power):
        current_vehicles = []
        current_tasks = []
        lane_counter = defaultdict(int)

        for vehicle in time_data.findall('vehicle'):
            v_id = vehicle.get('id')
            
            if v_id not in self.vehicle_lambdas:
                self.vehicle_lambdas[v_id] = random.uniform(
                    Config.VehicleConfig.MIN_BASE_LAMBDA,
                    Config.VehicleConfig.MAX_BASE_LAMBDA
                )
            
            base_lambda = self.vehicle_lambdas[v_id]

            data = dict(
                id=v_id,
                x=float(vehicle.get('x')),
                y=float(vehicle.get('y')),
                angle=90 - float(vehicle.get('angle')),
                speed=float(vehicle.get('speed')),
                lane=vehicle.get('lane'),
                type=vehicle.get('type'),
                weather=1,
                base_lambda=base_lambda,
            )

            if v_id in seen_ids_power:
                power = seen_ids_power[v_id]
                if vehicle.get('type') == "LKW_special":
                    frequency = CNF.Config.MobileFogNodeConfig.MOBILE_NODE_FREQUENCY
                elif vehicle.get('type') == "PKW_special":
                    frequency = CNF.Config.UserNodeConfig.USER_NODE_FREQUENCY
            elif vehicle.get('type') == "LKW_special":
                power = round(
                    random.uniform(
                        Config.MobileFogConfig.MIN_COMPUTATION_POWER,
                        Config.MobileFogConfig.MAX_COMPUTATION_POWER
                    ),
                    Config.MobileFogConfig.COMPUTATION_POWER_ROUND_DIGIT
                )
                frequency = CNF.Config.MobileFogNodeConfig.MOBILE_NODE_FREQUENCY
            elif vehicle.get('type') == "PKW_special":
                power = round(
                    random.uniform(
                        Config.VehicleConfig.MIN_COMPUTATION_POWER,
                        Config.VehicleConfig.MAX_COMPUTATION_POWER
                    ),
                    Config.MobileFogConfig.COMPUTATION_POWER_ROUND_DIGIT
                )
                frequency = CNF.Config.UserNodeConfig.USER_NODE_FREQUENCY
            else:
                continue

            seen_ids_power[v_id] = power
            data["power"] = power
            data["frequency"] = frequency

            vehicle_obj = Vehicle(**data)
            current_vehicles.append(vehicle_obj)
            lane_counter[vehicle_obj.lane] += 1

            if tasks := self.generate_one_step_tasks(step, vehicle_obj, lane_counter[vehicle_obj.lane]):
                for task in tasks:
                    current_tasks.append(task)

        self.calculate_metrics(step, current_vehicles, current_tasks)

        self.current_vehicles.append({"step": step, "vehicles": current_vehicles})
        self.current_tasks.append({"step": step, "tasks": current_tasks})

        self.save_current_chunk(step)

        return seen_ids_power

    def generate_data(self, path: str):
        with open(path, 'rb') as f:
            root = Et.parse(f).getroot()
        seen_ids_power = {}
        timesteps = root.findall('.//timestep')
        total_steps = len(timesteps)

        print(f"Starting data generation for {total_steps} timesteps...")

        for idx, time in enumerate(timesteps):
            step = round(float(time.get('time')))
            seen_ids_power = self.generate_one_step(step, time, seen_ids_power)

            if step % 100 == 0 or idx == total_steps - 1:
                progress_percent = (idx + 1) / total_steps * 100
                print(f"[Progress] Successfully generated up to timestep: {step} ({progress_percent:.1f}%)")

        if self.current_vehicles or self.current_tasks:
            self._save_vehicles_chunk()
            self._save_tasks_chunk()

    def save_metrics_to_csv(self, metrics_file: str):
        all_steps = sorted(set(self.tasks_count_per_step.keys()) |
                           set(self.average_speed_per_step.keys()) |
                           set(self.total_task_power_per_step.keys()))

        with open(metrics_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestep', 'task_count', 'average_speed', 'total_task_power'])
            for step in all_steps:
                writer.writerow([
                    f"{step:.2f}",
                    self.tasks_count_per_step[step],
                    self.average_speed_per_step[step],
                    self.total_task_power_per_step[step]
                ])

    def plot_metrics(self, output_file: str):
        steps = sorted(set(self.tasks_count_per_step.keys()) |
                       set(self.average_speed_per_step.keys()) |
                       set(self.total_task_power_per_step.keys()))
        task_counts = [self.tasks_count_per_step[step] for step in steps]
        avg_speeds = [self.average_speed_per_step[step] for step in steps]
        total_powers = [self.total_task_power_per_step[step] for step in steps]

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 12))

        ax1.plot(steps, task_counts, 'b-', label='Tasks per Step')
        ax1.set_xlabel('Time Step')
        ax1.set_ylabel('Number of Tasks')
        ax1.set_title('Tasks Generated per Time Step')
        ax1.grid(True)
        ax1.legend()

        ax2.plot(steps, avg_speeds, 'r-', label='Average Speed')
        ax2.set_xlabel('Time Step')
        ax2.set_ylabel('Speed')
        ax2.set_title('Average Speed of User Nodes per Time Step')
        ax2.grid(True)
        ax2.legend()

        ax3.plot(steps, total_powers, 'g-', label='Total Task Power')
        ax3.set_xlabel('Time Step')
        ax3.set_ylabel('Power Units')
        ax3.set_title('Total Power of Tasks per Time Step')
        ax3.grid(True)
        ax3.legend()

        plt.tight_layout()
        plt.savefig(output_file)
        plt.close()

def main(path: str):
    generator = Generator()
    generator.generate_data(path)
    generator.save_metrics_to_csv("./data/chunks/metrics/metrics.csv")
    generator.plot_metrics("./data/chunks/metrics/metrics_visualization.png")

if __name__ == '__main__':
    main("./data/raw/simulation.out.xml")