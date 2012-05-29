
import sys, re
import datetime, time
from util import *
from pprint import pprint
from twitter.util import htmlentitydecode
from urllib.parse import quote as url_quote
from itertools import zip_longest

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
                in_reply_to = tweet_in_reply_to(tweet)
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


def get_commands(db, twitter, search, username, tracker, updates, configuration):
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
                screen_name = tweet_user(tweet)
            twitter.blocks.create(id=screen_name)

    class ReportSpam(Command):
        commands = ['reportspam']
        def __call__(self, command, what):
            screen_name = what
            tweet = tracker.get_tweet_for_key(what)
            if tweet is not None:
                screen_name = tweet_user(tweet)
            print("Really report `%s' for spam (and block them)?" % (screen_name))
            if confirm():
                twitter.report_spam(id=screen_name)

    class Unblock(Command):
        commands = ['unblock']
        def __call__(self, command, what):
            screen_name = what
            tweet = tracker.get_tweet_for_key(what)
            if tweet is not None:
                screen_name = tweet_user(tweet)
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
            tweet = tracker.get_tweet_for_key(what)
            twitter.favorites.create(id=tweet['id'])
            pass

    class UnFavourite(Command):
        commands = ['unfave']
        def __call__(self, command, what):
            twitter.favorites.destroy(id=tweet['id'])

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
            print("Retweet following tweet by `%s'?" % (tweet_user(tweet)))
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
            usernames = [ tweet_user(tweet) ]
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
            est = estimate_tweet_length(what, configuration['short_url_length'])
            if est > 140:
                print("can't send tweet, too long at %d characters." % est)
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
                lat, lng = db.getloc()
                if lat is not None and lng is not None:
                    update['lat'] = lat
                    update['long'] = lng
                twitter.statuses.update(**update)

    class Info(Command):
        commands = ['info']
        def __call__(self, command, what):
            def display_info(tweet):
                print("Created: %s (%s)" % (tweet_ctime(tweet), tweet_ago(tweet)))
                if 'user' in tweet:
                    user = tweet['user']
                    print("User: `%s' / `%s' in `%s'" % (user['screen_name'], user['name'], user['location']))
                if tweet.get('in_reply_to_screen_name'):
                    print("In reply to user:", tweet['in_reply_to_screen_name'])
                in_reply_to = tweet_in_reply_to(tweet)
                if in_reply_to is not None:
                    print("In reply to status:", in_reply_to)
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

    class Console(Command):
        commands = ['console']
        def __call__(self, command, what):
            from code import InteractiveConsole
            console = InteractiveConsole(locals={
                'twitter'       : twitter, 
                'username'      : username, 
                'tracker'       : tracker, 
                'updates'       : updates, 
                'configuration' : configuration
                })
            console.interact("(entering python console)\n")
            print("(console closed.)")

    class Favourites(Command):
        commands = ['faves']
        def __call__(self, command, what):
            count = 20
            npages = 1
            if what is not None:
                parts = what.split(' ')
                try: count = int(parts[0])
                except ValueError: pass
                if len(parts) > 1:
                    try: npages = int(parts[1])
                    except ValueError: pass
            since_id = None
            while npages > 0:
                kwargs = {'count': count, 'include_entities': True}
                if since_id is not None:
                    kwargs['since_id'] = since_id
                tweets = twitter.favorites(**kwargs)
                if len(tweets) > 0: since_id = tweets[-1]['id_str']
                else: break
                sort_tweets_by_id(tweets)
                for tweet in tweets:
                    tracker.add(tweet)
                tracker.display_tweets(tweets)
                npages -= 1

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
                return matcher.search(tweet_user(tweet)) or \
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
            follows_us = twitter.friendships.exists(user_a = what, user_b = username)
            print("Follows you:", repr(follows_us))

    class Search(Command):
        commands = ['search']
        def __call__(self, command, what):
            res = search.search(q=what)
            for result in res['results']:
                print_wrap_to_prefix(result['id_str'] + " ", result['text'])

    class ListSearch(Command):
        commands = ['listsearch']
        def __call__(self, command, what):
            searches = db.saved_searches()
            searches.sort()
            print("Persistent searches:")
            for s in searches:
                print("  %s" % (s))

    class AddSearch(Command):
        commands = ['addsearch', 'removesearch']
        def __call__(self, command, what):
            searches = set(db.saved_searches())
            if command == 'addsearch':
                searches.add(what)
            elif command == 'removesearch':
                try:
                    searches.remove(what)
                except KeyError:
                    print ("search `%s' doesn't exist." % what)
                    return
            db.save_saved_searches(list(searches))

    class LatLng(Command):
        commands = ['setloc']
        def __call__(self, command, what):
            lat, lng = map(float, what.split(' '))
            db.setloc(lat, lng)


    class Pull(Command):
        commands = ['pull', 'fetch']
        def __call__(self, command, what):
            tweet = twitter.statuses.show(id=what)
            tracker.add(tweet)
            tracker.display_tweets([tweet])
    
    class GetFollowers(Command):
        commands = ['followers', 'following']
        def __call__(self, command, what):
            def grouper(n, iterable, fillvalue=None):
                args = [iter(iterable)] * n
                return zip_longest(*args, fillvalue=fillvalue)
            cursor = -1
            ids = set()
            if command == 'followers':
                method = twitter.followers.ids
            elif command == 'following':
                method = twitter.friends.ids
            tries = 10
            while True:
                print("getting %s, cursor %d", command, cursor)
                try:
                    resp = method(cursor=cursor, stringify_ids=True)
                except urllib.error.HTTPError:
                    tries -= 1
                    if tries == 0:
                        print("too many errors, giving up")
                        return
                    continue
                next_cursor = resp['next_cursor']
                if next_cursor == cursor:
                    break
                ids = ids.union(set(resp['ids']))
                cursor = next_cursor
                time.sleep(1)
            users = []
            for lookup_ids in grouper(100, ids):
                lookup_ids = [t for t in lookup_ids if t is not None]
                print("retrieving %s: have %d users" % (command, len(users)))
                while True:
                    try:
                        resp = twitter.users.lookup(user_id=','.join(lookup_ids), include_entities=True)
                        break
                    except urllib.error.HTTPError:
                        tries -= 1
                        if tries == 0:
                            print("too many errors, giving up")
                            return
                users += resp
                time.sleep(1)
            doc = { 'type' : command, command : users }
            name = command + "_" + datetime.datetime.utcnow().isoformat()
            db.savedoc(name, doc)
            print("%s: %d of %d saved to document %s" % (command, len(users), len(ids), name))

    return cmds

