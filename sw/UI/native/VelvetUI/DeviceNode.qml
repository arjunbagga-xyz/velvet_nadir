import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

Item {
    id: root

    property string name: "Device"
    property string status: "online" // 'online' | 'degraded' | 'offline'
    property real load: 0
    property bool selected: false
    property string iconType: "cpu" // 'cpu' | 'glasses' | 'smartphone' | 'camera' | 'server'

    signal clicked()

    width: mainLayout.implicitWidth
    height: mainLayout.implicitHeight
    z: selected ? 20 : 10

    scale: {
        if (mouseArea.pressed) return 0.95;
        if (mouseArea.containsMouse) return 1.1;
        return 1.0;
    }

    Behavior on scale {
        NumberAnimation {
            duration: 150
            easing.type: Easing.InOutQuad
        }
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    ColumnLayout {
        id: mainLayout
        anchors.centerIn: parent
        spacing: 0

        Item {
            id: iconBoxWrapper
            Layout.alignment: Qt.AlignHCenter
            width: 80
            height: 80

            // Ping ring for online devices
            Rectangle {
                id: pingRing
                anchors.fill: parent
                radius: 12
                color: "transparent"
                border.width: 1
                border.color: Qt.rgba(0, 0.831, 1.0, 0.3)
                visible: root.status === 'online'
                
                SequentialAnimation on scale {
                    running: root.status === 'online'
                    loops: Animation.Infinite
                    NumberAnimation { from: 1.0; to: 1.5; duration: 1500; easing.type: Easing.OutCubic }
                    PauseAnimation { duration: 500 }
                }
                
                SequentialAnimation on opacity {
                    running: root.status === 'online'
                    loops: Animation.Infinite
                    NumberAnimation { from: 0.5; to: 0.0; duration: 1500; easing.type: Easing.OutCubic }
                    PauseAnimation { duration: 500 }
                }
            }

            Rectangle {
                id: iconBox
                anchors.fill: parent
                radius: 12
                color: "#111111"
                border.width: 2
                border.color: (root.selected || mouseArea.containsMouse) ? "#00d4ff" : "#1a1a1a"
                
                Behavior on border.color {
                    ColorAnimation { duration: 150; easing.type: Easing.InOutQuad }
                }

                property string iconColor: (root.selected || mouseArea.containsMouse) ? "%2300d4ff" : "%23ffffff"

                function getIconPath(type) {
                    if (type === 'cpu') return '<rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>'
                    if (type === 'smartphone') return '<rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/>'
                    if (type === 'server') return '<rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/>'
                    if (type === 'camera') return '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>'
                    if (type === 'glasses') return '<circle cx="6" cy="15" r="4"/><circle cx="18" cy="15" r="4"/><path d="M14 14.5a3.5 3.5 0 0 0-4 0"/><path d="M2 15h2"/><path d="M20 15h2"/>'
                    return ''
                }

                Image {
                    anchors.centerIn: parent
                    width: 18
                    height: 18
                    source: "data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"" + parent.iconColor + "\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\">" + parent.getIconPath(root.iconType) + "</svg>"
                    sourceSize: Qt.size(18, 18)
                    
                    Behavior on source {
                        // Smoothly transition the SVG is tricky, but color will flip
                    }
                }
            }

            Rectangle {
                id: statusDot
                // absolute top: -4px, right: -4px
                x: parent.width - width + 4
                y: -4
                width: 12
                height: 12
                radius: 6
                border.width: 2
                border.color: "#111111"
                color: {
                    if (root.status === 'online') return "#00d4ff";
                    if (root.status === 'degraded') return "#f59e0b";
                    if (root.status === 'offline') return "#ff4444";
                    return "#ff4444";
                }
            }
        }

        Rectangle {
            id: labelBox
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 8
            color: Qt.rgba(0, 0, 0, 0.8)
            radius: 4
            border.width: 1
            border.color: "#1a1a1a"
            
            implicitWidth: labelLayout.implicitWidth + 16
            implicitHeight: labelLayout.implicitHeight + 8

            ColumnLayout {
                id: labelLayout
                anchors.centerIn: parent
                spacing: 2
                
                Text {
                    text: root.name
                    font.family: "Inter"
                    font.pixelSize: 12
                    font.weight: Font.Medium
                    color: "#ffffff"
                    Layout.alignment: Qt.AlignHCenter
                }
                Text {
                    text: root.load + "% LOAD"
                    font.family: "JetBrains Mono"
                    font.pixelSize: 10
                    font.capitalization: Font.AllUppercase
                    color: "#555555"
                    Layout.alignment: Qt.AlignHCenter
                }
            }
        }
    }
}
