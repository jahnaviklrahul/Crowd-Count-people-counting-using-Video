# zones.py
import cv2
import json
import os

zones = []          # list of dicts: {"id": int, "x1":..,"y1":..,"x2":..,"y2":..}
drawing = False
ix, iy = -1, -1
current_frame = None
next_zone_id = 1

ZONES_FILE = "zones.json"

def load_zones():
    global zones, next_zone_id
    if not os.path.exists(ZONES_FILE):
        zones = []
        next_zone_id = 1
        return zones

    with open(ZONES_FILE, "r") as f:
        data = json.load(f)
        zones = data.get("zones", [])
    
    # FIX: Find next available ID starting from 1
    used_ids = {z["id"] for z in zones}
    next_zone_id = 1
    while next_zone_id in used_ids:
        next_zone_id += 1
    
    return zones

def save_zones():
    data = {"zones": zones}
    with open(ZONES_FILE, "w") as f:
        json.dump(data, f, indent=4)
    print("✓ Zones saved to", ZONES_FILE)

def draw_all_zones(frame):
    """Draw all zones and labels on given frame."""
    for z in zones:
        x1, y1, x2, y2 = z["x1"], z["y1"], z["x2"], z["y2"]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"Zone {z['id']}"
        cv2.putText(frame, label, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    return frame

def mouse_draw_rectangle(event, x, y, flags, param):
    """
    Mouse callback for drawing a new zone.
    Left button down: start
    Mouse move: preview
    Left button up: finalize and store zone
    """
    global ix, iy, drawing, current_frame, zones, next_zone_id

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y

    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        temp = current_frame.copy()
        cv2.rectangle(temp, (ix, iy), (x, y), (0, 255, 0), 2)
        draw_all_zones(temp)
        cv2.imshow("CrowdCount M1", temp)

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        x1, y1 = ix, iy
        x2, y2 = x, y
        # normalize coordinates
        x1, x2 = sorted([x1, x2])
        y1, y2 = sorted([y1, y2])
        zone = {"id": next_zone_id, "x1": x1, "y1": y1, "x2": x2, "y2": y2}
        zones.append(zone)
        next_zone_id += 1
        print("Zone added:", zone)
        temp = current_frame.copy()
        draw_all_zones(temp)
        cv2.imshow("CrowdCount M1", temp)

def delete_zone_by_id(zone_id):
    global zones, next_zone_id
    before = len(zones)
    zones = [z for z in zones if z["id"] != zone_id]
    after = len(zones)
    if before == after:
        print(f"No zone with id {zone_id} found.")
    else:
        print(f"Zone {zone_id} deleted.")
        # Renumber remaining zones to start from 1
        for i, z in enumerate(zones):
            z["id"] = i + 1
        # Update next_zone_id
        if zones:
            next_zone_id = max(z["id"] for z in zones) + 1
        else:
            next_zone_id = 1
        save_zones()  # auto-save after delete