# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/digipot_dialog.ui'
#
# Created by: PyQt5 UI code generator 5.15.7
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_digipot_dialog(object):
    def setupUi(self, digipot_dialog):
        digipot_dialog.setObjectName("digipot_dialog")
        digipot_dialog.resize(404, 300)
        font = QtGui.QFont()
        font.setPointSize(14)
        digipot_dialog.setFont(font)
        self.gridLayout = QtWidgets.QGridLayout(digipot_dialog)
        self.gridLayout.setObjectName("gridLayout")
        self.label_34 = QtWidgets.QLabel(digipot_dialog)
        self.label_34.setObjectName("label_34")
        self.gridLayout.addWidget(self.label_34, 0, 0, 1, 1)
        self.label_digipot_value = QtWidgets.QLabel(digipot_dialog)
        self.label_digipot_value.setObjectName("label_digipot_value")
        self.gridLayout.addWidget(self.label_digipot_value, 0, 1, 1, 1)
        self.label_36 = QtWidgets.QLabel(digipot_dialog)
        self.label_36.setObjectName("label_36")
        self.gridLayout.addWidget(self.label_36, 1, 0, 1, 1)
        self.spinBox_digipot = QtWidgets.QSpinBox(digipot_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.spinBox_digipot.sizePolicy().hasHeightForWidth())
        self.spinBox_digipot.setSizePolicy(sizePolicy)
        self.spinBox_digipot.setMaximum(256)
        self.spinBox_digipot.setObjectName("spinBox_digipot")
        self.gridLayout.addWidget(self.spinBox_digipot, 1, 1, 1, 1)
        self.pushButton_digipot_read = QtWidgets.QPushButton(digipot_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_digipot_read.sizePolicy().hasHeightForWidth())
        self.pushButton_digipot_read.setSizePolicy(sizePolicy)
        self.pushButton_digipot_read.setObjectName("pushButton_digipot_read")
        self.gridLayout.addWidget(self.pushButton_digipot_read, 2, 0, 1, 1)
        self.pushButton_digipot_write = QtWidgets.QPushButton(digipot_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_digipot_write.sizePolicy().hasHeightForWidth())
        self.pushButton_digipot_write.setSizePolicy(sizePolicy)
        self.pushButton_digipot_write.setObjectName("pushButton_digipot_write")
        self.gridLayout.addWidget(self.pushButton_digipot_write, 2, 1, 1, 1)

        self.retranslateUi(digipot_dialog)
        QtCore.QMetaObject.connectSlotsByName(digipot_dialog)

    def retranslateUi(self, digipot_dialog):
        _translate = QtCore.QCoreApplication.translate
        digipot_dialog.setWindowTitle(_translate("digipot_dialog", "BMS Digipot Control"))
        self.label_34.setText(_translate("digipot_dialog", "Current:"))
        self.label_digipot_value.setText(_translate("digipot_dialog", "N/A"))
        self.label_36.setText(_translate("digipot_dialog", "Target"))
        self.pushButton_digipot_read.setText(_translate("digipot_dialog", "Read"))
        self.pushButton_digipot_write.setText(_translate("digipot_dialog", "Write"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    digipot_dialog = QtWidgets.QWidget()
    ui = Ui_digipot_dialog()
    ui.setupUi(digipot_dialog)
    digipot_dialog.show()
    sys.exit(app.exec_())
