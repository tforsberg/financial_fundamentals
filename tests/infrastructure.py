'''
Created on Sep 4, 2013

@author: akittredge

'''

import os

def turn_on_request_caching():
    import requests_cache
    requests_cache.configure(os.path.join(os.path.expanduser('~'), 
                                          '.fundamentals_test_requests'))

TEST_DOCS_DIR = os.path.join(os.path.dirname(__file__), 'assets') 


import datetime
import numpy as np
import pytz
class IntervalseriesTestCase(object):
    metric = 'EPS'
    def test_cache_miss(self):
        symbol = 'ABC'
        date = datetime.datetime(2012, 12, 1)
        self.assertIsNone(self.cache.get(symbol, date))

    def test_cache_hit(self):
        symbol = 'ABC'
        interval_start = datetime.datetime(2012, 12, 1)
        interval_end = datetime.datetime(2012, 12, 31)
        price = 100.
        data = {'symbol' : symbol,
                'start' : interval_start,
                'end' : interval_end,
                self.metric : price}
        self.insert_into_database(data)
        date = datetime.datetime(2012, 12, 14, tzinfo=pytz.UTC)
        cache_value = self.cache.get(symbol=symbol, date=date)
        self.assertEqual(cache_value, np.float(price))

    def test_set_interval(self):
        symbol = 'ABC'
        interval_start = datetime.datetime(2012, 12, 1)
        interval_end = datetime.datetime(2012, 12, 31)
        price = 100.
        self.cache.set_interval(symbol=symbol, 
                                start=interval_start, 
                                end=interval_end, 
                                value=price)
        value = self.find_in_database(start=interval_start,
                                          end=interval_end,
                                          symbol=symbol)
        self.assertEqual(value, np.float(price))
        
    def test_no_end_interval(self):
        '''verify the behavior of intervals that do not have and end date.'''
        symbol = 'CSCO'
        interval_start = datetime.datetime(2012, 12, 1)
        interval_end = None
        eps = 6.5
        self.insert_into_database(data={'symbol' : symbol,
                                        'start' : interval_start,
                                        'end' : interval_end,
                                        self.metric : eps})
        cached_value = self.cache.get(symbol=symbol, 
                                      date=datetime.datetime(2012, 12, 2))
        self.assertEqual(cached_value, eps)
        
