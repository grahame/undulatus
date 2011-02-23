#!/usr/bin/env python

from sqlalchemy import create_engine
from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey, LargeBinary, BigInteger
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.expression import cast
from sqlalchemy import desc
import zlib, json
from util import tweet_text

Base = declarative_base()
class Tweet(Base):
    __tablename__ = 'tweets'
    status_id = Column(String, primary_key=True, index=True)
    screen_name = Column(String(16), nullable=False, index=True)
    user_id = Column(String, index=True)
    in_reply_to_screen_name = Column(String(16))
    in_reply_to_status_id = Column(String, index=True)
    embedded_retweet_id = Column(String, ForeignKey('tweets.status_id'))
    embedded_retweet = relationship('Tweet', remote_side=status_id)
    text = Column(String)
    jsonz = Column(LargeBinary)

    @classmethod
    def _json_to_attrs(cls, tweet):
        attrs = {
                'status_id' : str(tweet['id']),
                'user_id' : str(tweet['user']['id']),
                'screen_name' : tweet['user']['screen_name'],
                'in_reply_to_status_id' : str(tweet['in_reply_to_status_id']),
                'in_reply_to_screen_name' : tweet['in_reply_to_screen_name'],
                'text' : tweet_text(tweet),
                'jsonz' : zlib.compress(json.dumps(tweet))
                }
        if tweet.has_key('retweeted_status'):
            attrs['embedded_retweet_id'] = tweet['retweeted_status']['id']
        return attrs

    @classmethod
    def from_json(cls, json):
            attrs = cls._json_to_attrs(json)
            obj = cls(**attrs)
            return obj

    def get_json(self):
        return json.loads(zlib.decompress(self.jsonz))

    # eg. if we've changed DB schema
    def update_from_jsonz(self):
        json = self.get_json()
        for attr in json:
            setattr(self, attr, json[attr])

class OAuthTokens(Base):
    __tablename__ = 'oauth_tokens'
    screen_name = Column(String(16), primary_key=True)
    oauth_token = Column(String, nullable=False)
    oauth_token_secret = Column(String, nullable=False)

class DBWrapper(object):
    def __init__(self, db_file_path):
        engine = create_engine('sqlite:///%s' % db_file_path, echo=False)
        Tweet.metadata.create_all(engine)
        OAuthTokens.metadata.create_all(engine)
        from sqlalchemy.orm import sessionmaker
        self.Session = sessionmaker(bind=engine)

    def tokens_for_screen_name(self, screen_name):
        try:
            session = self.Session()
            obj = session.query(OAuthTokens).filter(OAuthTokens.screen_name==str(screen_name)).one()
            return obj.oauth_token, obj.oauth_token_secret
        except NoResultFound:
            return None, None

    def add_tokens(self, screen_name, oauth_token, oauth_token_secret):
        session = self.Session()
        obj = OAuthTokens(screen_name=screen_name, 
                oauth_token=oauth_token, 
                oauth_token_secret=oauth_token_secret)
        session.add(obj)
        session.commit()

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

    # will probably break when twitter hits 63 bit status IDs..
    def get_recent(self, n):
        session = self.Session()
        big_status = cast(Tweet.status_id, BigInteger)
        return [t.get_json() for t in \
                session.query(Tweet).order_by(desc(big_status))[:n]]

    def make(self, tweet):
        def _make(tweet):
            obj = self._obj_for_status_id(tweet['id'])
            if obj is not None:
                return obj

            retweet_status_id = None
            # recurse, make the retweet
            if tweet.has_key('retweeted_status'):
                retweet_json = tweet['retweeted_status']
                _make(retweet_json)

            session = self.Session()
            obj = Tweet.from_json(tweet)
            session.add(obj)
            session.commit()
            return obj
        _make(tweet)

