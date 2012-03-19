#!/usr/bin/env python3

from util import *


if __name__ == '__main__':
    setup_env()
    import tweetdb
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', type=str, default='http://localhost:5984')
    parser.add_argument('-o', type=str, required=True)
    parser.add_argument('screen_name', type=str)
    args = parser.parse_args()
    dbname = args.screen_name.lower()
    db = tweetdb.DBWrapper(app_path, args.screen_name, args.s, dbname)

    x = []
    y = []
    today = None
    count = 0
    for tweet in ( db.get_by_status_id(row.id) for row in db.db.view('undulatus/byid')):
        try: ut = tweet_datetime(tweet).date()
        except KeyError: continue
        if ut != today:
            if today:
                x.append(today)
                y.append(count)
            today = ut
            count = 0
        count += 1

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(16,9), dpi=72)
    ax = fig.add_subplot(111)
    ax.plot_date(x, y, fmt='-')
    ax.set_title("Tweet rate", fontsize=14)
    ax.set_ylabel("followers")
    fig.savefig(args.o, format="png", bbox_inches='tight')

