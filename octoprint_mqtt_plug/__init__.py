# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import concurrent.futures
import json
import math
import threading
import time
import uuid

import flask
import octoprint.plugin
from flask_babel import gettext
from octoprint.access import ADMIN_GROUP

from octoprint_mqtt_plug.device import Device

class MqttPlugPlugin(
    octoprint.plugin.EventHandlerPlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.WizardPlugin,
    octoprint.plugin.BlueprintPlugin):
    shutdownAt = dict()
    stopTimer = dict()
    stopCooldown = dict()
    pool = concurrent.futures.ThreadPoolExecutor()
    baseTopic = None

    devices: [Device] = []

    def __init__(self):
        super().__init__()
        self.mqtt_publish = lambda *args, **kwargs: None
        self.mqtt_subscribe = lambda *args, **kwargs: None
        self.mqtt_unsubscribe = lambda *args, **kwargs: None

    def write_devices_in_settings(self):
        devices = self.get_serialized_devices()
        self._settings.set(['devices'], devices)

    def get_serialized_devices(self):
        settingsDevices = []
        for dev in self.devices:
            if dev.id is not None:
                settingsDevices.append(dev.serialize())

        return settingsDevices

    def save_settings(self):

        self.write_devices_in_settings()

        self._settings.save()
        self._logger.debug('Settings saved')

    def on_after_startup(self):

        helpers = self._plugin_manager.get_helpers("mqtt", "mqtt_publish", "mqtt_subscribe", "mqtt_unsubscribe")
        if helpers:
            if 'mqtt_publish' in helpers:
                self.mqtt_publish = helpers['mqtt_publish']
            if 'mqtt_subscribe' in helpers:
                self.mqtt_subscribe = helpers['mqtt_subscribe']
            if 'mqtt_unsubscribe' in helpers:
                self.mqtt_unsubscribe = helpers['mqtt_unsubscribe']

            if 'mqtt' in self._plugin_manager.enabled_plugins:
                mqttPlugin = self._plugin_manager.plugins['mqtt'].implementation
                if mqttPlugin:
                    self.baseTopic = mqttPlugin._settings.get(['publish', 'baseTopic'])

        if self.baseTopic:
            self._logger.info('Enable MQTT')
            self.mqtt_subscribe('%s%s' % (self.baseTopic, 'plugin/mqtt_plug/#'), self.on_mqtt_sub)

        self.devices = []

        settingsDevices = self._settings.get(['devices'])
        if settingsDevices is not None:
            for settingsDev in settingsDevices:
                dev = Device(settingsDev)
                self.devices.append(dev)
                self.mqtt_register_device_state(dev)

        self.getStateData()

    def on_mqtt_sub(self, topic, message, retain=None, qos=None, *args, **kwargs):
        self._logger.debug("Receive mqtt message %s" % (topic))

        if type(message) == bytes:
            message = message.decode()

        if self.baseTopic is None:
            if topic == '%s%s%s' % (self.baseTopic, 'plugin/mqtt_plug/', 'turnOn'):
                self._logger.info('MQTT request turn on : %s', message)
                payload = json.loads(message)
                if 'id' in payload:
                    dev = self.getDeviceFromId(payload['id'])
                    if dev is not None:
                        self._logger.info('MQTT turn on : %s', dev['name'])
                        self.turnOn(dev)

            elif topic == '%s%s%s' % (self.baseTopic, 'plugin/mqtt_plug/', 'turnOff'):
                self._logger.info('MQTT request turn off : %s', message)
                payload = json.loads(message)
                if 'id' in payload:
                    dev = self.getDeviceFromId(payload['id'])
                    if dev is not None:
                        self._logger.info('MQTT turn off : %s', dev['name'])
                        self.turnOff(dev)
            elif topic == '%s%s%s' % (self.baseTopic, 'plugin/mqtt_plug/', 'state'):
                self.getStateData()

        stateChanged = False

        for dev in self.devices:
            if dev.stateTopic == topic:
                if len(message) and message[0] == '{':
                    data = json.loads(message)
                    if 'state' in data:
                        dev.state = data['state'] == dev.onValue
                        stateChanged = True
                else:
                    dev.state = dev.onValue == message
                    stateChanged = True

        if stateChanged:
            self._send_message("sidebar", self.sidebarInfoData())
            self._send_message("navbar", self.navbarInfoData())

    def mqtt_publish_plugin(self, topic, payload):
        if self.baseTopic is None:
            return

        self.mqtt_publish('%s%s%s' % (self.baseTopic, 'plugin/mqtt_plug/', topic), payload)

    def mqtt_register_device_state(self, device: Device):
        self.mqtt_subscribe(device.stateTopic, self.on_mqtt_sub)

    def mqtt_unregister_device_state(self, device: Device):
        pass

    # ~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        return dict(
            # put your plugin's default settings here
            devices=[],
            config_version_key=1
        )

    # ~~ TemplatePlugin mixin

    def get_template_configs(self):
        configs = [
            dict(type="settings", custom_bindings=True),
            dict(type="wizard", custom_bindings=True),
            dict(type="sidebar", custom_bindings=True)
        ]
        for i in range(len(self.devices)):
            dev = self.devices[i]
            hidden = not dev.showNavbarIcon and not dev.showNavbarName
            item = dict(
                type="navbar",
                custom_bindings=True,
                suffix="_" + str(dev.id),
                data_bind="let: {idev: " + str(
                    i) + ", dev: settings.settings.plugins.mqtt_plug.devices()[" + str(i) + "] }",
                classes=["dropdown navbar_plugin_mqtt_plug"]
            )
            if hidden:
                item['classes'].append("navbar_plugin_mqtt_plug_hidden")
            configs.append(item)

        return configs

    def get_template_vars(self):
        return dict(
            baseTopic=self.baseTopic,
            devices=self.devices,
            shutdownAt=self.shutdownAt,
            hasPalette2='palette2' in self._plugin_manager.enabled_plugins
        )

    # ~~ AssetPlugin mixin

    def get_assets(self):
        # Define your plugin's asset files to automatically include in the
        # core UI here.
        return dict(
            js=["js/mqtt-plug.js"],
            css=["css/mqtt-plug.css"]
        )

    # ~~ Softwareupdate hook

    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://github.com/foosel/OctoPrint/wiki/Plugin:-Software-Update
        # for details.
        return dict(
            mqtt_plug=dict(
                displayName="MQTT Plug Plugin",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="ralmn",
                repo="OctoPrint-Mqtt-Plug",
                current=self._plugin_version,

                stable_branch=dict(
                    name="Stable", branch="master", comittish=["master"]
                ),
                prerelease_branches=[
                    dict(
                        name="Unstable / Develop",
                        branch="develop",
                        comittish=["develop", "master"],
                    )
                ],

                # update method: pip
                pip="https://github.com/ralmn/OctoPrint-Mqtt-Plug/archive/{target_version}.zip"
            )
        )

    def navbarInfoData(self):
        return dict(
            state=self.getStateData()
        )

    def planStop(self, dev: Device, force_postpone=False):
        if str(dev.id) in self.stopTimer and self.stopTimer[str(dev.id)] is not None:
            self.stopTimer[str(dev.id)].cancel()
            self.stopTimer[str(dev.id)] = None

        if str(dev.id) in self.stopCooldown and self.stopCooldown[str(dev.id)] is not None:
            self.stopCooldown[str(dev.id)].cancel()
            self.stopCooldown[str(dev.id)] = None

        if dev.shutdownType == "time" or force_postpone:
            delay = dev.postponeDelay if force_postpone else dev.stopDelay
            self.planStopTimeMode(dev, delay)
        else:
            self.planStopCooldown(dev)

    def planStopCooldown(self, dev: Device):

        hotend_request = int(dev.hotendTemp)
        bed_request = int(dev.bedTemp)

        def wrapper():
            temps = self._printer.get_current_temperatures()

            ready_for_stop = True

            if bed_request > -1 and temps['bed']['actual'] > bed_request:
                ready_for_stop = False
            if hotend_request > -1 and 'tool0' in temps and temps['tool0']['actual'] > hotend_request:
                ready_for_stop = False

            if ready_for_stop:
                self.turnOff(dev)
                self.stopCooldown[str(dev.id)] = None
            else:
                self.stopCooldown[str(dev.id)] = threading.Timer(5, wrapper)
                self.stopCooldown[str(dev.id)].start()
            self._send_message("sidebar", self.sidebarInfoData())

        self.stopCooldown[str(dev.id)] = threading.Timer(5, wrapper)
        self.stopCooldown[str(dev.id)].start()
        self._send_message("sidebar", self.sidebarInfoData())

    def planStopTimeMode(self, dev, delay):
        now = math.ceil(time.time())

        if self.shutdownAt[str(dev.id)] is not None:
            self.shutdownAt[str(dev.id)] += delay
        else:
            self.shutdownAt[str(dev.id)] = now + delay
        stopIn = (self.shutdownAt[str(dev.id)] - now)
        self._logger.info("Schedule turn off in %d s" % stopIn)

        def wrapper():
            self.turnOff(dev)

        self.stopTimer[str(dev.id)] = threading.Timer(stopIn, wrapper)
        self.stopTimer[str(dev.id)].start()

        self._send_message("sidebar", self.sidebarInfoData())

    def connect_palette2(self):
        try:
            palette2Plugin = self._plugin_manager.plugins['palette2'].implementation
            palette2Plugin.palette.connectOmega(None)
        except:
            self._logger.error('Failed to connect to palette')

    def turnOn(self, device: Device):
        self.turnOnOutlet(device)

        connection_timer = int(device.connectionDelay)

        def connect():
            if device.connectPalette2:
                self.connect_palette2()
            else:
                self._printer.connect()

        if connection_timer >= -1:
            c = threading.Timer(connection_timer, connect)
            c.start()

        self._send_message("sidebar", self.sidebarInfoData())
        self._send_message("navbar", self.navbarInfoData())

    def turnOnOutlet(self, device: Device):
        # device.state = True
        self.mqtt_publish(device.switchTopic, device.onValue, retained=True)

    def turnOff(self, device: Device):
        self.shutdownAt[str(device.id)] = None
        if device.id in self.stopTimer and self.stopTimer[str(device.id)] is not None:
            self.stopTimer[str(device.id)].cancel()
            self.stopTimer[str(device.id)] = None
        if device.id in self.stopCooldown and self.stopCooldown[str(device.id)] is not None:
            self.stopCooldown[str(device.id)].cancel()
            self.stopCooldown[str(device.id)] = None

        self._send_message("sidebar", self.sidebarInfoData())
        if self._printer.is_printing():
            self._logger.warn("Don't turn off outlet because printer is printing !")
            return
        elif self._printer.is_pausing() or self._printer.is_paused():
            self._logger.warn("Don't turn off outlet because printer is in pause !")
            return
        elif self._printer.is_cancelling():
            self._logger.warn("Don't turn off outlet because printer is cancelling !")
            return

        self._logger.debug('stop')
        self._printer.disconnect()
        self.turnOffOutlet(device)
        self._send_message("navbar", self.navbarInfoData())

    def turnOffOutlet(self, device: Device):
        # device.state = True
        self.mqtt_publish(device.switchTopic, device.offValue, retained=True)

    def get_api_commands(self):
        return dict(
            turnOn=[], turnOff=[], checkStatus=[]
        )

    def getDeviceFromId(self, id) -> Device or None:
        selected_devices = self.devices
        if id is None or id == '-1':
            return None
        if type(id) == str:
            id = uuid.UUID(id)
        for dev in selected_devices:
            if dev.id == id:
                return dev
        return None

    def on_api_command(self, command, data):
        import flask
        if command == "turnOn":
            if 'dev' in data:
                device = self.getDeviceFromId(data['dev']['id'])
                if device is not None:
                    self.turnOn(device)
            # elif 'ip' in data:  # Octopod ?
            #     device = self.getDeviceFromId(int(data['ip']))
            #     if device is None:
            #         pass
            #     else:
            #         self.turnOn(device)
            #         status = self.getStateDataById(device['id'])
            #         res = dict(ip=str(device['id']), currentState=("on" if status['state'] else "off"))
            #         return flask.jsonify(res)
            else:
                self._logger.warn('turn on without device data')
        elif command == "turnOff":
            if 'dev' in data:
                device = self.getDeviceFromId(data['dev']['id'])
                if device is not None:
                    self.turnOff(device)
            # elif 'ip' in data:  # Octopod ?
            #     device = self.getDeviceFromId(int(data['ip']))
            #     if device is None:
            #         pass
            #     else:
            #         self.turnOff(device)
            #         status = self.getStateDataById(device['id'])
            #         res = dict(ip=str(device['id']), currentState=("on" if status['state'] else "off"))
            #         return flask.jsonify(res)
            else:
                self._logger.warn('turn off without device data')
        elif command == "checkStatus":
            status = None
            if 'dev' in data:
                status = self.getStateDataById(data["dev"]['id'])
                return flask.jsonify(status)
            elif 'ip' in data:  # Octopod ?
                device = self.getDeviceFromId(int(data['ip']))
                if device is None:
                    pass
                else:
                    status = self.getStateDataById(device['id'])
                    res = dict(ip=str(device['id']), currentState=("on" if status['state'] else "off"))
                    return flask.jsonify(res)
            else:
                self._logger.warn('checkStatus without device data')

    def get_additional_permissions(self):
        return [
            dict(key="ADMIN",
                 name="Admin",
                 description=gettext("Allow user to set config."),
                 default_groups=[ADMIN_GROUP],
                 roles=["admins"])
        ]

    @octoprint.plugin.BlueprintPlugin.route("/navbar/info", methods=["GET"])
    def navbarInfo(self):
        data = self.navbarInfoData()
        return flask.make_response(json.dumps(data), 200)

    ##Sidebar

    def sidebarInfoData(self):
        # TODO : info stop cooldown
        selected_devices = self.devices
        cooldown_wait = dict()
        for dev in selected_devices:
            if str(dev.id) not in self.shutdownAt:
                self.shutdownAt[str(dev.id)] = None
            if dev.shutdownType == "cooldown":
                val = None
                if str(dev.id) in self.stopCooldown and self.stopCooldown[str(dev.id)] is not None:
                    val = True
                cooldown_wait[str(dev.id)] = val

        return dict(
            shutdownAt=self.shutdownAt,
            cooldown_wait=cooldown_wait
        )

    @octoprint.plugin.BlueprintPlugin.route("/sidebar/info", methods=["GET"])
    def sidebarInfo(self):
        data = self.sidebarInfoData()
        return flask.make_response(json.dumps(data), 200)

    @octoprint.plugin.BlueprintPlugin.route("/sidebar/postpone", methods=["POST"])
    def sidebarPostponeShutdown(self):
        dev = flask.request.json['dev']

        device = self.getDeviceFromId(dev['id'])

        if device is not None:
            self.planStop(device, True)
            self._send_message("sidebar", self.sidebarInfoData())

        return self.sidebarInfo()

    @octoprint.plugin.BlueprintPlugin.route("/sidebar/cancelShutdown", methods=["POST"])
    def sidebarCancelShutdown(self):
        dev = flask.request.json['dev']
        device = self.getDeviceFromId(dev['id'])

        if str(dev['id']) in self.stopTimer and self.stopTimer[str(dev['id'])] is not None:
            self.stopTimer[str(dev['id'])].cancel()
            self.shutdownAt[str(dev['id'])] = None
            self.stopTimer[str(dev['id'])] = None
        if str(dev['id']) in self.stopCooldown and self.stopCooldown[str(dev['id'])] is not None:
            self.stopCooldown[str(dev['id'])].cancel()
            self.shutdownAt[str(dev['id'])] = None
            self.stopCooldown[str(dev['id'])] = None

        self._send_message("sidebar", self.sidebarInfoData())
        return self.sidebarInfo()

    @octoprint.plugin.BlueprintPlugin.route("/sidebar/shutdownNow", methods=["POST"])
    def sidebarShutdownNow(self):
        dev = flask.request.json['dev']
        device = self.getDeviceFromId(dev['id'])
        self.turnOff(device)
        self._send_message("sidebar", self.sidebarInfoData())
        return self.sidebarInfo()

    ### Wizard
    def is_wizard_required(self):
        devices = self._settings.get(['devices'])
        return len(devices) == 0 and self.baseTopic is not None

    def get_wizard_version(self):
        return 1

    @octoprint.plugin.BlueprintPlugin.route("/wizard/setOutlet", methods=["POST"])
    def wizardSetOutlet(self):
        if not "device" in flask.request.json:
            return flask.make_response("Expected selected_outlet.", 400)
        data = flask.request.json['device']

        dev = Device(data)
        self.write_devices_in_settings()
        self._settings.save()

        return flask.make_response("OK", 200)

    @octoprint.plugin.BlueprintPlugin.route("/devices", methods=["GET"])
    def listDevices(self):
        return flask.make_response(json.dumps(self.get_serialized_devices(), indent=4), 200)

    @octoprint.plugin.BlueprintPlugin.route("/device/save", methods=["POST"])
    def saveDevice(self):
        if not "device" in flask.request.json:
            return flask.make_response("Missing device", 400)

        dev = flask.request.json['device']
        device = None

        if 'id' in dev:
            device = self.getDeviceFromId(dev['id'])

        if device is not None:
            requireChangeTopic = False
            if device.stateTopic != dev['stateTopic']:
                requireChangeTopic = True
                self.mqtt_unregister_device_state(device)
            device.update(dev)
            if requireChangeTopic:
                self.mqtt_register_device_state(device)
        else:
            device = Device(dev)
            self.devices.append(device)
            self.mqtt_register_device_state(device)

        self.write_devices_in_settings()
        self._settings.save()

        return flask.make_response(json.dumps(self.get_serialized_devices(), indent=4), 200)

    @octoprint.plugin.BlueprintPlugin.route("/device/delete", methods=["POST"])
    def deleteDevice(self):
        if not "device_id" in flask.request.json:
            return flask.make_response("Missing device", 400)

        device_id = flask.request.json['device_id']
        device = self.getDeviceFromId(device_id)
        if device is not None:
            self.devices.remove(device)

        self.write_devices_in_settings()
        self._settings.save()

        return flask.make_response(json.dumps(self.get_serialized_devices(), indent=4), 200)

    def getStateData(self):
        res = dict()

        for device in self.devices:
            if device.id is None:
                continue
            res[str(device.id)] = self.getStateDataById(device.id)
            self.mqtt_publish_plugin('state/%s' % str(device.id), res[str(device.id)])

        return res

    def getStateDataById(self, device_id):

        device = self.getDeviceFromId(device_id)

        if device is None:
            return dict(state=False)

        res = dict(
            state=device.state
        )
        return res

    def _send_message(self, msg_type, payload):
        self._logger.debug("send message type {}".format(msg_type))
        self._plugin_manager.send_plugin_message(
            self._identifier,
            dict(type=msg_type, payload=payload))

    def get_settings_version(self):
        return 1

    def on_settings_migrate(self, target, current=None):
        self._logger.info("Update version from {} to {}".format(current, target))
        settings_changed = False

        if current is None or current < 2:
            pass

        if settings_changed:
            self._settings.save()

    def on_event(self, event, payload):
        for dev in self.devices:
            schedule_stop = False
            if event == 'PrintDone' and dev.onDone:
                schedule_stop = True
            if event == 'PrintFailed' and dev.onFailed:
                schedule_stop = True
            if schedule_stop:
                self.planStop(dev)
            elif event == 'PrintStarted':
                if str(dev.id) in self.stopTimer and self.stopTimer[str(dev.id)] is not None:
                    self.stopTimer[str(dev.id)].cancel()
                    self.stopTimer[str(dev.id)] = None
                if str(dev.id) in self.stopCooldown and self.stopCooldown[str(dev.id)] is not None:
                    self.stopCooldown[str(dev.id)].cancel()
                    self.stopCooldown[str(dev.id)] = None


__plugin_name__ = "OctoPrint Mqtt Plug"
__plugin_pythoncompat__ = ">=3,<4"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = MqttPlugPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
        "octoprint.access.permissions": __plugin_implementation__.get_additional_permissions
    }
