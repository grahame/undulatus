#!/usr/bin/env python3

from util import *


if __name__ == '__main__':
    setup_env()
    import tweetdb
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', type=str, default='http://localhost:5984')
    parser.add_argument('screen_name', type=str)
    parser.add_argument('screen_names', nargs="+", type=str)
    args = parser.parse_args()
    dbname = args.screen_name.lower()
    db = tweetdb.DBWrapper(app_path, args.screen_name, args.s, dbname)

    for user in args.screen_names:
        for tweet in ( db.get_by_status_id(row.id) for row in db.db.view('undulatus/byuser')[[user]:[user+'^']] ):
            print(tweet['text'])

