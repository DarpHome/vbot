import aiohttp
from typing import Any


class VRunResponse:
    output: str
    build_output: str
    error: str

    def __init__(self, data: Any) -> None:
        self.output = data["output"]
        self.build_output = data["buildOutput"]
        self.error = data["error"]

    def __repr__(self) -> str:
        return f"<VRunResponse output={self.output!r} build_output={self.build_output!r} error={self.error!r}>"


class CgenResponse:
    cgen_code: str
    error: str

    def __init__(self, data: Any) -> None:
        self.cgen_code = data["cgenCode"]
        self.error = data["error"]

    def __repr__(self) -> str:
        return f"<CgenResponse cgen_code={self.cgen_code!r} error={self.error!r}>"


class VFormatResponse:
    error: str
    output: str

    def __init__(self, data: Any) -> None:
        self.error = data["error"]
        self.output = data["output"]

    def __repr__(self) -> str:
        return f"<VFormatResponse error={self.error!r} output={self.output!r}>"


class V:
    session: aiohttp.ClientSession

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session

    async def run(
        self,
        code: str,
        *,
        test: bool = False,
        build_arguments: str = "",
        run_arguments: str = "",
    ) -> VRunResponse:
        async with self.session.post(
            "https://play.vlang.io/run" + ("_test" if test else ""),
            data=aiohttp.FormData(
                {
                    "code": code,
                    "build-arguments": build_arguments,
                    "run-arguments": run_arguments,
                }
            ),
        ) as response:
            response.raise_for_status()
            return VRunResponse(await response.json())

    async def cgen(self, code: str, *, build_arguments: str = "") -> CgenResponse:
        async with self.session.post(
            "https://play.vlang.io/cgen",
            data=aiohttp.FormData(
                {
                    "code": code,
                    "build-arguments": build_arguments,
                }
            ),
        ) as response:
            response.raise_for_status()
            return CgenResponse(await response.json())

    async def format(self, code: str) -> VFormatResponse:
        async with self.session.post(
            "https://play.vlang.io/format",
            data=aiohttp.FormData({"code": code}),
        ) as response:
            response.raise_for_status()
            return VFormatResponse(await response.json())
