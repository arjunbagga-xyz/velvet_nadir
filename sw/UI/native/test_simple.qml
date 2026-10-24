
import QtQuick
import VelvetUI 1.0
Item {
    width: 1280
    height: 720
    Rectangle { anchors.fill: parent; color: "black" }
    MeshConnectionRenderer {
        id: renderer
        anchors.fill: parent
        color1: "red"; color2: "green"; color3: "blue"
        Component.onCompleted: {
            renderer.setConnections([{
                sx: 100, sy: 100, ex: 500, ey: 500, type: "silk_pulse", profile: 0
            }])
        }
        Timer {
            interval: 16; running: true; repeat: true
            onTriggered: renderer.time += 16
        }
    }
}
