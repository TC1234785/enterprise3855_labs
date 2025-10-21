import connexion  
from connexion import NoContent
import functools
import os
import yaml
import logging
import logging.config
from datetime import datetime as dt
from datetime import date

from event_models import PassengerCountEvent, WaitTimeEvent  
from sqlalchemy import create_engine, select  
from sqlalchemy.orm import sessionmaker 
 
# Seems like the datetime information does not get parsed correctly without this
from dateutil import parser

# Load configuration file
with open('app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())

# Load logging configuration
with open('log_conf.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
logging.config.dictConfig(log_config)

# Create logger
logger = logging.getLogger('basicLogger')

# Create MySQL database engine using configuration
db_config = app_config['datastore']
db_url = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['hostname']}:{db_config['port']}/{db_config['db']}"
ENGINE = create_engine(db_url)  
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

    start = dt.fromisoformat(start_timestamp)
    end = dt.fromisoformat(end_timestamp)

    statement = select(PassengerCountEvent).where(PassengerCountEvent.date_created >= start).where(PassengerCountEvent.date_created < end)
    results = [result.to_dict()
        for result in session.execute(statement).scalars().all()
        ]
    session.close()
    logger.debug("Found %d PassengerCountEvent pressure readings (start: %s, end: %s)", len(results), start, end)
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

    start = dt.fromisoformat(start_timestamp)
    end = dt.fromisoformat(end_timestamp)
    print(type(start), 'Start:',start)
    print(type(end), 'End:', end)
    statement = select(WaitTimeEvent).where(WaitTimeEvent.date_created >= start).where(WaitTimeEvent.date_created < end)
    results = [result.to_dict()
        for result in session.execute(statement).scalars().all()
        ]
    session.close()
    logger.debug("Found %d WaitTimeEvent pressure readings (start: %s, end: %s)", len(results), start, end)
    return results

app = connexion.FlaskApp(__name__, specification_dir='')  
app.add_api("student-770-NorthAmericanTrainInfo-1.0.0-swagger.yaml", strict_validation=True, validate_responses=True)  # Add OpenAPI spec
if __name__ == "__main__":
    logger.info("Starting Storage Service on port 8090")
    app.run(port=8090)  