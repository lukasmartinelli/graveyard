import locale
import datetime
import time
import calendar
import json
import urllib
import urllib2
import sys
import os


def load_substitution_param(substitution, default_value):
    if substitution.startswith('[$$'):
        return default_value
    else:
        return substitution


RUNS_IN_SAP = sys.executable.endswith(u'al_engine.exe')
POST_LIMIT = int(load_substitution_param(r'[$$FACEBOOK_POST_LIMIT]',
                                         os.environ.get('POST_LIMIT', 200)))
BASE_URL = u'https://graph.facebook.com'
MIN_SINCE = datetime.datetime(2015, 1, 1)
ACCESS_TOKEN = (u'CAAIcqYlr5QMBAEpoQTEqQn6y2qp6z5y1n3aoriTShRwvYo3SsusyWuAaGiz'
                u'qCYtZCmpw90yL5AaneoaDCqzLnZAZC3zbi2ZAdjanWNbLOts5LvcjFZCWRtv'
                u'beS5mX67Clyyec3uLZCz3VDiQ87Xyw4o9eMFpDijU5IojmZAo2QiZC0iYbb5'
                u'0uwKB')
if RUNS_IN_SAP:
    PROXY = u'iproxy.corproot.net:8080'
    locale.setlocale(locale.LC_ALL, 'C')
else:
    PROXY = u''
    from sap import Collection, DataManager


def get_data(url, proxy, oauth_helper, method=0, **queryParams):
    """
    Send an http or https request and receive a JSON object if
    there is no error.
    """

    handler = urllib2.BaseHandler()
    # Determine if the request must use a proxy
    if proxy is not None and proxy != '':
        handler = urllib2.ProxyHandler({u'http': proxy, u'https': proxy})

    params = urllib.urlencode(queryParams)
    http_body = None if method == 0 else params
    http_url = u'%s?%s' % (url, params) if method == 0 else url

    try:
        opener = urllib2.build_opener(handler)

        if oauth_helper:
            head = oauth_helper.generateHeader(url, queryParams)

            opener.addheaders = [(u'Authorization', head),
                                 (u'Accept-Charset', 'utf-8')]
            print(opener.addheaders)

        print u'GET {0}'.format(http_url)
        data = opener.open(http_url, data=http_body).read()

        try:
            result = json.loads(data, encoding='utf-8')
        except ValueError, e:
            print u'Could not load JSON: {0}'.format(e)
            return None
        return result
    except urllib2.HTTPError, e:
        print e.read()
    except urllib2.URLError, e:
        if hasattr(e, u'reason'):
            print u'Could not reach %s due to %s.' % (http_url, str(e.reason))
        elif hasattr(e, u'code'):
            print u'Could not fulfill the request due to %s.' % str(e.code)
        return None


def unix_timestamp(timestamp):
    """Convert python time object to unix timestamp"""
    return calendar.timegm(timestamp.utctimetuple())


def sap_timestamp(timestamp):
    return time.strftime('%Y.%m.%d %H:%M:%S', timestamp)


class Post(object):
    """Facebook post with metrics"""
    def __init__(self, page_name, page_id, id, message, typ, timestamp):
        self.page_name = page_name
        self.page_id = page_id
        self.id = id
        self.message = message[:200]
        self.typ = typ
        self.timestamp = timestamp
        self.metrics = {}  # Insights data

    def full_id(self):
        return '{0}_{1}'.format(self.page_id, self.id)


def create_record(post, page_likes):
    """Create DSRecord for post and add to collection"""
    rec = DataManager.NewDataRecord(1)

    # print 'Set basic fields for {0}'.format(post.id)
    rec.SetField(u'PAGE_NAME', unicode(post.page_name))
    rec.SetField(u'POST_ID', unicode(post.id))
    rec.SetField(u'TYP', unicode(post.typ))
    rec.SetField(u'TIMESTAMP', unicode(sap_timestamp(post.timestamp)))
    rec.SetField(u'POST_TEXT', post.message)
    rec.SetField(u'PAGE_FANS', unicode(page_likes))

    metrics = post.metrics
    engaged_users = metrics.get(u'post_engaged_users', 0)
    impr_organic = metrics.get(u'post_impressions_organic', 0)
    impr_organic_unique = metrics.get(u'post_impressions_organic_unique', 0)
    impr_paid = metrics.get(u'post_impressions_paid', 0)
    impr_paid_unique = metrics.get(u'post_impressions_paid_unique', 0)
    impr_viral = metrics.get(u'post_impressions_viral', 0)
    impr_viral_unique = metrics.get(u'post_impressions_viral_unique', 0)
    impr = metrics.get(u'post_impressions', 0)
    impr_unique = metrics.get(u'post_impressions_unique', 0)

    # print 'Set metrics for {0}'.format(post.id)
    rec.SetField(u'POST_ENGAGED_USERS', unicode(engaged_users))
    rec.SetField(u'POST_IMPRESSIONS_PAID', unicode(impr_paid))
    rec.SetField(u'POST_IMPRESSIONS_PAID_UNIQUE', unicode(impr_paid_unique))
    rec.SetField(u'POST_IMPRESSIONS_VIRAL', unicode(impr_viral))
    rec.SetField(u'POST_IMPRESSIONS_VIRAL_UNIQUE', unicode(impr_viral_unique))
    rec.SetField(u'POST_IMPRESSIONS', unicode(impr))
    rec.SetField(u'POST_IMPRESSIONS_UNIQUE', unicode(impr_unique))
    rec.SetField(u'POST_IMPRESSIONS_ORGANIC', unicode(impr_organic))
    rec.SetField(u'POST_IMPRESSIONS_ORGANIC_UNIQUE',
                 unicode(impr_organic_unique))

    # store record
    Collection.AddRecord(rec)
    del rec


