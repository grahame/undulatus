
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
        except Exception, e:
            print "(traceback playing back timeline)"
            traceback.print_exc()
            return
        recent.reverse()
        # issue tokens
        for update in recent:
            self.tracker.add(update)
            if update.has_key('retweeted_status'):
                self.tracker.add(update['retweeted_status'])
        # update last id
        if len(recent) > 0:
            self.last_id = recent[-1]['id']
        return recent

