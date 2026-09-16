import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import numpy as np
import os

def plot_traffic_with_servers(sumo_xml: str, servers_xml: str, output_img: str, grid_size: int = 60):
    print(f"Loading SUMO traffic data from {sumo_xml}...")
    
    if not os.path.exists(sumo_xml):
        print("Error: SUMO XML file not found.")
        return

    tree = ET.parse(sumo_xml)
    root = tree.getroot()

    x_coords = []
    y_coords = []

    # Extract all vehicle coordinates
    for timestep in root.findall('timestep'):
        for vehicle in timestep.findall('vehicle'):
            x_coords.append(float(vehicle.get('x', 0.0)))
            y_coords.append(float(vehicle.get('y', 0.0)))

    x_array = np.array(x_coords)
    y_array = np.array(y_coords)

    # Initialize the plot
    plt.figure(figsize=(10, 8))

    # 1. Plot the traffic density heatmap
    hb = plt.hexbin(x_array, y_array, gridsize=grid_size, cmap='YlOrRd', mincnt=1)
    plt.colorbar(hb, label='Vehicle Density (counts)')

    # 2. Overlay the 10 Edge Servers
    if os.path.exists(servers_xml):
        print(f"Loading edge server locations from {servers_xml}...")
        server_tree = ET.parse(servers_xml)
        s_root = server_tree.getroot()
        
        sx = []
        sy = []
        for node in s_root.findall('node'):
            sx.append(float(node.get('x', 0.0)))
            sy.append(float(node.get('y', 0.0)))

        # Plot servers as large blue triangles
        plt.scatter(
            sx, sy, 
            color='blue', 
            marker='^', 
            s=150, 
            edgecolor='black', 
            linewidth=1.5,
            label='Edge Servers',
            zorder=5  # Ensure servers are drawn on top of the heatmap
        )
        plt.legend(loc='upper right')
    else:
        print("Warning: Edge servers XML not found. Run Phase 1 first.")

    # Apply labels and formatting
    plt.title('Traffic Density and Edge Server Placement (K=10)')
    plt.xlabel('X Coordinate (meters)')
    plt.ylabel('Y Coordinate (meters)')
    plt.axis('equal')
    plt.tight_layout()

    # Save the figure FIRST with high resolution
    print(f"Saving high-resolution image to {output_img}...")
    plt.savefig(output_img, dpi=300, bbox_inches='tight')
    
    # Show the figure on screen SECOND
    plt.show()

if __name__ == "__main__":
    # Define file paths
    sumo_file_path = "../data/raw/simulation.out.xml" 
    servers_file_path = "../data/dataset/edge_placement.xml"
    output_image_path = "traffic_servers_topology.png"
    
    plot_traffic_with_servers(
        sumo_xml=sumo_file_path, 
        servers_xml=servers_file_path, 
        output_img=output_image_path,
        grid_size=60
    )