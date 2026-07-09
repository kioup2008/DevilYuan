from time import sleep
import pandas as pd
import tushare as ts
import numpy as np
from .DyStockDataEfinance import DyStockDataEfinance
import warnings

# copy from tushare
try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib3 import urlopen, Request
    pass

from pandas.compat import StringIO
from tushare.stock import cons as ct

from DyCommon.DyCommon import *
from EventEngine.DyEvent import *
from ..DyStockDataCommon import *
from .DyStockDataWind import *
from ...Common.DyStockCommon import *


class DyStockDataTicksGateway(object):
    """
        股票历史分笔数据网络接口
        分笔数据可以从新浪，腾讯，网易获取
        每个hand一个实例，这样可以防止数据互斥
    """


    def __init__(self, eventEngine, info, hand):
        self._eventEngine = eventEngine
        self._info = info
        self._hand = hand

        self._setTicksDataSource(DyStockDataCommon.defaultHistTicksDataSource)

        self._registerEvent()

    def _codeTo163Symbol(code):
        if code[:3] == '920' or code[0] == '8':
            return '0' + code
        if code[0] in ['5', '6']:
            return '0' + code

        return '1' + code

    def _getTickDataFrom163(code=None, date=None, retry_count=3, pause=0.001):
        """
            从网易获取分笔数据
            网易的分笔数据只有最近5日的
            接口和返回的DF，保持跟tushare一致
        Parameters
        ------
            code:string
                        股票代码 e.g. 600848
            date:string
                        日期 format：YYYY-MM-DD
            retry_count : int, 默认 3
                        如遇网络等问题重复执行的次数
            pause : int, 默认 0
                        重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
            return
            -------
            DataFrame 当日所有股票交易数据(DataFrame)
                    属性:成交时间、成交价格、价格变动，成交手、成交金额(元)，买卖类型
        """
        if code is None or len(code)!=6 or date is None:
            return None
        symbol = DyStockDataTicksGateway._codeTo163Symbol(code)
        yyyy, mm, dd = date.split('-')
        for _ in range(retry_count):
            sleep(pause)
            try:
                url = 'http://quotes.money.163.com/cjmx/{0}/{1}/{2}.xls'.format(yyyy, yyyy+mm+dd, symbol)
                socket = urlopen(url)
                xd = pd.ExcelFile(socket)
                df = xd.parse(xd.sheet_names[0], names=['time', 'price', 'change', 'volume', 'amount', 'type'])
                df['amount'] = df['amount'].astype('int64') # keep same as tushare
            except Exception as e:
                print(e)
                ex = e
            else:
                return df
        raise ex

    def _codeToTencentSymbol(code):
        if code[:3] == '920' or code[0] == '8':
            return 'bj' + code
        if code[0] in ['5', '6']:
            return 'sh' + code

        return 'sz' + code

    def _getTickDataFromTencent(code=None, date=None, retry_count=3, pause=0.001):
        """
            从腾讯获取分笔数据
            接口和返回的DF，保持跟tushare一致
        Parameters
        ------
            code:string
                        股票代码 e.g. 600848
            date:string
                        日期 format：YYYY-MM-DD
            retry_count : int, 默认 3
                        如遇网络等问题重复执行的次数
            pause : int, 默认 0
                        重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
            return
            -------
            DataFrame 当日所有股票交易数据(DataFrame)
                    属性:成交时间、成交价格、价格变动，成交手、成交金额(元)，买卖类型
        """
        if code is None or len(code)!=6 or date is None:
            return None
        symbol = DyStockDataTicksGateway._codeToTencentSymbol(code)
        yyyy, mm, dd = date.split('-')
        for _ in range(retry_count):
            sleep(pause)
            try:
                re = Request('http://stock.gtimg.cn/data/index.php?appn=detail&action=download&c={0}&d={1}'.format(symbol, yyyy+mm+dd))
                lines = urlopen(re, timeout=10).read()
                lines = lines.decode('GBK') 
                df = pd.read_table(StringIO(lines), names=['time', 'price', 'change', 'volume', 'amount', 'type'],
                                    skiprows=[0])      
            except Exception as e:
                print(e)
                ex = e
            else:
                return df
        raise ex

    def _codeToSinaSymbol(code):
        return DyStockDataTicksGateway._codeToTencentSymbol(code)

    def _getTickDataFromSina(code=None, date=None, retry_count=3, pause=0.001):
        """
            获取分笔数据
        Parameters
        ------
            code:string
                      股票代码 e.g. 600848
            date:string
                      日期 format：YYYY-MM-DD
            retry_count : int, 默认 3
                      如遇网络等问题重复执行的次数
            pause : int, 默认 0
                     重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
         return
         -------
            DataFrame 当日所有股票交易数据(DataFrame)
                  属性:成交时间、成交价格、价格变动，成交手、成交金额(元)，买卖类型
        """
        if code is None or len(code)!=6 or date is None:
            return None
        symbol = DyStockDataTicksGateway._codeToSinaSymbol(code)
        for _ in range(retry_count):
            sleep(pause)
            try:
                re = Request('http://market.finance.sina.com.cn/downxls.php?date={}&symbol={}'.format(date, symbol))
                lines = urlopen(re, timeout=10).read()
                lines = lines.decode('GBK') 
                if len(lines) < 20:
                    return None
                df = pd.read_table(StringIO(lines), names=['time', 'price', 'change', 'volume', 'amount', 'type'],
                                   skiprows=[0])      
            except Exception as e:
                print(e)
                ex = e
            else:
                return df
        raise ex

    def _getTicks(self, code, date):
        """
            get history ticks data from network
            @returns: None - error happened, i.e. timer out or errors from server
                             If error happened, ticks engine will retry it.
                      DyStockHistTicksAckData.noData - no data for specified date
                      BSON format data - sucessful situation
        """
        switch = False

        for i, func in enumerate(self._ticksDataSource):
            # get ticks from data source
            data = self._getTicksByFunc(func, code, date)

            # 如果数据源应该有数据却没有数据或者发生错误，则换个数据源获取
            if data == DyStockHistTicksAckData.noData or data is None:
                # fatal error from data source
                if data is None:
                    self._ticksDataSourceErrorCount[i] += 1

                    if self._ticksDataSourceErrorCount[i] >= 3:
                        switch = True
                        self._ticksDataSourceErrorCount[i] = 0

            else: # 超时或者有数据, we don't think timer out as needed to switch data source, which might happen because of network
                break

        # Too many errors happend for data source, so we think it as fatal error and then switch data source
        if switch:
            oldTicksDataSourceName = self._ticksDataSourceName

            self._ticksDataSource = self._ticksDataSource[1:] + self._ticksDataSource[0:1]
            self._ticksDataSourceName = self._ticksDataSourceName[1:] + self._ticksDataSourceName[0:1]
            self._ticksDataSourceErrorCount = self._ticksDataSourceErrorCount[1:] + self._ticksDataSourceErrorCount[0:1]

            self._info.print('Hand {}: 历史分笔数据源切换{}->{}'.format(self._hand, oldTicksDataSourceName, self._ticksDataSourceName), DyLogData.warning)

        # convert return value to retain same interface for ticks engine
        return None if data == 'timer out' else data

    def _getTicksByFunc(self, func, code, date):
        """
            @return: [{indicator: value}], i.e. MongoDB BSON format
                     None - fatal error from server
                     DyStockHistTicksAckData.noData - no data for sepcified date
                     'timer out'
        """
        try:
            df = func(code[:-3], date=date)

            del df['change']

            df = df.dropna() # sometimes Sina will give wrong data that price is NaN
            df = df[df['volume'] > 0] # !!!drop 0 volume, added 2017/05/30, sometimes Sina contains tick with 0 volume.
            df = df.drop_duplicates(['time']) # drop duplicates

            # sometimes Sina will give wrong time format like some time for 002324.SZ at 2013-03-18 is '14.06'
            while True:
                try:
                    df['time']  =  pd.to_datetime(date + ' ' + df['time'], format='%Y-%m-%d %H:%M:%S')
                except ValueError as ex:
                    strEx = str(ex)
                    errorTime = strEx[strEx.find(date) + len(date) + 1:strEx.rfind("'")]
                    df = df[~(df['time'] == errorTime)]
                    continue
                break

            df.rename(columns={'time': 'datetime'}, inplace=True)

            df = df.T
            data = [] if df.empty else list(df.to_dict().values())

        except Exception as ex:
            if '当天没有数据' in str(ex):
                return DyStockHistTicksAckData.noData
            else:
                self._info.print("Hand {}: {}获取[{}, {}]Tick数据异常: {}".format(self._hand, func.__name__, code, date, str(ex)), DyLogData.error)
                if 'timed out' in str(ex):
                    return 'timer out'
                else:
                    return None

        return data if data else DyStockHistTicksAckData.noData

    def _stockHistTicksReqHandler(self, event):
        code = event.data.code
        date = event.data.date

        data = self._getTicks(code, date)

        # put ack event
        event = DyEvent(DyEventType.stockHistTicksAck)
        event.data = DyStockHistTicksAckData(code, date, data)

        self._eventEngine.put(event)

    def _registerEvent(self):
        self._eventEngine.register(DyEventType.stockHistTicksReq + str(self._hand), self._stockHistTicksReqHandler, self._hand)
        self._eventEngine.register(DyEventType.updateHistTicksDataSource, self._updateHistTicksDataSourceHandler, self._hand)

    def _updateHistTicksDataSourceHandler(self, event):
        self._setTicksDataSource(event.data)

    def _setTicksDataSource(self, dataSource):
        if dataSource == '新浪':
            self._ticksDataSource = [self.__class__._getTickDataFromSina]
            self._ticksDataSourceName = ['新浪']
        elif dataSource == '腾讯':
            self._ticksDataSource = [self.__class__._getTickDataFromTencent]
            self._ticksDataSourceName = ['腾讯']
        else: # '智能'
            self._ticksDataSource = [self.__class__._getTickDataFromTencent, self.__class__._getTickDataFromSina]
            self._ticksDataSourceName = ['腾讯', '新浪']
            
        self._ticksDataSourceErrorCount = [0]*len(self._ticksDataSource)


