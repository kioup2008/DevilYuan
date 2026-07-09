import json

from PyQt5.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QGroupBox

from DyCommon.DyCommon import DyCommon
from Stock.Common.DyStockCommon import DyStockCommon
from ..DyStockConfig import DyStockConfig


class DyStockNotifyConfigDlg(QDialog):
    """通知配置对话框（替代旧版微信 Server酱）"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._read()
        self._initUi()
        
    def _initUi(self):
        self.setWindowTitle('配置-消息通知')
        self.resize(480, 300)
 
        # 飞书 Webhook
        feishuGroup = QGroupBox('飞书机器人')
        feishuLabel = QLabel('Webhook URL:')
        self._feishuLineEdit = QLineEdit(self._data.get("feishuWebhookUrl", ""))
        feishuHint = QLabel('飞书群机器人 -> 设置 -> Webhook URL')
        feishuHint.setStyleSheet('color: gray; font-size: 10px;')

        feishuLayout = QVBoxLayout()
        feishuLayout.addWidget(feishuLabel)
        feishuLayout.addWidget(self._feishuLineEdit)
        feishuLayout.addWidget(feishuHint)
        feishuGroup.setLayout(feishuLayout)

        # 企业微信 Webhook
        wxGroup = QGroupBox('企业微信机器人')
        wxLabel = QLabel('Webhook URL:')
        self._wxLineEdit = QLineEdit(self._data.get("wechatWorkWebhookUrl", ""))
        wxHint = QLabel('企业微信群机器人 -> 添加机器人 -> Webhook URL')
        wxHint.setStyleSheet('color: gray; font-size: 10px;')

        wxLayout = QVBoxLayout()
        wxLayout.addWidget(wxLabel)
        wxLayout.addWidget(self._wxLineEdit)
        wxLayout.addWidget(wxHint)
        wxGroup.setLayout(wxLayout)

        # 按钮
        cancelPushButton = QPushButton('Cancel')
        okPushButton = QPushButton('OK')
        cancelPushButton.clicked.connect(self._cancel)
        okPushButton.clicked.connect(self._ok)

        btnLayout = QHBoxLayout()
        btnLayout.addStretch()
        btnLayout.addWidget(okPushButton)
        btnLayout.addWidget(cancelPushButton)

        # 主布局
        vbox = QVBoxLayout()
        vbox.addWidget(feishuGroup)
        vbox.addWidget(wxGroup)
        vbox.addStretch()
        vbox.addLayout(btnLayout)
 
        self.setLayout(vbox)

    def _read(self):
        file = DyStockConfig.getStockNotifyFileName()

        try:
            with open(file, encoding='utf-8') as f:
                self._data = json.load(f)
        except:
            self._data = DyStockConfig.defaultNotify

    def _ok(self):
        data = {
            "feishuWebhookUrl": self._feishuLineEdit.text().strip(),
            "wechatWorkWebhookUrl": self._wxLineEdit.text().strip()
        }

        DyStockConfig.configStockNotify(data)

        file = DyStockConfig.getStockNotifyFileName()
        with open(file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(data, indent=4, ensure_ascii=False))

        self.accept()

    def _cancel(self):
        self.reject()
