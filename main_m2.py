# main_m2.py
import cv2
from ultralytics import YOLO

from camera_feed import open_source, read_frame, release_source
from zones import load_zones, draw_all_zones
from tracker_utils import CentroidTracker, point_in_rect, get_centroid
import zones as zones_module  # to access current_frame if needed


def main():
    # ===== CHOOSE SOURCE TYPE HERE =====
    # "video" -> use sample.mp4
    # "webcam" -> laptop camera
    # "image" -> single image (for demo, not real-time)
    source_type = "video"          # change to "webcam" or "image"
    source_path = "sample.mp4"    # set video/image path; None for webcam

    # ---------- Open source ----------
    cap, is_image, image_frame = open_source(source_type, source_path)
    if source_type != "image" and cap is None:
        return

    # ---------- Load YOLOv8 model ----------
    model = YOLO("yolov8n.pt")  # download automatically first time

    # ---------- Load zones from Milestone 1 ----------
    zones = load_zones()  # list of {"id", "x1","y1","x2","y2"}

    # ---------- Tracker ----------
    tracker = CentroidTracker(max_distance=60)

    cv2.namedWindow("CrowdCount M2", cv2.WINDOW_NORMAL)

    print("Controls:")
    print("  q : quit")

    while True:
        ret, frame = read_frame(cap, is_image, image_frame)
        if not ret or frame is None:
            print("No more frames / cannot read frame.")
            break

        zones_module.current_frame = frame.copy()

        display = frame.copy()
        draw_all_zones(display)

        # ---------- YOLO person detection ----------
        # classes=[0] -> person only
        results = model.predict(display, classes=[0], conf=0.4, imgsz=640, verbose=False)
        boxes = results[0].boxes

        detections = []
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            detections.append((x1, y1, x2, y2))

        # ---------- Tracking (assign IDs) ----------
        tracked = tracker.update(detections)  # list of (id,x1,y1,x2,y2)

        # ---------- Zone occupancy count (exact persons present now) ----------
        # reset counts for this frame
        zone_current_counts = {z["id"]: 0 for z in zones}

        # for each tracked person, see which zones they are in
        for tid, x1, y1, x2, y2 in tracked:
            cx, cy = get_centroid(x1, y1, x2, y2)
            for z in zones:
                if point_in_rect(cx, cy, z):
                    zone_current_counts[z["id"]] += 1

        # ---------- Draw tracked boxes, IDs, centroid, zone label ----------
        for tid, x1, y1, x2, y2 in tracked:
            cx, cy = get_centroid(x1, y1, x2, y2)
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 255), 2)
            label = f"ID {tid}"
            cv2.putText(display, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.circle(display, (cx, cy), 3, (0, 0, 255), -1)

            # show zone name if inside any zone
            inside_text = None
            for z in zones:
                if point_in_rect(cx, cy, z):
                    inside_text = f"Zone {z['id']}"
                    break
            if inside_text:
                cv2.putText(display, inside_text, (x1, y2 + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

        # ---------- Draw live zone occupancy on top-left ----------
        y0 = 30
        for z in zones:
            zid = z["id"]
            text = f"Zone {zid} Now: {zone_current_counts[zid]}"
            cv2.putText(display, text, (10, y0),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            y0 += 30

        cv2.imshow("CrowdCount M2", display)

        key = cv2.waitKey(1 if not is_image else 0) & 0xFF
        if key == ord('q'):
            break

        # for image mode, break after first show
        if is_image:
            break

    release_source(cap)


if __name__ == "__main__":
    main()
