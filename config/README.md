Config layout

- Shared logging config:
  - log_conf.yml

- Per-service application configs (mounted at /config inside each container):
  - analyzer/app_conf.yml
  - receiver/app_conf.yml
  - storage/app_conf.yml
  - processing/app_conf.yml

Notes
- The old top-level *_config.yml files are removed. Each service now reads its own app_conf.yml under its folder.
- Processing persists its JSON to /data/processing/processing.json; host bind mount is ./data/processing.
- Zookeeper uses named volumes for data/log; Kafka uses a bind mount at ./data/kafka mapped to /kafka.
- On Windows, if MySQL fails with a bind mount, run with the override docker-compose.win.yaml to switch DB to a named volume.
