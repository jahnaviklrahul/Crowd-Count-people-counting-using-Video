# app.py
import threading
import time
import datetime
import csv
import io

import cv2
from flask import (
    Flask, jsonify, render_template,
    request, redirect, url_for, session,
    send_file, flash
)
from ultralytics import YOLO
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

from tracker_utils import CentroidTracker, point_in_rect, get_centroid
from zones import load_zones, draw_all_zones
from camera_feed import open_source, read_frame, release_source

app = Flask(__name__)
app.secret_key = "change_this_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///crowd.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ----------------- DB MODELS -----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(16))  # "admin" or "user"

class Camera(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    source_type = db.Column(db.String(16))  # "webcam" or "video"
    source_path = db.Column(db.String(256), nullable=True)
    active = db.Column(db.Boolean, default=True)

class ZoneMeta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    zone_id = db.Column(db.Integer)  # matches zones.json id
    name = db.Column(db.String(128))
    threshold = db.Column(db.Integer, default=50)

class CountLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    zone_id = db.Column(db.Integer)
    count = db.Column(db.Integer)

class AlertLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    zone_id = db.Column(db.Integer)
    count = db.Column(db.Integer)
    threshold = db.Column(db.Integer)
    message = db.Column(db.String(256))

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        admin_user = User(
            username="admin",
            password_hash=generate_password_hash("admin123"),
            role="admin"
        )
        db.session.add(admin_user)
        db.session.commit()

# ----------------- GLOBAL STATE -----------------
live_state = {
    "total_now": 0,
    "zones_now": {},    # {zone_id: count}
    "alerts": [],
    "people": {}        # {id_str: {zone, x, y, t}}
}
state_lock = threading.Lock()

# ----------------- AUTH HELPERS -----------------
def current_user():
    username = session.get("username")
    if not username:
        return None
    return User.query.filter_by(username=username).first()

def login_required(role=None):
    def decorator(fn):
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for("login"))
            if role and user.role != role:
                return "Forbidden", 403
            return fn(*args, **kwargs)
        wrapped.__name__ = fn.__name__
        return wrapped
    return decorator

# ----------------- ROUTES -----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(username=request.form["username"]).first()
        if u and check_password_hash(u.password_hash, request.form["password"]):
            session["username"] = u.username
            return redirect(url_for("dashboard"))
        flash("Invalid credentials")
    return render_template("login.html", title="Login", user=current_user())

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required()
def dashboard():
    return render_template("dashboard.html", title="Dashboard", user=current_user())

@app.route("/get_state")
def get_state():
    with state_lock:
        data = {
            "total_now": live_state["total_now"],
            "zones_now": live_state["zones_now"],
            "alerts": live_state["alerts"],
            "people": live_state["people"],
        }
    return jsonify(data)

@app.route("/admin")
@login_required(role="admin")
def admin_panel():
    cameras = Camera.query.all()
    zones = load_zones()
    zones_meta = []
    for z in zones:
        zm = ZoneMeta.query.filter_by(zone_id=z["id"]).first()
        if not zm:
            zm = ZoneMeta(zone_id=z["id"], name=f"Zone {z['id']}", threshold=50)
            db.session.add(zm)
            db.session.commit()
        zones_meta.append(zm)
    return render_template(
        "admin.html",
        title="Admin",
        user=current_user(),
        cameras=cameras,
        zones_meta=zones_meta
    )

@app.route("/admin/add_camera", methods=["POST"])
@login_required(role="admin")
def add_camera():
    name = request.form["name"]
    stype = request.form["source_type"]
    spath = request.form.get("source_path") or None
    cam = Camera(name=name, source_type=stype, source_path=spath, active=True)
    db.session.add(cam)
    db.session.commit()
    flash("Camera added")
    return redirect(url_for("admin_panel"))

@app.route("/admin/update_thresholds", methods=["POST"])
@login_required(role="admin")
def update_thresholds():
    zones = load_zones()
    for z in zones:
        zid = z["id"]
        field = f"threshold_{zid}"
        if field in request.form:
            val = int(request.form[field])
            zm = ZoneMeta.query.filter_by(zone_id=zid).first()
            if zm:
                zm.threshold = val
            else:
                zm = ZoneMeta(zone_id=zid, name=f"Zone {zid}", threshold=val)
                db.session.add(zm)
    db.session.commit()
    flash("Thresholds updated")
    return redirect(url_for("admin_panel"))

