
from tweetdb import DBWrapper
from util import *
from twitter.api import TwitterHTTPError
import traceback, sys
import threading

class BiDict:
    def __init__(self, a, ka_f, b, kb_f):
        self.a_b = {}
        self.b_a = {}
        self.ka_f, self.kb_f = ka_f, kb_f
        def a_b(k):
            return self.a_b.get(self.get_ka(k))
        def b_a(k):
            return self.b_a.get(self.get_kb(k))
        def a_values():
            return self.a_b.values()
        def b_values():
            return self.b_a.values()

        setattr(self, "%s_to_%s" % (a, b), a_b)
        setattr(self, "%s_to_%s" % (b, a), b_a)
        setattr(self, "%s_values" % (a), a_values)
        setattr(self, "%s_values" % (b), b_values)

    def get_ka(self, a):
        if self.ka_f is None:
            return a
        else:
            return self.ka_f(a)

    def get_kb(self, b):
        if self.kb_f is None:
            return b
        else:
            return self.kb_f(b)

    def set(self, a, b):
        ka = self.get_ka(a)
        if ka in self.a_b:
            dup = self.get_kb(self.a_b[ka])
            del self.b_a[dup]
        kb = self.get_kb(b)
        if kb in self.b_a:
            dup = self.get_ka(self.b_a[kb])
            del self.a_b[dup]
        self.a_b[ka] = b
        self.b_a[kb] = a

    def __len__(self):
        return len(self.a_b)

class TweetTracker(threading.Thread):
    tbl = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

    def __init__(self, twitter, db):
        self.twitter = twitter
        self.db = db
        self.bd = BiDict("key", None, "tweet", lambda x: x['id_str'])
        self.last_idx = 0
        self.base = len(self.tbl)
        self.seen_users = set()
        self.load_recent()

    def status(self):
        info = self.db.info()
        info['tracker_cache_keys'] = len(self.key_to_tweet)
        info['tracker_cache_tweets'] = len(self.tweet_to_key)
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

    def add(self, tweet):
        if 'retweeted_status' in tweet:
            self.add(tweet['retweeted_status'])
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
        self.seen_users.add(tweet['user']['screen_name'])
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
            suffix = " (retweeted by %s)" % (tweet['user']['screen_name'])
        screen_name = "%-15s" % (details['user']['screen_name'])
        prefix = "%s) %s " % (key, screen_name)
        print_wrap_to_prefix(prefix, tweet_text(details) + suffix)

    def display_tweets(self, tweets):
        if len(tweets) == 0:
            return
        print()
        for tweet in tweets:
            self.print_tweet(tweet)


