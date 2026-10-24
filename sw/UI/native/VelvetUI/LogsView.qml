import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes

Item {
    id: root
    
    property alias logs: mockModel

    signal filterClicked()
    signal exportClicked()

    Item {
        id: centerContainer
        width: Math.min(1280, parent.width) // max-width: 80rem (assuming 1rem=16px)
        height: parent.height
        anchors.horizontalCenter: parent.horizontalCenter

        ColumnLayout {
            anchors.fill: parent
            anchors.bottomMargin: 96
            spacing: 0

            // Header
            RowLayout {
                Layout.fillWidth: true
                Layout.bottomMargin: 16

                Text {
                    text: "Stream Logs"
                    font.family: "Inter"
                    font.pixelSize: 24
                    font.weight: Font.Medium
                    color: "#ffffff"
                    Layout.fillWidth: true
                }

                RowLayout {
                    spacing: 8
                    
                    RemoteCtrlBtn {
                        text: "Filter"
                        onClicked: root.filterClicked()
                    }
                    RemoteCtrlBtn {
                        text: "Export"
                        onClicked: root.exportClicked()
                    }
                }
            }
            
            // Logs container
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#000000"
                border.color: "#1a1a1a"
                border.width: 1
                radius: 8

                ListView {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 4
                    clip: true

                    model: mockModel
                    
                    delegate: Rectangle {
                        id: delegateItem
                        width: ListView.view.width
                        height: rowLayout.implicitHeight + 12
                        color: ma.containsMouse ? "#111111" : "transparent"
                        radius: 4

                        Behavior on color {
                            ColorAnimation { duration: 150; easing.type: Easing.OutQuad }
                        }

                        MouseArea {
                            id: ma
                            anchors.fill: parent
                            hoverEnabled: true
                        }

                        RowLayout {
                            id: rowLayout
                            anchors.fill: parent
                            anchors.margins: 6
                            spacing: 16

                            Text {
                                text: model.time
                                font.family: "JetBrains Mono"
                                font.pixelSize: 14
                                color: root.getLogColor(model.type)
                                opacity: 0.5
                                Layout.preferredWidth: 80
                                Layout.alignment: Qt.AlignTop
                            }
                            Text {
                                text: model.source
                                font.family: "JetBrains Mono"
                                font.pixelSize: 14
                                color: root.getLogColor(model.type)
                                opacity: 0.7
                                elide: Text.ElideRight
                                Layout.preferredWidth: 128
                                Layout.alignment: Qt.AlignTop
                            }
                            Text {
                                text: model.type
                                font.family: "JetBrains Mono"
                                font.pixelSize: 14
                                font.capitalization: Font.AllUppercase
                                color: root.getLogColor(model.type)
                                opacity: 0.7
                                Layout.preferredWidth: 64
                                Layout.alignment: Qt.AlignTop
                            }
                            Text {
                                text: model.content
                                font.family: "JetBrains Mono"
                                font.pixelSize: 14
                                color: root.getLogColor(model.type)
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                                Layout.alignment: Qt.AlignTop
                            }
                        }
                    }
                }
            }
        }
    }

    function getLogColor(type) {
        if (type === "INFO") return "#999999"
        if (type === "WAKE") return "#f59e0b"
        if (type === "REASONING") return "#00d4ff"
        return "#999999"
    }

    ListModel {
        id: mockModel
        ListElement { time: "[09:14:23]"; source: "[shen.yi]"; type: "INFO"; content: "Context evaluation complete. Score: D=3 + V=4.5 + M=6 + S=2 = 15.5" }
        ListElement { time: "[09:14:25]"; source: "[agent.kira]"; type: "WAKE"; content: "Wake word detected: 'Hey Velvet'" }
        ListElement { time: "[09:14:27]"; source: "[llm.router]"; type: "REASONING"; content: "Routing to local Qwen-2.5 (load: 34%)" }
        ListElement { time: "[09:14:30]"; source: "[zenoh.fabric]"; type: "INFO"; content: "Heartbeat from 'Smart Glasses' — latency 12ms" }
        ListElement { time: "[09:14:33]"; source: "[jing.memory]"; type: "INFO"; content: "Committed 3 new episodic fragments" }
    }

    component RemoteCtrlBtn: Item {
        id: btnRoot
        property string text: "Button"
        signal clicked()
        
        implicitWidth: btnText.implicitWidth + 28
        implicitHeight: btnText.implicitHeight + 16

        Shape {
            anchors.fill: parent
            ShapePath {
                strokeWidth: 0
                fillColor: btnMa.pressed ? "#555555" : (btnMa.containsMouse ? "#4d4d4d" : "#444444")
                startX: 4; startY: 0
                PathLine { x: btnRoot.width; y: 0 }
                PathLine { x: btnRoot.width; y: btnRoot.height - 4 }
                PathLine { x: btnRoot.width - 4; y: btnRoot.height }
                PathLine { x: 0; y: btnRoot.height }
                PathLine { x: 0; y: 4 }
                PathLine { x: 4; y: 0 }
            }
            Behavior on fillColor { ColorAnimation { duration: 150 } }
        }

        Text {
            id: btnText
            anchors.centerIn: parent
            text: btnRoot.text
            color: "#ffffff"
            font.family: "Inter"
            font.pixelSize: 12
            font.weight: Font.DemiBold
            font.capitalization: Font.AllUppercase
            font.letterSpacing: 0.6 // 0.05em of 12px
        }

        MouseArea {
            id: btnMa
            anchors.fill: parent
            hoverEnabled: true
            onClicked: btnRoot.clicked()
        }
    }
}
