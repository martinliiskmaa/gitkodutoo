# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/balancing_dialog.ui'
#
# Created by: PyQt5 UI code generator 5.15.7
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_balancing_dialog(object):
    def setupUi(self, balancing_dialog):
        balancing_dialog.setObjectName("balancing_dialog")
        balancing_dialog.resize(400, 300)
        font = QtGui.QFont()
        font.setPointSize(14)
        balancing_dialog.setFont(font)
        self.gridLayout = QtWidgets.QGridLayout(balancing_dialog)
        self.gridLayout.setObjectName("gridLayout")
        self.label_27 = QtWidgets.QLabel(balancing_dialog)
        self.label_27.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_27.setObjectName("label_27")
        self.gridLayout.addWidget(self.label_27, 0, 0, 1, 1)
        self.label_balancing = QtWidgets.QLabel(balancing_dialog)
        self.label_balancing.setObjectName("label_balancing")
        self.gridLayout.addWidget(self.label_balancing, 0, 1, 1, 1)
        self.pushButton_balancing_enable = QtWidgets.QPushButton(balancing_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_balancing_enable.sizePolicy().hasHeightForWidth())
        self.pushButton_balancing_enable.setSizePolicy(sizePolicy)
        self.pushButton_balancing_enable.setObjectName("pushButton_balancing_enable")
        self.gridLayout.addWidget(self.pushButton_balancing_enable, 1, 0, 1, 1)
        self.pushButton_balancing_disable = QtWidgets.QPushButton(balancing_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_balancing_disable.sizePolicy().hasHeightForWidth())
        self.pushButton_balancing_disable.setSizePolicy(sizePolicy)
        self.pushButton_balancing_disable.setObjectName("pushButton_balancing_disable")
        self.gridLayout.addWidget(self.pushButton_balancing_disable, 1, 1, 1, 1)
        self.lineEdit_balancing_pattern = QtWidgets.QLineEdit(balancing_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lineEdit_balancing_pattern.sizePolicy().hasHeightForWidth())
        self.lineEdit_balancing_pattern.setSizePolicy(sizePolicy)
        self.lineEdit_balancing_pattern.setObjectName("lineEdit_balancing_pattern")
        self.gridLayout.addWidget(self.lineEdit_balancing_pattern, 2, 0, 1, 2)
        self.pushButton_send_pattern = QtWidgets.QPushButton(balancing_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_send_pattern.sizePolicy().hasHeightForWidth())
        self.pushButton_send_pattern.setSizePolicy(sizePolicy)
        self.pushButton_send_pattern.setObjectName("pushButton_send_pattern")
        self.gridLayout.addWidget(self.pushButton_send_pattern, 3, 0, 1, 2)

        self.retranslateUi(balancing_dialog)
        QtCore.QMetaObject.connectSlotsByName(balancing_dialog)

    def retranslateUi(self, balancing_dialog):
        _translate = QtCore.QCoreApplication.translate
        balancing_dialog.setWindowTitle(_translate("balancing_dialog", "BMS Balancing"))
        self.label_27.setText(_translate("balancing_dialog", "Balancing:"))
        self.label_balancing.setText(_translate("balancing_dialog", "N/A"))
        self.pushButton_balancing_enable.setText(_translate("balancing_dialog", "Enable"))
        self.pushButton_balancing_disable.setText(_translate("balancing_dialog", "Disable"))
        self.lineEdit_balancing_pattern.setText(_translate("balancing_dialog", "0"))
        self.pushButton_send_pattern.setText(_translate("balancing_dialog", "Send pattern"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    balancing_dialog = QtWidgets.QWidget()
    ui = Ui_balancing_dialog()
    ui.setupUi(balancing_dialog)
    balancing_dialog.show()
    sys.exit(app.exec_())
