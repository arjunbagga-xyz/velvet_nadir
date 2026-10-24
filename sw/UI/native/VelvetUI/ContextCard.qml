import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import QtQuick.Shapes

Item {
    id: root
    width: 256
    height: contentColumn.implicitHeight + 32
    
    // Properties
    property string title: "Unnamed Context"
    property string type: "Unknown"
    property string status: "idle" // 'active', 'monitoring', 'idle'
    property bool isProject: false
    property real progress: 0 // 0 to 100
    property int agentCount: 0
    property int humanCount: 0
    property int hardwareCount: 0
    property bool selected: false
    property bool deleteSelected: false

    // Signals
    signal clicked()
    signal deleteToggled()

    // Internal state
    property bool _hovered: mouseArea.containsMouse

    z: selected ? 20 : 10

    // Scaling animation for hover
    scale: _hovered && !selected ? 1.02 : 1.0
    Behavior on scale {
        NumberAnimation { duration: 150; easing.type: Easing.OutQuad }
    }

    // Shadow background
    Rectangle {
        id: shadowRect
        anchors.fill: parent
        radius: 8
        color: "transparent"
    }

    MultiEffect {
        source: shadowRect
        anchors.fill: shadowRect
        shadowEnabled: true
        shadowColor: Qt.rgba(0, 0.831, 1.0, 0.2)
        shadowBlur: selected ? 60.0 : 30.0
        shadowOpacity: 1.0
        shadowHorizontalOffset: 0
        shadowVerticalOffset: 0
        
        Behavior on shadowBlur {
            NumberAnimation { duration: 150; easing.type: Easing.OutQuad }
        }
    }

    // Main Card
    Rectangle {
        id: cardBg
        anchors.fill: parent
        radius: 8
        color: root.selected ? "#111111" : Qt.rgba(0.059, 0.059, 0.059, 0.8)
        border.width: 1
        border.color: {
            if (root.selected) return "#00d4ff";
            if (root._hovered) return Qt.rgba(0, 0.831, 1.0, 0.3);
            return "#1a1a1a";
        }
        
        Behavior on color { ColorAnimation { duration: 150 } }
        Behavior on border.color { ColorAnimation { duration: 150 } }

        // Border top color trick
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 1
            radius: 8
            color: Qt.rgba(1, 1, 1, 0.1)
            opacity: (!root.selected && !root._hovered) ? 1.0 : 0.0
            visible: parent.border.width > 0
            z: 1
        }
        
        // Inset shadow (0 1px 0 rgba(255,255,255,0.05))
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.topMargin: 1
            height: 1
            color: Qt.rgba(1, 1, 1, 0.05)
            visible: !root.selected
            z: 1
        }
        
        ColumnLayout {
            id: contentColumn
            anchors.fill: parent
            anchors.margins: 16
            spacing: 8

            // Header
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    id: titleText
                    Layout.fillWidth: true
                    text: root.title
                    color: "white"
                    font.family: "Inter"
                    font.pixelSize: 14 // 0.875rem
                    font.weight: Font.Medium
                    elide: Text.ElideRight
                }

                // Status Dot
                Item {
                    width: 8
                    height: 8
                    Layout.alignment: Qt.AlignVCenter

                    Rectangle {
                        id: statusDot
                        anchors.centerIn: parent
                        width: 8
                        height: 8
                        radius: 4
                        color: {
                            if (root.status === "active") return "#00d4ff";
                            if (root.status === "monitoring") return "#f59e0b";
                            return "#555555";
                        }
                    }

                    // Glow and Pulse for active status
                    MultiEffect {
                        source: statusDot
                        anchors.fill: statusDot
                        shadowEnabled: root.status === "active"
                        shadowColor: "#00d4ff"
                        shadowBlur: 10
                        shadowOpacity: 0.8
                        shadowHorizontalOffset: 0
                        shadowVerticalOffset: 0
                        visible: root.status === "active"
                    }

                    SequentialAnimation {
                        running: root.status === "active"
                        loops: Animation.Infinite
                        NumberAnimation { target: statusDot; property: "opacity"; from: 1.0; to: 0.4; duration: 1000; easing.type: Easing.InOutSine }
                        NumberAnimation { target: statusDot; property: "opacity"; from: 0.4; to: 1.0; duration: 1000; easing.type: Easing.InOutSine }
                    }
                }
            }

            // Type
            Text {
                Layout.fillWidth: true
                text: root.type
                color: "#999999"
                font.family: "Inter"
                font.pixelSize: 12 // 0.75rem
                font.capitalization: Font.AllUppercase
                font.letterSpacing: 12 * 0.05
            }

            // Optional Progress Bar
            Item {
                Layout.fillWidth: true
                height: 4
                visible: root.isProject

                Rectangle {
                    anchors.fill: parent
                    color: "#000000"
                    radius: 2
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: parent.width * (root.progress / 100.0)
                    color: "#00d4ff" // accent fill
                    radius: 2
                }
            }

            // Spacer to separate meta items if needed, though spacing handles it
            Item { Layout.fillHeight: true; visible: !root.isProject; height: 8 }

            // Meta Items
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                // Agents
                RowLayout {
                    spacing: 4
                    Image {
                        source: "data:image/svg+xml;utf8,<svg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23555555' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><rect x='3' y='11' width='18' height='10' rx='2'/><circle cx='12' cy='5' r='2'/><path d='M12 7v4'/><line x1='8' y1='16' x2='8' y2='16'/><line x1='16' y1='16' x2='16' y2='16'/></svg>"
                        sourceSize: Qt.size(12, 12)
                    }
                    Text {
                        text: root.agentCount.toString()
                        color: "#555555"
                        font.family: "Inter"
                        font.pixelSize: 12
                    }
                }

                // Humans
                RowLayout {
                    spacing: 4
                    Image {
                        source: "data:image/svg+xml;utf8,<svg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23555555' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2'></path><circle cx='9' cy='7' r='4'></circle><path d='M23 21v-2a4 4 0 0 0-3-3.87'></path><path d='M16 3.13a4 4 0 0 1 0 7.75'></path></svg>"
                        sourceSize: Qt.size(12, 12)
                    }
                    Text {
                        text: root.humanCount.toString()
                        color: "#555555"
                        font.family: "Inter"
                        font.pixelSize: 12
                    }
                }

                // Hardware
                RowLayout {
                    spacing: 4
                    Image {
                        source: "data:image/svg+xml;utf8,<svg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23555555' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z'/></svg>"
                        sourceSize: Qt.size(12, 12)
                    }
                    Text {
                        text: root.hardwareCount.toString()
                        color: "#555555"
                        font.family: "Inter"
                        font.pixelSize: 12
                    }
                }
                
                Item { Layout.fillWidth: true } // push to left
            }
        }
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
