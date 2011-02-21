#!/usr/bin/env python

import readline, itertools, sys, os, signal, threading, traceback, re, json
from twitter.oauth import OAuth, write_token_file, read_token_file
from twitter.api import Twitter, TwitterError
from pprint import pprint
from tweetdb import Tweet, DBWrapper

db = DBWrapper()
commands = {}
class CompletionMeta(type):
    def __init__(cls, name, bases, dct):
        super(CompletionMeta, cls).__init__(name, bases, dct)
        for command in cls.commands:
            commands['/' + command] = cls

def cmd_and_arg(line):
    cmd = arg = None
    fs = line.find(' ')
    if fs != -1:
        cmd = line[:fs]
        fse = fs
        while fse < len(line) and line[fse] == ' ':
            fse += 1
        arg = line[fse:].rstrip()
    else:
        cmd = line
    return cmd, arg

def print_wrap_to_prefix(prefix, text):
    ll = 80 - len(prefix)
    text = text.replace('\n', ' ')
    while text:
        outl = -1
        # can we fit the whole string?
        if len(text) <= ll:
            outl = len(text)
        # try and pick characters that fit in our line length with 
        # word splitting
        if outl <= 0:
            for i in xrange(min((ll, len(text)))):
                if text[i] == ' ':
                    outl = i
        # just find the first space
        if outl <= 0:
            outl = text.find(' ')
        # or just the whole string
        if outl <= 0:
            outl = len(text)
        print "%s%s" % (prefix, text[:outl])
        prefix = ' ' * len(prefix)
        # strip off spaces we didn't output
        for i in xrange(outl, len(text)):
            if text[i] != ' ':
                break
            outl = i + 1
        text = text[outl:]

def debug(f):
    def __debug(*args, **kwargs):
        rv = f(*args, **kwargs)
        print >> sys.stderr, "%s(%s, %s) -> %s" % (f.__name__, repr(args), repr(kwargs), repr(rv))
    return __debug

def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return itertools.izip(a, b)

