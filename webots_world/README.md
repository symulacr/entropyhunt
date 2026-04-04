# Webots World Assets

This directory contains an optional Webots-backed lane for Entropy Hunt.

## Files
- `entropy_hunt.wbt` — minimal arena with DEF-named drones, target, and supervisor robot
- `controllers/entropy_hunt_webots_supervisor/entropy_hunt_webots_supervisor.py` — Webots supervisor entrypoint that delegates to `simulation.webots_runtime`

## Notes
- This lane is optional for CI.
- It expects the Webots Python `controller` module to be available at runtime.
- The supervisor controller writes a JSON snapshot to `webots_world/webots_snapshot.json` on every successful simulation step.

## Environment variables
- `ENTROPYHUNT_PEER_ID` / `ENTROPYHUNT_DRONE_DEF` select which logical peer / DEF node the controller should drive.
- `ENTROPYHUNT_TRANSPORT=local|foxmq` switches between the local UDP mesh and the optional FoxMQ-backed transport.
- `ENTROPYHUNT_MQTT_HOST` / `ENTROPYHUNT_MQTT_PORT` configure the FoxMQ client connection when using `foxmq` transport.
- `ENTROPYHUNT_SNAPSHOT_PATH` / `ENTROPYHUNT_FINAL_MAP_PATH` control where the supervisor writes JSON output.
