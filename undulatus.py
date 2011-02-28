#!/usr/bin/env python3

import readline, sys, os, threading, traceback
from pprint import pprint

from commands import get_commands
from tracker import TweetTracker
from util import *
from timeline import TimelinePlayback
import tweetdb, base64

def splash():
    print("""\
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
""")

def obsc():
    # pretty pointless, and IMHO OAuth is broken for standalone, open source applications
    return [str(base64.decodebytes(t), encoding='utf8') for t in 
            (b'aWdpcGRPVXp0dHJWVWF5Sk9kTVpLQQ==', b'Q1U2RHpFNzEwY1NFRGN3WnUzS0NsdEt1V0V0TmNqVVBVc1Zzb25abDVCOA==')]

if __name__ == '__main__':
    splash()

    from twitter.oauth import OAuth, write_token_file, read_token_file
    from twitter.api import Twitter, TwitterError

    from optparse import OptionParser
    parser = OptionParser()
    (options, args) = parser.parse_args()
    screen_name = args[0]

    dbfile = get_dbfile(screen_name)
    db = tweetdb.DBWrapper(dbfile)
    oauth_token, oauth_token_secret = db.tokens_for_screen_name(screen_name)

    if oauth_token is None:
        from twitter.oauth_dance import oauth_dance
        from tempfile import mkstemp
        fd, filepath = mkstemp()
        args = ["undulatus"] + obsc() + [filepath]
        oauth_dance(*args)
        oauth_token, oauth_token_secret = read_token_file(filepath)
        os.unlink(filepath)
        db.add_tokens(screen_name, oauth_token, oauth_token_secret)

    twitter = Twitter(
        auth=OAuth(
            oauth_token, oauth_token_secret, *obsc()),
        secure=True,
        api_version='1',
        domain='api.twitter.com')

    tracker = TweetTracker(twitter, db)
    timelines = [
            TimelinePlayback(tracker, twitter.statuses.friends_timeline,
                {'include_rts' : True}),
            TimelinePlayback(tracker, twitter.statuses.mentions, {})]

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
                    recent = [tweet for tweet in timeline.update() if tweet['id'] not in printed]
                    for tweet in recent:
                        printed.add(tweet['id'])
                    tracker.display_tweets(recent)
            try:
                _update()
            except:
                print("exception during timeline update")
                traceback.print_exc()
            self.go_in(self.update_delay)

        def go_in(self, secs):
            if self.thread is not None:
                self.thread.cancel()
            self.thread = threading.Timer(secs, self.update)
            self.thread.daemon = True
            self.thread.start()

    updates = TimelineUpdates()
    command_classes = get_commands(twitter, screen_name, tracker, updates)

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
                return '', [x for x in list(command_classes.keys()) if x.startswith(s)]
            # word token, complete usernames
            prefix = ''
            if s.startswith('@'):
                prefix = '@'
                s = s[1:]
            return prefix, [x for x in tracker.seen_users if x.startswith(s)]

        def complete(self, s, state):
            if s != self.last_s:
                self.prefix, self.matches = self.get_matches(s)
                self.matches.sort()
                self.last_s = s
            if state >= len(self.matches):
                return None
            return self.prefix + self.matches[state] + ' '

    smart_complete = SmartCompletion()

    while True:
        line = get_line("%s> " % screen_name, smart_complete.complete)
        cmd = None
        arg = None
        if line.startswith('/'):
            cmd, arg = cmd_and_arg(line)
        else:
            cmd = '/say'
            arg = line.rstrip()
        ex = command_classes.get(cmd, None)
        if ex is not None:
            try:
                ex()(cmd[1:], arg)
            except Exception as e:
                if isinstance(e, SystemExit):
                    raise
                traceback.print_exc()
        else:
            print("unknown command.")