if __name__ == '__main__':
    CONSUMER_KEY='uS6hO2sV6tDKIOeVjhnFnQ'
    CONSUMER_SECRET='MEYTOS97VvlHX7K1rwHPEqVpTSqZ71HtvoK4sVuYk'
    oauth_filename = os.path.expanduser(os.environ.get('HOME', '') + os.sep + '.twitter_oauth')
    oauth_token, oauth_token_secret = read_token_file(oauth_filename)
    twitter = Twitter(
        auth=OAuth(
            oauth_token, oauth_token_secret, CONSUMER_KEY, CONSUMER_SECRET),
        secure=True,
        api_version='1',
        domain='api.twitter.com')

    def sort_tweets_by_id(tweets):
        tweets.sort(key=lambda a: a['id'])

    def eof_help():
        print "\nuse /quit to quit"

    def get_line(prompt):
        try:
            return raw_input(prompt)
        except EOFError:
            eof_help()
            return ''
        except KeyboardInterrupt:
            eof_help()
            return ''

    def confirm():
        confirm = get_line("confirm? ")
        return (confirm == 'y') or (confirm == 'yes')

    def print_tweet(tweet, suffix=''):
        screen_name = "%-15s" % (tweet['user']['screen_name'])
        key = tracker.get_key_for_tweet(tweet)
        prefix = "%s) %s " % (key, screen_name)
        print_wrap_to_prefix(prefix, tweet['text'] + suffix)

    def display_tweets(tweets):
        if len(tweets) == 0:
            return
        print
        for tweet in tweets:
            if tweet.has_key('retweeted_status'):
                print_tweet(tweet['retweeted_status'], 
                        " (retweeted by %s)" % (tweet['user']['screen_name']))
            else:
                print_tweet(tweet)

    class TimelinePlayback(object):
        def __init__(self, api_method, api_options, initial_count = 20):
            self.api_method = api_method
            self.api_options = api_options
            self.initial_count = initial_count
            self.last_id = None

        def update(self):
            try:
                options = self.api_options.copy()
                if self.last_id is None:
                    options['count'] = self.initial_count
                else:
                    options['since_id'] = self.last_id
                    options['count'] = 200
                recent = self.api_method(**options)
            except Exception, e:
                print "(traceback playing back timeline)"
                traceback.print_exc()
                return
            recent.reverse()
            # issue tokens
            for update in recent:
                tracker.add(update)
                if update.has_key('retweeted_status'):
                    tracker.add(update['retweeted_status'])
            # update last id
            if len(recent) > 0:
                self.last_id = recent[-1]['id']
            return recent

    username_re = re.compile(r'[^\@]*(\@[a-zA-Z0-9]+)')
    def get_usernames(status):
        usernames = []
        m = username_re.match(status)
        while m:
            usernames.append(m.groups()[0][1:]) # without the '@'
            status = status[m.end():]
            m = username_re.match(status)
        return usernames

    def uniq_usernames(usernames):
        seen = set()
        rv = []
        for username in usernames:
            lu = username.lower()
            if lu in seen:
                continue
            seen.add(lu)
            rv.append(username)
        return rv

    class TweetTracker(object):
        def __init__(self, nstored=10000):
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
            db.get_or_make(tweet)
            self.cache_tweet(tweet)

        def get_tweet_for_id(self, twitter_id):
            # if we can, retrieve from our DB
            tweet = db.get_by_status_id(twitter_id)
            if tweet is not None:
                self.cache_tweet(tweet)
                return tweet
            # else, pull it via the API
            try:
                print "pull", twitter_id
                tweet = twitter.statuses.show(id=twitter_id)
            except Exception, e:
                print "(traceback getting tweet)"
                traceback.print_exc()
                return None
            # add it to the database, cache it
            self.add(tweet)
            return tweet

        def get_replies_to_tweet(self, tweet):
            replies = db.get_replies_to_status_id(tweet['id'])
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

    tracker = TweetTracker()

    class SmartCompletion(object):
        def __init__(self):
            self.last_s = None

        @classmethod
        def get_matches(cls, s):
            word = 0
            for (c1, c2) in pairwise(readline.get_line_buffer()):
                if c2 == ' ' and c1 != ' ':
                    word += 1
            # command
            if word == 0 and s.startswith('/'):
                return '', filter(lambda x: x.startswith(s), commands.keys())
            # word token, complete usernames
            prefix = ''
            if s.startswith('@'):
                prefix = '@'
                s = s[1:]
            return prefix, filter(lambda x: x.startswith(s), tracker.seen_users)

        def complete(self, s, state):
            if s != self.last_s:
                self.prefix, self.matches = self.get_matches(s)
                self.matches.sort()
                self.last_s = s
            if state >= len(self.matches):
                return None
            return self.prefix + self.matches[state] + ' '

    smart_complete = SmartCompletion()
    def complete_nowt(s, state):
        return None

    class TimelineUpdates(object):
        def __init__(self):
            self.thread = None
            self.update_delay = 60
            self.go_in(0)

        def update(self):
            def _update():
                # try and suppress tweets that come through in multiple
                # timelines, eg. @replies from people we follow
                printed = set()
                for timeline in timelines:
                    recent = filter(lambda tweet: tweet['id'] not in printed,
                            timeline.update())
                    map(lambda tweet: printed.add(tweet['id']), recent)
                    display_tweets(recent)
            try:
                _update()
            except:
                print "exception during timeline update"
                traceback.print_exc()
            self.go_in(self.update_delay)

        def go_in(self, secs):
            if self.thread is not None:
                self.thread.cancel()
            self.thread = threading.Timer(secs, self.update)
            self.thread.daemon = True
            self.thread.start()

    timelines = [TimelinePlayback(twitter.statuses.friends_timeline, {'include_rts' : True}), TimelinePlayback(twitter.statuses.mentions, {})]
    updates = TimelineUpdates()

    class Refresh(object):
        __metaclass__ = CompletionMeta
        commands = ['refresh']
        def __call__(self, command, what):
            updates.go_in(0)

    class Quit(object):
        __metaclass__ = CompletionMeta
        commands = ['quit']
        def __call__(self, command, what):
            sys.exit(0)

    class Block(object):
        __metaclass__ = CompletionMeta
        commands = ['block']
        def __call__(self, command, what):
            twitter.blocks.create(id=what)

    class Unblock(object):
        __metaclass__ = CompletionMeta
        commands = ['unblock']
        def __call__(self, command, what):
            twitter.blocks.destroy(id=what)

    class BlockExists(object):
        __metaclass__ = CompletionMeta
        commands = ['blockexists']
        def __call__(self, command, what):
            print twitter.blocks.exists(id=what)

    class Blocking(object):
        __metaclass__ = CompletionMeta
        commands = ['blocking']
        def __call__(self, command, what):
            users = twitter.blocks.blocking()
            screen_names = [x['screen_name'] for x in users]
            screen_names.sort()
            print "Blocking:"
            for screen_name in screen_names:
                print "    %s" % screen_name

    class Delete(object):
        __metaclass__ = CompletionMeta
        commands = ['delete']
        def __call__(self, command, what):
            tweet = tracker.get_tweet_for_key(what)
            twitter.statuses.destroy(id=tweet['id'])

    class DeleteLast(object):
        __metaclass__ = CompletionMeta
        commands = ['deletelast']
        def __call__(self, command, what):
            updates.go_in(0)

    class DirectMessage(object):
        __metaclass__ = CompletionMeta
        commands = ['dm']
        def __call__(self, command, what):
            Say()(command, 'D ' + what)

    class Favourite(object):
        __metaclass__ = CompletionMeta
        commands = ['fave']
        def __call__(self, command, what):
            pass

    class Favourites(object):
        __metaclass__ = CompletionMeta
        commands = ['faves']
        def __call__(self, command, what):
            pass

    class Follow(object):
        __metaclass__ = CompletionMeta
        commands = ['follow']
        def __call__(self, command, what):
            twitter.friendships.create(id=what)

    class UnFollow(object):
        __metaclass__ = CompletionMeta
        commands = ['unfollow']
        def __call__(self, command, what):
            twitter.friendships.destroy(id=what)

    class DoesFollow(object):
        __metaclass__ = CompletionMeta
        commands = ['doesfollow']
        def __call__(self, command, what):
            users = what.split()
            if len(users) != 2:
                print "usage: /doesfollow subject_user test_user"
                return
            print twitter.friendships.exists(user_a = users[0], user_b = users[1])

    class Retweet(object):
        __metaclass__ = CompletionMeta
        commands = ['rt']
        def __call__(self, command, what):
            tweet = tracker.get_tweet_for_key(what)
            twitter.statuses.retweet(id=tweet['id'])

    class Reply(object):
        __metaclass__ = CompletionMeta
        commands = ['reply', 'replyall']
        def __call__(self, command, what):
            if what is None:
                print "usage: reply <code> <status>"
                return
            reply_to_key, arg = cmd_and_arg(what)
            tweet = tracker.get_tweet_for_key(reply_to_key)
            if tweet is None:
                print "reply to unknown tweet!"
                return
            if arg is None:
                print "usage: reply <code> <status>"
                return
            usernames = [ tweet['user']['screen_name'] ]
            if command == 'replyall':
                usernames += get_usernames(tweet['text'])
            usernames = uniq_usernames(usernames)
            arg = "%s %s" % (' '.join("@" + u for u in usernames), arg)
            Say()(command, arg, in_reply_to=tweet['id'])

    class Say(object):
        __metaclass__ = CompletionMeta
        commands = ['say']
        def __call__(self, command, what, in_reply_to=None):
            # ignore null tweet attempts
            if what == '':
                return
            print_wrap_to_prefix("send tweet ", what)
            if confirm():
                update = {}
                if in_reply_to is not None:
                    update['in_reply_to_status_id'] = in_reply_to
                update['status'] = what
                twitter.statuses.update(**update)

    class Info(object):
        __metaclass__ = CompletionMeta
        commands = ['info']
        def __call__(self, command, what):
            tweet = tracker.get_tweet_for_key(what)
            if not tweet:
                print "can't find tweet"
            print "Created: %s" % (tweet['created_at'])
            user = tweet['user']
            print "User: `%s' / `%s' in `%s'" % (user['screen_name'], user['name'], user['location'])
            if tweet.get('in_reply_to_screen_name'):
                print "In reply to user:", tweet['in_reply_to_screen_name']
            if tweet.get('in_reply_to_status_id'):
                print "In reply to status:", tweet['in_reply_to_status_id']
            if tweet.get('truncated') == True:
                print "Tweet was truncated."
            print "Status:"
            print tweet['text']

    class Dump(object):
        __metaclass__ = CompletionMeta
        commands = ['dumptweet']
        def __call__(self, command, what):
            tweet = tracker.get_tweet_for_key(what)
            if not tweet:
                print "can't find tweet"
                return
            pprint(tweet)

    class Search(object):
        __metaclass__ = CompletionMeta
        commands = ['search']
        def __call__(self, command, what):
            pass

    class Thread(object):
        __metaclass__ = CompletionMeta
        commands = ['thread']

        def __call__(self, command, what):
            tweet = tracker.get_tweet_for_key(what)
            if not tweet:
                print "can't find tweet"
                return
            # for each tweet;
            #  -> if it replies, add that tweet to our 'to examine' list
            #  -> find the tweets that reply to it. add the to our 'to 
            #     examine' list (after this tweet)
            #  -> sort by twitter ID

            thread = []
            thread_ids = set()
            examine = [ tweet ]

            def append_to_thread(tweet):
                thread_ids.add(tweet['id'])
                thread.append(tweet)

            while len(examine) > 0:
                this_pass = list(examine)
                examine = []
                for tweet in this_pass:
                    append_to_thread(tweet)
                    # whatever this tweet replied to
                    in_reply_to = tweet['in_reply_to_status_id']
                    if in_reply_to is not None:
                        reply = tracker.get_tweet_for_id(in_reply_to)
                        if reply['id'] not in thread_ids:
                            examine.append(reply)
                    # whatever tweets replied to this tweet
                    for reply in tracker.get_replies_to_tweet(tweet):
                        if reply['id'] not in thread_ids:
                            examine.append(reply)
            sort_tweets_by_id(thread)
            display_tweets(thread)

    class Last(object):
        __metaclass__ = CompletionMeta
        commands = ['last']
        def __call__(self, command, what):
            try:
                last = int(what)
            except ValueError:
                print "usage: last <n>"
                return
            except TypeError:
                print "usage: last <n>"
                return
            display_tweets(tracker.get_cached_tweets()[-last:])

    class Recent(object):
        __metaclass__ = CompletionMeta
        commands = ['recent']
        def __call__(self, command, what):
            Last()(command, '10')

    class Grep(object):
        __metaclass__ = CompletionMeta
        commands = ['grep']
        def __call__(self, command, what):
            try:
                matcher = re.compile(what)
            except:
                print "grep: error compiling regular expression"
                return
            def match(tweet):
                return matcher.search(tweet['user']['screen_name']) or \
                        matcher.search(tweet['text'])
            matches = filter(match, tracker.get_cached_tweets())
            sort_tweets_by_id(matches)
            display_tweets(matches)

    class UnFavourite(object):
        __metaclass__ = CompletionMeta
        commands = ['unfave']
        def __call__(self, command, what):
            pass

    class Whois(object):
        __metaclass__ = CompletionMeta
        commands = ['whois']
        def __call__(self, command, what):
            user = twitter.users.show(id=what)
            print "`%s' / `%s' in `%s'" % (user['screen_name'], user['name'], user['location'])
            print "Followers: %8d  Following: %8d" % (user['followers_count'], user['friends_count'])
            if user['following']:
                print "You follow %s." % (user['screen_name'])
            else:
                print "You do not follow %s." % (user['screen_name'])
            print_wrap_to_prefix("Description: ", user['description'])

    # set up completion
    readline.set_completer(smart_complete.complete)
    readline.parse_and_bind('tab: complete')
    delims = readline.get_completer_delims()
    delims = ''.join(filter(lambda x: x != '/', delims))
    readline.set_completer_delims(delims)

    print """\
Undulatus
Copyright (C) 2011 Grahame Bowland <grahame@angrygoats.net>

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

See the file 'LICENSE' included with this software for more detail.
"""


    while True:
            readline.redisplay()
            line = get_line(">> ")
            cmd = None
            arg = None
            if line.startswith('/'):
                cmd, arg = cmd_and_arg(line)
            else:
                cmd = '/say'
                arg = line.rstrip()
            ex = commands.get(cmd, None)
            readline.set_completer(complete_nowt)
            if ex is not None:
                try:
                    ex()(cmd[1:], arg)
                except Exception, e:
                    if isinstance(e, SystemExit):
                        raise
                    traceback.print_exc()
            else:
                print "unknown command."
            readline.set_completer(smart_complete.complete)

