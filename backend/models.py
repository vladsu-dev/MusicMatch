from sqlalchemy import MetaData, Table, Column, Integer, String

metadata = MetaData()

users = Table(
    'users',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('first_name', String(50)),
    Column('last_name', String(50), nullable=True),
    Column('email', String(50), unique=True, nullable=False),
    Column('gender', String(7), nullable=True),
    Column('password', String(255), nullable=False),
)