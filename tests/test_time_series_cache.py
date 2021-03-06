'''
Created on Sep 12, 2013

@author: akittredge
'''


import unittest
from financial_fundamentals.time_series_cache import FinancialDataTimeSeriesCache,\
    FinancialIntervalCache
import datetime
import pytz
import pandas as pd

from financial_fundamentals.mongo_drivers import MongoTimeseries,\
    MongoIntervalseries
from financial_fundamentals import prices
from tests.test_mongo_drivers import MongoTestCase
from tests.infrastructure import turn_on_request_caching
from financial_fundamentals.sqlite_drivers import SQLiteTimeseries
import numpy as np

class FinancialDataTimeSeriesCacheTestCase(MongoTestCase, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        turn_on_request_caching()
        
    def test_load_from_cache(self):
        cache = FinancialDataTimeSeriesCache(gets_data=None, database=None)
        test_date, test_price = datetime.datetime(2012, 12, 3, tzinfo=pytz.UTC), 100
        cache.get = lambda *args, **kwargs : [(test_date, test_price),
                                              (datetime.datetime(2012, 12, 4, tzinfo=pytz.UTC), 101),
                                              (datetime.datetime(2012, 12, 5, tzinfo=pytz.UTC), 102),
                                              ]
        symbol = 'ABC'
        df = cache.load_from_cache(start=datetime.datetime(2012, 11, 30, tzinfo=pytz.UTC),
                                   end=datetime.datetime(2013, 1, 1, tzinfo=pytz.UTC),
                                   stocks=[symbol])
        self.assertIsInstance(df, pd.DataFrame)
        self.assertIn(symbol, df.keys())
        self.assertEqual(df[symbol][test_date], test_price)
        
    def run_load_from_cache_yahoo(self, cache):
        symbol = 'GOOG'
        df = cache.load_from_cache(stocks=[symbol], 
                              start=datetime.datetime(2012, 12, 1, tzinfo=pytz.UTC), 
                              end=datetime.datetime(2012, 12, 31, tzinfo=pytz.UTC))
        self.assertEqual(df['GOOG'][datetime.datetime(2012, 12, 3, tzinfo=pytz.UTC)], 695.25)
        
        cache._get_data = None # Make sure we're using the cached value
        df = cache.load_from_cache(stocks=[symbol],
                                   start=datetime.datetime(2012, 12, 1, tzinfo=pytz.UTC),
                                   end=datetime.datetime(2012, 12, 31, tzinfo=pytz.UTC))

    def run_load_from_cache_multiple_tickers(self, cache):
        cache = FinancialDataTimeSeriesCache.build_sqlite_price_cache(sqlite_file_path=':memory:', 
                                                                      table='price', 
                                                                      metric='Adj Close')
        symbols = ['GOOG', 'AAPL']  
        df = cache.load_from_cache(stocks=symbols,
                                   start=datetime.datetime(2012, 12, 1, tzinfo=pytz.UTC), 
                                   end=datetime.datetime(2012, 12, 31, tzinfo=pytz.UTC))
        self.assertEqual(df['GOOG'][datetime.datetime(2012, 12, 3, tzinfo=pytz.UTC)], 695.25)
        self.assertEqual(df['AAPL'][datetime.datetime(2012, 12, 31, tzinfo=pytz.UTC)], 522.16)

    def test_sqlite(self):
        cache = FinancialDataTimeSeriesCache.build_sqlite_price_cache(sqlite_file_path=':memory:', 
                                                                      table='price', 
                                                                      metric='Adj Close')
        self.run_load_from_cache_yahoo(cache=cache)
        cache = FinancialDataTimeSeriesCache.build_sqlite_price_cache(sqlite_file_path=':memory:', 
                                                                       table='price', 
                                                                       metric='Adj Close')
        self.run_load_from_cache_multiple_tickers(cache=cache)
    
    def _build_mongo_cache(self):
        db_driver = MongoTimeseries(mongo_collection=self.collection, 
                                    metric='Adj Close')
        cache = FinancialDataTimeSeriesCache(gets_data=prices.get_prices_from_yahoo,
                                             database=db_driver)
        return cache
    
    def test_mongo_single(self):
        self.run_load_from_cache_yahoo(self._build_mongo_cache())
    
    def test_mongo_multiple(self):
        self.run_load_from_cache_multiple_tickers(self._build_mongo_cache())
        
    def test_indexes(self):
        cache = FinancialDataTimeSeriesCache.build_sqlite_price_cache(sqlite_file_path=':memory:', 
                                                                      table='price', 
                                                                      metric='Adj Close')
        df = cache.load_from_cache(indexes={'SPX' : '^GSPC'},
                                   start=datetime.datetime(2012, 12, 1, tzinfo=pytz.UTC),
                                   end=datetime.datetime(2012, 12, 31, tzinfo=pytz.UTC))
        self.assertEqual(df['SPX'][datetime.datetime(2012, 12, 3, tzinfo=pytz.UTC)], 1409.46)
        
    def test_nan_insertion(self):
        '''when the external data source returns a subset of the requested dates
        NaNs are inserted into the database for the dates not returned.
        '''
        connection = SQLiteTimeseries.connect(':memory:')
        driver = SQLiteTimeseries(connection=connection, 
                                  table='price', 
                                  metric='Adj Close')
        symbol = 'MSFT'
        missing_date = datetime.datetime(2012, 12, 4, tzinfo=pytz.UTC)
        missing_dates = {missing_date}
        returned_dates = {datetime.datetime(2012, 12, 1, tzinfo=pytz.UTC),
                          datetime.datetime(2012, 12, 2, tzinfo=pytz.UTC),
                          datetime.datetime(2012, 12, 3, tzinfo=pytz.UTC),
                          }
        requested_dates = missing_dates | returned_dates
        mock_yahoo = mock.Mock()
        mock_yahoo.return_value = ((date, 10.) for date in returned_dates)
        cache = FinancialDataTimeSeriesCache(gets_data=mock_yahoo, database=driver)
        cached_values = list(cache.get(symbol=symbol, dates=list(requested_dates)))
        db_val = connection.execute("SELECT value FROM price WHERE date = '{}'".format(missing_date)).next()
        self.assertEqual(db_val['value'], 'NaN')
        cache_value_dict = {date : value for date, value in cached_values}
        assert np.isnan(cache_value_dict[missing_date])

        
import mock
class FinancialDataRangesCacheTestCase(unittest.TestCase):
    def setUp(self):
        self.mock_data_getter = mock.Mock()
        self.mock_db = mock.Mock()
        self.date_range_cache = FinancialIntervalCache(get_data=self.mock_data_getter,
                                                         database=self.mock_db)
        
    def test_get_cache_hit(self):
        symbol = 'ABC'
        date = datetime.datetime(2012, 12, 1)
        value = 100.
        self.mock_db.get.return_value = value
        cache_value = self.date_range_cache.get(symbol=symbol, dates=[date]).next()
        self.assertEqual(cache_value, value)

        
    def test_cache_miss(self):
        symbol = 'ABC'
        date = datetime.datetime(2012, 12, 1)
        self.mock_db.get.return_value = None
        mock_get_set = mock.Mock()
        self.date_range_cache._get_set = mock_get_set
        self.mock_db.get.return_value = None
        self.date_range_cache.get(symbol=symbol, dates=[date]).next()
        mock_get_set.assert_called_once_with(symbol=symbol, date=date)


class MongoDataRangesIntegrationTestCase(MongoTestCase):
    metric = 'price'
    def setUp(self):
        super(MongoDataRangesIntegrationTestCase, self).setUp()
        self.mock_getter = mock.Mock()
        self.mongo_db = MongoIntervalseries(mongo_collection=self.collection,
                                            metric=self.metric)
        self.cache = FinancialIntervalCache(get_data=self.mock_getter, 
                                              database=self.mongo_db)
        
    def test_init(self):
        self.assertIs(self.cache._database, self.mongo_db)
    
    def test_set(self):
        price = 100.
        symbol = 'ABC'
        date = datetime.datetime(2012, 12, 15, tzinfo=pytz.UTC)
        range_start, range_end = datetime.datetime(2012, 12, 1), datetime.datetime(2012, 12, 31)
        self.mock_getter.return_value = (range_start,
                                         price,
                                         range_end)
        cache_price = self.cache.get(symbol=symbol, dates=[date]).next()
        self.assertEqual(cache_price, price)
        self.assertEqual(self.collection.find({'start' : range_start,
                                               'end' : range_end,
                                               'symbol' : symbol}).next()['price'], price)
        
if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(FinancialDataTimeSeriesCacheTestCase)
    unittest.TextTestRunner().run(suite)