class FacebookPage(object):
    """Collects insights about posts from a Facebook page"""
    def __init__(self, access_token, page_name, last_post_time=MIN_SINCE):
        self.access_token = access_token
        self.page_name = page_name
        self.since = unix_timestamp(last_post_time)
        self.params = {'access_token': self.access_token,
                       'limit': POST_LIMIT,
                       'since': self.since,
                       'fields': u'type,message,privacy'}
        self.post_detail_params = {'access_token': self.access_token}

    def parse_post(self, post):
        try:
            page_id, id = post[u'id'].split('_')
            message = post.get(u'message', u'')
            typ = post[u'type']
            timestamp = time.strptime(post[u'created_time'],
                                      '%Y-%m-%dT%H:%M:%S+0000')
            return Post(self.page_name, page_id, id, message, typ, timestamp)
        except Exception, ex:
            print u'Could not parse post: %s' % ex

    def add_post_metrics(self, post):
        detail_url = u'{0}/{1}/insights'.format(BASE_URL, post.full_id())
        try:
            resp = get_data(detail_url, PROXY, None, **self.post_detail_params)
            data = resp[u'data']
            post.metrics = self.extract_metrics(data)
        except Exception, e:
            print 'Could not fetch post metrics: {0}'.format(e)
        return post

    def is_irrelevant_status_post(self, post):
        return (post.typ == 'status' and
                len(post.message) == 0 and
                post.metrics.get(u'post_engaged_users', 0) == 0)

    def extract_metrics(self, insights):
        """Put metrics into dict with metric name as key"""
        def metric_value(insight):
            try:
                return insight[u'values'][0][u'value']
            except KeyError:
                print u'Metric %s does not have value' % insight[u'name']

        metrics = {}
        for insight in insights:
            metric_name = insight[u'name']
            metrics[metric_name] = metric_value(insight)
        return metrics

    def newest_posts(self):
        """Fetch newest posts from page"""
        try:
            request_url = u'{0}/{1}/posts'.format(BASE_URL, self.page_name)
            results = get_data(request_url, PROXY,
                               None, **self.params)
            data = results[u'data']
            posts = [self.parse_post(post) for post in data]
            posts = [self.add_post_metrics(post) for post in posts]
            posts = [p for p in posts if not self.is_irrelevant_status_post(p)]

            return posts
        except Exception, e:
            print u'Could not fetch posts {0}'.format(e)
            return []

    def likes(self):
        try:
            request_url = u'{0}/{1}'.format(BASE_URL, self.page_name)
            data = get_data(request_url, PROXY,
                            None, access_token=self.access_token)
            return data[u'likes']
        except Exception, e:
            print u'Could not determine likes {0}'.format(e)
            return 0


if __name__ == '__main__':
    print u'Start collecting Facebook Posts...'
    Collection.Truncate()  # clear input collection

    swisscom = FacebookPage(ACCESS_TOKEN, 'swisscom')
    swisscom_business = FacebookPage(ACCESS_TOKEN, 'Swisscom.Business')
    pages = [swisscom_business, swisscom]

    print u'Total %d tasks to search.\n' % len(pages)
    for page in pages:
        print u'Fetch newest posts for page {0}...'.format(page.page_name)
        likes = page.likes()
        newest_posts = page.newest_posts()
        for post in newest_posts:
            create_record(post, likes)
            print 'Successfully added {0} to collection'.format(post.id)
        print u'Page {0} finished. Total posts collected: {1}.'.format(
            page.page_name, len(newest_posts))
    print u'Finished collecting Facebook posts'
