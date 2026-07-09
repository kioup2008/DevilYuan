# -*- coding: utf-8 -*-
"""
    统一消息通知引擎
    替代旧的 Server酱 (微信) 推送
    支持：飞书 Webhook / 企业微信 Webhook / 预留扩展
"""

import requests
import json
from datetime import datetime

from DyCommon.DyCommon import *
from EventEngine.DyEvent import *
from ..DyStockTradeCommon import *


class DyStockNotifyChannel:
    """通知渠道常量"""
    FEISHU = 'feishu'
    WECHAT_WORK = 'wechat_work'
    # 预留：钉钉、Slack、邮件等


class DyStockNotifyEngine(object):
    """
        统一通知引擎
        支持飞书、企业微信机器人 Webhook 推送
    """

    # Webhook URLs - 从配置文件加载
    feishuWebhookUrl = ''
    wechatWorkWebhookUrl = ''

    def __init__(self, eventEngine, info):
        self._eventEngine = eventEngine
        self._info = info

        self._registerEvent()

    def _registerEvent(self):
        self._eventEngine.register(DyEventType.startStockCtaStrategy, self._startStockCtaStrategyHandler, DyStockTradeEventHandType.notifyEngine)
        self._eventEngine.register(DyEventType.stopStockCtaStrategy, self._stopStockCtaStrategyHandler, DyStockTradeEventHandType.notifyEngine)

        self._eventEngine.register(DyEventType.sendStockTestNotify, self._sendStockTestNotifyHandler, DyStockTradeEventHandType.notifyEngine)
        self._eventEngine.register(DyEventType.stockMarketStrengthUpdateFromUi, self._stockMarketStrengthUpdateFromUiHandler, DyStockTradeEventHandType.notifyEngine)
        self._eventEngine.register(DyEventType.stockStrategyOnOpen, self._stockStrategyOnOpenHandler, DyStockTradeEventHandType.notifyEngine)

    def _startStockCtaStrategyHandler(self, event):
        strategyCls = event.data['class']
        self._eventEngine.register(DyEventType.stockMarketMonitorUi + strategyCls.name, self._stockMarketMonitorUiHandler, DyStockTradeEventHandType.notifyEngine)

    def _stopStockCtaStrategyHandler(self, event):
        strategyCls = event.data['class']
        self._eventEngine.unregister(DyEventType.stockMarketMonitorUi + strategyCls.name, self._stockMarketMonitorUiHandler, DyStockTradeEventHandType.notifyEngine)

    # ---------- 发送实现 ----------

    def _sendFeishu(self, title, content):
        """通过飞书机器人 Webhook 发送消息"""
        if not self.feishuWebhookUrl:
            return False

        try:
            payload = {
                "msg_type": "post",
                "content": {
                    "post": {
                        "zh_cn": {
                            "title": title,
                            "content": [
                                [{"tag": "text", "text": content}]
                            ]
                        }
                    }
                }
            }
            resp = requests.post(self.feishuWebhookUrl, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as ex:
            self._info.print("飞书推送异常: {}".format(ex), DyLogData.warning)
            return False

    def _sendWechatWork(self, title, content):
        """通过企业微信机器人 Webhook 发送消息"""
        if not self.wechatWorkWebhookUrl:
            return False

        try:
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": "## {}\n{}".format(title, content)
                }
            }
            resp = requests.post(self.wechatWorkWebhookUrl, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as ex:
            self._info.print("企业微信推送异常: {}".format(ex), DyLogData.warning)
            return False

    def send(self, title, content):
        """统一发送：同时推送到所有已配置的渠道"""
        sent = False
        if self.feishuWebhookUrl:
            if self._sendFeishu(title, content):
                sent = True
        if self.wechatWorkWebhookUrl:
            if self._sendWechatWork(title, content):
                sent = True
        if not sent:
            self._info.print("通知未发送（未配置任何通知渠道）", DyLogData.warning)
        return sent

    # ---------- 消息格式化与分发 ----------

    def _formatAndSend(self, strategyCls, time, name, data, pureMsg=False):
        """格式化策略通知并发送"""
        if pureMsg:
            text = '{0}[{1}]:\n{2}-{3}'.format(strategyCls.chName, time.strftime('%H:%M:%S'), name, data)
            self.send(strategyCls.chName, text)
        else:
            newData = []
            for row in data:
                newData.append([float('%.2f' % x) if isinstance(x, float) else x for x in row])
            text = '{0}[{1}]:\n{2}-{3}'.format(strategyCls.chName, time.strftime('%H:%M:%S'), name, newData)
            self.send(strategyCls.chName, text)

    def _stockMarketMonitorUiHandler(self, event):
        strategyCls = event.data['class']
        if 'ind' in event.data:
            if 'signalDetails' in event.data['ind']:
                self._formatAndSend(strategyCls, datetime.now(), '信号明细', event.data['ind']['signalDetails'])
            if 'op' in event.data['ind']:
                self._formatAndSend(strategyCls, datetime.now(), '操作', event.data['ind']['op'])

    def _sendStockTestNotifyHandler(self, event):
        self.send('测试', event.data)

    def _stockMarketStrengthUpdateFromUiHandler(self, event):
        """处理来自于UI的市场强度更新事件（预留）"""
        pass

    def _stockStrategyOnOpenHandler(self, event):
        strategyCls = event.data['class']
        msg = event.data['msg']
        self._formatAndSend(strategyCls, datetime.now(), 'OnOpen', msg, pureMsg=True)

    def _stockStrategyOnClose(self, strategyCls, msg):
        self._formatAndSend(strategyCls, datetime.now(), 'OnClose', msg, pureMsg=True)
