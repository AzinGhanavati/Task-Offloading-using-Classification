import xml.etree.ElementTree as ET
import numpy as np
from sklearn.cluster import KMeans
import os

def analyze_coverage(sumo_file: str, test_k_values: list, radius_m: float = 300.0):
    print(f"Loading vehicle coordinates from {sumo_file}...")
    
    if not os.path.exists(sumo_file):
        print("Error: SUMO file not found.")
        return

    tree = ET.parse(sumo_file)
    root = tree.getroot()
    
    coords = []
    # Only extract one coordinate per vehicle to avoid heavy processing
    # and find the spatial distribution of the roads
    for timestep in root.findall('timestep'):
        for vehicle in timestep.findall('vehicle'):
            coords.append([
                float(vehicle.get('x', 0.0)), 
                float(vehicle.get('y', 0.0))
            ])
            
    data = np.array(coords)
    # Use unique road points to represent the urban grid traffic
    unique_data = np.unique(data, axis=0)
    total_points = len(unique_data)
    
    print(f"Total unique traffic points extracted: {total_points}")
    print(f"Testing coverage with Edge Server Radius = {radius_m} meters\n")
    print(f"{'Number of Servers (K)':<25} | {'Coverage Percentage'}")
    print("*" * 50)
    
    for k in test_k_values:
        # Run K-Means
        kmeans = KMeans(n_clusters=k, random_state=42, n_init='auto')
        kmeans.fit(unique_data)
        centroids = kmeans.cluster_centers_
        
        # Calculate distance from each point to all centroids
        # Shape: (total_points, k)
        distances = np.linalg.norm(unique_data[:, np.newaxis] - centroids, axis=2)
        
        # Find the distance to the nearest server for each point
        min_distances = np.min(distances, axis=1)
        
        # Count how many points are within the coverage radius
        covered_points = np.sum(min_distances <= radius_m)
        coverage_percent = (covered_points / total_points) * 100
        
        print(f"{k:<25} | {coverage_percent:.2f}%")
        
    print("\nRecommendation:")
    print("Choose the lowest K that gives you at least 85% to 90% coverage.")

if __name__ == "__main__":
    # Ensure this path matches your SUMO xml file
    sumo_xml_path = "../data/raw/simulation.out.xml"
    
    # Test different quantities of edge servers
    k_test_list = [3, 5, 10, 15, 20, 25]
    
    analyze_coverage(sumo_xml_path, k_test_list, radius_m=300.0)