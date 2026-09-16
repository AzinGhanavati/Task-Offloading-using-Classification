import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import numpy as np
import os

def plot_hexbin_traffic(file_name: str, grid_size: int = 50):
    print(f"Extracting coordinates from {file_name}...")
    
    if not os.path.exists(file_name):
        print("File not found!")
        return

    tree = ET.parse(file_name)
    root = tree.getroot()

    x_coords = []
    y_coords = []

    for timestep in root.findall('timestep'):
        for vehicle in timestep.findall('vehicle'):
            x_coords.append(float(vehicle.get('x')))
            y_coords.append(float(vehicle.get('y')))

    if not x_coords:
        print("No vehicle data found in the XML.")
        return

    x_array = np.array(x_coords)
    y_array = np.array(y_coords)

    print(f"Plotting {len(x_array)} data points...")

    plt.figure(figsize=(10, 8))
    
    # Create the hexagonal bin plot
    hb = plt.hexbin(x_array, y_array, gridsize=grid_size, cmap='YlOrRd', mincnt=1)
    
    plt.colorbar(hb, label='Vehicle Density (counts)')
    plt.title('Traffic Density Heatmap (Hexagonal)')
    plt.xlabel('X Coordinate (meters)')
    plt.ylabel('Y Coordinate (meters)')
    
    # Maintain the aspect ratio of the map
    plt.axis('equal') 
    
    plt.tight_layout()
    plt.savefig('traffic_density_heatmap_gridsize10.png', dpi=300, bbox_inches='tight')
    plt.show()

if __name__ == "__main__":
    # Replace with your actual SUMO xml file path
    # You can change grid_size to make hexagons smaller (e.g., 100) or larger (e.g., 30)
    plot_hexbin_traffic("../data/raw/simulation.out.xml", grid_size=10)