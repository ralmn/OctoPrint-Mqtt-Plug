import uuid


def loadFromDict(data, key, default):
        res = None
        if key in data:
            res = data[key]
        if res is None:
            res = default
        return res

class Device:

    def __init__(self, data):
        id = loadFromDict(data, "id", uuid.uuid4())
        if id == "-1":
            id = uuid.uuid4()
        elif type(id) == str:
            id = uuid.UUID(id)

        self.id = id

        self.deviceName = loadFromDict(data, "deviceName", "New device")
        self.stateTopic = loadFromDict(data, "stateTopic", "topic/device/state")
        self.switchTopic = loadFromDict(data, "switchTopic", "topic/device/switch")
        self.onValue = loadFromDict(data, "onValue", "ON")
        self.offValue = loadFromDict(data, "offValue", "OFF")

        self.icon = loadFromDict(data, "icon", "plug")
        self.showNavbarIcon = loadFromDict(data, "showNavbarIcon", True)
        self.showNavbarName = loadFromDict(data, "showNavbarName", False)

        self.connectionDelay = loadFromDict(data, "connectionDelay", 15)

        self.onDone = loadFromDict(data, "onDone", True)
        self.onFailed = loadFromDict(data, "onFailed", False)

        self.shutdownType = loadFromDict(data, "shutdownType", "coldown")

        self.stopDelay = loadFromDict(data, "stopDelay", 60)
        self.postponeDelay = loadFromDict(data, "postponeDelay", 60)

        self.hotendTemp = loadFromDict(data, "hotendTemp", 50)
        self.bedTemp = loadFromDict(data, "bedTemp", 30)

        self.connectPalette2 = loadFromDict(data, "connectPalette2", False)

        # Unpersistant field
        self.state = False


    def update(self, data):
        for k in data:
            if k == "id":
                continue
            setattr(self, k, data[k])

    def serialize(self):
        return dict(
            id=str(self.id),
            deviceName=self.deviceName,
            stateTopic=self.stateTopic,
            switchTopic=self.switchTopic,
            onValue=self.onValue,
            offValue=self.offValue,
            icon=self.icon,
            showNavbarIcon=self.showNavbarIcon,
            showNavbarName=self.showNavbarName,
            connectionDelay=self.connectionDelay,
            onDone=self.onDone,
            onFailed=self.onFailed,
            shutdownType=self.shutdownType,
            stopDelay=self.stopDelay,
            postponeDelay=self.postponeDelay,
            hotendTemp=self.hotendTemp,
            bedTemp=self.bedTemp,
            connectPalette2=self.connectPalette2
        )
