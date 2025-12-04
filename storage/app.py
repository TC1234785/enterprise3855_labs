import connexion  
from connexion import NoContent
import functools
import os
import yaml
import logging
import logging.config
import json
import datetime
import time
import random
from pykafka import KafkaClient
from pykafka.common import OffsetType
from pykafka.exceptions import KafkaException
import threading
from datetime import datetime as dt
from datetime import date, timezone

from event_models import PassengerCountEvent, WaitTimeEvent  
from sqlalchemy import create_engine, select  
from sqlalchemy.orm import sessionmaker 
 
# Seems like the datetime information does not get parsed correctly without this
from dateutil import parser

# Load configuration file from shared config mount (per-service folder)
with open('/config/storage/app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())

# Load logging configuration and set per-service logfile under /logs
with open('/config/log_conf.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    if 'handlers' in log_config and 'file' in log_config['handlers']:
        log_config['handlers']['file']['filename'] = '/logs/storage.log'
logging.config.dictConfig(log_config)

# Create logger
logger = logging.getLogger('basicLogger')

# Create MySQL database engine using configuration with connection pooling
db_config = app_config['datastore']
db_url = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['hostname']}:{db_config['port']}/{db_config['db']}"
ENGINE = create_engine(
    db_url,
    pool_size=10,              # Maximum number of connections to keep in pool
    max_overflow=20,           # Maximum overflow connections beyond pool_size
    pool_recycle=3600,         # Recycle connections after 1 hour (3600s) to prevent stale connections
    pool_pre_ping=True         # Test connections before using them to catch stale/closed connections
)
SessionLocal = sessionmaker(bind=ENGINE)  

def make_session():
    #Creates a new database session
    return SessionLocal()

def use_db_session(func):
    #create decorator to handle db sessions automatically. This is given in the lab instructions
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        session = make_session()
        try:
            return func(session, *args, **kwargs)
        finally:
            session.close()
    return wrapper

@use_db_session
def report_count_reading(session, body):
    trace_id = body.get("trace_id")
    event = PassengerCountEvent(
        trace_id=trace_id,
        station_id=body.get("station_id"),
        station_name=body.get("station_name"),
        transit_system=body.get("transit_system"),
        average=body.get("passenger_count"),
        num_values=1,
        batch_timestamp=parser.isoparse(body.get("batch_timestamp")),
        date_created=None,
    )
    session.add(event)
    session.commit()
    
    # Log after successful storage
    logger.debug(f"Stored event passenger_count with a trace id of {trace_id}")
    
    return NoContent, 201 

@use_db_session
def get_passenger_count_readings(session,start_timestamp, end_timestamp):
    """ Gets new passenger_count readings between the start and end timestamps """

    # Use dateutil to support ISO-8601 with 'Z' suffix and various precisions
    start = parser.isoparse(start_timestamp)
    end = parser.isoparse(end_timestamp)
    # Normalize to naive UTC to match DB timestamps (MySQL container typically stores NOW() in UTC)
    if start.tzinfo is not None:
        start = start.astimezone(timezone.utc).replace(tzinfo=None)
    if end.tzinfo is not None:
        end = end.astimezone(timezone.utc).replace(tzinfo=None)

    statement = select(PassengerCountEvent).where(PassengerCountEvent.date_created >= start).where(PassengerCountEvent.date_created < end)
    results = [result.to_dict()
        for result in session.execute(statement).scalars().all()
        ]
    logger.debug("Found %d PassengerCountEvent readings (start: %s, end: %s)", len(results), start, end)
    return results

@use_db_session
def report_wait_time_reading(session, body):
    trace_id = body.get("trace_id")
    #Store wait time reading in the database
    event = WaitTimeEvent(
        trace_id=trace_id,
        station_id=body.get("station_id"),
        station_name=body.get("station_name"),
        transit_system=body.get("transit_system"),
        average=body.get("current_minutes_wait"),
        num_values=1,
        batch_timestamp=parser.isoparse(body.get("batch_timestamp")),
        date_created=None
    )
    session.add(event)  
    session.commit()
    
    # Log after successful storage
    logger.debug(f"Stored event wait_time with a trace id of {trace_id}")
    
    return NoContent, 201  

@use_db_session
def get_wait_time_reading(session,start_timestamp, end_timestamp):
    """ Gets new wait_time readings between the start and end timestamps """

    # Use dateutil to support ISO-8601 with 'Z' suffix and various precisions
    start = parser.isoparse(start_timestamp)
    end = parser.isoparse(end_timestamp)
    # Normalize to naive UTC to match DB timestamps (MySQL container typically stores NOW() in UTC)
    if start.tzinfo is not None:
        start = start.astimezone(timezone.utc).replace(tzinfo=None)
    if end.tzinfo is not None:
        end = end.astimezone(timezone.utc).replace(tzinfo=None)
    statement = select(WaitTimeEvent).where(WaitTimeEvent.date_created >= start).where(WaitTimeEvent.date_created < end)
    results = [result.to_dict()
        for result in session.execute(statement).scalars().all()
        ]
    logger.debug("Found %d WaitTimeEvent readings (start: %s, end: %s)", len(results), start, end)
    return results

def health():
    """Health check endpoint"""
    return {"status": "ok"}, 200

app = connexion.FlaskApp(__name__, specification_dir='')  
app.add_api("student-770-NorthAmericanTrainInfo-1.0.0-swagger.yaml", strict_validation=True, validate_responses=True)  # Add OpenAPI spec


class KafkaConsumerWrapper:
    """Kafka consumer wrapper with retry logic for storage service"""
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
                consumer_group=b'event_group',
                reset_offset_on_start=False,
                auto_offset_reset=OffsetType.LATEST
            )
            logger.info(f"Kafka consumer created for topic {self.topic}")
            return True
        except KafkaException as e:
            logger.warning(f"Kafka error when making consumer: {e}")
            self.client = None
            self.consumer = None
            return False
    
    def messages(self):
        """Generator method that catches exceptions in the consumer loop"""
        if self.consumer is None:
            self.connect()
        while True:
            try:
                for msg in self.consumer:
                    yield msg
            except KafkaException as e:
                logger.warning(f"Kafka issue in consumer: {e}")
                self.client = None
                self.consumer = None
                self.connect()


