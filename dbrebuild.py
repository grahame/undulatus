#!/usr/bin/env python

import tweetdb, sys

if __name__ == '__main__':
    print "Updating all tweets from their compressed JSON information."
    print "This will take a while."
    db = tweetdb.DBWrapper()
    session = db.Session()
    for tweet in session.query(tweetdb.Tweet):
        tweet.update_from_jsonz()
        sys.stdout.write('.')
        sys.stdout.flush()
    print "committing"
    session.commit()
    print ".. done"
