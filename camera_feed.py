# camera_feed.py
import cv2

def open_source(source_type="webcam", path=None):
    """
    source_type: "webcam", "video", "image"
    path: file path for video/image
    Returns: (cap, is_image, frame)
      - cap: VideoCapture or None (for image)
      - is_image: True if single image
      - frame: initial frame (for image mode)
    """
    if source_type == "webcam":
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Cannot open webcam")
            return None, False, None
        return cap, False, None

    elif source_type == "video":
        if path is None:
            print("Error: Provide video path")
            return None, False, None
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            print("Error: Cannot open video file")
            return None, False, None
        return cap, False, None

    elif source_type == "image":
        if path is None:
            print("Error: Provide image path")
            return None, True, None
        frame = cv2.imread(path)
        if frame is None:
            print("Error: Cannot read image")
            return None, True, None
        return None, True, frame

    else:
        print("Unknown source_type")
        return None, False, None


def read_frame(cap, is_image, image_frame):
    """
    Returns a frame for display:
      - if is_image: always returns the same image_frame
      - if video/webcam: reads next frame from cap
    """
    if is_image:
        return True, image_frame.copy()

    if cap is None:
        return False, None

    ret, frame = cap.read()
    if not ret:
        return False, None
    return True, frame


def release_source(cap):
    if cap is not None:
        cap.release()
    cv2.destroyAllWindows()