def process_messages():
    """Process event messages from Kafka and store them in the DB."""
    hostname = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
    logger.info("Kafka consumer loop starting; target broker=%s topic=%s",
                hostname, app_config['events']['topic'])
    
    # Create global Kafka consumer wrapper (handles reconnection automatically)
    kafka_wrapper = KafkaConsumerWrapper(hostname, app_config['events']['topic'])
    
    for msg in kafka_wrapper.messages():
        if msg is None:
            continue
        try:
            msg_str = msg.value.decode('utf-8')
            msg_obj = json.loads(msg_str)
            logger.info("Message: %s", msg_obj)
            payload = msg_obj.get('payload')
            mtype = msg_obj.get('type')

            # Dispatch based on message type
            if mtype == 'passenger_count' or mtype == 'event1':
                report_count_reading(payload)
            elif mtype == 'wait_time' or mtype == 'event2':
                report_wait_time_reading(payload)

            # commit that we've processed this message
            kafka_wrapper.consumer.commit_offsets()
            logger.info(f"Connected to Kafka")
        except Exception as e:
            logger.error(f"Error processing message: {e}")


def setup_kafka_thread():
    t1 = threading.Thread(target=process_messages)
    t1.daemon = True  # setDaemon is deprecated
    logger.info("Launching Kafka consumer background thread")
    t1.start()

if __name__ == "__main__":
    setup_kafka_thread()
    # Bind to 0.0.0.0 so Docker can expose the port outside the container
    app.run(host="0.0.0.0", port=8090)  