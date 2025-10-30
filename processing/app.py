import connexion                
from connexion import NoContent 
import httpx
import yaml
import logging
import logging.config
from apscheduler.schedulers.background import BackgroundScheduler
import os
import json
from datetime import datetime, timezone

# Load configuration file
with open('app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())

# Load logging configuration
with open("log_conf.yml", "r") as f:
    log_config = yaml.safe_load(f.read())
    
logging.config.dictConfig(log_config)
logger = logging.getLogger('basicLogger')     

def get_stats():
    """Return the current statistics object as defined in OpenAPI."""
    logger.info("Received request for statistics")
    data_file = app_config.get('data_store', {}).get('filename', 'data.json')
    # If stats file doesn't exist, return 404 as per requirement
    if not os.path.isfile(data_file):
        logger.error("Statistics file does not exist: %s", data_file)
        return {"message": "Statistics do not exist"}, 404

    # Read stats and filter to API schema keys only
    with open(data_file, 'r') as f:
        data = json.load(f)
    logger.debug("Current statistics: %s", data)
    resp = {
        'num_wait_time_readings': data.get('num_wait_time_readings', 0),
        'num_passengers_readings': data.get('num_passengers_readings', 0),
        'max_passengers': data.get('max_passengers', 0),
        'min_wait_time': data.get('min_wait_time', 0)
    }
    logger.info("Successfully processed statistics request")
    return resp, 200

def populate_stats():
    logger.info("Periodic processing has started")
    current_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data_file = app_config.get('data_store', {}).get('filename', 'data.json')
    
    if os.path.isfile(data_file):
        with open(data_file, "r") as file:
            data = json.load(file)
            params= {'start_timestamp' : data['last_updated'], 'end_timestamp': current_time}
            passenger_response = httpx.get(app_config['events']['passenger_count']['url'],params=params)
            wait_response = httpx.get(app_config['events']['wait_time']['url'], params=params)
            
            stats = {
                'num_wait_time_readings': data['num_wait_time_readings'],
                'min_wait_time' : data['min_wait_time'],
                'num_passengers_readings' : data['num_passengers_readings'],
                'max_passengers' : data['max_passengers']
            }
            if passenger_response.status_code != 200 or wait_response.status_code != 200:
                if passenger_response.status_code != 200:
                    logger.error("Storage GET passenger_count failed. status: %s", passenger_response.status_code)
                if wait_response.status_code != 200:
                    logger.error("Storage GET wait_time failed. status: %s", wait_response.status_code)
                logger.info("Periodic processing has ended (with errors)")
                return
            else:
                cumulative_passenger = len(passenger_response.json())
                logger.info("Passenger events received: %d", cumulative_passenger)
                cumulative_wait = len(wait_response.json())
                logger.info("Wait time events received: %d", cumulative_wait)
                # Update cumulative counts
                stats['num_passengers_readings'] = stats.get('num_passengers_readings', 0) + cumulative_passenger
                stats['num_wait_time_readings'] = stats.get('num_wait_time_readings', 0) + cumulative_wait

                # Update max_passengers from returned passenger events
                for ev in passenger_response.json():
                    # ev may contain either 'passenger_count' (reading) or 'average' (event)
                    val = ev.get('passenger_count') if 'passenger_count' in ev else ev.get('average')
                    if isinstance(val, (int, float)):
                        stats['max_passengers'] = max(stats.get('max_passengers', 0), int(val))

                # Update min_wait_time from returned wait events
                for ev in wait_response.json():
                    # ev may contain either 'current_minutes_wait' (reading) or 'average' (event)
                    val = ev.get('current_minutes_wait') if 'current_minutes_wait' in ev else ev.get('average')
                    if isinstance(val, (int, float)):
                        if stats.get('min_wait_time') in (None, 0):
                            stats['min_wait_time'] = int(val)
                        else:
                            stats['min_wait_time'] = min(stats['min_wait_time'], int(val))

            # Persist stats and last_updated to the window end to avoid double-counting on inclusive queries
            stats['last_updated'] = str(current_time)
            logger.debug("Updated stats: %s", stats)
            with open(data_file, 'w') as f:
                json.dump(stats, f, indent=4)
            # Emit a concise INFO summary so it's visible with current log level
            logger.info(
                "Totals so far - Passenger Readings=%d, Wait Time Readings=%d",
                stats.get('num_passengers_readings', 0),
                stats.get('num_wait_time_readings', 0)
            )
            logger.info("Periodic processing has ended")


    else:
        # No existing JSON: initialize defaults and use current time
        stats = {
            'num_wait_time_readings': 0,
            'min_wait_time': 0,
            'num_passengers_readings': 0,
            'max_passengers': 0,
            'last_updated': str(current_time)
        }
        with open(data_file, "w") as f:
            json.dump(stats, f, indent=4)
        logger.debug("Initialized stats file with: %s", stats)
        logger.info("Periodic processing has ended (initialized)")
    

def init_scheduler():
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(populate_stats,
        'interval',
        seconds=app_config['scheduler']['interval'])
        
    sched.start()

app = connexion.FlaskApp(__name__, specification_dir='') 
app.add_api("student-770-NorthAmericanTrainInfo-1.0.0-swagger.yaml", strict_validation=True, validate_responses=True) 
if __name__ == "__main__":
    logger.info("Starting Processing Service on port 8100")
    init_scheduler()
    app.run(port=8100)        