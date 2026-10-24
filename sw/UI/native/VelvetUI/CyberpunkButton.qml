import QtQuick
import QtQuick.Shapes
import VelvetUI

Item {
    id: root
    width: 120
    height: 36

    property string text: "BUTTON"
    // Use the Theme singleton for styling
    property color color: Theme.c2
    property color textColor: Theme.textPrimary

    signal clicked()

    Shape {
        id: buttonShape
        anchors.fill: parent
        
        // This achieves the CSS clip-path: 
        // polygon(4px 0, 100% 0, 100% calc(100% - 4px), calc(100% - 4px) 100%, 0 100%, 0 4px)
        ShapePath {
            strokeWidth: 0
            fillColor: root.color

            startX: 4; startY: 0
            PathLine { x: root.width; y: 0 }
            PathLine { x: root.width; y: root.height - 4 }
            PathLine { x: root.width - 4; y: root.height }
            PathLine { x: 0; y: root.height }
            PathLine { x: 0; y: 4 }
            PathLine { x: 4; y: 0 }
        }
    }

    Text {
        anchors.centerIn: parent
        text: root.text
        color: root.textColor
        font.family: Theme.fontSans
        font.pixelSize: 14
        font.bold: true
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        onClicked: root.clicked()
        
        onEntered: buttonShape.opacity = 0.85
        onExited: buttonShape.opacity = 1.0
        onPressed: buttonShape.opacity = 0.6
        onReleased: buttonShape.opacity = mouseArea.containsMouse ? 0.85 : 1.0
    }
}
