# backend/models.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Table, Float, Boolean
from sqlalchemy.orm import relationship
from database.database import Base


# Функция для получения текущего времени в UTC
def utcnow():
    return datetime.now(timezone.utc)


# Таблица для связи many-to-many между пользователями и исполнителями
user_artists = Table(
    'user_artists',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('artist_id', Integer, ForeignKey('artists.id'), primary_key=True),
    Column('created_at', DateTime(timezone=True), default=utcnow)
)


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    gender = Column(String(7), nullable=False)
    age = Column(Integer)
    bio = Column(Text)
    avatar_url = Column(String(255))
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Отношения
    favorite_artists = relationship('Artist', secondary=user_artists, back_populates='fans')
    music_profile = relationship('MusicProfile', back_populates='user', uselist=False)
    swipes_given = relationship('Swipe', foreign_keys='Swipe.swiper_id', back_populates='swiper')
    swipes_received = relationship('Swipe', foreign_keys='Swipe.swiped_id', back_populates='swiped')
    matches_as_user1 = relationship('Match', foreign_keys='Match.user1_id', back_populates='user1')
    matches_as_user2 = relationship('Match', foreign_keys='Match.user2_id', back_populates='user2')
    messages = relationship('Message', back_populates='sender')


class Artist(Base):
    __tablename__ = 'artists'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    genre = Column(String(100), index=True)
    description = Column(Text)
    image_url = Column(String(255))
    popularity = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Отношения
    fans = relationship('User', secondary=user_artists, back_populates='favorite_artists')


class MusicProfile(Base):
    __tablename__ = 'music_profiles'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    favorite_genres = Column(String(500))  # JSON строка с жанрами
    personality_analysis = Column(Text)  # Анализ от DeepSeek
    emotional_profile = Column(String(500))  # JSON строка
    musical_personality_type = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Отношения
    user = relationship('User', back_populates='music_profile')


class Swipe(Base):
    __tablename__ = 'swipes'

    id = Column(Integer, primary_key=True, index=True)
    swiper_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    swiped_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    direction = Column(String(10), nullable=False)  # 'like' or 'dislike'
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Отношения
    swiper = relationship('User', foreign_keys=[swiper_id], back_populates='swipes_given')
    swiped = relationship('User', foreign_keys=[swiped_id], back_populates='swipes_received')


class Match(Base):
    __tablename__ = 'matches'

    id = Column(Integer, primary_key=True, index=True)
    user1_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user2_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    match_score = Column(Float, default=0.0)
    matched_at = Column(DateTime(timezone=True), default=utcnow)
    is_active = Column(Boolean, default=True)

    # Отношения
    user1 = relationship('User', foreign_keys=[user1_id], back_populates='matches_as_user1')
    user2 = relationship('User', foreign_keys=[user2_id], back_populates='matches_as_user2')
    messages = relationship('Message', back_populates='match')


class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey('matches.id'), nullable=False)
    sender_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Отношения
    match = relationship('Match', back_populates='messages')
    sender = relationship('User', back_populates='messages')