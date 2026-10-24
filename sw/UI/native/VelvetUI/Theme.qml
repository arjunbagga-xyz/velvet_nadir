pragma Singleton
import QtQuick

QtObject {
    // Backgrounds — Pure Black
    property color bg: "#000000"
    property color bgAlt: "#0a0a0a"
    property color surface: "#111111"
    property color surfaceHover: "#1a1a1a"

    // Text
    property color textPrimary: "#ffffff"
    property color textSecondary: "#999999"
    property color textMuted: "#555555"

    // Borders — Dark
    property color border: "#1a1a1a"
    property color borderHover: "#333333"

    // 3-Color Accent System (Dynamic System from theme.css)
    property color c1: "#00d4ff" // Primary: Cyan
    property color c2: "#444444" // Neutral: Grey
    property color c3: "#ff44aa" // Secondary: Magenta

    // Primary accent aliases (matching CSS variables)
    property color accent: c1
    property color accentDim: Qt.rgba(0, 212/255, 255/255, 0.1)
    property color accentMid: Qt.rgba(0, 212/255, 255/255, 0.3)
    property color accentGlow: Qt.rgba(0, 212/255, 255/255, 0.2)

    // Semantic
    property color warning: "#f59e0b"
    property color danger: "#ff4444"
    property color success: "#10b981"

    // Typography
    property string fontSans: "Inter"
    property string fontMono: "JetBrains Mono"

    // Radii
    property int radiusSm: 2
    property int radius: 4
    property int radiusLg: 6
    property int radiusXl: 8
    
    // Glow and Glassmorphism
    property int glowRadius: 5
    property color surfaceGlass: Qt.rgba(15/255, 15/255, 15/255, 0.8)
}
