# tracker_utils.py
import math

class CentroidTracker:
    def __init__(self, max_distance=50):
        self.next_id = 1
        self.objects = {}  # id -> (cx, cy)
        self.max_distance = max_distance

    def update(self, detections):
        """
        detections: list of (x1, y1, x2, y2)
        returns: list of (id, x1, y1, x2, y2)
        """
        tracked = []
        used_ids = set()

        for (x1, y1, x2, y2) in detections:
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2

            # find closest existing id
            best_id = None
            best_dist = None
            for oid, (ox, oy) in self.objects.items():
                dist = math.hypot(cx - ox, cy - oy)
                if best_dist is None or dist < best_dist:
                    best_dist = dist
                    best_id = oid

            if best_id is not None and best_dist is not None and best_dist < self.max_distance and best_id not in used_ids:
                # update existing id
                self.objects[best_id] = (cx, cy)
                used_ids.add(best_id)
                tracked.append((best_id, x1, y1, x2, y2))
            else:
                # new id
                oid = self.next_id
                self.next_id += 1
                self.objects[oid] = (cx, cy)
                used_ids.add(oid)
                tracked.append((oid, x1, y1, x2, y2))

        # optional: remove ids not updated this frame (simple clean-up)
        self.objects = {oid: self.objects[oid] for oid in used_ids}
        return tracked


def point_in_rect(cx, cy, rect):
    """
    rect: dict with x1,y1,x2,y2
    """
    return rect["x1"] <= cx <= rect["x2"] and rect["y1"] <= cy <= rect["y2"]


def get_centroid(x1, y1, x2, y2):
    cx = int((x1 + x2) / 2)
    cy = int((y1 + y2) / 2)
    return cx, cy
