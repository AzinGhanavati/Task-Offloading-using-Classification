import xml.etree.ElementTree as ET

def find_map_boundaries(file_name: str) -> None:
    print(f"Parsing {file_name}...")
    
    try:
        tree = ET.parse(file_name)
        root = tree.getroot()
    except Exception as e:
        print(f"Error reading XML file: {e}")
        return

    min_x, max_x = float('inf'), float('-inf')
    min_y, max_y = float('inf'), float('-inf')
    vehicle_count = 0

    for timestep in root.findall('timestep'):
        for vehicle in timestep.findall('vehicle'):
            vehicle_count += 1
            x = float(vehicle.get('x', 0.0))
            y = float(vehicle.get('y', 0.0))

            if x < min_x: min_x = x
            if x > max_x: max_x = x
            if y < min_y: min_y = y
            if y > max_y: max_y = y

    print("Map Boundaries Analysis:")
    print(f"Total vehicle records processed: {vehicle_count}")
    print(f"X-Axis: Min = {min_x:.2f}, Max = {max_x:.2f}")
    print(f"Y-Axis: Min = {min_y:.2f}, Max = {max_y:.2f}")
    print(f"Map Width: {(max_x - min_x):.2f} meters")
    print(f"Map Height: {(max_y - min_y):.2f} meters")

if __name__ == "__main__":
    # Replace with your actual SUMO xml file path
    find_map_boundaries("../data/raw/simulation.out.xml")