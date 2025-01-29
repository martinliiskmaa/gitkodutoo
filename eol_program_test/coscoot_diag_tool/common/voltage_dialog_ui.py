# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/voltage_dialog.ui'
#
# Created by: PyQt5 UI code generator 5.15.7
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_voltage_dialog(object):
    def setupUi(self, voltage_dialog):
        voltage_dialog.setObjectName("voltage_dialog")
        voltage_dialog.resize(511, 300)
        font = QtGui.QFont()
        font.setPointSize(14)
        voltage_dialog.setFont(font)
        self.gridLayout = QtWidgets.QGridLayout(voltage_dialog)
        self.gridLayout.setObjectName("gridLayout")
        self.label_31 = QtWidgets.QLabel(voltage_dialog)
        self.label_31.setObjectName("label_31")
        self.gridLayout.addWidget(self.label_31, 0, 0, 1, 1)
        self.label_32 = QtWidgets.QLabel(voltage_dialog)
        self.label_32.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_32.setObjectName("label_32")
        self.gridLayout.addWidget(self.label_32, 0, 1, 1, 1)
        self.spinBox = QtWidgets.QSpinBox(voltage_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.spinBox.sizePolicy().hasHeightForWidth())
        self.spinBox.setSizePolicy(sizePolicy)
        self.spinBox.setMinimum(4040)
        self.spinBox.setMaximum(4220)
        self.spinBox.setSingleStep(10)
        self.spinBox.setObjectName("spinBox")
        self.gridLayout.addWidget(self.spinBox, 0, 2, 1, 1)
        self.pushButton_voltage_ov_write = QtWidgets.QPushButton(voltage_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_voltage_ov_write.sizePolicy().hasHeightForWidth())
        self.pushButton_voltage_ov_write.setSizePolicy(sizePolicy)
        self.pushButton_voltage_ov_write.setObjectName("pushButton_voltage_ov_write")
        self.gridLayout.addWidget(self.pushButton_voltage_ov_write, 0, 3, 1, 1)
        self.label_39 = QtWidgets.QLabel(voltage_dialog)
        self.label_39.setObjectName("label_39")
        self.gridLayout.addWidget(self.label_39, 1, 0, 1, 1)
        self.label_40 = QtWidgets.QLabel(voltage_dialog)
        self.label_40.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_40.setObjectName("label_40")
        self.gridLayout.addWidget(self.label_40, 1, 1, 1, 1)
        self.spinBox_undevoltage = QtWidgets.QSpinBox(voltage_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.spinBox_undevoltage.sizePolicy().hasHeightForWidth())
        self.spinBox_undevoltage.setSizePolicy(sizePolicy)
        self.spinBox_undevoltage.setMinimum(2500)
        self.spinBox_undevoltage.setMaximum(3700)
        self.spinBox_undevoltage.setSingleStep(10)
        self.spinBox_undevoltage.setProperty("value", 3000)
        self.spinBox_undevoltage.setObjectName("spinBox_undevoltage")
        self.gridLayout.addWidget(self.spinBox_undevoltage, 1, 2, 1, 1)
        self.pushButton_voltage_uv_write = QtWidgets.QPushButton(voltage_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_voltage_uv_write.sizePolicy().hasHeightForWidth())
        self.pushButton_voltage_uv_write.setSizePolicy(sizePolicy)
        self.pushButton_voltage_uv_write.setObjectName("pushButton_voltage_uv_write")
        self.gridLayout.addWidget(self.pushButton_voltage_uv_write, 1, 3, 1, 1)
        self.pushButton_voltage_read = QtWidgets.QPushButton(voltage_dialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_voltage_read.sizePolicy().hasHeightForWidth())
        self.pushButton_voltage_read.setSizePolicy(sizePolicy)
        self.pushButton_voltage_read.setObjectName("pushButton_voltage_read")
        self.gridLayout.addWidget(self.pushButton_voltage_read, 2, 0, 1, 4)

        self.retranslateUi(voltage_dialog)
        QtCore.QMetaObject.connectSlotsByName(voltage_dialog)

    def retranslateUi(self, voltage_dialog):
        _translate = QtCore.QCoreApplication.translate
        voltage_dialog.setWindowTitle(_translate("voltage_dialog", "BMS Voltage Limits"))
        self.label_31.setText(_translate("voltage_dialog", "Overvoltage:"))
        self.label_32.setText(_translate("voltage_dialog", "N/A"))
        self.spinBox.setSuffix(_translate("voltage_dialog", " mV"))
        self.pushButton_voltage_ov_write.setText(_translate("voltage_dialog", "Write OV"))
        self.label_39.setText(_translate("voltage_dialog", "Undervoltage:"))
        self.label_40.setText(_translate("voltage_dialog", "N/A"))
        self.spinBox_undevoltage.setSuffix(_translate("voltage_dialog", " mV"))
        self.pushButton_voltage_uv_write.setText(_translate("voltage_dialog", "Write UV"))
        self.pushButton_voltage_read.setText(_translate("voltage_dialog", "Read"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    voltage_dialog = QtWidgets.QWidget()
    ui = Ui_voltage_dialog()
    ui.setupUi(voltage_dialog)
    voltage_dialog.show()
    sys.exit(app.exec_())
