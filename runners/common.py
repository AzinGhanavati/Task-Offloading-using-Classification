from __future__ import annotations

from config.hyperparameters import Hyperparameters, default_hyperparameters
from config.simulation_config import default_simulation_config
from simulation.entities import CloudNode, EdgeServer
from simulation.network.urban_grid import UrbanGrid
from simulation.placement import build_placement_strategy
from simulation.scenario import Scenario


def build_scenario(vehicles_dir: str, tasks_dir: str) -> Scenario:
    """Load every SUMO task/vehicle chunk under the given directories."""
    return Scenario.from_chunk_files(vehicles_dir, tasks_dir)


def vehicle_points(scenario: Scenario) -> list[tuple[float, float]]:
    """All observed vehicle (x, y) positions, used for edge placement."""
    return [(snap.x, snap.y) for _t, snaps in scenario.mobility for snap in snaps]


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
    return UrbanGrid(hyper.urban_grid)
