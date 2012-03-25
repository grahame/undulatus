
import sys, re
from util import *
from pprint import pprint
from twitter.util import htmlentitydecode
from urllib.parse import quote as url_quote

class Threader(object):
    def __init__(self, tracker):
        self.tracker = tracker
        self.thread = []
        self.thread_ids = set()
        self.examine = [ ]

    def append_to_thread(self, tweet):
        self.thread_ids.add(tweet['id'])
        self.thread.append(tweet)

    def process(self, tweet):
        # for each tweet;
        #  -> if it replies, add that tweet to our 'to examine' list
        #  -> find the tweets that reply to it. add the to our 'to 
        #     examine' list (after this tweet)
        #  -> sort by twitter ID
        if tweet['id'] not in self.thread_ids:
            self.examine.append(tweet)

        while len(self.examine) > 0:
            this_pass = list(self.examine)
            self.examine = []
            for tweet in this_pass:
                self.append_to_thread(tweet)
                # whatever this tweet replied to
                in_reply_to = tweet['in_reply_to_status_id_str']
                if in_reply_to is not None:
                    reply = self.tracker.get_tweet_for_id(in_reply_to)
                    if reply is None:
                        print("(tweet in thread deleted or protected: %s)" % in_reply_to)
                    elif reply['id'] not in self.thread_ids:
                        self.examine.append(reply)
                # whatever tweets replied to this tweet
                for reply in self.tracker.get_replies_to_tweet(tweet):
                    if reply['id'] not in self.thread_ids:
                        self.examine.append(reply)

    def get(self):
        sort_tweets_by_id(self.thread)
        return self.thread


