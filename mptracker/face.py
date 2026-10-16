"""Face embedding + crowd scanning (DeepFace ArcFace). DeepFace is imported lazily."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, List, Optional

import cv2
import numpy as np

from .config import Settings
from . import repository


def _normalize(vec) -> np.ndarray:
    emb = np.array(vec, dtype=np.float32)
    n = np.linalg.norm(emb)
    return emb / n if n > 0 else emb


def embed_image(path: str, settings: Settings) -> np.ndarray:
    from deepface import DeepFace
    reps = DeepFace.represent(img_path=path, model_name=settings.model_name,
                              detector_backend=settings.detector_backend, enforce_detection=True)
    return _normalize(reps[0]["embedding"])


@dataclass
class Detection:
    x: int
    y: int
    w: int
    h: int
    person: Optional[dict]
    distance: float


def scan_frame(frame, cur, settings: Settings) -> List[Detection]:
    from deepface import DeepFace
    results: List[Detection] = []
    try:
        faces = DeepFace.extract_faces(img_path=frame, detector_backend=settings.detector_backend,
                                       enforce_detection=False, align=True)
    except Exception:
        return results
    for f in faces:
        a = f["facial_area"]
        x, y, w, h = a["x"], a["y"], a["w"], a["h"]
        if w < settings.min_face_px or h < settings.min_face_px:
            continue
        crop = frame[max(0, y):y + h, max(0, x):x + w]
        if crop.size == 0:
            continue
        try:
            reps = DeepFace.represent(img_path=crop, model_name=settings.model_name,
                                      detector_backend="skip", enforce_detection=False)
        except Exception:
            continue
        person, dist = repository.find_match(cur, _normalize(reps[0]["embedding"]), settings.cosine_threshold)
        results.append(Detection(x, y, w, h, person, dist))
    return results


def annotate_frame(frame, detections: List[Detection]):
    for d in detections:
        if d.person:
            cv2.rectangle(frame, (d.x, d.y), (d.x + d.w, d.y + d.h), (0, 0, 255), 3)
            cv2.putText(frame, f"ALERT: {d.person['name']} ({d.distance:.2f})", (d.x, max(22, d.y - 24)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
            cv2.putText(frame, f"Age:{d.person['age']} | Clothes:{d.person['clothes']}",
                        (d.x, max(40, d.y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        else:
            cv2.rectangle(frame, (d.x, d.y), (d.x + d.w, d.y + d.h), (60, 60, 60), 1)
    return frame


def scan_images(cur, paths: List[str], settings: Settings,
                on_match: Callable[[dict, float, Optional[int], Optional[float]], None]) -> None:
    for path in paths:
        frame = cv2.imread(path)
        if frame is None:
            print(f"[!] Unable to read image: {path}")
            continue
        print(f"[*] Scanning {os.path.basename(path)} ...")
        dets = scan_frame(frame, cur, settings)
        for d in dets:
            if d.person:
                on_match(d.person, d.distance, None, None)
        base, fname = os.path.split(path)
        out = os.path.join(base, f"matched_{fname}")
        cv2.imwrite(out, annotate_frame(frame, dets))
        print(f"  [+] {sum(1 for d in dets if d.person)} match(es). Saved: {out}")


def scan_video(cur, path: str, settings: Settings,
               on_match: Callable[[dict, float, Optional[int], Optional[float]], None],
               cooldown_sec: float = 10.0, preview: bool = True) -> None:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f"[!] Could not open video: {path}")
        return
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    base, fname = os.path.split(path)
    out_path = os.path.join(base, f"matched_{fname}")
    out = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    n, cached, last_logged = 0, [], {}
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        n += 1
        if n % settings.frame_skip == 0:
            cached = scan_frame(frame, cur, settings)
            ts = n / fps
            for d in cached:
                if d.person and ts - last_logged.get(d.person["id"], -1e9) >= cooldown_sec:
                    last_logged[d.person["id"]] = ts
                    on_match(d.person, d.distance, n, round(ts, 2))
        out.write(annotate_frame(frame, cached))
        if preview:
            cv2.imshow("Crowd Search Preview", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    cap.release()
    out.release()
    if preview:
        cv2.destroyAllWindows()
    print(f"[+] Annotated video saved: {out_path}")
