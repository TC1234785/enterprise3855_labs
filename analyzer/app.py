import connexion
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
import json
import yaml
import logging
import logging.config
import time
import random
from connexion import NoContent
from pykafka import KafkaClient
from pykafka.exceptions import KafkaException

# Load configuration from shared config mount (per-service folder)
with open('/config/analyzer/app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())

with open('/config/log_conf.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    if 'handlers' in log_config and 'file' in log_config['handlers']:
        log_config['handlers']['file']['filename'] = '/logs/analyzer.log'
logging.config.dictConfig(log_config)
logger = logging.getLogger('basicLogger')


class KafkaConsumerWrapper:
    """Thread-safe Kafka consumer wrapper with retry logic for analyzer"""
    def __init__(self, hostname, topic):
        self.hostname = hostname
        self.topic = topic
        self.client = None
        self.consumer = None
        self.connect()
    
    def connect(self):
        """Infinite loop: will keep trying until connected"""
        while True:
            logger.debug("Trying to connect to Kafka...")
            if self.make_client():
                if self.make_consumer():
                    break
            # Sleep for random amount of time (0.5 to 1.5s)
            time.sleep(random.randint(500, 1500) / 1000)
    
    def make_client(self):
        """Creates Kafka client. Returns True on success, False on failure"""
        if self.client is not None:
            return True
        try:
            self.client = KafkaClient(hosts=self.hostname)
            logger.info("Kafka client created!")
            return True
        except KafkaException as e:
            logger.warning(f"Kafka error when making client: {e}")
            self.client = None
            self.consumer = None
            return False
    
    def make_consumer(self):
        """Creates Kafka consumer. Returns True on success, False on failure"""
        if self.consumer is not None:
            return True
        if self.client is None:
            return False
        try:
            topic = self.client.topics[str.encode(self.topic)]
            self.consumer = topic.get_simple_consumer(
                reset_offset_on_start=True,
                consumer_timeout_ms=10000  # 10 seconds to ensure all messages are read
            )
            logger.info(f"Kafka consumer created for topic {self.topic}")
            return True
        except KafkaException as e:
            logger.warning(f"Kafka error when making consumer: {e}")
            self.client = None
            self.consumer = None
            return False
    
    def get_consumer(self):
        """Returns a fresh consumer that reads from beginning"""
        # Always create a new consumer to ensure we read from start
        self.consumer = None
        self.connect()
        return self.consumer


# Create global Kafka consumer wrapper (reused across all requests)
hosts = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
kafka_wrapper = KafkaConsumerWrapper(hosts, app_config['events']['topic'])
logger.info(f"Connected to Kafka brokers at {hosts}, topic={app_config['events']['topic']}")


def get_passenger_event(index: int):
    """Return the passenger_count payload at given index."""
    try:
        consumer = kafka_wrapper.get_consumer()
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
    except Exception as e:
        logger.error(f"Error fetching passenger event: {e}")
        # Reset consumer on error
        kafka_wrapper.consumer = None
        return {"message": "Error fetching event"}, 500


def get_wait_time_event(index: int):
    """Return the wait_time payload at given index."""
    try:
        consumer = kafka_wrapper.get_consumer()
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
    except Exception as e:
        logger.error(f"Error fetching wait_time event: {e}")
        # Reset consumer on error
        kafka_wrapper.consumer = None
        return {"message": "Error fetching event"}, 500


def get_stats():
    """Return counts of passenger_count and wait_time events."""
    try:
        consumer = kafka_wrapper.get_consumer()
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
    except Exception as e:
        logger.error(f"Error computing stats: {e}")
        # Reset consumer on error
        kafka_wrapper.consumer = None
        return {"message": "Error computing stats"}, 500


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
