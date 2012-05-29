#!/usr/bin/env python3

import csv, sys, json, time, datetime
sys.path.append('./couchdb-python3/')
import couchdb
from string import digits

if __name__ == '__main__':
    def log(s):
        print(s, file=sys.stderr)
    dbname = sys.argv[1]
    srv = couchdb.Server('http://localhost:5984/')
    db = srv[dbname]
    following = dict([(t['id'], t) for t in db[sys.argv[2]]['following']])
    followers = dict([(t['id'], t) for t in db[sys.argv[3]]['followers']])
    everybody = following.copy()
    everybody.update(followers)
    not_following = set(following) - set(followers)
    not_following_back = set(followers) - set(following)
    w = csv.writer(sys.stdout)
    def log_users(l, s):
        for user_id in s:
            user = everybody[user_id]
            #print(user.keys())
            w.writerow([l, user['screen_name'], user['description'], user['name'], user['location'], user['url']])
    log_users("not_following", not_following)
    log_users("not_following_back", not_following_back)

