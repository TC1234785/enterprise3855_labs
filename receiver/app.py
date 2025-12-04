import connexion                
from connexion import NoContent 
import time
import json
import datetime
import yaml
import logging
import logging.config
import random
from pykafka import KafkaClient
from pykafka.exceptions import KafkaException

# Load configuration file from shared config mount (per-service folder)
with open('/config/receiver/app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())

# Load logging configuration and set per-service logfile under /logs
with open('/config/log_conf.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    # ensure logs go to service-specific file
    if 'handlers' in log_config and 'file' in log_config['handlers']:
        log_config['handlers']['file']['filename'] = '/logs/receiver.log'

logging.config.dictConfig(log_config)
logger = logging.getLogger('basicLogger')        


class KafkaProducerWrapper:
    """Thread-safe Kafka producer wrapper with retry logic"""
    def __init__(self, hostname, topic):
        self.hostname = hostname
        self.topic = topic
        self.client = None
        self.producer = None
        self.connect()
    
    def connect(self):
        """Infinite loop: will keep trying until connected"""
        while True:
            logger.debug("Trying to connect to Kafka...")
            if self.make_client():
                if self.make_producer():
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
            self.producer = None
            return False
    
    def make_producer(self):
        """Creates Kafka producer. Returns True on success, False on failure"""
        if self.producer is not None:
            return True
        if self.client is None:
            return False
        try:
            topic = self.client.topics[str.encode(self.topic)]
            self.producer = topic.get_sync_producer()
            logger.info(f"Kafka producer created for topic {self.topic}")
            return True
        except KafkaException as e:
            logger.warning(f"Kafka error when making producer: {e}")
            self.client = None
            self.producer = None
            return False
    
    def produce(self, message):
        """Produces message with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self.producer is None:
                    self.connect()
                self.producer.produce(message)
                return True
            except KafkaException as e:
                logger.warning(f"Kafka error when producing (attempt {attempt+1}/{max_retries}): {e}")
                self.client = None
                self.producer = None
                if attempt < max_retries - 1:
                    time.sleep(random.randint(500, 1500) / 1000)
                    self.connect()
        logger.error("Failed to produce message after retries")
        return False


# Create global Kafka producer wrapper (thread-safe, reused across all requests)
kafka_hosts = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
kafka_wrapper = KafkaProducerWrapper(kafka_hosts, app_config['events']['topic'])
logger.info(f"Connected to Kafka brokers at {kafka_hosts}, topic={app_config['events']['topic']}")

def report_count_readings(body):
    # Receives batch passenger count readings and forwards each individual reading to the storage service.
    event_type = "passenger_count"
    readings = body.get("readings", [])
    logger.info(f"Received event {event_type} with {len(readings)} readings")

    # Loop through each individual reading in the batch
    for i, reading in enumerate(readings):
        # Generate unique trace_id for this event
        trace_id = time.time_ns()
        logger.info(f"Received event {event_type} with a trace id of {trace_id}")

        # Create individual event data for storage service
        event_data = {
            "trace_id": trace_id,
            "station_id": body.get("station_id"),
            "station_name": body.get("station_name"),
            "transit_system": body.get("transit_system"),
            "passenger_count": reading.get("passenger_count"),
            "batch_timestamp": body.get("reporting_timestamp"),
            "recorded_timestamp": reading.get("recorded_timestamp")
        }

        # Produce to Kafka instead of calling storage
        msg = {
            "type": "passenger_count",
            "datetime": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "payload": event_data
        }
        kafka_wrapper.produce(json.dumps(msg).encode('utf-8'))
        logger.info(f"Produced passenger_count message with trace_id={trace_id}")

    # Always return 201 as per async design
    return NoContent, 201

def report_wait_time_reading(body):
    # Receives batch incoming train readings and forwards each individual reading to the storage service.
    event_type = "wait_time"
    readings = body.get("readings", [])
    logger.info(f"Received event {event_type} with {len(readings)} readings")

    # Loop through each individual reading in the batch
    for i, reading in enumerate(readings):
        # Generate unique trace_id for this event
        trace_id = time.time_ns()
        logger.info(f"Received event {event_type} with a trace id of {trace_id}")

        # Create individual event data for storage service
        event_data = {
            "trace_id": trace_id,
            "station_id": body.get("station_id"),
            "station_name": body.get("station_name"),
            "transit_system": body.get("transit_system"),
            "current_minutes_wait": reading.get("current_minutes_wait"),
            "active_alerts": reading.get("active_alerts"),
            "batch_timestamp": body.get("reporting_timestamp"),
            "recorded_timestamp": reading.get("recorded_timestamp")
        }

        # Produce to Kafka instead of calling storage
        msg = {
            "type": "wait_time",
            "datetime": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "payload": event_data
        }
        kafka_wrapper.produce(json.dumps(msg).encode('utf-8'))
        logger.info(f"Produced wait_time message with trace_id={trace_id}")

    # Always return 201 as per async design
    return NoContent, 201

def health():
    """Health check endpoint"""
    return {"status": "ok"}, 200

app = connexion.FlaskApp(__name__, specification_dir='') 
app.add_api("student-770-NorthAmericanTrainInfo-1.0.0-swagger.yaml", strict_validation=True, validate_responses=True) 
if __name__ == "__main__":
    logger.info("Starting Receiver Service on port 8080")
    # Bind to 0.0.0.0 so Docker can expose the port outside the container
    app.run(host="0.0.0.0", port=8080)        