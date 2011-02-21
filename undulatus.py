#!/usr/bin/env python

import readline, sys, os, threading, traceback
from pprint import pprint

from commands import get_commands
from tracker import TweetTracker
from util import *
from timeline import TimelinePlayback

if __name__ == '__main__':
    from twitter.oauth import OAuth, write_token_file, read_token_file
    from twitter.api import Twitter, TwitterError
    # fix me, this shouldn't be here
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

    tracker = TweetTracker(twitter)
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
                    recent = filter(lambda tweet: tweet['id'] not in printed,
                            timeline.update())
                    map(lambda tweet: printed.add(tweet['id']), recent)
                    tracker.display_tweets(recent)
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

    updates = TimelineUpdates()
    command_classes = get_commands(twitter, tracker, updates)

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
                return '', filter(lambda x: x.startswith(s), command_classes.keys())
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
            line = get_line(">> ", smart_complete.complete)
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
                except Exception, e:
                    if isinstance(e, SystemExit):
                        raise
                    traceback.print_exc()
            else:
                print "unknown command."

