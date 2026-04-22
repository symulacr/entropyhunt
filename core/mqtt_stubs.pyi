
from typing import Any, Protocol

class MqttReasonCode(Protocol):
    value: int


class MqttConnectFlags(Protocol):
    ...


class MqttDisconnectFlags(Protocol):
    ...


class MqttMessage(Protocol):
    payload: bytes


class MqttClient(Protocol):
    on_message: Any
    on_connect: Any
    on_disconnect: Any

    def username_pw_set(self, username: str | None, password: str | None = None) -> None: ...
    def connect(self, host: str, port: int) -> None: ...
    def subscribe(self, topic: str) -> tuple[int, int]: ...
    def loop_start(self) -> None: ...
    def loop_stop(self) -> None: ...
    def disconnect(self) -> None: ...
    def reconnect(self) -> None: ...
    def publish(self, topic: str, payload: bytes, qos: int = 0) -> object: ...


class MqttCallbackAPIVersion(Protocol):
    VERSION2: object


class MqttModule(Protocol):
    CallbackAPIVersion: MqttCallbackAPIVersion

    def Client(
        self,
        callback_api_version: object = None,
        client_id: str = "",
    ) -> MqttClient: ...
