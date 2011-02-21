
from tweetdb import Tweet, DBWrapper
from util import *
import traceback

class TweetTracker(object):
    def __init__(self, twitter, nstored=10000):
        self.twitter = twitter
        self.db = DBWrapper()
        self.nstored = nstored
        self.last_id = 0
        self.tbl = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        self.base = len(self.tbl)
        self.key_to_tweet = {}
        self.twitter_to_key = {}
        self.seen_users = set()

    def get_cached_tweets(self):
        cache = self.key_to_tweet.values()
        sort_tweets_by_id(cache)
        return cache

    def make_key(self, i):
        i1 = i % self.base
        i2 = i / self.base
        return self.tbl[i2] + self.tbl[i1]

    def remove(self, key):
        tweet = self.twitter_to_key.pop(key, None)
        if tweet is None:
            return
        self.twitter_to_key.pop(tweet['id'])

    def add(self, tweet):
        # look up our database object (or make it)
        self.db.get_or_make(tweet)
        self.cache_tweet(tweet)

    def get_tweet_for_id(self, twitter_id):
        # if we can, retrieve from our DB
        tweet = self.db.get_by_status_id(twitter_id)
        if tweet is not None:
            self.cache_tweet(tweet)
            return tweet
        # else, pull it via the API
        try:
            print "pull", twitter_id
            tweet = self.twitter.statuses.show(id=twitter_id)
        except Exception, e:
            print "(traceback getting tweet)"
            traceback.print_exc()
            return None
        # add it to the database, cache it
        self.add(tweet)
        return tweet

    def get_replies_to_tweet(self, tweet):
        replies = self.db.get_replies_to_status_id(tweet['id'])
        map(self.cache_tweet, replies)
        return replies

    def cache_tweet(self, tweet):
        # is it already cached?
        key = self.get_key_for_tweet(tweet)
        if key is not None:
            return key
        # calculate our 'A9' style key
        key = self.make_key(self.last_id)
        # remove something to limit memory use
        remove_key = self.make_key((self.last_id - self.nstored) % (self.base * self.base))
        self.remove(remove_key)
        # update
        self.last_id = (self.last_id + 1) % (self.base * self.base)
        # copy ourself in
        twitter_id = tweet['id']
        self.key_to_tweet[key] = tweet
        self.twitter_to_key[twitter_id] = key
        for username in get_usernames(tweet['text']):
            self.seen_users.add(username)
        self.seen_users.add(tweet['user']['screen_name'])
        return key

    def get_tweet_for_key(self, key):
        return self.key_to_tweet.get(key, None)

    def get_key_for_tweet(self, tweet):
        return self.twitter_to_key.get(tweet['id'], None)

    def display_tweets(self, tweets):
        def print_tweet(tweet, suffix=''):
            screen_name = "%-15s" % (tweet['user']['screen_name'])
            key = self.get_key_for_tweet(tweet)
            prefix = "%s) %s " % (key, screen_name)
            print_wrap_to_prefix(prefix, tweet['text'] + suffix)

        if len(tweets) == 0:
            return
        print
        for tweet in tweets:
            if tweet.has_key('retweeted_status'):
                print_tweet(tweet['retweeted_status'], 
                        " (retweeted by %s)" % (tweet['user']['screen_name']))
            else:
                print_tweet(tweet)


