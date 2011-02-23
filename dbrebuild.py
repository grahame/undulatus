#!/usr/bin/env python

import tweetdb, sys

if __name__ == '__main__':
    print "Updating all tweets from their compressed JSON information."
    print "This will take a while."
    screen_name = sys.argv[1]
    dbfile = get_dbfile(screen_name)
    db = tweetdb.DBWrapper(dbfile)
    session = db.Session()
    for tweet in session.query(tweetdb.Tweet):
        tweet.update_from_jsonz()
        sys.stdout.write('.')
        sys.stdout.flush()
    print "committing"
    session.commit()
    print ".. done"