def get_commands(twitter, username, tracker, updates, configuration):
    cmds = {}

    class CommandMeta(type):
        def __init__(cls, name, bases, dct):
            super(CommandMeta, cls).__init__(name, bases, dct)
            if not hasattr(cls, "commands"):
                return
            for command in cls.commands:
                cmds['/' + command] = cls

    class Command(object, metaclass=CommandMeta):
        pass

    class Status(Command):
        commands = ['status']
        def __call__(self, command, what):
            info = tracker.status()
            pprint(info)

    class Refresh(Command):
        commands = ['refresh']
        def __call__(self, command, what):
            updates.go_in(0)

    class Traceback(Command):
        commands = ['traceback']
        def __call__(self, command, what):
            tb = last_tb.get()
            if tb is None:
                print("No traceback has occurred since undulatus was launched.")
            else:
                print("Traceback follows:\n%s\n", tb)

    class Quit(Command):
        commands = ['quit']
        def __call__(self, command, what):
            sys.exit(0)

    class Block(Command):
        commands = ['block']
        def __call__(self, command, what):
            screen_name = what
            tweet = tracker.get_tweet_for_key(what)
            if tweet is not None:
                screen_name = tweet['user']['screen_name']
            twitter.blocks.create(id=screen_name)

    class ReportSpam(Command):
        commands = ['reportspam']
        def __call__(self, command, what):
            screen_name = what
            tweet = tracker.get_tweet_for_key(what)
            if tweet is not None:
                screen_name = tweet['user']['screen_name']
            print("Really report `%s' for spam (and block them)?" % (screen_name))
            if confirm():
                twitter.report_spam(id=screen_name)

    class Unblock(Command):
        commands = ['unblock']
        def __call__(self, command, what):
            screen_name = what
            tweet = tracker.get_tweet_for_key(what)
            if tweet is not None:
                screen_name = tweet['user']['screen_name']
            twitter.blocks.destroy(id=screen_name)

    class BlockExists(Command):
        commands = ['blockexists']
        def __call__(self, command, what):
            print(twitter.blocks.exists(id=what))

    class Blocking(Command):
        commands = ['blocking']
        def __call__(self, command, what):
            users = twitter.blocks.blocking()
            screen_names = [x['screen_name'] for x in users]
            screen_names.sort()
            print("Blocking:")
            for screen_name in screen_names:
                print("    %s" % screen_name)

    class Delete(Command):
        commands = ['delete']
        def __call__(self, command, what):
            tweet = tracker.get_tweet_for_key(what)
            twitter.statuses.destroy(id=tweet['id'])

    class DeleteLast(Command):
        commands = ['deletelast']
        def __call__(self, command, what):
            updates.go_in(0)

    class DirectMessage(Command):
        commands = ['dm']
        def __call__(self, command, what):
            Say()(command, 'D ' + what)

    class Favourite(Command):
        commands = ['fave']
        def __call__(self, command, what):
            pass

    class Favourites(Command):
        commands = ['faves']
        def __call__(self, command, what):
            pass

    class Follow(Command):
        commands = ['follow']
        def __call__(self, command, what):
            twitter.friendships.create(id=what)

    class UnFollow(Command):
        commands = ['unfollow']
        def __call__(self, command, what):
            twitter.friendships.destroy(id=what)

    class DoesFollow(Command):
        commands = ['doesfollow']
        def __call__(self, command, what):
            users = what.split()
            if len(users) != 2:
                print("usage: /doesfollow subject_user test_user")
                return
            print(twitter.friendships.exists(user_a = users[0], user_b = users[1]))

    class Retweet(Command):
        commands = ['rt']
        def __call__(self, command, what):
            tweet = tracker.get_tweet_for_key(what)
            print("Retweet following tweet by `%s'?" % (tweet['user']['screen_name']))
            tracker.print_tweet(tweet)
            if confirm():
                twitter.statuses.retweet(id=tweet['id'])

    class Reply(Command):
        commands = ['reply', 'replyall']
        def __call__(self, command, what):
            if what is None:
                print("usage: reply <code> <status>")
                return
            reply_to_key, arg = cmd_and_arg(what)
            tweet = tracker.get_tweet_for_key(reply_to_key)
            if tweet is None:
                print("reply to unknown tweet!")
                return
            if arg is None:
                print("usage: reply <code> <status>")
                return
            usernames = [ tweet['user']['screen_name'] ]
            if command == 'replyall':
                usernames += get_usernames(tweet_text(tweet))
            # unique usernames, and don't reply to ourselves
            usernames = uniq_usernames(
                    [u for u in usernames if u != username])
            arg = "%s %s" % (' '.join("@" + u for u in usernames), arg)
            Say()(command, arg, in_reply_to=int(tweet['id_str']))

    class Say(Command):
        commands = ['say']
        def __call__(self, command, what, in_reply_to=None):
            # ignore null tweet attempts
            if what == '':
                return
            if estimate_tweet_length(what, configuration['short_url_length']) > 140:
                print("can't send tweet, too long at %d characters." % len(what))
                return
            if what.startswith('d '):
                print_wrap_to_prefix("send dm ", what)
            else:
                print_wrap_to_prefix("send tweet ", what)
            if confirm():
                update = {}
                if in_reply_to is not None:
                    update['in_reply_to_status_id'] = in_reply_to
                update['status'] = what
                twitter.statuses.update(**update)

    class Info(Command):
        commands = ['info']
        def __call__(self, command, what):
            def display_info(tweet):
                print("Created: %s (%s)" % (tweet_ctime(tweet), tweet_ago(tweet)))
                user = tweet['user']
                print("User: `%s' / `%s' in `%s'" % (user['screen_name'], user['name'], user['location']))
                if tweet.get('in_reply_to_screen_name'):
                    print("In reply to user:", tweet['in_reply_to_screen_name'])
                if tweet.get('in_reply_to_status_id_str'):
                    print("In reply to status:", tweet['in_reply_to_status_id_str'])
                if tweet.get('truncated') == True:
                    print("Tweet was truncated.")
                print("Status:")
                print_wrap_to_prefix("  ", tweet_text(tweet))
                if 'retweeted_status' in tweet:
                    print("Tweet includes a retweet:")
                    display_info(tweet['retweeted_status'])

            tweet = tracker.get_tweet_for_key(what)
            if not tweet:
                print("can't find tweet")
                return
            display_info(tweet)

    class Dump(Command):
        commands = ['dumptweet']
        def __call__(self, command, what):
            tweet = tracker.get_tweet_for_key(what)
            if not tweet:
                print("can't find tweet")
                return
            pprint(tweet)

    class Search(Command):
        commands = ['search']
        def __call__(self, command, what):
            pass

    class UserTweets(Command):
        commands = ['usertweets']

        def __call__(self, command, what):
            screen_name, count = cmd_and_arg(what)
            if count is not None:
                try: count = int(count)
                except ValueError:
                    print("usage: /usertweets <user> [count]")
                    return
                except TypeError:
                    print("usage: /usertweets <user> [count]")
                    return
            count = count or 20
            tweets = twitter.statuses.user_timeline(screen_name=screen_name, count=count, include_rts=True, include_entities=True)
            sort_tweets_by_id(tweets)
            for tweet in tweets:
                tracker.add(tweet)
            tracker.display_tweets(tweets)

    class Thread(Command):
        commands = ['thread']

        def __call__(self, command, what):
            tweet = tracker.get_tweet_for_key(what)
            if not tweet:
                print("can't find tweet")
                return
            threader = Threader(tracker)
            threader.process(tweet)
            tracker.display_tweets(threader.get())

    class Last(Command):
        commands = ['last']
        def __call__(self, command, what):
            try:
                last = int(what)
            except ValueError:
                print("usage: last <n>")
                return
            except TypeError:
                print("usage: last <n>")
                return
            tracker.display_tweets(tracker.get_cached_tweets()[-last:])

    class Recent(Command):
        commands = ['recent']
        def __call__(self, command, what):
            Last()(command, '10')

    class Grep(Command):
        commands = ['grep', 'tgrep']
        def __call__(self, command, what):
            try:
                matcher = re.compile(what, re.IGNORECASE | re.UNICODE)
            except:
                print("grep: error compiling regular expression")
                return
            def match(tweet):
                return matcher.search(tweet['user']['screen_name']) or \
                        matcher.search(tweet_text(tweet))
            if command == 'grep':
                matches = list(filter(match, tracker.get_cached_tweets()))
                sort_tweets_by_id(matches)
                tracker.display_tweets(matches)
            elif command == 'tgrep':
                threader = Threader(tracker)
                matches = list(filter(match, tracker.get_cached_tweets()))
                for match in matches:
                    threader.process(match)
                tracker.display_tweets(threader.get())

    class UnFavourite(Command):
        commands = ['unfave']
        def __call__(self, command, what):
            pass

    class Whois(Command):
        commands = ['whois']
        def __call__(self, command, what):
            user = twitter.users.show(id=what)
            print("%s in %s" % (user['name'], user['location']))
            print("Followers: %8d  Following: %8d" % (user['followers_count'], user['friends_count']))
            if user['following']:
                print("You follow %s." % (user['screen_name']))
            else:
                print("You do not follow %s." % (user['screen_name']))
            if user['verified'] == True:
                print("User is verified.")
            print_wrap_to_prefix("Description: ", user['description'] or '')

    return cmds