@app.route("/admin/export_csv")
@login_required(role="admin")
def export_csv():
    minutes = int(request.args.get("minutes", 60))
    since = datetime.datetime.utcnow() - datetime.timedelta(minutes=minutes)
    logs = CountLog.query.filter(CountLog.timestamp >= since).order_by(CountLog.timestamp.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp_utc", "zone_id", "count"])
    for log in logs:
        writer.writerow([log.timestamp.isoformat(), log.zone_id, log.count])
    mem = io.BytesIO()
    mem.write(output.getvalue().encode("utf-8"))
    mem.seek(0)
    return send_file(
        mem,
        mimetype="text/csv",
        as_attachment=True,
        download_name="counts.csv"
    )

# ----------------- DETECTION THREAD -----------------
def detection_loop():
    '''with app.app_context():
        cam = Camera.query.filter_by(active=True).first()
    if cam:
        if cam.source_type == "webcam":
            source_type = "webcam"
            source_path = None
        else:
            source_type = "video"
            source_path = cam.source_path or "sample.mp4"
    else:
        source_type = "video"
        source_path = "sample.mp4" '''
    source_type = "video"
    source_path = "sample2.mp4" #YOUR VIDEO # 3 1
    cap, is_image, image_frame = open_source(source_type, source_path)
    if source_type != "image" and cap is None:
        print("Error: cannot open source")
        return

    model = YOLO("yolov8n.pt")
    zones = load_zones()
    tracker = CentroidTracker(max_distance=60)

    cv2.namedWindow("CrowdCount", cv2.WINDOW_NORMAL)

    while True:
        ret, frame = read_frame(cap, is_image, image_frame)
        if not ret or frame is None:
            print("No more frames / cannot read frame.")
            break

        display = frame.copy()
        draw_all_zones(display)

        results = model.predict(display, classes=[0], conf=0.4, imgsz=640, verbose=False)
        boxes = results[0].boxes

        detections = []
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            detections.append((x1, y1, x2, y2))

        tracked = tracker.update(detections)

        zone_current_counts = {z["id"]: 0 for z in zones}
        people_info = {}  # id -> {zone, x, y, t}

        for tid, x1, y1, x2, y2 in tracked:
            cx, cy = get_centroid(x1, y1, x2, y2)
            zone_here = None
            for z in zones:
                if point_in_rect(cx, cy, z):
                    zid = z["id"]
                    zone_here = zid
                    zone_current_counts[zid] += 1
            people_info[tid] = {
                "zone": zone_here,
                "x": int(cx),
                "y": int(cy),
                "t": datetime.datetime.now().strftime("%H:%M:%S")
            }

        total_now = sum(zone_current_counts.values())

        now_utc = datetime.datetime.utcnow()
        alerts = []
        with app.app_context():
            for zid, count in zone_current_counts.items():
                clog = CountLog(timestamp=now_utc, zone_id=zid, count=count)
                db.session.add(clog)

                zm = ZoneMeta.query.filter_by(zone_id=zid).first()
                if zm and count > zm.threshold:
                    msg = f"[{now_utc.strftime('%H:%M:%S')}] Zone {zid} exceeded threshold {zm.threshold} with {count}"
                    al = AlertLog(
                        timestamp=now_utc,
                        zone_id=zid,
                        count=count,
                        threshold=zm.threshold,
                        message=msg
                    )
                    db.session.add(al)
                    alerts.append(msg)
            db.session.commit()

        with state_lock:
            live_state["total_now"] = int(total_now)
            live_state["zones_now"] = {int(k): int(v) for k, v in zone_current_counts.items()}
            live_state["alerts"] = alerts
            live_state["people"] = {str(k): v for k, v in people_info.items()}

        # local preview
        for tid, x1, y1, x2, y2 in tracked:
            cx, cy = get_centroid(x1, y1, x2, y2)
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.putText(display, f"ID {tid}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.circle(display, (cx, cy), 3, (0, 0, 255), -1)

        y0 = 30
        for z in zones:
            zid = z["id"]
            text = f"Zone {zid}: {zone_current_counts[zid]}"
            cv2.putText(display, text, (10, y0),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            y0 += 30

        cv2.imshow("CrowdCount", display)
        key = cv2.waitKey(1 if not is_image else 0) & 0xFF
        if key == ord('q'):
            break
        if is_image:
            time.sleep(1)
 
    release_source(cap)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    t = threading.Thread(target=detection_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000, debug=True)
