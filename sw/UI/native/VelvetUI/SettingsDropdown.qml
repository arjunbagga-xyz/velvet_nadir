import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtGraphicalEffects 1.15

Item {
    id: root
    width: 280
    height: dropdownBg.height

    property bool isOpen: false
    property color c1Color: "#00d4ff"
    property color c2Color: "#ff00d4"
    property color c3Color: "#d4ff00"
    property bool isLightMode: false

    signal colorChanged(string key, color value)
    signal lightModeToggled(bool enabled)

    // Animation state
    state: isOpen ? "open" : "closed"

    states: [
        State {
            name: "open"
            PropertyChanges { target: dropdownItem; opacity: 1; y: 0 }
            PropertyChanges { target: root; visible: true }
        },
        State {
            name: "closed"
            PropertyChanges { target: dropdownItem; opacity: 0; y: -8 }
            // Small delay to allow animation to finish before hiding
        }
    ]

    transitions: [
        Transition {
            from: "closed"; to: "open"
            ParallelAnimation {
                NumberAnimation { target: dropdownItem; property: "opacity"; duration: 200; easing.type: Easing.OutQuad }
                NumberAnimation { target: dropdownItem; property: "y"; duration: 200; easing.type: Easing.OutQuad }
            }
        },
        Transition {
            from: "open"; to: "closed"
            SequentialAnimation {
                ParallelAnimation {
                    NumberAnimation { target: dropdownItem; property: "opacity"; duration: 200; easing.type: Easing.InQuad }
                    NumberAnimation { target: dropdownItem; property: "y"; duration: 200; easing.type: Easing.InQuad }
                }
                PropertyAction { target: root; property: "visible"; value: false }
            }
        }
    ]

    Item {
        id: dropdownItem
        width: parent.width
        height: dropdownBg.height
        opacity: 0
        y: -8

        Rectangle {
            id: dropdownBg
            width: parent.width
            height: mainLayout.height + 40
            color: Qt.rgba(0, 0, 0, 0.92)
            border.color: "#1a1a1a"
            border.width: 1
            radius: 8

            ColumnLayout {
                id: mainLayout
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 20
                spacing: 16

                // SECTION 1: THEME COLORS
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Text {
                        text: "THEME COLORS"
                        font.family: "Inter"
                        font.pixelSize: 10
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1.0 // 0.1em approx for 10px
                        color: "#555555"
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 16

                        // C1
                        ColumnLayout {
                            spacing: 6
                            Layout.alignment: Qt.AlignHCenter

                            Rectangle {
                                id: c1Wrap
                                width: 32; height: 32; radius: 16
                                color: root.c1Color
                                border.color: c1MouseArea.containsMouse ? "#999999" : "#1a1a1a"
                                border.width: 2
                                scale: c1MouseArea.containsMouse ? 1.1 : 1.0
                                
                                Behavior on border.color { ColorAnimation { duration: 150 } }
                                Behavior on scale { NumberAnimation { duration: 150 } }

                                MouseArea {
                                    id: c1MouseArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    // Normally you'd open a ColorDialog here
                                    onClicked: root.colorChanged("c1", root.c1Color)
                                }
                            }
                            Text {
                                text: "C1"
                                font.family: "Inter"
                                font.pixelSize: 10
                                font.weight: Font.Medium
                                font.letterSpacing: 0.5 // 0.05em approx for 10px
                                color: "#999999"
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }

                        // C2
                        ColumnLayout {
                            spacing: 6
                            Layout.alignment: Qt.AlignHCenter

                            Rectangle {
                                id: c2Wrap
                                width: 32; height: 32; radius: 16
                                color: root.c2Color
                                border.color: c2MouseArea.containsMouse ? "#999999" : "#1a1a1a"
                                border.width: 2
                                scale: c2MouseArea.containsMouse ? 1.1 : 1.0
                                
                                Behavior on border.color { ColorAnimation { duration: 150 } }
                                Behavior on scale { NumberAnimation { duration: 150 } }

                                MouseArea {
                                    id: c2MouseArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: root.colorChanged("c2", root.c2Color)
                                }
                            }
                            Text {
                                text: "C2"
                                font.family: "Inter"
                                font.pixelSize: 10
                                font.weight: Font.Medium
                                font.letterSpacing: 0.5
                                color: "#999999"
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }

                        // C3
                        ColumnLayout {
                            spacing: 6
                            Layout.alignment: Qt.AlignHCenter

                            Rectangle {
                                id: c3Wrap
                                width: 32; height: 32; radius: 16
                                color: root.c3Color
                                border.color: c3MouseArea.containsMouse ? "#999999" : "#1a1a1a"
                                border.width: 2
                                scale: c3MouseArea.containsMouse ? 1.1 : 1.0
                                
                                Behavior on border.color { ColorAnimation { duration: 150 } }
                                Behavior on scale { NumberAnimation { duration: 150 } }

                                MouseArea {
                                    id: c3MouseArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: root.colorChanged("c3", root.c3Color)
                                }
                            }
                            Text {
                                text: "C3"
                                font.family: "Inter"
                                font.pixelSize: 10
                                font.weight: Font.Medium
                                font.letterSpacing: 0.5
                                color: "#999999"
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }
                }

                // SECTION 2: APPEARANCE
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Text {
                        text: "APPEARANCE"
                        font.family: "Inter"
                        font.pixelSize: 10
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1.0
                        color: "#555555"
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12

                        Text {
                            text: "Light Mode"
                            font.family: "Inter"
                            font.pixelSize: 13
                            color: "#999999"
                            Layout.fillWidth: true
                        }

                        Rectangle {
                            id: toggleTrack
                            width: 40; height: 22
                            radius: 11
                            color: root.isLightMode ? "#00d4ff" : "#111111"
                            border.color: root.isLightMode ? "#00d4ff" : "#1a1a1a"
                            border.width: 1

                            Behavior on color { ColorAnimation { duration: 150 } }
                            Behavior on border.color { ColorAnimation { duration: 150 } }

                            Rectangle {
                                id: toggleThumb
                                width: 16; height: 16
                                radius: 8
                                color: root.isLightMode ? "#ffffff" : "#555555"
                                x: root.isLightMode ? 20 : 2
                                y: 2

                                Behavior on x { NumberAnimation { duration: 150 } }
                                Behavior on color { ColorAnimation { duration: 150 } }
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    root.isLightMode = !root.isLightMode
                                    root.lightModeToggled(root.isLightMode)
                                }
                            }
                        }
                    }
                }
            }
        }
        
        DropShadow {
            anchors.fill: dropdownBg
            source: dropdownBg
            color: Qt.rgba(0, 0, 0, 0.5)
            verticalOffset: 25
            radius: 50 // Represents roughly the 50px blur in box-shadow
            samples: 101
            transparentBorder: true
            // spread is -12px in css, QML doesn't have a direct spread but radius and color adjust it.
        }
    }
}
