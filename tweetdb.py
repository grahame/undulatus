#!/usr/bin/env python

import zlib, json
from util import tweet_text

import couchdb

class DBWrapper(object):
    def __init__(self, screen_name, srvuri, dbname):
        srv = couchdb.Server(srvuri)
        try:
            self.db = srv.create(dbname)
        except couchdb.http.PreconditionFailed:
            self.db = srv[dbname]

    def tokens(self):
        try:
            doc = self.db['oauth_tokens']
            return doc['token'], doc['secret']
        except couchdb.http.ResourceNotFound:
            return None, None

    def add_tokens(self, oauth_token, oauth_token_secret):
        self.db['oauth_tokens'] = {'token': oauth_token, 'secret': oauth_token_secret}

    def get_by_status_id(self, status_id):
        try:
            return self.db[str(status_id)]
        except couchdb.http.ResourceNotFound:
            return None

    def get_replies_to_status_id(self, status_id):
        return list(self.db.view('undulatus/replies')[status_id])

    # will probably break when twitter hits 63 bit status IDs..
    def get_recent(self, n):
        session = self.Session()
        big_status = cast(Tweet.status_id, BigInteger)
        return [t.get_json() for t in \
                session.query(Tweet).order_by(desc(big_status))[:n]]

    def make(self, tweet):
        doc = self.get_by_status_id(tweet['id'])
        if doc is None:
            self.db[str(tweet['id'])] = tweet

