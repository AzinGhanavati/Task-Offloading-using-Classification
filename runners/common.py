from __future__ import annotations

<<<<<<< HEAD
=======
import os
import xml.etree.ElementTree as ET

>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
from config.hyperparameters import Hyperparameters, default_hyperparameters
from config.simulation_config import default_simulation_config
from simulation.entities import CloudNode, EdgeServer
from simulation.network.urban_grid import UrbanGrid
from simulation.placement import build_placement_strategy
<<<<<<< HEAD
=======
from simulation.placement.base import PlacementPoint
>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
from simulation.scenario import Scenario


def build_scenario(vehicles_dir: str, tasks_dir: str) -> Scenario:
    """Load every SUMO task/vehicle chunk under the given directories."""
    return Scenario.from_chunk_files(vehicles_dir, tasks_dir)


def vehicle_points(scenario: Scenario) -> list[tuple[float, float]]:
    """All observed vehicle (x, y) positions, used for edge placement."""
    return [(snap.x, snap.y) for _t, snaps in scenario.mobility for snap in snaps]


<<<<<<< HEAD
def build_infrastructure(
    hyper: Hyperparameters, vehicle_pts: list[tuple[float, float]]
):
    """Instantiate the cloud and deploy edge servers via the placement strategy.

    Returns ``(config, cloud, edge_servers)``.
    """
    config = default_simulation_config()
    cloud = CloudNode(node_id="cloud-0", hardware=config.cloud)
    strategy = build_placement_strategy(
        hyper.placement,
        area_x_max=hyper.urban_grid.area_x_max,
        area_y_max=hyper.urban_grid.area_y_max,
    )
    locations = strategy.place(vehicle_pts)
=======
def save_placement_xml(locations: list[PlacementPoint], filepath: str) -> None:
    """Save the calculated edge server locations to an XML file."""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" ?>\n')
        f.write('<nodes version="1.0">\n')
        for index, loc in enumerate(locations):
            f.write(f'    <node id="edge-{index}" x="{loc.x:.2f}" y="{loc.y:.2f}"/>\n')
        f.write('</nodes>\n')


def load_placement_xml(filepath: str) -> list[PlacementPoint]:
    """Load edge server locations from an existing XML file."""
    tree = ET.parse(filepath)
    root = tree.getroot()
    locations = []
    for node in root.findall("node"):
        x = float(node.get("x"))
        y = float(node.get("y"))
        locations.append(PlacementPoint(x, y))
    return locations


def build_infrastructure(
    hyper: Hyperparameters,
    vehicle_pts: list[tuple[float, float]],
    xml_path: str = "data/dataset/edge_placement.xml"
):
    """Instantiate the cloud and deploy edge servers.
    
    If the XML placement file exists, load it to ensure topology consistency
    across training and evaluation phases. Otherwise, calculate and save it.
    """
    config = default_simulation_config()
    cloud = CloudNode(node_id="cloud-0", hardware=config.cloud)
    
    if os.path.exists(xml_path):
        print(f"[*] Loading fixed edge placement from: {xml_path}")
        locations = load_placement_xml(xml_path)
    else:
        print(f"[*] Calculating new edge placement and saving to: {xml_path}")
        strategy = build_placement_strategy(
            hyper.placement,
            area_x_max=hyper.urban_grid.area_x_max,
            area_y_max=hyper.urban_grid.area_y_max,
        )
        locations = strategy.place(vehicle_pts)
        save_placement_xml(locations, xml_path)

>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
    edge_servers = [
        EdgeServer(
            node_id=f"edge-{index}",
            hardware=config.edge,
            x=point.x,
            y=point.y,
            coverage_radius_m=hyper.placement.edge_coverage_radius_m,
        )
        for index, point in enumerate(locations)
    ]
    return config, cloud, edge_servers


def build_urban_grid(hyper: Hyperparameters) -> UrbanGrid:
<<<<<<< HEAD
    return UrbanGrid(hyper.urban_grid)
=======
    return UrbanGrid(hyper.urban_grid)
>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
