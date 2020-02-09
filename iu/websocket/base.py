from dataclasses import dataclass
from typing import Mapping, Optional, Tuple, Union

from typeguard import typechecked
from websockets import WebSocketServerProtocol

from ..orm import SessionType, create_session
from ..web.wsgi import create_wsgi_app


@dataclass
class BaseWebSocketServer:
    session: Optional[SessionType] = None

    def __init__(self, config):
        self.app = create_wsgi_app(config)
        self.session = None

    async def __call__(self, websocket: WebSocketServerProtocol, path: str):
        raise NotImplementedError

    def __enter__(self):
        self.session = create_session(self.app)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
        self.session = None

    @typechecked
    def process_request(
        self, path: str, request_headers: Mapping[str, str],
    ) -> Optional[
        Union[
            Tuple[int, Mapping[str, str]],
            Tuple[int, Mapping[str, str], bytes],
        ]
    ]:
        pass