class DyStockDataGateway(object):
    """
        股票数据网络接口
        日线数据从Wind获取，分笔数据可以从新浪，腾讯，网易获取
    """


    def __init__(self, eventEngine, info, registerEvent=True):
        self._eventEngine = eventEngine
        self._info = info

        if DyStockCommon.WindPyInstalled:
        # efinance 作为免费数据源，无需 token，支持沪深北
        self._efinance = DyStockDataEfinance(self._info)
            self._wind = DyStockDataWind(self._info)

        if registerEvent:
            self._registerEvent()

    def _registerEvent(self):
        """
            register events for each ticks gateway for each hand
        """
        # new DyStockDataTicksGateway instance for each ticks hand to avoid mutex
        self._ticksGateways = [DyStockDataTicksGateway(self._eventEngine, self._info, i) for i in range(DyStockDataEventHandType.stockHistTicksHandNbr)]

    def _getTradeDaysFromEfinance(self, startDate, endDate):
    def _getStockCodesFromEfinance(self):
        return self._efinance.getStockCodes()
        return self._efinance.getTradeDays(startDate, endDate)

    def getTradeDays(self, startDate, endDate):
        """
            Wind可能出现数据错误，所以需要从其他数据源做验证
        """
        # from Wind
        if 'Wind' in DyStockCommon.defaultHistDaysDataSource:
            windTradeDays = self._wind.getTradeDays(startDate, endDate)
            tradeDays = windTradeDays

        # always get from TuShare
        efinanceTradeDays = self._getTradeDaysFromEfinance(startDate, endDate)
        tradeDays = efinanceTradeDays

        # verify
        if 'Wind' in DyStockCommon.defaultHistDaysDataSource:
            if windTradeDays is None or efinanceTradeDays is None or len(windTradeDays) != len(efinanceTradeDays):
                self._info.print("Wind交易日数据跟Efinance不一致".format(windTradeDays, efinanceTradeDays), DyLogData.error)
                return None

            for x, y in zip(windTradeDays, efinanceTradeDays):
                if x != y:
                    self._info.print("Wind交易日数据跟Efinance不一致".format(windTradeDays, efinanceTradeDays), DyLogData.error)
                    return None

        return tradeDays

    def getStockCodes(self):
        """
            获取股票代码表
        """
        # from Wind
        if 'Wind' in DyStockCommon.defaultHistDaysDataSource:
            windCodes = self._wind.getStockCodes()
            codes = windCodes

        # from TuShare
        if 'TuShare' in DyStockCommon.defaultHistDaysDataSource:
            efinanceCodes = self._getStockCodesFromEfinance()
            codes = efinanceCodes

        # verify
        if 'Wind' in DyStockCommon.defaultHistDaysDataSource and 'TuShare' in DyStockCommon.defaultHistDaysDataSource:
            if windCodes is None or efinanceCodes is None or len(windCodes) != len(efinanceCodes):
                self._info.print("Wind股票代码表跟Efinance不一致", DyLogData.error)
                return None

            for code, name in windCodes.items():
                name_ = efinanceCodes.get(code)
                if name_ is None or name_ != name:
                    self._info.print("Wind股票代码表跟Efinance不一致", DyLogData.error)
                    return None

        return codes

    def getSectorStockCodes(self, sectorCode, startDate, endDate):
        return self._wind.getSectorStockCodes(sectorCode, startDate, endDate)

    def getDays(self, code, startDate, endDate, fields, name=None):
        """
            获取股票日线数据
            @return: MongoDB BSON format like [{'datetime': value, 'indicator': value}]
                     None - erros
        """
        # get from Wind
        if 'Wind' in DyStockCommon.defaultHistDaysDataSource:
            windDf = self._wind.getDays(code, startDate, endDate, fields, name)
            df = windDf

        # get from TuShare
        if 'TuShare' in DyStockCommon.defaultHistDaysDataSource:
            efinanceDf = self._getDaysFromEfinance(code, startDate, endDate, fields, name)
            df = efinanceDf

        # verify data
        if 'Wind' in DyStockCommon.defaultHistDaysDataSource and 'TuShare' in DyStockCommon.defaultHistDaysDataSource:
            if windDf is None or efinanceDf is None or windDf.shape[0] != efinanceDf.shape[0]:
                self._info.print("{}({})日线数据[{}, {}]: Wind和Efinance不相同".format(code, name, startDate, endDate), DyLogData.error)
                return None

            # remove adjfactor because Sina adjfactor is different with Wind
            fields_ = [x for x in fields if x != 'adjfactor']
            fields_ = ['datetime'] + fields_

            if (windDf[fields_].values != efinanceDf[fields_].values).sum() > 0:
                self._info.print("{}({})日线数据[{}, {}]: Wind和Efinance不相同".format(code, name, startDate, endDate), DyLogData.error)
                return None

        # BSON
        return None if df is None else list(df.T.to_dict().values())

    def isNowAfterTradingTime(self):
        today = datetime.now().strftime("%Y-%m-%d")

        for _ in range(3):
            days = self.getTradeDays(today, today)
            if days is not None:
                break

            sleep(1)
        else:
            self._info.print("@DyStockDataGateway.isNowAfterTradingTime: 获取交易日数据[{}, {}]失败3次".format(today, today), DyLogData.error)
            return None # error

        if today in days:
            year, month, day = today.split('-')
            afterTradeTime = datetime(int(year), int(month), int(day), 18, 0, 0)

            if datetime.now() < afterTradeTime:
                return False

        return True

    def _getDaysFromEfinance(self, code, startDate, endDate, fields, name=None):
        return self._efinance.getDays(code, startDate, endDate, fields, name)
