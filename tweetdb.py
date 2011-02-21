#!/usr/bin/env python

from sqlalchemy import create_engine
from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.ext.declarative import declarative_base
import zlib, json

Base = declarative_base()
class Tweet(Base):
    __tablename__ = 'tweets'
    status_id = Column(String, primary_key=True, index=True)
    screen_name = Column(String(16), nullable=False, index=True)
    in_reply_to_screen_name = Column(String(16))
    in_reply_to_status_id = Column(String, index=True)
    embedded_retweet_id = Column(String, ForeignKey('tweets.status_id'))
    embedded_retweet = relationship('Tweet', remote_side=status_id)
    text = Column(String)
    jsonz = Column(LargeBinary)

    def get_json(self):
        return json.loads(zlib.decompress(self.jsonz))

class DBWrapper(object):
    def __init__(self):
        engine = create_engine('sqlite:///undulatus.db', echo=False)
        Tweet.metadata.create_all(engine)
        from sqlalchemy.orm import sessionmaker
        self.Session = sessionmaker(bind=engine)

    def _obj_for_status_id(self, status_id):
        try:
            session = self.Session()
            return session.query(Tweet).filter(Tweet.status_id==str(status_id)).one()
        except NoResultFound:
            return None

    def get_by_status_id(self, status_id):
            obj = self._obj_for_status_id(status_id)
            if obj is not None:
                return obj.get_json()
            else:
                return None

    def get_replies_to_status_id(self, status_id):
        session = self.Session()
        return [t.get_json() for t in session.query(Tweet).filter(Tweet.in_reply_to_status_id==status_id).all()]

    def get_or_make(self, tweet):
        def _get_or_make(tweet):
            obj = self._obj_for_status_id(tweet['id'])
            if obj is not None:
                return obj

            attrs = {
                    'status_id' : str(tweet['id']),
                    'screen_name' : tweet['user']['screen_name'],
                    'in_reply_to_status_id' : str(tweet['in_reply_to_status_id']),
                    'in_reply_to_screen_name' : tweet['in_reply_to_screen_name'],
                    'text' : tweet['text'],
                    'jsonz' : zlib.compress(json.dumps(tweet))
                    }
            if tweet.has_key('retweeted_status'):
                retweet_json = tweet['retweeted_status']
                retweet = _get_or_make(retweet_json)
                attrs['embedded_retweet_id'] = retweet.status_id

            session = self.Session()
            obj = Tweet(**attrs)
            session.add(obj)
            session.commit()
            return obj
        _get_or_make(tweet)

