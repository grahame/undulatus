#!/usr/bin/env python3

from util import *

if __name__ == '__main__':
    import sys, os
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

    def main():
        import readline, sys, os, threading, traceback
        from pprint import pprint

        from commands import get_commands
        from tracker import TweetTracker
        from timeline import TimelinePlayback, SearchPlayback
        import tweetdb, base64

        from twitter.oauth import OAuth, write_token_file, read_token_file
        from twitter.api import Twitter, TwitterError
        from twitter.api import TwitterHTTPError

        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--reauth', '-r', action='store_true', default=False)
        parser.add_argument('screen_name')
        parser.add_argument('-u', default='http://localhost:5984')
        parser.add_argument('-d', default=None)

        args = parser.parse_args()
        screen_name = args.screen_name
        srvuri = args.u
        dbname = args.d or args.screen_name.lower()
        reauth = args.reauth

        def obsc():
            # pretty pointless, and IMHO OAuth is broken for standalone, open source applications
            return [str(base64.decodebytes(t), encoding='utf8') for t in 
                    (b'aWdpcGRPVXp0dHJWVWF5Sk9kTVpLQQ==', b'Q1U2RHpFNzEwY1NFRGN3WnUzS0NsdEt1V0V0TmNqVVBVc1Zzb25abDVCOA==')]

        db = tweetdb.DBWrapper(app_path, screen_name, srvuri, dbname)
        oauth_doc, oauth_token, oauth_token_secret = db.tokens()

        if (oauth_token is None) or reauth:
            from twitter.oauth_dance import oauth_dance
            from tempfile import mkstemp
            fd, filepath = mkstemp()
            args = ["undulatus"] + obsc() + [filepath]
            oauth_dance(*args)
            oauth_token, oauth_token_secret = read_token_file(filepath)
            os.unlink(filepath)
            db.add_tokens(oauth_doc, oauth_token, oauth_token_secret)

        twitter = Twitter(
            auth=OAuth(
                oauth_token, oauth_token_secret, *obsc()),
            secure=True,
            api_version='1.1',
            domain='api.twitter.com')
        search = Twitter(
            auth=OAuth(
                oauth_token, oauth_token_secret, *obsc()),
            secure=True,
            api_version='1',
            domain='search.twitter.com')
        search.uriparts = ()

        configuration = db.configuration()
        if configuration is None or (datetime.datetime.now() - datetime_strptime(configuration['updated'])).days > 1:
            print("retrieving twitter configuration.")
            new_config = twitter.help.configuration()
            configuration = db.save_configuration(new_config)

        tracker = TweetTracker(twitter, db)

        class TimelineUpdates(object):
            def __init__(self):
                self._lock = threading.Lock()
                self.thread = None
                self.update_delay = 60
                self._schedule = {}
                self.timelines = [
                        TimelinePlayback(tracker, twitter.statuses.home_timeline,
                            {'include_rts' : True, 'include_entities' : True}),
                        TimelinePlayback(tracker, twitter.statuses.mentions_timeline, {})]
                self.go_in(0)
                self.saved_search_playbacks = {}

            def update(self):
                def _update():
                    # try and suppress tweets that come through in multiple
                    # timelines, eg. @replies from people we follow
                    printed = set()
                    for timeline in self.timelines:
                        update = timeline.update()
                        if update is None:
                            print("timeline update failed: %s" % repr(timeline))
                            continue
                        recent = [tweet for tweet in update if tweet['id'] not in printed]
                        for tweet in recent:
                            printed.add(tweet['id'])
                        tracker.display_tweets(recent)
                def _update_searches():
                    saved_searches = db.saved_searches()
                    # manage search instances
                    existing = set(self.saved_search_playbacks)
                    required = set(saved_searches)
                    cancelled = existing - required
                    new = required - existing
                    for s in cancelled:
                        print("cancelled search: `%s'" % (s))
                        self.saved_search_playbacks.pop(s)
                    for s in new:
                        print("started search: `%s'" % (s))
                        self.saved_search_playbacks[s] = SearchPlayback(tracker,
                                search.search, {
                                    'q' : s,
                                    'result_type' : 'recent',
                                    'include_entities' : 't'
                                    })
                    # run and then print searches
                    printed = set()
                    for s in self.saved_search_playbacks:
                        timeline = self.saved_search_playbacks[s]
                        update = timeline.update()
                        if update is None:
                            print("search update failed (%s): %s" % (s, repr(timeline)))
                            continue
                        recent = [tweet for tweet in update if tweet['id'] not in printed]
                        for tweet in recent:
                            printed.add(tweet['id'])
                        tracker.display_tweets(recent)
                def _scheduled():
                    done = []
                    for cb in self._schedule.values():
                        try:
                            res = cb()
                        except Exception as e:
                            if isinstance(e, SystemExit):
                                raise
                            traceback.print_exc()
                        if not res:
                            done.append(id(cb))
                    for cb_id in done:
                        del self._schedule[cb_id]
                with self._lock:
                    try:
                        _scheduled()
                        _update()
                        _update_searches()
                    except TwitterHTTPError as e:
                        print("(twitter API error: %s)" % e)
                        return
                    except:
                        print("exception during timeline update")
                        last_tb.set(traceback.format_exc())
                    self.go_in(self.update_delay)

            def schedule(self, cb):
                with self._lock:
                    self._schedule[id(cb)] = cb

            def go_in(self, secs):
                if self.thread is not None:
                    self.thread.cancel()
                self.thread = threading.Timer(secs, self.update)
                self.thread.daemon = True
                self.thread.start()

        updates = TimelineUpdates()
        command_classes = get_commands(db, twitter, search, screen_name, tracker, updates, configuration['configuration'])

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
                    cb = ex()(cmd[1:], arg)
                    # commands can return a callback function, which will then be 
                    # called each time update() is called until it returns False
                    if cb is not None:
                        updates.schedule(cb)
                except Exception as e:
                    if isinstance(e, SystemExit):
                        raise
                    traceback.print_exc()
            else:
                print("unknown command.")

    setup_env()
    splash()
    main()


