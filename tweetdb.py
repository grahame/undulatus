#!/usr/bin/env python

import zlib, json, os
from util import tweet_text
import couchdb

class DBWrapper(object):
    def __init__(self, app_path, screen_name, srvuri, dbname):
        srv = couchdb.Server(srvuri)
        try:
            self.db = srv.create(dbname)
        except couchdb.http.PreconditionFailed:
            self.db = srv[dbname]

        js = open(os.path.join(app_path, 'undulatus.js')).read()
        revision = json.loads(js)["revision"]
        try:
            design = self.db['_design/undulatus']
            db_revision = None
            try:
                db_revision = design['revision']
            except KeyError:
                pass
            if db_revision != revision:
                print('Note: updating javascript design document')
                del self.db['_design/undulatus']
                self.db['_design/undulatus'] = js
        except couchdb.http.ResourceNotFound:
            self.db['_design/undulatus'] = js

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
        return list(map(lambda row: self.get_by_status_id(row.id), self.db.view('undulatus/replies')[status_id]))

    # will probably break when twitter hits 63 bit status IDs..
    def get_recent(self, n):
        session = self.Session()
        big_status = cast(Tweet.status_id, BigInteger)
        return [t.get_json() for t in \
                session.query(Tweet).order_by(desc(big_status))[:n]]

    def make(self, tweet):
        doc = self.get_by_status_id(tweet['id_str'])
        if doc is None:
            self.db[str(tweet['id_str'])] = tweet

