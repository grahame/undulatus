#!/usr/bin/env python

from sqlalchemy import create_engine
from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey, LargeBinary, BigInteger
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.expression import cast
from sqlalchemy import desc
import zlib, json, sys
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
                'jsonz' : zlib.compress(bytes(json.dumps(tweet), encoding='utf8'))
                }
        if 'retweeted_status' in tweet:
            attrs['embedded_retweet_id'] = tweet['retweeted_status']['id']
        return attrs

    @classmethod
    def from_json(cls, json):
            attrs = cls._json_to_attrs(json)
            obj = cls(**attrs)
            return obj

    def get_json(self):
        s = str(zlib.decompress(self.jsonz), encoding='utf8')
        return json.loads(s)

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

if __name__ == '__main__':
    from util import setup_env
    setup_env()
    engine = create_engine('sqlite:///%s' % sys.argv[1], echo=False)
    from sqlalchemy.orm import sessionmaker
    import couchdb
    l = input('this upgrader is destructive to any tweets in couchdb. are you sure? ')
    if l != 'yes':
        sys.exit(1)
    Session = sessionmaker(bind=engine)
    srv = couchdb.Server()
    try:
        del srv[sys.argv[2]]
    except couchdb.http.ResourceNotFound:
        pass
    srv.create(sys.argv[2])
    db = couchdb.Database(sys.argv[2])
    try:
        del db['oauth_tokens']
    except couchdb.http.ResourceNotFound:
        pass
    for toks in Session().query(OAuthTokens).yield_per(1):
        db['oauth_tokens'] = { 'token' : toks.oauth_token, 'secret' : toks.oauth_token_secret }
    buf = []
    sz = 400
    for tweet in Session().query(Tweet).yield_per(sz):
        obj = tweet.get_json()
        obj['_id'] = str(obj['id'])
        buf.append(obj)
        if len(buf) == sz:
            sys.stderr.write('.')
            sys.stderr.flush()
            db.update(buf)
            buf = []

