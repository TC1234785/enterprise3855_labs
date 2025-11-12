Data persistence

This folder holds bind-mounted data used by Docker Compose services:

- database/ -> mounted to MySQL at /var/lib/mysql (Linux/macOS). On Windows, use docker-compose.win.yaml to switch to a named volume (db_data) for reliability.
- kafka/ -> mounted to Kafka at /kafka for broker logs and metadata.
- processing/ -> mounted to processing service at /data/processing to persist processing.json outputs.
- zookeeper/ -> ZooKeeper uses named volumes (zookeeper_data, zookeeper_log); this folder is not mounted by default and may remain empty.

Operational tips
- If Kafka and ZooKeeper cluster IDs get out of sync, use scripts/reset-kafka-cluster.ps1 to clear Kafka meta.properties and restart ZK → Kafka.
- Avoid manually editing files inside these directories while services are running.
- Back up database/ before reinitializing MySQL if you need to preserve data.