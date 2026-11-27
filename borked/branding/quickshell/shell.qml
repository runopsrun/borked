//@ pragma IconTheme Cosmic
import Quickshell
import Quickshell.Bluetooth
import Quickshell.Io
import Quickshell.Networking
import Quickshell.Services.Pipewire
import Quickshell.Services.SystemTray
import Quickshell.Services.UPower
import Quickshell.Widgets
import QtQuick

// Floating top edge. cosmic-session still starts cosmic-panel; the system
// entries list keeps only the dock. This Quickshell build lists Wi-Fi only,
// so the network icon also reads nmcli for a wired link. Without an icon
// theme Qt falls back to hicolor, and every status glyph becomes a magenta
// checkerboard. Cosmic inherits Pop and Adwaita, so the names resolve.
Variants {
    component Island: Rectangle {
        radius: 18
        color: "#f012101a"
        border.width: 1
        border.color: "#2a2540"
        height: 36
    }

    component IconButton: Item {
        id: button
        property string icon: ""
        property string fallback: ""
        property bool active: false
        signal clicked()
        signal altClicked()
        signal wheelMoved(real delta)
        width: 32
        height: 32

        Rectangle {
            anchors.fill: parent
            radius: 12
            color: button.active ? "#2a2540" : (buttonHover.containsMouse ? "#1c1928" : "transparent")
            Behavior on color { ColorAnimation { duration: 120 } }
        }

        IconImage {
            anchors.centerIn: parent
            implicitSize: 18
            source: Quickshell.iconPath(button.icon, button.fallback !== "" ? button.fallback : button.icon)
        }

        MouseArea {
            id: buttonHover
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            onClicked: (mouse) => {
                if (mouse.button === Qt.RightButton)
                    button.altClicked()
                else
                    button.clicked()
            }
            onWheel: (wheel) => button.wheelMoved(wheel.angleDelta.y)
        }
    }

    component CenterRow: Rectangle {
        id: row
        property string icon: ""
        property string fallback: ""
        property string label: ""
        property string detail: ""
        signal triggered()
        width: 300
        height: 36
        radius: 10
        color: rowHover.containsMouse ? "#1c1928" : "transparent"

        IconImage {
            anchors.left: parent.left
            anchors.leftMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            implicitSize: 16
            source: Quickshell.iconPath(row.icon, row.fallback !== "" ? row.fallback : row.icon)
        }

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 32
            anchors.right: detailText.left
            anchors.verticalCenter: parent.verticalCenter
            text: row.label
            color: "#f4f0ff"
            font.pixelSize: 13
            elide: Text.ElideRight
        }

        Text {
            id: detailText
            anchors.right: parent.right
            anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            text: row.detail
            color: "#ff3d81"
            font.pixelSize: 12
        }

        MouseArea {
            id: rowHover
            anchors.fill: parent
            hoverEnabled: true
            onClicked: row.triggered()
        }
    }

    component Action: Rectangle {
        id: action
        property string label: ""
        signal triggered()
        height: 32
        radius: 10
        color: actionHover.containsMouse ? "#2a2540" : "#1c1928"

        Text {
            anchors.centerIn: parent
            text: action.label
            color: "#f4f0ff"
            font.pixelSize: 12
        }

        MouseArea {
            id: actionHover
            anchors.fill: parent
            hoverEnabled: true
            onClicked: action.triggered()
        }
    }

    model: Quickshell.screens

    delegate: Component {
        PanelWindow {
            id: bar
            required property var modelData
            screen: modelData

            property string menu: ""
            property string section: ""
            property var sink: Pipewire.defaultAudioSink
            property bool soundReady: sink !== null && sink.ready && sink.audio !== null
            property var adapter: Bluetooth.defaultAdapter
            property var battery: UPower.displayDevice
            property bool batteryReady: battery !== null && battery.ready && battery.isLaptopBattery
            property string linkDump: ""

            readonly property real level: soundReady ? sink.audio.volume : 0
            readonly property bool muted: soundReady && sink.audio.muted
            readonly property var wifi: {
                const devs = Networking.devices.values
                for (let i = 0; i < devs.length; i++) {
                    if (devs[i].type === DeviceType.Wifi)
                        return devs[i]
                }
                return null
            }
            readonly property string wifiLink: connectedName(linkDump, "wifi")
            readonly property string wiredLink: connectedName(linkDump, "ethernet")
            readonly property string linkLabel: {
                if (wifiLink !== "")
                    return wifiLink
                if (wiredLink !== "")
                    return wiredLink
                if (!Networking.wifiEnabled)
                    return "Wi-Fi off"
                return "Offline"
            }
            readonly property string netIcon: {
                if (wiredLink !== "")
                    return "network-wired-symbolic"
                if (!Networking.wifiEnabled)
                    return "network-wireless-offline-symbolic"
                return "network-wireless-symbolic"
            }
            readonly property string soundIcon: {
                if (!soundReady || muted)
                    return "audio-volume-muted-symbolic"
                if (level < 0.33)
                    return "audio-volume-low-symbolic"
                if (level < 0.67)
                    return "audio-volume-medium-symbolic"
                return "audio-volume-high-symbolic"
            }
            readonly property string btIcon: adapter !== null && adapter.enabled ? "bluetooth-symbolic" : "bluetooth-disabled-symbolic"
            readonly property string btDetail: {
                if (adapter === null || !adapter.enabled)
                    return "Off"
                const devs = Bluetooth.devices.values
                for (let i = 0; i < devs.length; i++) {
                    if (devs[i].connected && devs[i].name)
                        return devs[i].name
                }
                return "On"
            }
            readonly property int batteryPct: batteryReady ? Math.round(battery.percentage * 100) : 0
            readonly property string batteryIcon: {
                if (batteryReady && (battery.state === UPowerDeviceState.Charging || battery.state === UPowerDeviceState.FullyCharged))
                    return "battery-good-charging-symbolic"
                if (batteryPct < 20)
                    return "battery-caution-symbolic"
                return "battery-good-symbolic"
            }

            function connectedName(dump, type) {
                const lines = dump.split("\n")
                for (let i = 0; i < lines.length; i++) {
                    const parts = lines[i].split(":")
                    if (parts.length < 3 || parts[0] !== type || parts[1] !== "connected")
                        continue
                    return parts.slice(2).join(":")
                }
                return ""
            }

            function setVolume(value) {
                if (!soundReady)
                    return
                sink.audio.muted = false
                sink.audio.volume = Math.max(0, Math.min(1, value))
            }

            function toggleMute() {
                if (soundReady)
                    sink.audio.muted = !sink.audio.muted
            }

            function refreshLink() {
                linkTimer.interval = 800
                if (!linkProbe.running)
                    linkTimer.restart()
            }

            function openCenter(name) {
                if (menu === "center" && section === name) {
                    menu = ""
                    syncScan()
                    return
                }
                section = name
                menu = "center"
                syncScan()
            }

            function syncScan() {
                if (wifi !== null)
                    wifi.scannerEnabled = menu === "center" && section === "network"
            }

            function openSettings() {
                Quickshell.execDetached(["cosmic-settings"])
                menu = ""
            }

            function runPower(args) {
                Quickshell.execDetached(args)
                menu = ""
            }

            function place(item, popupWidth) {
                const edge = item.x + item.width
                return Math.max(12, Math.min(edge - popupWidth, width - popupWidth - 12))
            }

            anchors {
                top: true
                left: true
                right: true
            }

            margins.top: 10
            margins.left: 14
            margins.right: 14
            implicitHeight: 40
            exclusiveZone: margins.top + implicitHeight
            color: "transparent"

            PwObjectTracker {
                objects: bar.sink !== null ? [bar.sink] : []
            }

            Process {
                id: linkProbe
                command: ["nmcli", "-t", "-f", "TYPE,STATE,CONNECTION", "device"]
                running: true
                stdout: StdioCollector {
                    onStreamFinished: bar.linkDump = text
                }
                onRunningChanged: {
                    if (!running)
                        linkTimer.start()
                }
            }

            Timer {
                id: linkTimer
                interval: 4000
                onTriggered: {
                    interval = 4000
                    linkProbe.running = true
                }
            }

            Island {
                id: brand
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                width: brandRow.implicitWidth + 22

                Row {
                    id: brandRow
                    anchors.centerIn: parent
                    spacing: 8

                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 8
                        height: 8
                        radius: 2
                        color: "#ff3d81"
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Borked"
                        color: "#f4f0ff"
                        font.pixelSize: 13
                        font.weight: Font.Medium
                    }
                }
            }

            Island {
                id: clockIsland
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.verticalCenter: parent.verticalCenter
                width: clockText.implicitWidth + 28

                SystemClock {
                    id: clock
                    precision: SystemClock.Minutes
                }

                Text {
                    id: clockText
                    anchors.centerIn: parent
                    text: Qt.formatDateTime(clock.date, "ddd  HH:mm")
                    color: "#f4f0ff"
                    font.pixelSize: 13
                }
            }

            Island {
                id: status
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: statusRow.implicitWidth + 6

                Row {
                    id: statusRow
                    anchors.centerIn: parent
                    spacing: 0

                    Repeater {
                        model: SystemTray.items

                        Item {
                            id: trayItem
                            required property var modelData
                            width: 28
                            height: 32

                            IconImage {
                                anchors.centerIn: parent
                                implicitSize: 16
                                visible: trayItem.modelData.icon !== ""
                                source: trayItem.modelData.icon
                            }

                            Text {
                                anchors.centerIn: parent
                                visible: trayItem.modelData.icon === ""
                                text: (trayItem.modelData.title || trayItem.modelData.id || "?").slice(0, 1)
                                color: "#f4f0ff"
                                font.pixelSize: 11
                            }

                            MouseArea {
                                anchors.fill: parent
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                onClicked: (mouse) => {
                                    if (mouse.button === Qt.RightButton || trayItem.modelData.onlyMenu)
                                        trayItem.modelData.display(bar, status.x + trayItem.x, bar.height)
                                    else
                                        trayItem.modelData.activate()
                                }
                            }
                        }
                    }

                    IconButton {
                        icon: bar.soundIcon
                        fallback: "audio-volume-high-symbolic"
                        active: bar.menu === "center" && bar.section === "sound"
                        onClicked: bar.openCenter("sound")
                        onAltClicked: bar.toggleMute()
                        onWheelMoved: (delta) => {
                            if (bar.soundReady)
                                bar.setVolume(bar.level + (delta > 0 ? 0.05 : -0.05))
                        }
                    }

                    IconButton {
                        icon: bar.btIcon
                        fallback: "bluetooth-symbolic"
                        active: bar.menu === "center" && bar.section === "bluetooth"
                        onClicked: bar.openCenter("bluetooth")
                    }

                    IconButton {
                        icon: bar.netIcon
                        fallback: "network-wireless-symbolic"
                        active: bar.menu === "center" && bar.section === "network"
                        onClicked: bar.openCenter("network")
                    }

                    IconButton {
                        visible: bar.batteryReady
                        width: visible ? 32 : 0
                        icon: bar.batteryIcon
                        fallback: "battery-symbolic"
                        active: bar.menu === "center" && bar.section === "battery"
                        onClicked: bar.openCenter("battery")
                    }

                    IconButton {
                        icon: "starred-symbolic"
                        fallback: "emblem-favorite-symbolic"
                        active: bar.menu === "agents"
                        onClicked: bar.menu = bar.menu === "agents" ? "" : "agents"
                    }

                    IconButton {
                        icon: "system-shutdown-symbolic"
                        fallback: "system-shutdown"
                        active: bar.menu === "center" && bar.section === "power"
                        onClicked: bar.openCenter("power")
                    }
                }
            }

            PopupWindow {
                id: center
                visible: bar.menu === "center"
                implicitWidth: 324
                implicitHeight: centerCard.implicitHeight
                color: "transparent"
                anchor.window: bar
                anchor.rect.x: bar.place(status, implicitWidth)
                anchor.rect.y: bar.height + 8

                Rectangle {
                    id: centerCard
                    width: 324
                    implicitHeight: centerCol.implicitHeight + 20
                    radius: 18
                    color: "#f012101a"
                    border.width: 1
                    border.color: "#2a2540"

                    Column {
                        id: centerCol
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 10
                        spacing: 4

                        Text {
                            text: "Controls"
                            color: "#f4f0ff"
                            font.pixelSize: 13
                            font.weight: Font.Medium
                            leftPadding: 8
                            bottomPadding: 4
                        }

                        CenterRow {
                            icon: bar.soundIcon
                            fallback: "audio-volume-high-symbolic"
                            label: bar.soundReady ? (bar.muted ? "Muted" : "Sound") : "No output"
                            detail: bar.soundReady && !bar.muted ? Math.round(bar.level * 100) + "%" : ""
                            onTriggered: bar.section = "sound"
                        }

                        Item {
                            width: parent.width
                            height: 22
                            visible: bar.soundReady

                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                height: 6
                                radius: 3
                                color: "#2a2540"

                                Rectangle {
                                    width: Math.max(6, parent.width * (bar.muted ? 0 : bar.level))
                                    height: parent.height
                                    radius: 3
                                    color: "#ff3d81"
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                onPressed: (mouse) => bar.setVolume((mouse.x - 12) / (width - 24))
                                onPositionChanged: (mouse) => {
                                    if (pressed)
                                        bar.setVolume((mouse.x - 12) / (width - 24))
                                }
                            }
                        }

                        CenterRow {
                            icon: "audio-volume-muted-symbolic"
                            fallback: "audio-volume-muted"
                            label: bar.muted ? "Unmute" : "Mute"
                            onTriggered: bar.toggleMute()
                        }

                        CenterRow {
                            icon: bar.netIcon
                            fallback: "network-wireless-symbolic"
                            label: bar.linkLabel
                            detail: bar.section === "network" ? "" : (bar.wiredLink !== "" ? "Wired" : "")
                            onTriggered: bar.openCenter("network")
                        }

                        Column {
                            width: parent.width
                            visible: bar.section === "network"
                            spacing: 2

                            CenterRow {
                                label: Networking.wifiEnabled ? "Turn Wi-Fi off" : "Turn Wi-Fi on"
                                icon: "network-wireless-symbolic"
                                fallback: "network-wireless"
                                onTriggered: {
                                    Networking.wifiEnabled = !Networking.wifiEnabled
                                    bar.refreshLink()
                                }
                            }

                            Text {
                                visible: bar.wiredLink !== ""
                                leftPadding: 12
                                text: "Wired · " + bar.wiredLink
                                color: "#f4f0ff"
                                font.pixelSize: 12
                            }

                            Repeater {
                                model: bar.wifi !== null ? bar.wifi.networks : null

                                CenterRow {
                                    required property var modelData
                                    icon: "network-wireless-symbolic"
                                    fallback: "network-wireless"
                                    label: modelData.name
                                    detail: modelData.connected ? "On" : (modelData.known ? "" : "New")
                                    onTriggered: {
                                        if (modelData.connected)
                                            modelData.disconnect()
                                        else
                                            modelData.connect()
                                        bar.refreshLink()
                                    }
                                }
                            }

                            Text {
                                visible: bar.wifi === null
                                leftPadding: 12
                                rightPadding: 12
                                width: parent.width
                                wrapMode: Text.WordWrap
                                text: "No Wi-Fi device. A cable can still be the network."
                                color: "#f4f0ff"
                                font.pixelSize: 12
                            }
                        }

                        CenterRow {
                            icon: bar.btIcon
                            fallback: "bluetooth-symbolic"
                            label: "Bluetooth"
                            detail: bar.btDetail
                            onTriggered: bar.openCenter("bluetooth")
                        }

                        Column {
                            width: parent.width
                            visible: bar.section === "bluetooth"
                            spacing: 2

                            CenterRow {
                                icon: bar.btIcon
                                fallback: "bluetooth-symbolic"
                                label: bar.adapter === null ? "No adapter" : (bar.adapter.enabled ? "Turn off" : "Turn on")
                                onTriggered: {
                                    if (bar.adapter !== null)
                                        bar.adapter.enabled = !bar.adapter.enabled
                                }
                            }

                            CenterRow {
                                icon: "bluetooth-symbolic"
                                fallback: "bluetooth"
                                label: bar.adapter !== null && bar.adapter.discovering ? "Stop scanning" : "Scan"
                                onTriggered: {
                                    if (bar.adapter !== null)
                                        bar.adapter.discovering = !bar.adapter.discovering
                                }
                            }

                            Repeater {
                                model: bar.adapter !== null ? bar.adapter.devices : null

                                CenterRow {
                                    required property var modelData
                                    icon: "bluetooth-symbolic"
                                    fallback: "bluetooth"
                                    label: modelData.name
                                    detail: modelData.connected ? "On" : (modelData.paired ? "" : "Pair")
                                    onTriggered: {
                                        if (!modelData.paired)
                                            modelData.pair()
                                        else if (modelData.connected)
                                            modelData.disconnect()
                                        else
                                            modelData.connect()
                                    }
                                }
                            }
                        }

                        CenterRow {
                            visible: bar.batteryReady
                            height: visible ? 36 : 0
                            icon: bar.batteryIcon
                            fallback: "battery-symbolic"
                            label: "Battery"
                            detail: bar.batteryPct + "%"
                            onTriggered: bar.openCenter("battery")
                        }

                        Text {
                            visible: bar.section === "battery" && bar.batteryReady
                            leftPadding: 12
                            text: {
                                const state = UPowerDeviceState.toString(bar.battery.state)
                                const seconds = bar.battery.state === UPowerDeviceState.Charging ? bar.battery.timeToFull : bar.battery.timeToEmpty
                                if (!seconds || seconds <= 0)
                                    return state
                                const hours = Math.floor(seconds / 3600)
                                const minutes = Math.floor((seconds % 3600) / 60)
                                const left = hours > 0 ? hours + "h " + minutes + "m" : minutes + "m"
                                return state + " · " + left
                            }
                            color: "#f4f0ff"
                            font.pixelSize: 12
                        }

                        Row {
                            width: parent.width
                            spacing: 6
                            leftPadding: 4
                            rightPadding: 4
                            topPadding: 6

                            Action {
                                width: (parent.width - 20) / 3
                                label: "Log out"
                                onTriggered: bar.runPower(["bash", "-c", "loginctl terminate-user \"$USER\""])
                            }

                            Action {
                                width: (parent.width - 20) / 3
                                label: "Restart"
                                onTriggered: bar.runPower(["loginctl", "reboot"])
                            }

                            Action {
                                width: (parent.width - 20) / 3
                                label: "Power off"
                                onTriggered: bar.runPower(["loginctl", "poweroff"])
                            }
                        }

                        CenterRow {
                            icon: "preferences-system-symbolic"
                            fallback: "preferences-system"
                            label: "Settings"
                            onTriggered: bar.openSettings()
                        }
                    }
                }
            }

            PopupWindow {
                id: agentsPopup
                visible: bar.menu === "agents"
                implicitWidth: 300
                implicitHeight: 132
                color: "transparent"
                anchor.window: bar
                anchor.rect.x: bar.place(status, implicitWidth)
                anchor.rect.y: bar.height + 8

                Rectangle {
                    anchors.fill: parent
                    radius: 18
                    color: "#f012101a"
                    border.width: 1
                    border.color: "#2a2540"

                    Text {
                        anchors.fill: parent
                        anchors.margins: 16
                        wrapMode: Text.WordWrap
                        text: "Agents\n\nNothing is signed in, so there is nothing to meter."
                        color: "#f4f0ff"
                        font.pixelSize: 13
                    }
                }
            }
        }
    }
}
