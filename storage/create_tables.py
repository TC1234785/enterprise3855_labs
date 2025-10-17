from sqlalchemy import create_engine
from event_models import Base
import yaml

# Load configuration file
with open('app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())

# Create a database engine for MySQL using configuration
db_config = app_config['datastore']
db_url = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['hostname']}:{db_config['port']}/{db_config['db']}"
engine = create_engine(db_url)
Base.metadata.create_all(engine)