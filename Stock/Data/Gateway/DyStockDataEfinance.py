# -*- coding: utf-8 -*-
"""
    新数据源网关：使用 efinance 库替代废弃的 TuShare 旧版 API
    依赖：pip install efinance
    特点：
      - 无需 token，完全免费
      - 支持沪深北全部 A 股（含 920xxx 北交所代码）
      - 数据源为东方财富
"""

import pandas as pd
from datetime import datetime, timedelta
from collections import OrderedDict

from DyCommon.DyCommon import *
from ...Common.DyStockCommon import DyStockCommon


class DyStockDataEfinance(object):
    """ efinance 数据接口 """

    def __init__(self, info):
        self._info = info
        self._ef = None

    def _lazy_import(self):
        """延迟导入 efinance，避免未安装时报错"""
        if self._ef is None:
            try:
                import efinance as ef
                self._ef = ef
            except ImportError:
                self._info.print("efinance 未安装，请执行: pip install efinance", DyLogData.error)
                return False
        return True

    def getStockCodes(self):
        """
            获取全量 A 股股票代码表（沪深北）
            @return: {code: name} 如 {'000001.SZ': '平安银行', '920002.BJ': '中科美菱'}
        """
        if not self._lazy_import():
            return None

        self._info.print("开始从 efinance 获取股票代码表...")

        try:
            df = self._ef.stock.get_realtime_quotes()
        except Exception as ex:
            self._info.print("从 efinance 获取股票代码表失败: {}".format(ex), DyLogData.error)
            return None

        if df is None or df.empty:
            return None

        codes = OrderedDict()
        for _, row in df.iterrows():
            code = str(row['股票代码'])
            name = row['股票名称']
            
            # 转换为 DevilYuan 格式
            if code.startswith(('920', '8')):
                # 北交所
                codes[code + '.BJ'] = name
            elif code.startswith(('6', '5')):
                # 上海主板
                codes[code + '.SH'] = name
            else:
                # 深圳主板、创业板、科创板
                codes[code + '.SZ'] = name

        self._info.print("从 efinance 获取股票代码表完成，共 {} 只".format(len(codes)))
        return codes

    def getTradeDays(self, startDate, endDate):
        """
            获取交易日数据
            @return: ['2024-01-02', '2024-01-03', ...] or None
        """
        if not self._lazy_import():
            return None

        self._info.print("开始从 efinance 获取交易日数据[{}, {}]...".format(startDate, endDate))

        try:
            # 用上证指数获取交易日历（指数每天都有数据，交易日才有行情）
            df = self._ef.stock.get_quote_history('000001', beg=startDate.replace('-', ''),
                                                    end=endDate.replace('-', ''), klt=101)
        except Exception as ex:
            self._info.print("从 efinance 获取交易日数据失败: {}".format(ex), DyLogData.error)
            return None

        if df is None or df.empty:
            # 可能没有交易日
            self._info.print("efinance 返回的交易日数据为空")
            return []

        trade_days = []
        for date_str in df['日期']:
            # 格式 YYYY-MM-DD
            trade_days.append(date_str)

        self._info.print("从 efinance 获取交易日数据完成，共 {} 个交易日".format(len(trade_days)))
        return trade_days

    def getDays(self, code, startDate, endDate, fields, name=None):
        """
            获取股票日线数据
            @code: DevilYuan 格式代码，如 '000001.SZ'
            @fields: ['open', 'high', 'low', 'close', 'volume', 'amt', 'turn', 'adjfactor']
            @return: df['datetime', indicators] or None
        """
        if not self._lazy_import():
            return None

        # 转换为 efinance 使用的纯数字代码
        raw_code = code[:6]
        exchange = code[-2:]
        
        self._info.print("从 efinance 获取 {} ({}) 日线数据[{}, {}]...".format(code, name or '', startDate, endDate))

        try:
            # klt=101 表示日K线
            df = self._ef.stock.get_quote_history(raw_code, 
                                                    beg=startDate.replace('-', ''),
                                                    end=endDate.replace('-', ''),
                                                    klt=101)
        except Exception as ex:
            self._info.print("从 efinance 获取{}({})日线数据失败: {}".format(code, name, ex), DyLogData.warning)
            return None

        if df is None or df.empty:
            self._info.print("{}({}) 日线数据为空（可能未上市或停牌）".format(code, name))
            return pd.DataFrame(columns=['datetime'] + fields)

        # 转换列名为 DevilYuan 格式
        column_map = {
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amt',
            '换手率': 'turn',
        }
        
        df.rename(columns=column_map, inplace=True)

        # 确保 datetime 列
        df.rename(columns={'日期': 'datetime'}, inplace=True)
        df['datetime'] = pd.to_datetime(df['datetime'], format='%Y-%m-%d')

        # 计算复权因子（efinance 默认返回前复权数据，所以 adjfactor=1）
        df['adjfactor'] = 1.0

        # 保留请求的字段
        available = [c for c in fields if c in df.columns]
        result = df[['datetime'] + available].copy()

        # 对缺失的字段补默认值
        for f in fields:
            if f not in result.columns:
                result[f] = 0.0 if f != 'volume' else 0

        self._info.print("{}({}) 日线数据获取完成，共 {} 条".format(code, name or '', len(result)))
        return result

    @staticmethod
    def getEfinanceCode(code):
        """
            将 DevilYuan 代码转为 efinance 纯数字代码
            如 '000001.SZ' -> '000001', '920002.BJ' -> '920002'
        """
        return code[:6]
