import Quickshell
import Quickshell.Bluetooth
import Quickshell.Io
import Quickshell.Networking
import Quickshell.Services.Pipewire
import Quickshell.Services.SystemTray
import Quickshell.Services.UPower
import QtQuick

// Top edge. cosmic-session still starts cosmic-panel; the system
// entries list keeps only the dock, so this is the bar.
// This Quickshell build lists Wi-Fi only. The chip label also reads
// nmcli so a wired link still shows up.
Variants {
    component Chip: Item {
        id: chip
        property string label: ""
        property bool active: false
        signal clicked()
        signal wheelMoved(real delta)
        width: chipLabel.implicitWidth + 16
        height: 24

        Rectangle {
            anchors.fill: parent
            radius: 4
            color: chip.active ? "#2a2540" : (chipHover.containsMouse ? "#161422" : "transparent")
        }

        Text {
            id: chipLabel
            anchors.centerIn: parent
            text: chip.label
            color: "#f4f0ff"
            font.pixelSize: 13
        }

        MouseArea {
            id: chipHover
            anchors.fill: parent
            hoverEnabled: true
            onClicked: chip.clicked()
            onWheel: (wheel) => chip.wheelMoved(wheel.angleDelta.y)
        }
    }

    component MenuRow: Rectangle {
        id: row
        property string label: ""
        signal triggered()
        height: 28
        radius: 4
        color: rowHover.containsMouse ? "#2a2540" : "transparent"

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 8
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            text: row.label
            color: "#f4f0ff"
            font.pixelSize: 13
            elide: Text.ElideRight
        }

        MouseArea {
            id: rowHover
            anchors.fill: parent
            hoverEnabled: true
            onClicked: row.triggered()
        }
    }

    model: Quickshell.screens

    delegate: Component {
        PanelWindow {
            id: bar
            required property var modelData
            screen: modelData

            property string menu: ""
            property var sink: Pipewire.defaultAudioSink
            property bool soundReady: sink !== null && sink.ready && sink.audio !== null
            property var adapter: Bluetooth.defaultAdapter
            property var battery: UPower.displayDevice
            property bool batteryReady: battery !== null && battery.ready && battery.isLaptopBattery
            property string linkDump: ""

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
            readonly property string btLabel: {
                if (adapter === null || !adapter.enabled)
                    return "BT off"
                const devs = Bluetooth.devices.values
                for (let i = 0; i < devs.length; i++) {
                    if (devs[i].connected && devs[i].name)
                        return clip(devs[i].name, 14)
                }
                return "BT"
            }
            readonly property string batteryLabel: {
                if (!batteryReady)
                    return ""
                const pct = Math.round(battery.percentage * 100)
                const charging = battery.state === UPowerDeviceState.Charging
                        || battery.state === UPowerDeviceState.FullyCharged
                return charging ? pct + "%+" : pct + "%"
            }

            function clip(name, max) {
                if (!name)
                    return ""
                return name.length > max ? name.slice(0, max - 1) + "…" : name
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

            function refreshLink() {
                linkTimer.interval = 800
                if (!linkProbe.running)
                    linkTimer.restart()
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
                const edge = cluster.x + item.x + item.width
                return Math.max(8, Math.min(edge - popupWidth, width - popupWidth - 8))
            }

            anchors {
                top: true
                left: true
                right: true
            }

            implicitHeight: 36

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

            Rectangle {
                anchors.fill: parent
                color: "#0b0a12"
            }

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                text: "Borked"
                color: "#f4f0ff"
                font.pixelSize: 13
                font.weight: Font.Medium
            }

            SystemClock {
                id: clock
                precision: SystemClock.Minutes
            }

            Text {
                anchors.centerIn: parent
                text: Qt.formatDateTime(clock.date, "hh:mm")
                color: "#f4f0ff"
                font.pixelSize: 13
            }

            Row {
                id: cluster
                anchors.right: parent.right
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                Repeater {
                    model: SystemTray.items

                    Item {
                        id: trayItem
                        required property var modelData
                        width: 22
                        height: 24

                        Image {
                            anchors.centerIn: parent
                            width: 16
                            height: 16
                            visible: trayItem.modelData.icon !== ""
                            source: trayItem.modelData.icon
                            fillMode: Image.PreserveAspectFit
                            asynchronous: true
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: trayItem.modelData.icon === ""
                            text: (trayItem.modelData.title || trayItem.modelData.id || "?").slice(0, 1)
                            color: "#f4f0ff"
                            font.pixelSize: 12
                        }

                        MouseArea {
                            anchors.fill: parent
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            onClicked: (mouse) => {
                                if (mouse.button === Qt.RightButton || trayItem.modelData.onlyMenu)
                                    trayItem.modelData.display(bar, cluster.x + trayItem.x, bar.height)
                                else
                                    trayItem.modelData.activate()
                            }
                        }
                    }
                }

                Chip {
                    id: soundChip
                    label: !bar.soundReady ? "Sound" : (bar.sink.audio.muted ? "Muted" : Math.round(bar.sink.audio.volume * 100) + "%")
                    active: bar.menu === "sound"
                    onClicked: bar.menu = bar.menu === "sound" ? "" : "sound"
                    onWheelMoved: (delta) => {
                        if (!bar.soundReady)
                            return
                        bar.setVolume(bar.sink.audio.volume + (delta > 0 ? 0.05 : -0.05))
                    }
                }

                Chip {
                    id: btChip
                    label: bar.btLabel
                    active: bar.menu === "bluetooth"
                    onClicked: bar.menu = bar.menu === "bluetooth" ? "" : "bluetooth"
                }

                Chip {
                    id: netChip
                    label: bar.clip(bar.linkLabel, 16)
                    active: bar.menu === "network"
                    onClicked: bar.menu = bar.menu === "network" ? "" : "network"
                }

                Chip {
                    id: batteryChip
                    label: bar.batteryLabel
                    active: bar.menu === "battery"
                    visible: bar.batteryReady
                    onClicked: bar.menu = bar.menu === "battery" ? "" : "battery"
                }

                Chip {
                    id: agentsChip
                    label: "Agents"
                    active: bar.menu === "agents"
                    onClicked: bar.menu = bar.menu === "agents" ? "" : "agents"
                }

                Chip {
                    id: powerChip
                    label: "Power"
                    active: bar.menu === "power"
                    onClicked: bar.menu = bar.menu === "power" ? "" : "power"
                }
            }

            PopupWindow {
                id: soundPopup
                visible: bar.menu === "sound"
                implicitWidth: 260
                implicitHeight: 156
                color: "#13111d"
                anchor.window: bar
                anchor.rect.x: bar.place(soundChip, width)
                anchor.rect.y: bar.height + 6

                Column {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    Text {
                        text: "Sound"
                        color: "#f4f0ff"
                        font.pixelSize: 13
                        font.weight: Font.Medium
                    }

                    Text {
                        width: parent.width
                        text: !bar.soundReady ? "PipeWire has no default output." : (bar.sink.audio.muted ? "Muted" : Math.round(bar.sink.audio.volume * 100) + "%")
                        color: "#f4f0ff"
                        font.pixelSize: 13
                    }

                    Rectangle {
                        width: parent.width
                        height: 8
                        radius: 4
                        color: "#2a2540"
                        visible: bar.soundReady

                        Rectangle {
                            width: parent.width * (bar.soundReady && !bar.sink.audio.muted ? bar.sink.audio.volume : 0)
                            height: parent.height
                            radius: 4
                            color: "#ff3d81"
                        }

                        MouseArea {
                            anchors.fill: parent
                            anchors.margins: -8
                            onPressed: (mouse) => bar.setVolume(mouse.x / width)
                            onPositionChanged: (mouse) => {
                                if (pressed)
                                    bar.setVolume(mouse.x / width)
                            }
                        }
                    }

                    MenuRow {
                        width: parent.width
                        label: bar.soundReady && bar.sink.audio.muted ? "Unmute" : "Mute"
                        onTriggered: {
                            if (bar.soundReady)
                                bar.sink.audio.muted = !bar.sink.audio.muted
                        }
                    }

                    MenuRow {
                        width: parent.width
                        label: "Settings"
                        onTriggered: bar.openSettings()
                    }
                }
            }

            PopupWindow {
                id: btPopup
                visible: bar.menu === "bluetooth"
                implicitWidth: 280
                implicitHeight: Math.min(360, 132 + (bar.adapter !== null ? bar.adapter.devices.values.length : 0) * 28)
                color: "#13111d"
                anchor.window: bar
                anchor.rect.x: bar.place(btChip, width)
                anchor.rect.y: bar.height + 6

                Column {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 6

                    Text {
                        text: "Bluetooth"
                        color: "#f4f0ff"
                        font.pixelSize: 13
                        font.weight: Font.Medium
                    }

                    MenuRow {
                        width: parent.width
                        label: bar.adapter === null ? "No adapter" : (bar.adapter.enabled ? "Turn off" : "Turn on")
                        onTriggered: {
                            if (bar.adapter !== null)
                                bar.adapter.enabled = !bar.adapter.enabled
                        }
                    }

                    MenuRow {
                        width: parent.width
                        label: bar.adapter !== null && bar.adapter.discovering ? "Stop scanning" : "Scan"
                        onTriggered: {
                            if (bar.adapter !== null)
                                bar.adapter.discovering = !bar.adapter.discovering
                        }
                    }

                    Repeater {
                        model: bar.adapter !== null ? bar.adapter.devices : null

                        MenuRow {
                            required property var modelData
                            width: btPopup.width - 24
                            label: modelData.name + (modelData.connected ? " · on" : (modelData.paired ? "" : " · pair"))
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

                    Text {
                        visible: bar.adapter === null || bar.adapter.devices.values.length === 0
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: bar.adapter === null ? "BlueZ is asleep, or this machine has no radio." : "Nothing here. Scan looks for more."
                        color: "#f4f0ff"
                        font.pixelSize: 13
                    }

                    MenuRow {
                        width: parent.width
                        label: "Settings"
                        onTriggered: bar.openSettings()
                    }
                }
            }

            PopupWindow {
                id: netPopup
                visible: bar.menu === "network"
                implicitWidth: 280
                implicitHeight: Math.min(380, 160 + (bar.wifi !== null ? bar.wifi.networks.values.length : 0) * 28)
                color: "#13111d"
                anchor.window: bar
                anchor.rect.x: bar.place(netChip, width)
                anchor.rect.y: bar.height + 6
                onVisibleChanged: {
                    if (bar.wifi !== null)
                        bar.wifi.scannerEnabled = visible
                }

                Column {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 6

                    Text {
                        text: "Network"
                        color: "#f4f0ff"
                        font.pixelSize: 13
                        font.weight: Font.Medium
                    }

                    Text {
                        visible: bar.wiredLink !== ""
                        width: parent.width
                        elide: Text.ElideRight
                        text: "Wired · " + bar.wiredLink
                        color: "#f4f0ff"
                        font.pixelSize: 13
                    }

                    MenuRow {
                        width: parent.width
                        label: Networking.wifiEnabled ? "Turn Wi-Fi off" : "Turn Wi-Fi on"
                        onTriggered: {
                            Networking.wifiEnabled = !Networking.wifiEnabled
                            bar.refreshLink()
                        }
                    }

                    Repeater {
                        model: bar.wifi !== null ? bar.wifi.networks : null

                        MenuRow {
                            required property var modelData
                            width: netPopup.width - 24
                            label: modelData.name + (modelData.connected ? " · on" : "") + (modelData.known ? "" : " · new")
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
                        visible: bar.wifi === null || bar.wifi.networks.values.length === 0
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: bar.wifi === null ? "No Wi-Fi device. A cable can still be the network." : "No networks yet. Scanning."
                        color: "#f4f0ff"
                        font.pixelSize: 13
                    }

                    MenuRow {
                        width: parent.width
                        label: "Settings"
                        onTriggered: bar.openSettings()
                    }
                }
            }

            PopupWindow {
                id: batteryPopup
                visible: bar.menu === "battery"
                implicitWidth: 240
                implicitHeight: 96
                color: "#13111d"
                anchor.window: bar
                anchor.rect.x: bar.place(batteryChip, width)
                anchor.rect.y: bar.height + 6

                Column {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 6

                    Text {
                        text: bar.batteryReady ? bar.batteryLabel : "Battery"
                        color: "#f4f0ff"
                        font.pixelSize: 13
                        font.weight: Font.Medium
                    }

                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: {
                            if (!bar.batteryReady)
                                return "No laptop battery."
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
                        font.pixelSize: 13
                    }
                }
            }

            PopupWindow {
                id: agentsPopup
                visible: bar.menu === "agents"
                implicitWidth: 320
                implicitHeight: 148
                color: "#13111d"
                anchor.window: bar
                anchor.rect.x: bar.place(agentsChip, width)
                anchor.rect.y: bar.height + 6

                Text {
                    anchors.fill: parent
                    anchors.margins: 16
                    wrapMode: Text.WordWrap
                    text: "Agents\n\nNothing is signed in, so there is nothing to meter."
                    color: "#f4f0ff"
                    font.pixelSize: 13
                }
            }

            PopupWindow {
                id: powerPopup
                visible: bar.menu === "power"
                implicitWidth: 220
                implicitHeight: 148
                color: "#13111d"
                anchor.window: bar
                anchor.rect.x: bar.place(powerChip, width)
                anchor.rect.y: bar.height + 6

                Column {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 4

                    Text {
                        text: "Power"
                        color: "#f4f0ff"
                        font.pixelSize: 13
                        font.weight: Font.Medium
                    }

                    MenuRow {
                        width: parent.width
                        label: "Log out"
                        onTriggered: bar.runPower(["bash", "-c", "loginctl terminate-user \"$USER\""])
                    }

                    MenuRow {
                        width: parent.width
                        label: "Restart"
                        onTriggered: bar.runPower(["loginctl", "reboot"])
                    }

                    MenuRow {
                        width: parent.width
                        label: "Power off"
                        onTriggered: bar.runPower(["loginctl", "poweroff"])
                    }
                }
            }

        }
    }
}
