import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Shapes 1.15

Item {
    id: root
    anchors.fill: parent

    // Properties
    property bool isOpen: false
    property string agentStatus: "Idle" // 'Idle' | 'Processing' | 'Speaking' | 'Listening'

    // Signals
    signal messageSent(string text)
    signal micToggled()
    signal closeRequested()

    // Orb Button
    Item {
        id: orbContainer
        width: 64
        height: 64
        x: 32
        y: parent.height - height - 32
        z: 50
        visible: !root.isOpen
        opacity: visible ? 1 : 0
        
        Behavior on opacity { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }

        Rectangle {
            id: orbBtn
            anchors.centerIn: parent
            width: 64
            height: 64
            radius: 32
            color: "#111111"
            border.width: 2
            border.color: {
                if (root.agentStatus === "Listening") return "#ff4444"
                return "#00d4ff"
            }

            scale: orbMouse.pressed ? 0.95 : (orbMouse.containsMouse ? 1.08 : 1.0)
            
            Behavior on scale {
                NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
            }
            Behavior on border.color {
                ColorAnimation { duration: 300 }
            }

            // Pulse animation for Speaking/Listening
            SequentialAnimation on scale {
                id: pulseAnim
                running: root.agentStatus === "Listening" || root.agentStatus === "Speaking"
                loops: Animation.Infinite
                NumberAnimation { 
                    to: 1.05 
                    duration: root.agentStatus === "Listening" ? 750 : 500
                    easing.type: Easing.InOutQuad 
                }
                NumberAnimation { 
                    to: 1.0 
                    duration: root.agentStatus === "Listening" ? 750 : 500
                    easing.type: Easing.InOutQuad 
                }
            }

            // Glow approximations
            Rectangle {
                anchors.fill: parent
                radius: 32
                color: "transparent"
                border.width: 4
                border.color: orbBtn.border.color
                opacity: orbMouse.containsMouse ? 0.3 : 0.2
                scale: 1.15
                Behavior on opacity { NumberAnimation { duration: 300 } }
            }

            Image {
                anchors.centerIn: parent
                width: 28
                height: 28
                source: "data:image/svg+xml;utf8,<svg viewBox='0 0 24 24' fill='none' stroke='" + (root.agentStatus === 'Listening' ? '%23ff4444' : '%2300d4ff') + "' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z'/><path d='M19 10v2a7 7 0 0 1-14 0v-2'/><line x1='12' x2='12' y1='19' y2='22'/></svg>"
                fillMode: Image.PreserveAspectFit
            }

            MouseArea {
                id: orbMouse
                anchors.fill: parent
                hoverEnabled: true
                onClicked: root.isOpen = true
            }
        }
    }

    // Chat Panel
    Rectangle {
        id: chatPanel
        width: 400
        height: 600
        x: 24
        y: parent.height - height - 24
        z: 50
        color: Qt.rgba(0, 0, 0, 0.95)
        radius: 12
        border.width: 1
        border.color: Qt.rgba(0, 212/255, 1, 0.3)
        clip: true

        // Simulate max-height: 85vh
        Binding on height {
            when: chatPanel.height > parent.height * 0.85
            value: parent.height * 0.85
        }

        transform: [
            Scale {
                id: chatScale
                origin.x: 0
                origin.y: chatPanel.height
                xScale: root.isOpen ? 1 : 0.95
                yScale: root.isOpen ? 1 : 0.95
                Behavior on xScale { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
                Behavior on yScale { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
            },
            Translate {
                id: chatTranslate
                y: root.isOpen ? 0 : 20
                Behavior on y { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
            }
        ]

        opacity: root.isOpen ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
        visible: opacity > 0

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // Header
            Rectangle {
                Layout.fillWidth: true
                height: 64
                color: "transparent"
                border.width: 1
                border.color: "transparent"
                
                // Bottom border
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: Qt.rgba(0, 212/255, 1, 0.3)
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 12

                    // Avatar
                    Rectangle {
                        width: 40
                        height: 40
                        radius: 20
                        color: Qt.rgba(0, 212/255, 1, 0.1) // accent-dim bg
                        
                        Image {
                            anchors.centerIn: parent
                            width: 20
                            height: 20
                            // Brain icon
                            source: "data:image/svg+xml;utf8,<svg viewBox='0 0 24 24' fill='none' stroke='%2300d4ff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z'/><path d='M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z'/></svg>"
                            fillMode: Image.PreserveAspectFit
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            text: "Velvet Agent"
                            color: "#ffffff"
                            font.family: "Inter"
                            font.pixelSize: 15
                            font.bold: true
                        }
                        Text {
                            text: root.agentStatus
                            color: root.agentStatus === "Listening" ? "#ff4444" : "#00d4ff"
                            font.family: "Inter"
                            font.pixelSize: 12
                        }
                    }

                    // Close button
                    Rectangle {
                        width: 32
                        height: 32
                        radius: 16
                        color: closeMouse.containsMouse ? Qt.rgba(1,1,1,0.1) : "transparent"
                        Image {
                            anchors.centerIn: parent
                            width: 16
                            height: 16
                            source: "data:image/svg+xml;utf8,<svg viewBox='0 0 24 24' fill='none' stroke='%23ffffff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><line x1='18' y1='6' x2='6' y2='18'/><line x1='6' y1='6' x2='18' y2='18'/></svg>"
                        }
                        MouseArea {
                            id: closeMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: {
                                root.isOpen = false
                                root.closeRequested()
                            }
                        }
                    }
                }
            }

            // Messages Area
            ListView {
                id: messagesList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 16
                topMargin: 16
                bottomMargin: 16
                
                // Mockup messages
                model: ListModel {
                    ListElement { isUser: false; text: "Hello! I'm Velvet. How can I help you today?" }
                    ListElement { isUser: true; text: "Can you analyze this project?" }
                }
                
                delegate: Item {
                    width: messagesList.width
                    height: bubble.height
                    
                    Rectangle {
                        id: bubble
                        width: Math.min(msgText.implicitWidth + 32, messagesList.width * 0.8)
                        height: msgText.implicitHeight + 24
                        radius: 12
                        
                        anchors.right: model.isUser ? parent.right : undefined
                        anchors.rightMargin: model.isUser ? 16 : 0
                        anchors.left: model.isUser ? undefined : parent.left
                        anchors.leftMargin: model.isUser ? 0 : 16

                        // User bubbles: accent bg, black text
                        // Agent bubbles: black bg, border, white text
                        color: model.isUser ? "#00d4ff" : "#0a0a0a"
                        border.width: model.isUser ? 0 : 1
                        border.color: Qt.rgba(0, 212/255, 1, 0.3)

                        Text {
                            id: msgText
                            anchors.fill: parent
                            anchors.margins: 12
                            text: model.text
                            color: model.isUser ? "#000000" : "#ffffff"
                            font.family: "Inter"
                            font.pixelSize: 13.6 // 0.85rem approx
                            wrapMode: Text.Wrap
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }

            // Input Area
            Rectangle {
                Layout.fillWidth: true
                height: 72
                color: "transparent"
                
                // Top border
                Rectangle {
                    anchors.top: parent.top
                    width: parent.width
                    height: 1
                    color: Qt.rgba(0, 212/255, 1, 0.3)
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 12

                    // Mic button
                    Rectangle {
                        width: 44
                        height: 44
                        radius: 22
                        color: root.agentStatus === "Listening" ? "#ff4444" : "#1a1a1a"
                        border.width: 1
                        border.color: root.agentStatus === "Listening" ? "#ff4444" : Qt.rgba(1,1,1,0.2)
                        
                        Image {
                            anchors.centerIn: parent
                            width: 20
                            height: 20
                            source: "data:image/svg+xml;utf8,<svg viewBox='0 0 24 24' fill='none' stroke='" + (root.agentStatus === 'Listening' ? '%23ffffff' : '%2300d4ff') + "' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z'/><path d='M19 10v2a7 7 0 0 1-14 0v-2'/><line x1='12' x2='12' y1='19' y2='22'/></svg>"
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: root.micToggled()
                        }
                    }

                    // Text Input (Pill-shaped)
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: height / 2
                        color: "#111111"
                        border.width: 1
                        border.color: Qt.rgba(1,1,1,0.2)

                        TextInput {
                            id: inputField
                            anchors.fill: parent
                            anchors.leftMargin: 16
                            anchors.rightMargin: 48
                            verticalAlignment: TextInput.AlignVCenter
                            color: "#ffffff"
                            font.family: "Inter"
                            font.pixelSize: 13.6
                            clip: true
                            onAccepted: {
                                if (text.trim() !== "") {
                                    root.messageSent(text)
                                    text = ""
                                }
                            }
                        }

                        // Send button
                        Rectangle {
                            width: 32
                            height: 32
                            radius: 16
                            anchors.right: parent.right
                            anchors.rightMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            color: inputField.text.trim() !== "" ? "#00d4ff" : "#1a1a1a"

                            Image {
                                anchors.centerIn: parent
                                width: 14
                                height: 14
                                source: "data:image/svg+xml;utf8,<svg viewBox='0 0 24 24' fill='none' stroke='" + (inputField.text.trim() !== '' ? '%23000000' : '%23888888') + "' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><line x1='22' y1='2' x2='11' y2='13'/><polygon points='22 2 15 22 11 13 2 9 22 2'/></svg>"
                                anchors.horizontalCenterOffset: -1
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    if (inputField.text.trim() !== "") {
                                        root.messageSent(inputField.text)
                                        inputField.text = ""
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
