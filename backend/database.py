import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
host = os.getenv('DB_HOST')
dbname = os.getenv('DB_NAME')

DATABASE_URL = f'postgresql+psycopg2://{user}:{password}@{host}/{dbname}'
engine = create_engine(DATABASE_URL)