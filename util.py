
import re, os, sys, traceback, itertools, time, calendar

def debug(f):
    def __debug(*args, **kwargs):
        try:
            rv = f(*args, **kwargs)
        except:
            # cover case of things that swallow exceptions above us
            print("(debug decorator) exception in wrapped function", file=sys.stderr)
            traceback.print_exc()
            raise
        print("%s(%s, %s) -> %s" % (f.__name__, repr(args), repr(kwargs), repr(rv)), file=sys.stderr)
        return rv
    return __debug

# unescape twitter 'text' messages, which according to:
#     http://apiwiki.twitter.com/w/page/22554664/Return-Values
# are escaped. We're using JSON and according to:
#     http://code.google.com/p/twitter-api/issues/detail?id=1695
# we thus only have to unescape &lt; and &gt;
def tweet_text(tweet):
    return tweet['text'].replace('&lt;', '<').replace('&gt;', '>')

def tweet_unixtime(tweet):
    return calendar.timegm(time.strptime(tweet['created_at'], '%a %b %d %H:%M:%S +0000 %Y'))

def tweet_ago(tweet):
    ago = time.time() - tweet_unixtime(tweet)
    if ago < 60:
        return "%d seconds ago" % (ago)
    if ago < 3600:
        return "%d minutes ago" % (ago / 60.)
    hours = ago / 3600.
    days = hours // 24
    hours -= 24 * days
    if days > 0:
        return "%d days, %d hours ago" % (days, hours)
    return "%d hours ago" % (hours)

def tweet_ctime(tweet):
    return time.ctime(tweet_unixtime(tweet))

def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)

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
            for i in range(min((ll, len(text)))):
                if text[i] == ' ':
                    outl = i
        # just find the first space
        if outl <= 0:
            outl = text.find(' ')
        # or just the whole string
        if outl <= 0:
            outl = len(text)
        print("%s%s" % (prefix, text[:outl]))
        prefix = ' ' * len(prefix)
        # strip off spaces we didn't output
        for i in range(outl, len(text)):
            if text[i] != ' ':
                break
            outl = i + 1
        text = text[outl:]

def sort_tweets_by_id(tweets):
    tweets.sort(key=lambda a: a['id'])

def eof_help():
    print("\nuse /quit to quit")

import readline
# set up readline on module import
# seems to be associated with source file
delims = readline.get_completer_delims()
# remove / from delims as that is our command char
delims = ''.join([x for x in delims if x != '/'])
readline.set_completer_delims(delims)

def get_line(prompt, completer):
    # set up completion
    readline.parse_and_bind('tab: complete')
    def c(*args, **kwargs):
        print(args, kwargs)
    readline.set_completer(completer)
    try:
        return input(prompt)
    except EOFError:
        eof_help()
        return ''
    except KeyboardInterrupt:
        eof_help()
        return ''

def confirm():
    def complete_nowt(s, state):
        return None
    confirm = get_line("confirm? ", complete_nowt)
    return (confirm == 'y') or (confirm == 'yes')

username_re = re.compile(r'[^\@]*(\@[a-zA-Z0-9\_]+)')
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

def get_dbfile(screen_name):
    undulatus_dir = os.path.expanduser('~/.undulatus')
    # make the dir if it's not there
    if not os.access(undulatus_dir, os.R_OK):
        try: os.mkdir(undulatus_dir)
        except:
            print("unable to make directory `%s'." % undulatus_dir, file=sys.stderr)
            os.exit(1)
    # fix the permissions on it
    os.chmod(undulatus_dir, 0o700)
    dbfile = os.path.join(undulatus_dir, '%s.db' % screen_name)
    return dbfile

