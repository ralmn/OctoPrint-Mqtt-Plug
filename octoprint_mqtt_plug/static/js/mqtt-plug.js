/*
 * View model for OctoPrint-Mqtt-Plug
 *
 * Author: Mathieu "ralmn" HIREL
 * License: AGPLv3
 */
$(function () {
    function MqttPlugViewModel(parameters) {
        var self = this;

        // assign the injected parameters, e.g.:
        //self.loginStateViewModel = parameters[0];
        self.settings = parameters[0];

        self.printer = parameters[3];


        self.wizardError = ko.observable(null);

        self.sidebarInfo = ko.observable({
            shutdownAt: {},
            cooldown_wait: {}
        });

        self.navInfo = ko.observable({
            state: false
        });

        self.reloadRequired = ko.observable(false);


        self.devices = ko.observable([])

        self.deviceIdEdit = ko.observable(-1);

        self.iconClass = function (dev) {
            //debugger;
            let info = self.navInfo().state[dev.id()];
            return "fa fa-" + dev.icon() + " state-icon " + (info && info.state ? 'state-on' : 'state-off');
        };


        self.command = function (command_name, payload) {
            let data = payload || {};
            data.command = command_name;
            $.ajax({
                url: API_BASEURL + "plugin/mqtt_plug",
                type: "POST",
                dataType: "json",
                data: JSON.stringify(data),
                contentType: "application/json; charset=UTF-8"
            }).done(function (data) {
            });
        };

        self.turnOn = function (dev) {
            self.command("turnOn", {dev: ko.toJS(dev)});
        };
        self.turnOff = function (dev) {
            self.command("turnOff", {dev: ko.toJS(dev)});
        };

        self.canDisplayNavbar = function () {
            return self.settings.getLocalData().plugins.mqtt_plug.devices.length > 0;
        };

        self.onDataUpdaterPluginMessage = function (plugin, msg) {
            if (plugin == 'mqtt_plug') {
                if (msg.type == 'sidebar') {
                    self.onSidebarInfo(msg.payload);
                } else if (msg.type == 'navbar') {
                    self.navInfo(msg.payload);
                }
            }
        }

        self.onStartupComplete = function (event) {
            self.getSideBarInfo();
            self.getNavbarInfo();
            setInterval(self.getNavbarInfo, 60 * 1000);

        }


        self.onWizardDetails = function () {
            self.setDefaultDeviceDialogValue($('#mqttPlugWizardForm'))
        }

        self.getSideBarInfo = function () {
            $.ajax({
                url: BASEURL + "plugin/mqtt_plug/sidebar/info",
                type: "GET",
                dataType: "json"
            }).done(self.onSidebarInfo);
        };

        self.getNavbarInfo = function () {
            $.ajax({
                url: BASEURL + "plugin/mqtt_plug/navbar/info",
                type: "GET",
                dataType: "json"
            }).done(self.navInfo);
        };

        self.onSidebarInfo = function (data) {
            //console.log("onSidebarInfo ==>", data)
            self.sidebarInfo(data);
            // console.log("onSidebarInfo <== ", self.sidebarInfo())
        };

        self.sidebarShutdownAt = function (dev) {
            return new Date((self.sidebarInfo().shutdownAt[dev.id()] || 0) * 1000).toLocaleTimeString();
        }

        self.sidebarInfoShutdownPlanned = function (dev) {
            return self.sidebarInfo() && self.sidebarInfo().shutdownAt[dev.id()] != null
        }

        self.sidebarInfoCooldownPlanned = function (dev) {
            return self.sidebarInfo() && self.sidebarInfo().cooldown_wait[dev.id()] != null
        }

        self.postponeShutdown = function () {
            $.ajax({
                url: BASEURL + "plugin/mqtt_plug/sidebar/postpone",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    dev: ko.toJS(this)
                }),
                contentType: "application/json; charset=UTF-8"
            }).done(self.onSidebarInfo).fail(function (jqXHR, textStatus, errorThrown) {
                //console.log('error',  jqXHR, textStatus, errorThrown);
                self.wizardError("Error when connection")
            });
        }

        self.cancelShutdown = function () {
            $.ajax({
                url: BASEURL + "plugin/mqtt_plug/sidebar/cancelShutdown",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    dev: ko.toJS(this)
                }),
                contentType: "application/json; charset=UTF-8"
            }).done(self.onSidebarInfo).fail(function (jqXHR, textStatus, errorThrown) {
                //console.log('error',  jqXHR, textStatus, errorThrown);
                self.wizardError("Error when connection")
            });
        }

        self.shutdownNow = function () {
            $.ajax({
                url: BASEURL + "plugin/mqtt_plug/sidebar/shutdownNow",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    dev: ko.toJS(this)
                }),
                contentType: "application/json; charset=UTF-8"
            }).done(self.onSidebarInfo).fail(function (jqXHR, textStatus, errorThrown) {
                //console.log('error',  jqXHR, textStatus, errorThrown);
                self.wizardError("Error when connection")
            });
        }

        self.onBeforeWizardFinish = function () {
            let dialog = $('#mqttPlugWizardForm');
            let device = self.extractDeviceDialogData(dialog);

            $.ajax({
                url: BASEURL + "plugin/mqtt_plug/device/save",
                type: "POST",
                //dataType: "json",
                data: JSON.stringify({
                    device: device
                }),
                contentType: "application/json; charset=UTF-8"
            })

            return true;
        };

        self.getDevices = function () {
            $.ajax({
                url: BASEURL + "plugin/mqtt_plug/devices",
                type: "GET",
                dataType: "json",
                contentType: "application/json; charset=UTF-8"
            }).done((res) => {
                self.devices(res);
            }).fail(function (jqXHR, textStatus, errorThrown) {
                //console.log('error',  jqXHR, textStatus, errorThrown);
                self.wizardError("Error when get devices")
            });
        }

        let currentDevice = null;

        self.showDeviceDialogEdit = function (device) {
            currentDevice = device;

            self.getDevices();

            let dialog = $('#mqtt_plug_device_modal');
            dialog.find('[name="device_name"]').val(device.name());
            dialog.find('[name="device_id"]').val(device.id());
            dialog.find('[name="on_done"]').prop('checked', device.on_done());
            dialog.find('[name="on_failed"]').prop('checked', device.on_failed());
            dialog.find('[name="stop_timer"]').val(device.stop_timer());
            dialog.find('[name="postpone_delay"]').val(device.postpone_delay());
            dialog.find('[name="connection_timer"]').val(device.connection_timer());
            dialog.find('[name="icon"]').val(device.icon());
            dialog.find('[name="nav_icon"]').prop('checked', device.nav_icon());
            dialog.find('[name="nav_name"]').prop('checked', device.nav_name());
            dialog.find('[name="connect_palette2"]').prop('checked', device.connect_palette2 && device.connect_palette2());

            dialog.find('[name="turn_off_mode"]').val(device.shutdownType());
            dialog.find('[name="cooldown_bed"]').val(device.cooldown_bed());
            dialog.find('[name="cooldown_hotend"]').val(device.cooldown_hotend());

            self.dialogOnTurnOffModeChange();

            dialog.modal();
            self.deviceIdEdit(device.id());
        }


        self.showDeviceDialogNew = function (device) {
            currentDevice = null;

            self.getDevices();
            self.deviceIdEdit(-1);


            let dialog = $('#mqtt_plug_device_modal');
            self.setDefaultDeviceDialogValue(dialog);
            dialog.modal();
        }

        self.setDefaultDeviceDialogValue = function (dialog) {
            dialog.find('[name="deviceName"]').val('new Printer');
            dialog.find('[name="device_id"]').val(-1);

            let baseTopic = self.settings.getLocalData().plugins.mqtt.publish.baseTopic;
            dialog.find('[name="stateTopic"]').val(baseTopic + "device/state")
            dialog.find('[name="switchTopic"]').val(baseTopic + "device/switch")

            dialog.find('[name="on_done"]').prop('checked', true);
            dialog.find('[name="on_failed"]').prop('checked', false);
            dialog.find('[name="stop_timer"]').val(30);
            dialog.find('[name="postpone_delay"]').val(60);
            dialog.find('[name="connection_timer"]').val(5);
            dialog.find('[name="icon"]').val('plug');
            dialog.find('[name="nav_icon"]').prop('checked', true);
            dialog.find('[name="nav_name"]').prop('checked', false);
            let connect_palette2 = dialog.find('[name="connect_palette2"]');
            if (connect_palette2)
                connect_palette2.prop('checked', false);

            dialog.find('[name="turn_off_mode"]').val('cooldown');
            dialog.find('[name="cooldown_bed"]').val(-1);
            dialog.find('[name="cooldown_hotend"]').val(50);

            self.dialogOnTurnOffModeChange();

        }

        self.extractDeviceDialogData = function (dialog) {
            let device = {
                name: dialog.find('[name="device_name"]').val(),
                id: parseInt(dialog.find('[name="device_id"]').val()),
                stateTopic: dialog.find('[name="stateTopic"]').val(),
                switchTopic: dialog.find('[name="switchTopic"]').val(),
                // onValue: dialog.find('[name="onValue"]').val(),
                // offValue: dialog.find('[name="offValue"]').val(),
                onDone: dialog.find('[name="on_done"]').prop('checked'),
                onFailed: dialog.find('[name="on_failed"]').prop('checked'),
                stopDelay: parseInt(dialog.find('[name="stop_timer"]').val()),
                postponeDelay: parseInt(dialog.find('[name="postpone_delay"]').val()),
                connectionDelay: parseInt(dialog.find('[name="connection_timer"]').val()),
                icon: dialog.find('[name="icon"]').val(),
                showNavbarIcon: dialog.find('[name="nav_icon"]').prop('checked'),
                showNavbarName: dialog.find('[name="nav_name"]').prop('checked'),
                shutdownType: dialog.find('[name="turn_off_mode"]').val(),
                bedTemp: dialog.find('[name="cooldown_bed"]').val(),
                hotendTemp: dialog.find('[name="cooldown_hotend"]').val()
            };
            let connect_palette2 = dialog.find('[name="connect_palette2"]');
            if (connect_palette2) {
                device.connectPalette2 = connect_palette2.prop('checked');
            }
            return device;
        }

        self.saveDeviceDialog = function () {
            let dialog = $('#mqtt_plug_device_modal');
            let device = self.extractDeviceDialogData(dialog);

            $.ajax({
                url: BASEURL + "plugin/mqtt_plug/device/save",
                type: "POST",
                //dataType: "json",
                data: JSON.stringify({
                    device: device
                }),
                contentType: "application/json; charset=UTF-8"
            }).then((data) => {
                let deviceObs = {}
                for (let key in device) {
                    deviceObs[key] = ko.observable(device[key]);
                }
                if (currentDevice) {
                    self.settings.settings.plugins.mqtt_plug.devices.replace(currentDevice, deviceObs);
                    if (currentDevice.nav_icon() != deviceObs.nav_icon() || currentDevice.nav_name() != deviceObs.nav_name()) {
                        self.reloadRequired(true);
                    }
                } else {
                    self.settings.settings.plugins.mqtt_plug.devices.push(deviceObs);
                }

            });

            dialog.modal('hide');

        }

        self.dialogOnTurnOffModeChange = function () {
            let dialog = $('#mqtt_plug_device_modal');
            const timeMode = dialog.find('[name="turn_off_mode"]').val() === "time";

            $('#plugins_mqtt_plug_grp_cooldown_bed')[timeMode ? 'hide' : 'show'](); // TODO : c'est moche... faudra voir a changer ça
            $('#plugins_mqtt_plug_grp_cooldown_hotend')[timeMode ? 'hide' : 'show']();
            $('#plugins_mqtt_plug_grp_stop_timer')[timeMode ? 'show' : 'hide']();
            //$('#plugins_mqtt_plug_grp_postpone_delay')[timeMode ? 'show' : 'hide']();

        }


        self.deleteDevice = function (device) {
            let deviceId = device.id();

            $.ajax({
                url: BASEURL + "plugin/mqtt_plug/device/delete",
                type: "POST",
                //dataType: "json",
                data: JSON.stringify({
                    device_id: deviceId
                }),
                contentType: "application/json; charset=UTF-8"
            }).then((data) => {
                self.settings.settings.plugins.mqtt_plug.devices.remove(device)
            });
            return true;
        }

    }


    if (ko.bindingHandlers['let'] == null) {
        ko.bindingHandlers['let'] = {
            init: function (element, valueAccessor, allBindings, viewModel, bindingContext) {
                var innerContext = bindingContext.extend(valueAccessor);
                ko.applyBindingsToDescendants(innerContext, element);
                return {controlsDescendantBindings: true};
            }
        }
    }


    /* view model class, parameters for constructor, container to bind to
     * Please see http://docs.octoprint.org/en/master/plugins/viewmodels.html#registering-custom-viewmodels for more details
     * and a full list of the available options.
     */
    OCTOPRINT_VIEWMODELS.push({
        construct: MqttPlugViewModel,
        additionalNames: ["mqttPlugViewModel"],
        dependencies: ["settingsViewModel", "loginStateViewModel", "wizardViewModel", "printerStateViewModel"],
        elements: [...Array.from($(".navbar_plugin_mqtt_plug")).map(e => `#${e.id}`), "#settings_plugin_mqtt_plug", "#wizard_plugin_mqtt_plug", "#sidebar_plugin_mqtt_plug"]
    });
});
