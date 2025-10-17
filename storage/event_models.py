from sqlalchemy.orm import DeclarativeBase, mapped_column
from sqlalchemy import Integer, String, Float, DateTime, BigInteger, func

class Base(DeclarativeBase):
    pass

class PassengerCountEvent(Base):
    __tablename__ = "passenger_count_event"
    id = mapped_column(Integer, primary_key=True)
    trace_id = mapped_column(BigInteger, nullable=False)
    station_id = mapped_column(String(250), nullable=False)
    station_name = mapped_column(String(250), nullable=False)
    transit_system = mapped_column(String(250), nullable=True)
    average = mapped_column(Float, nullable=False)
    num_values = mapped_column(Integer, nullable=False)
    batch_timestamp = mapped_column(DateTime, nullable=False)
    date_created = mapped_column(DateTime, nullable=False, default=func.now())

class WaitTimeEvent(Base):
    __tablename__ = "wait_time_event"
    id = mapped_column(Integer, primary_key=True)
    trace_id = mapped_column(BigInteger, nullable=False)
    station_id = mapped_column(String(250), nullable=False)
    station_name = mapped_column(String(250), nullable=False)
    transit_system = mapped_column(String(250), nullable=True)
    average = mapped_column(Float, nullable=False)
    num_values = mapped_column(Integer, nullable=False)
    batch_timestamp = mapped_column(DateTime, nullable=False)
    date_created = mapped_column(DateTime, nullable=False, default=func.now())