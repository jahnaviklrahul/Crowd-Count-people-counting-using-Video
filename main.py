# main.py
import cv2
from camera_feed import open_source, read_frame, release_source
from zones import (
    load_zones,
    save_zones,
    draw_all_zones,
    mouse_draw_rectangle,
    delete_zone_by_id,
    # globals from zones.py:
    )

import zones as zones_module  # to access current_frame global

def main():
    # ====== CHOOSE SOURCE HERE ======
    # options:
    #   ("webcam", None)
    #   ("video", "sample.mp4")
    #   ("image", "sample.jpg")
    source_type = "video"      # change to "webcam" or "image" as needed
    source_path = "sample2.mp4" # or "sample.jpg" or None

    cap, is_image, image_frame = open_source(source_type, source_path)
    if source_type != "image" and cap is None:
        return

    # Load existing zones
    load_zones()

    cv2.namedWindow("CrowdCount M1", cv2.WINDOW_NORMAL)  # resizable window
    cv2.setWindowProperty("CrowdCount M1",cv2.WND_PROP_FULLSCREEN,cv2.WINDOW_NORMAL)  # NOT WINDOW_FULLSCREEN
    cv2.setMouseCallback("CrowdCount M1", mouse_draw_rectangle)


    print("Controls:")
    print("  Draw zone: Left-click and drag on window")
    print("  s : save zones")
    print("  d : delete zone (then press zone id digit)")
    print("  q : quit")

    delete_mode = False
    pending_delete_id = None

    while True:
        ret, frame = read_frame(cap, is_image, image_frame)
        if not ret or frame is None:
            print("No more frames or cannot read frame.")
            break

        # update global current_frame used by mouse callback
        zones_module.current_frame = frame.copy()

        # draw all zones
        display = frame.copy()
        draw_all_zones(display)

        cv2.imshow("CrowdCount M1", display)

        key = cv2.waitKey(20) & 0xFF

        if key == ord('q'):
            break

        elif key == ord('s'):
            save_zones()

        elif key == ord('d'):
            print("Delete mode: press zone id digit (e.g., 1,2,3)")
            delete_mode = True
            pending_delete_id = None

        elif delete_mode:
            # expecting a digit key for zone id
            if ord('0') <= key <= ord('9'):
                zone_id = int(chr(key))
                delete_zone_by_id(zone_id)
                delete_mode = False
                pending_delete_id = None
            elif key == 27:  # ESC to cancel delete mode
                delete_mode = False
                pending_delete_id = None

        # if image source, break after interaction unless you want loop
        if is_image:
            # keep showing same image until q
            pass

    release_source(cap)


if __name__ == "__main__":
    main()
