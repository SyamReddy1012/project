"""Command line interface:  python -m mptracker <command>"""
from __future__ import annotations

import argparse
import math
import os
import sys

from . import dispatch as dsp
from . import repository as repo
from .config import get_settings
from .models import GeoPoint
from .zones import SearchZoneAnalyzer, zones_to_geojson


def _print_zones(zones) -> None:
    print(f"\n{'#':<3} {'Location':<26} {'Score':>6} {'Dist km':>8} {'Radius km':>10}  Reason")
    for z in zones:
        print(f"{z.rank:<3} {z.location.name:<26} {z.score:>6.2f} {z.distance_km:>8.2f} "
              f"{z.radius_km:>10.2f}  {z.reason}")


def cmd_demo(args) -> None:
    from .demo import build_demo
    graph, person, now = build_demo()
    last = person.last_sighting
    print(f"{person.name} (age {person.age}) last seen at '{last.location.name}' "
          f"{(now - last.timestamp).seconds // 60} min ago")
    zones = SearchZoneAnalyzer(graph).analyze(person, now=now, top_k=args.top)
    _print_zones(zones)
    if args.geojson:
        with open(args.geojson, "w", encoding="utf-8") as fh:
            fh.write(zones_to_geojson(zones))
        print(f"\nGeoJSON written to {args.geojson}")


def cmd_web(args) -> None:
    from .web import run_server
    port = args.port or int(os.environ.get("PORT", 10000))
    run_server(host=args.host, port=port)


def cmd_init_db(args) -> None:
    from .db import init_db
    init_db(get_settings())
    print("[+] Schema applied.")


def cmd_enroll(args) -> None:
    from .db import connect
    from .face import embed_image
    s = get_settings()
    print("[*] Generating ArcFace embedding ...")
    emb = embed_image(args.photo, s)
    conn = connect(s)
    with conn, conn.cursor() as cur:
        pid, created = repo.insert_person(cur, args.name, args.age, args.gender, args.photo,
                                          args.clothes, args.last_seen, emb, args.lat, args.lon)
    conn.close()
    print(f"[+] Enrolled '{args.name}' as ID {pid} at {created}")


def _make_on_match(cur, conn, args):
    camera = repo.get_or_create_camera(cur, args.camera, args.lat, args.lon) if args.camera else None
    has_coords = camera is not None and not math.isnan(camera.point.lat)
    source = args.camera or "unknown"

    def on_match(person, dist, frame_no, ts_sec):
        print(f"  [ALERT] {person['name']} (id={person['id']}, distance={dist:.3f})")
        repo.log_sighting(cur, person["id"], camera, source, ts_sec, frame_no, dist)
        if args.dispatch and has_coords:
            res = dsp.create_dispatch(cur, person["id"], camera.name, camera.point)
            if res:
                team, km, eta = res
                print(f"  [DISPATCH] {team.name} ({team.phone}) - {km:.1f} km, ETA {eta} min")
        conn.commit()
    return on_match


def cmd_scan_photo(args) -> None:
    from .db import connect
    from .face import scan_images
    s = get_settings()
    conn = connect(s)
    cur = conn.cursor()
    scan_images(cur, args.paths, s, _make_on_match(cur, conn, args))
    conn.close()


def cmd_scan_video(args) -> None:
    from .db import connect
    from .face import scan_video
    s = get_settings()
    conn = connect(s)
    cur = conn.cursor()
    scan_video(cur, args.path, s, _make_on_match(cur, conn, args), preview=not args.no_preview)
    conn.close()


def cmd_dispatches(args) -> None:
    from .db import connect
    conn = connect(get_settings())
    with conn.cursor() as cur:
        rows = dsp.list_active(cur)
    conn.close()
    if not rows:
        print("[*] No en-route dispatches.")
    for d_id, p, t, loc, when in rows:
        print(f"[{d_id}] {p} | team: {t} | at: {loc} | dispatched: {when}")


def cmd_resolve(args) -> None:
    from .db import connect
    conn = connect(get_settings())
    with conn, conn.cursor() as cur:
        status = dsp.resolve(cur, args.dispatch_id, args.outcome, args.notes or "")
    conn.close()
    print(f"[+] Dispatch {args.dispatch_id} -> {status}. Team freed.")


def cmd_analyze(args) -> None:
    from datetime import datetime
    from .db import connect
    conn = connect(get_settings())
    with conn.cursor() as cur:
        graph = repo.load_graph(cur, args.connect_km)
        person = repo.load_person(cur, args.person_id, graph)
    conn.close()
    if not person.last_sighting:
        print("[!] No located sightings for this person yet.")
        return
    graph.ingest_person(person)
    zones = SearchZoneAnalyzer(graph).analyze(person, datetime.now(), args.top, args.speed)
    _print_zones(zones)
    if args.geojson:
        with open(args.geojson, "w", encoding="utf-8") as fh:
            fh.write(zones_to_geojson(zones))
        print(f"\nGeoJSON written to {args.geojson}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mptracker", description="Missing Person Search-and-Track System")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="Run graph/search-zone demo (no DB needed)")
    d.add_argument("--top", type=int, default=5)
    d.add_argument("--geojson")
    d.set_defaults(func=cmd_demo)

    w = sub.add_parser("web", help="Start web dashboard server")
    w.add_argument("--port", type=int, default=None, help="Port to listen on (default: $PORT or 10000)")
    w.add_argument("--host", default="0.0.0.0", help="Host address to bind (default: 0.0.0.0)")
    w.set_defaults(func=cmd_web)

    sub.add_parser("init-db", help="Create tables").set_defaults(func=cmd_init_db)

    e = sub.add_parser("enroll", help="Enroll a missing person")
    e.add_argument("--name", required=True)
    e.add_argument("--photo", required=True)
    e.add_argument("--age", type=int)
    e.add_argument("--gender")
    e.add_argument("--clothes")
    e.add_argument("--last-seen")
    e.add_argument("--lat", type=float)
    e.add_argument("--lon", type=float)
    e.set_defaults(func=cmd_enroll)

    def add_loc(sp):
        sp.add_argument("--camera", help="Camera/location name (creates graph node)")
        sp.add_argument("--lat", type=float)
        sp.add_argument("--lon", type=float)
        sp.add_argument("--dispatch", action="store_true", help="Auto-dispatch nearest team on match")

    sp = sub.add_parser("scan-photo", help="Scan crowd photo(s)")
    sp.add_argument("paths", nargs="+")
    add_loc(sp)
    sp.set_defaults(func=cmd_scan_photo)

    sv = sub.add_parser("scan-video", help="Scan crowd video")
    sv.add_argument("path")
    sv.add_argument("--no-preview", action="store_true")
    add_loc(sv)
    sv.set_defaults(func=cmd_scan_video)

    sub.add_parser("dispatches", help="List en-route dispatches").set_defaults(func=cmd_dispatches)

    r = sub.add_parser("resolve", help="Close a dispatch")
    r.add_argument("dispatch_id", type=int)
    r.add_argument("--outcome", required=True, choices=list(dsp.OUTCOMES))
    r.add_argument("--notes")
    r.set_defaults(func=cmd_resolve)

    a = sub.add_parser("analyze", help="Rank likely search zones for a person")
    a.add_argument("person_id", type=int)
    a.add_argument("--speed", type=float, help="Override travel speed km/h")
    a.add_argument("--top", type=int, default=5)
    a.add_argument("--connect-km", type=float, default=1.5)
    a.add_argument("--geojson")
    a.set_defaults(func=cmd_analyze)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
