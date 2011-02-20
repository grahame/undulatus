
from django.db import models
from django.core.exceptions import ObjectDoesNotExist
import json

class Tweet(models.Model):
    status_id = models.BigIntegerField(primary_key=True, unique=True)
    screen_name = models.CharField(max_length=16)
    in_reply_to_screen_name = models.CharField(max_length=16, null=True)
    in_reply_to_status_id = models.BigIntegerField(null=True)
    embedded_retweet = models.ForeignKey('self', null=True)
    text = models.TextField()
    json = models.TextField()

    @classmethod
    def get_by_status_id(cls, status_id):
        try:
            obj = cls.objects.get(status_id=status_id)
            return obj
        except ObjectDoesNotExist:
            return None

    @classmethod
    def get_replies_to_status_id(cls, status_id):
        return cls.objects.filter(in_reply_to_status_id=status_id)

    @classmethod
    def get_or_make(cls, tweet):
        obj = cls.get_by_status_id(tweet['id'])
        if obj is not None:
            return obj
        attrs = {
                'status_id' : tweet['id'],
                'screen_name' : tweet['user']['screen_name'],
                'in_reply_to_status_id' : tweet['in_reply_to_status_id'],
                'in_reply_to_screen_name' : tweet['in_reply_to_screen_name'],
                'text' : tweet['text'],
                'json' : json.dumps(tweet)
                }
        if tweet.has_key('retweeted_status'):
            retweet_json = tweet['retweeted_status']
            retweet = Tweet.get_or_make(retweet_json)
            retweet.save()
            attrs['embedded_retweet'] = retweet
        obj = Tweet(**attrs)
        obj.save()
        return obj

