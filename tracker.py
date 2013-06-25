
from tweetdb import DBWrapper
from util import *
from twitter.api import TwitterHTTPError
import traceback, sys
import threading
from bidict import BiDict

class TweetTracker(threading.Thread):
    tbl = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

    def __init__(self, twitter, db):
        self.twitter = twitter
        self.db = db
        self.bd = BiDict("key", None, "tweet", lambda x: x['id_str'])
        self.last_idx = 0
        self.base = len(self.tbl)
        self.seen_users = set()
        #self.load_recent()
        self.reindex_counter = 0
        self.reindex_interval = 50

    def status(self):
        info = self.db.info()
        info['undulatus_cache_size'] = len(self.bd)
        return info

    def load_recent(self):
        sys.stdout.write("loading recent tweets from database... ")
        sys.stdout.flush()
        for tweet in self.db.get_recent(self.base * self.base):
            self.cache_tweet(tweet)
        sys.stdout.write("done! %d tweets loaded.\n" % (len(self.bd)))
        sys.stdout.flush()

    def get_cached_tweets(self):
        cache = list(self.bd.key_values())
        sort_tweets_by_id(cache)
        return cache

    def make_key(self, i):
        i1 = i % self.base
        i2 = i // self.base
        return self.tbl[i2] + self.tbl[i1]

    def add(self, tweet, from_search=False):
        # special code from "from_search" to allow us to upgrade to the 
        # full tweet if we happen to pull it in later (searches show a 
        # truncated tweet without all the included user info, etc)
        if 'retweeted_status' in tweet:
            self.add(tweet['retweeted_status'], from_search=from_search)
        # look up our database object (or make it)
        if from_search:
            tweet['undulatus_from_search'] = True
        self.db.make(tweet)
        self.cache_tweet(tweet)
        self.reindex_counter += 1
        if self.reindex_counter == self.reindex_interval:
            # poke the index
            self.reindex_counter = 0
            self.db.get_recent(1)

    def get_tweet_for_id(self, twitter_id):
        # if we can, retrieve from our DB
        tweet = self.db.get_by_status_id(twitter_id)
        if tweet is not None:
            self.cache_tweet(tweet)
            return tweet
        if self.twitter is None:
            return None
        # else, pull it via the API
        try:
            print("pull", twitter_id)
            tweet = self.twitter.statuses.show(id=twitter_id)
        except TwitterHTTPError as e:
            print("(twitter API error: %s)" % e)
            return None
        except Exception as e:
            print("(traceback getting tweet - /traceback to retrieve)")
            last_tb.set(traceback.format_exc())
            return None
        # add it to the database, cache it
        self.add(tweet)
        return tweet

    def get_replies_to_tweet(self, tweet):
        replies = self.db.get_replies_to_status_id(tweet['id_str'])
        for tweet in replies:
            self.cache_tweet(tweet)
        return replies

    def cache_tweet(self, tweet):
        # is it already cached?
        key = self.get_key_for_tweet(tweet)
        if key is not None:
            return key
        # calculate our 'A9' style key
        key = self.make_key(self.last_idx)
        # update
        self.last_idx = (self.last_idx + 1) % (self.base * self.base)
        # copy ourself in
        twitter_id = tweet['id']
        self.bd.set(key, tweet)
        text = tweet_text(tweet)
        for username in get_usernames(text):
            self.seen_users.add(username)
        self.seen_users.add(tweet_user(tweet))
        return key

    def get_tweet_for_key(self, key):
        return self.bd.key_to_tweet(key)

    def get_key_for_tweet(self, tweet):
        return self.bd.tweet_to_key(tweet)

    def print_tweet(self, tweet):
        key = self.get_key_for_tweet(tweet)
        suffix = ''
        details = tweet
        if 'retweeted_status' in tweet:
            details = tweet['retweeted_status']
            suffix = " (retweeted by %s)" % (tweet_user(tweet))
        screen_name = "%-15s" % (tweet_user(details))
        prefix = "%s) %s " % (key, screen_name)
        print_wrap_to_prefix(prefix, tweet_text(details) + suffix)

    def display_tweets(self, tweets):
        if len(tweets) == 0:
            return
        print()
        for tweet in tweets:
            self.print_tweet(tweet)


