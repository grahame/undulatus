#!/usr/bin/env python3

from util import *
import sys, json

if __name__ == '__main__':
    setup_env()
    import tweetdb
    import argparse
    from commands import Threader
    from tracker import TweetTracker
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', type=str, default='http://localhost:5984')
    parser.add_argument('-t', type=bool, default=False)
    parser.add_argument('screen_name', type=str)
    parser.add_argument('screen_names', nargs="+", type=str)
    args = parser.parse_args()
    dbname = args.screen_name.lower()
    db = tweetdb.DBWrapper(app_path, args.screen_name, args.s, dbname)

    thread = args.t

    tracker = TweetTracker(None, db)

    for user in args.screen_names:
        result = {}
        for tweet in ( db.get_by_status_id(row.id) for row in db.db.view('undulatus/byuser')[[user]:[user+'^']] ):
            if thread:
                threader = Threader(tracker)
                threader.process(tweet)
                tweets = threader.get()
            else:
                tweets = [ tweet ]
            for tweet in tweets:
                result[tweet['id_str']] = tweet
            sys.stderr.write('.')
            sys.stderr.flush()
        with open('%s.json' % user, 'w') as out:
            json.dump(sorted(result.values(), key=lambda x: int(x['id_str'])), out)

