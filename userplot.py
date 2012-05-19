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
    parser.add_argument('plot_name', nargs="+", type=str)
    args = parser.parse_args()
    dbname = args.screen_name.lower()
    db = tweetdb.DBWrapper(app_path, args.screen_name, args.s, dbname)

    def get_lines():
        for user in sorted(args.plot_name):
            x = []
            y = []
            for tweet in ( db.get_by_status_id(row.id) for row in db.db.view('undulatus/byuser')[[user]:[user+'^']] ):
                ut = tweet_datetime(tweet)
                if 'user' not in tweet:
                    continue
                followers = tweet['user']['followers_count']
                if followers == 0: continue #glitch
                x.append(ut)
                y.append(followers)
            yield user, x, y

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(16,9), dpi=72)
    ax = fig.add_subplot(111)
    for user, x, y in get_lines():
        ax.plot_date(x, y, label=user, fmt='-')
    ax.legend(loc="upper left")
    ax.set_title("Twitter followers", fontsize=14)
    ax.set_ylabel("followers")
    leg = plt.gca().get_legend()
    ltext = leg.get_texts()
    plt.setp(ltext, fontsize='6')
    fig.savefig(args.o, format="png", bbox_inches='tight')

