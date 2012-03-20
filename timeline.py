
import traceback
from twitter.api import TwitterHTTPError
from util import last_tb

class TimelinePlayback(object):
    def __init__(self, tracker, api_method, api_options, initial_count = 20):
        self.tracker = tracker
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
        except TwitterHTTPError as e:
            print("(twitter API error: %s)" % e)
            return
        except Exception as e:
            print("(traceback playing back timeline - /traceback to retrieve)")
            last_tb.set(traceback.format_exc())
            return
        recent.reverse()
        # issue tokens
        for update in recent:
            self.tracker.add(update)
        # update last id
        if len(recent) > 0:
            self.last_id = recent[-1]['id']
        return recent

