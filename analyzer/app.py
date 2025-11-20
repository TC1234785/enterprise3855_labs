import connexion
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
import json
import yaml
import logging
import logging.config
from connexion import NoContent
from pykafka import KafkaClient

# Load configuration from shared config mount (per-service folder)
with open('/config/analyzer/app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())

with open('/config/log_conf.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    if 'handlers' in log_config and 'file' in log_config['handlers']:
        log_config['handlers']['file']['filename'] = '/logs/analyzer.log'
logging.config.dictConfig(log_config)
logger = logging.getLogger('basicLogger')


def _make_consumer():
    hosts = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
    client = KafkaClient(hosts=hosts)
    topic = client.topics[str.encode(app_config['events']['topic'])]
    consumer = topic.get_simple_consumer(
        reset_offset_on_start=True,
        consumer_timeout_ms=1000
    )
    return consumer


def get_passenger_event(index: int):
    """Return the passenger_count payload at given index."""
    consumer = _make_consumer()
    count = 0
    for msg in consumer:
        data = json.loads(msg.value.decode('utf-8'))
        if data.get('type') == 'passenger_count':
            if count == index:
                logger.debug("Fetched passenger_count index=%d trace_id=%s", index, data['payload'].get('trace_id'))
                return data['payload'], 200
            count += 1
    logger.debug("No passenger_count at index=%d; total passenger_count seen=%d", index, count)
    return {"message": f"No message at index {index}!"}, 404


def get_wait_time_event(index: int):
    """Return the wait_time payload at given index."""
    consumer = _make_consumer()
    count = 0
    for msg in consumer:
        data = json.loads(msg.value.decode('utf-8'))
        if data.get('type') == 'wait_time':
            if count == index:
                logger.debug("Fetched wait_time index=%d trace_id=%s", index, data['payload'].get('trace_id'))
                return data['payload'], 200
            count += 1
    logger.debug("No wait_time at index=%d; total wait_time seen=%d", index, count)
    return {"message": f"No message at index {index}!"}, 404


def get_stats():
    """Return counts of passenger_count and wait_time events."""
    consumer = _make_consumer()
    num_passenger = 0
    num_wait = 0
    for msg in consumer:
        data = json.loads(msg.value.decode('utf-8'))
        t = data.get('type')
        if t == 'passenger_count':
            num_passenger += 1
        elif t == 'wait_time':
            num_wait += 1
    res = {"num_passenger_readings": num_passenger, "num_wait_time_readings": num_wait}
    logger.debug("Stats computed: %s", res)
    return res, 200


app = connexion.FlaskApp(__name__, specification_dir='')
app.add_middleware(
    CORSMiddleware,
    position=MiddlewarePosition.BEFORE_EXCEPTION,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_api('openapi.yaml', strict_validation=True, validate_responses=True)

if __name__ == '__main__':
    logger.info("Starting Analyzer on port %d", app_config['server']['port'])
    # Bind to 0.0.0.0 so Docker can expose the port outside the container
    app.run(host="0.0.0.0", port=app_config['server']['port'])
