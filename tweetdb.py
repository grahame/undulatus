#!/usr/bin/env python

import zlib, json, os
from util import tweet_text, now_tweettime, couch_fields
import couchdb

class DBWrapper(object):
    def __init__(self, app_path, screen_name, srvuri, dbname):
        self.srvuri, self.dbname = srvuri, dbname
        self.reconnect()
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
                self.reconnect() # work around python couchdb bug
                self.db['_design/undulatus'] = js
        except couchdb.http.ResourceNotFound:
            self.db['_design/undulatus'] = js

    def reconnect(self):
        srv = couchdb.Server(self.srvuri)
        try:
            self.db = srv.create(self.dbname)
        except couchdb.http.PreconditionFailed:
            self.db = srv[self.dbname]

    def info(self):
        return self.db.info()
    
    def setloc(self, lat, lng):
        try:
            doc = self.db['latlng']
        except couchdb.http.ResourceNotFound:
            doc = {}
        doc['lat'] = lat
        doc['long'] = lng
        self.db['latlng'] = doc

    def clearloc(self):
        try:
            del self.db['latlng']
        except couchdb.http.ResourceNotFound:
            pass

    def getloc(self):
        try:
            doc = self.db['latlng']
        except couchdb.http.ResourceNotFound:
            doc = {}
        return doc.get('lat'), doc.get('long')
        
    def saved_searches(self):
        try:
            doc = self.db['saved_searches']
        except couchdb.http.ResourceNotFound:
            doc = None
        if not doc or "searches" not in doc:
            return []
        return doc['searches']

    def save_saved_searches(self, searches):
        try:
            doc = self.db['saved_searches']
        except couchdb.http.ResourceNotFound:
            doc = {}
        doc['searches'] = searches
        self.db['saved_searches'] = doc
        return doc

    def configuration(self):
        try:
            doc = self.db['help_configuration']
            return doc
        except couchdb.http.ResourceNotFound:
            return None

    def save_configuration(self, new_config):
        try:
            doc = self.db['help_configuration']
        except couchdb.http.ResourceNotFound:
            doc = {}
        doc['configuration'] = new_config
        doc['updated'] = now_tweettime()
        self.db['help_configuration'] = doc
        return doc

    def tokens(self):
        try:
            doc = self.db['oauth_tokens']
            return doc, doc['token'], doc['secret']
        except couchdb.http.ResourceNotFound:
            return {}, None, None

    def add_tokens(self, base_doc, oauth_token, oauth_token_secret):
        from copy import copy
        doc = copy(base_doc)
        doc['token'] = oauth_token
        doc['secret'] = oauth_token_secret
        self.db['oauth_tokens'] = doc

    def get_by_status_id(self, status_id):
        try:
            return self.db[str(status_id)]
        except couchdb.http.ResourceNotFound:
            return None

    def get_replies_to_status_id(self, status_id):
        return [ self.get_by_status_id(row.id) for row in self.db.view('undulatus/replies')[status_id] ]

    # will probably break when twitter hits 63 bit status IDs..
    def get_recent(self, n):
        rv = [ self.get_by_status_id(row.id) for row in self.db.view('undulatus/byid', limit=n, descending=True) ]
        rv.reverse()
        return rv

    def savedoc(self, name, doc):
        self.db[name] = doc

    def make(self, tweet):
        k = str(tweet['id_str'])
        doc = self.get_by_status_id(k)
        if doc is None or 'undulatus_from_search' in doc:
            if doc is not None:
                tweet.update(couch_fields(doc))
            self.db[k] = tweet

