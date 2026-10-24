import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

Item {
    id: root
    width: parent ? parent.width : 800
    height: parent ? parent.height : 600
    
    // Properties
    property bool panelOpen: false
    property int unreadCount: 3
    
    // Functions
    function showToast(type, icon, title, text) {
        toastModel.insert(0, {
            "type": type,
            "iconText": icon,
            "title": title,
            "message": text,
            "timeText": "just now"
        })
        
        // Add to history too
        historyModel.insert(0, {
            "type": type,
            "iconText": icon,
            "title": title,
            "message": text,
            "timeText": "just now",
            "unread": true
        })
        unreadCount++
    }
    
    function togglePanel() {
        panelOpen = !panelOpen
    }
    
    function clearAll() {
        historyModel.clear()
        unreadCount = 0
    }
    
    ListModel {
        id: toastModel
    }
    
    ListModel {
        id: historyModel
        ListElement { type: "info"; iconText: "i"; title: "System Update"; message: "Velvet OS v2.1 is available."; timeText: "10 min ago"; unread: true }
        ListElement { type: "success"; iconText: "✓"; title: "Sync Complete"; message: "All files have been synced to the cloud."; timeText: "1 hour ago"; unread: true }
        ListElement { type: "warning"; iconText: "!"; title: "Low Disk Space"; message: "Less than 10% storage remaining."; timeText: "2 hours ago"; unread: true }
    }
    
    // Toast Container
    ListView {
        id: toastList
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: 20
        anchors.bottomMargin: 20
        width: 380
        height: root.height
        verticalLayoutDirection: ListView.BottomToTop
        spacing: 8
        interactive: false
        model: toastModel
        z: 10000
        
        delegate: Item {
            id: toastDelegate
            width: ListView.view.width
            height: toastContent.height
            
            Component.onCompleted: {
                toastTimer.start()
            }
            
            Timer {
                id: toastTimer
                interval: 5000
                onTriggered: {
                    // Safe removal by finding index of this item via title/message or we just remove from bottom 
                    // To avoid index mismatch due to dynamic removals, we can just find it:
                    for (var i = 0; i < toastModel.count; i++) {
                        if (toastModel.get(i).title === model.title && toastModel.get(i).message === model.message) {
                            toastModel.remove(i);
                            break;
                        }
                    }
                }
            }
            
            Rectangle {
                id: toastContent
                width: parent.width
                height: layout.height + 24
                color: Qt.rgba(17/255, 17/255, 17/255, 0.95)
                border.color: hoverHandler.hovered ? "#333333" : "#1a1a1a"
                border.width: 1
                radius: 10
                
                x: hoverHandler.hovered ? -4 : 0
                Behavior on x { NumberAnimation { duration: 200 } }
                
                HoverHandler { id: hoverHandler }
                
                TapHandler {
                    onTapped: {
                        for (var i = 0; i < toastModel.count; i++) {
                            if (toastModel.get(i).title === model.title && toastModel.get(i).message === model.message) {
                                toastModel.remove(i);
                                break;
                            }
                        }
                    }
                }
                
                RowLayout {
                    id: layout
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 12
                    anchors.leftMargin: 16
                    anchors.rightMargin: 16
                    spacing: 12
                    
                    Rectangle {
                        Layout.preferredWidth: 32
                        Layout.preferredHeight: 32
                        Layout.alignment: Qt.AlignTop
                        radius: 8
                        color: {
                            if (model.type === "info") return Qt.rgba(0, 212/255, 255/255, 0.1)
                            if (model.type === "success") return Qt.rgba(16/255, 185/255, 129/255, 0.1)
                            if (model.type === "warning") return Qt.rgba(245/255, 158/255, 11/255, 0.1)
                            if (model.type === "danger") return Qt.rgba(255/255, 68/255, 68/255, 0.1)
                            return "transparent"
                        }
                        
                        Text {
                            anchors.centerIn: parent
                            text: model.iconText
                            font.pixelSize: 14.4
                            font.family: "Inter"
                            color: {
                                if (model.type === "info") return "#00d4ff"
                                if (model.type === "success") return "#10b981"
                                if (model.type === "warning") return "#f59e0b"
                                if (model.type === "danger") return "#ff4444"
                                return "#ffffff"
                            }
                        }
                    }
                    
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        
                        Text {
                            text: model.title
                            font.family: "Inter"
                            font.pixelSize: 12.8
                            font.weight: Font.Medium
                            color: "#ffffff"
                        }
                        
                        Text {
                            text: model.message
                            font.family: "Inter"
                            font.pixelSize: 11.5
                            color: "#999999"
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                            lineHeight: 1.4
                        }
                        
                        Text {
                            text: model.timeText
                            font.family: "JetBrains Mono"
                            font.pixelSize: 10.4
                            color: "#555555"
                            Layout.topMargin: 2
                        }
                    }
                }
                
                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    height: 2
                    width: parent.width
                    clip: true
                    
                    Rectangle {
                        height: 2
                        width: parent.width
                        color: {
                            if (model.type === "info") return "#00d4ff"
                            if (model.type === "success") return "#10b981"
                            if (model.type === "warning") return "#f59e0b"
                            if (model.type === "danger") return "#ff4444"
                            return "#00d4ff"
                        }
                        
                        NumberAnimation on width {
                            from: toastContent.width
                            to: 0
                            duration: 5000
                        }
                    }
                }
            }
            
            // Enter animation
            NumberAnimation on opacity {
                from: 0; to: 1; duration: 400
            }
            NumberAnimation on x {
                from: 20; to: 0; duration: 400
                easing.type: Easing.OutCubic
            }
        }
    }
    
    // Notification Panel
    Item {
        id: notifPanelContainer
        width: 360
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        z: 10002
        
        transform: Translate {
            x: root.panelOpen ? 0 : notifPanelContainer.width
            Behavior on x {
                NumberAnimation {
                    duration: 350
                    easing.type: Easing.OutCubic
                }
            }
        }
        
        Rectangle {
            anchors.fill: parent
            color: Qt.rgba(10/255, 10/255, 10/255, 0.97)
            
            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: 1
                color: "#1a1a1a"
            }
            
            ColumnLayout {
                anchors.fill: parent
                spacing: 0
                
                // Header
                Rectangle {
                    Layout.fillWidth: true
                    height: 52
                    color: "transparent"
                    
                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: 1
                        color: "#1a1a1a"
                    }
                    
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        anchors.leftMargin: 20
                        anchors.rightMargin: 20
                        
                        Text {
                            text: "NOTIFICATIONS"
                            font.family: "Inter"
                            font.pixelSize: 13.6
                            font.weight: Font.Medium
                            font.letterSpacing: 13.6 * 0.08
                            color: "#ffffff"
                        }
                        
                        Item { Layout.fillWidth: true }
                        
                        Text {
                            text: "Clear all"
                            font.family: "Inter"
                            font.pixelSize: 11.2
                            color: clearHover.hovered ? "#ffffff" : "#555555"
                            
                            HoverHandler { id: clearHover }
                            TapHandler { onTapped: root.clearAll() }
                            
                            Behavior on color { ColorAnimation { duration: 150 } }
                        }
                    }
                }
                
                // List
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: historyModel
                    
                    contentItem.padding: 16
                    spacing: 4
                    
                    delegate: Rectangle {
                        width: ListView.view.width - 32
                        height: itemLayout.height + 20
                        color: itemHover.hovered ? "#111111" : "transparent"
                        border.color: itemHover.hovered ? "#1a1a1a" : "transparent"
                        border.width: 1
                        radius: 6
                        
                        HoverHandler { id: itemHover }
                        TapHandler { 
                            onTapped: {
                                if (model.unread) {
                                    model.unread = false
                                    root.unreadCount = Math.max(0, root.unreadCount - 1)
                                }
                            }
                        }
                        
                        Rectangle {
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: 2
                            color: "#00d4ff"
                            visible: model.unread
                            radius: 2
                        }
                        
                        RowLayout {
                            id: itemLayout
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 10
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            spacing: 10
                            
                            Rectangle {
                                Layout.preferredWidth: 32
                                Layout.preferredHeight: 32
                                Layout.alignment: Qt.AlignTop
                                radius: 8
                                color: {
                                    if (model.type === "info") return Qt.rgba(0, 212/255, 255/255, 0.1)
                                    if (model.type === "success") return Qt.rgba(16/255, 185/255, 129/255, 0.1)
                                    if (model.type === "warning") return Qt.rgba(245/255, 158/255, 11/255, 0.1)
                                    if (model.type === "danger") return Qt.rgba(255/255, 68/255, 68/255, 0.1)
                                    return "transparent"
                                }
                                
                                Text {
                                    anchors.centerIn: parent
                                    text: model.iconText
                                    font.pixelSize: 14.4
                                    font.family: "Inter"
                                    color: {
                                        if (model.type === "info") return "#00d4ff"
                                        if (model.type === "success") return "#10b981"
                                        if (model.type === "warning") return "#f59e0b"
                                        if (model.type === "danger") return "#ff4444"
                                        return "#ffffff"
                                    }
                                }
                            }
                            
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                
                                Text {
                                    text: model.title
                                    font.family: "Inter"
                                    font.pixelSize: 12.8
                                    font.weight: Font.Medium
                                    color: "#ffffff"
                                }
                                
                                Text {
                                    text: model.message
                                    font.family: "Inter"
                                    font.pixelSize: 11.5
                                    color: "#999999"
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                    lineHeight: 1.4
                                }
                                
                                Text {
                                    text: model.timeText
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: 10.4
                                    color: "#555555"
                                    Layout.topMargin: 2
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
