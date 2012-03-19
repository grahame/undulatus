
from tweetdb import DBWrapper
from util import *
from twitter.api import TwitterHTTPError
import traceback, sys
import threading

class TweetTracker(threading.Thread):
    tbl = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

    def __init__(self, twitter, db):
        self.twitter = twitter
        self.db = db
        self.key_to_tweet = {}
        self.tweet_to_key = {}
        self.last_idx = 0
        self.base = len(self.tbl)
        self.seen_users = set()
        self.load_recent()

    def load_recent(self):
        sys.stdout.write("loading recent tweets from database... ")
        sys.stdout.flush()
        for tweet in self.db.get_recent(500):
            self.cache_tweet(tweet)
        sys.stdout.write("done! %d tweets loaded.\n" % (len(self.key_to_tweet)))
        sys.stdout.flush()

    def get_cached_tweets(self):
        cache = list(self.key_to_tweet.values())
        sort_tweets_by_id(cache)
        return cache

    def make_key(self, i):
        i1 = i % self.base
        i2 = i // self.base
        return self.tbl[i2] + self.tbl[i1]

    def add(self, tweet):
        # look up our database object (or make it)
        self.db.make(tweet)
        self.cache_tweet(tweet)

    def get_tweet_for_id(self, twitter_id):
        # if we can, retrieve from our DB
        tweet = self.db.get_by_status_id(twitter_id)
        if tweet is not None:
            self.cache_tweet(tweet)
            return tweet
        # else, pull it via the API
        try:
            print("pull", twitter_id)
            tweet = self.twitter.statuses.show(id=twitter_id)
        except TwitterHTTPError as e:
            print("(twitter API error: %s)" % e)
            return None
        except Exception as e:
            print("(traceback getting tweet)")
            traceback.print_exc()
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
        # remove any old points for that key
        try:
            old_tweet = self.key_to_tweet.pop(key)
            twitter_id = old_tweet['id_str']
            self.tweet_to_key.pop(twitter_id)
        except KeyError:
            pass
        # update
        self.last_idx = (self.last_idx + 1) % (self.base * self.base)
        # copy ourself in
        twitter_id = tweet['id']
        self.key_to_tweet[key] = tweet
        self.tweet_to_key[twitter_id] = key
        text = tweet_text(tweet)
        for username in get_usernames(text):
            self.seen_users.add(username)
        self.seen_users.add(tweet['user']['screen_name'])
        return key

    def get_tweet_for_key(self, key):
        return self.key_to_tweet.get(key, None)

    def get_key_for_tweet(self, tweet):
        return self.tweet_to_key.get(tweet['id'], None)

    def print_tweet(self, tweet, suffix=''):
        screen_name = "%-15s" % (tweet['user']['screen_name'])
        key = self.get_key_for_tweet(tweet)
        prefix = "%s) %s " % (key, screen_name)
        text = tweet_text(tweet)
        print_wrap_to_prefix(prefix, text + suffix)

    def display_tweets(self, tweets):
        if len(tweets) == 0:
            return
        print()
        for tweet in tweets:
            if 'retweeted_status' in tweet:
                self.print_tweet(tweet['retweeted_status'], 
                        " (retweeted by %s)" % (tweet['user']['screen_name']))
            else:
                self.print_tweet(tweet)


