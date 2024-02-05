# requires discord.py v2.4

import aiohttp
import asyncio
import dataclasses
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import io
from os.path import join
import re
import traceback
import typing
import vplayground

with open("config.json", "r") as file:
    config = json.load(file)


def load_docs() -> dict[str, typing.Any]:
    docs = {}
    for module in os.listdir(join("docs", "_docs")):
        if not module.endswith(".json"):
            continue
        module_name = module[:-5]
        try:
            with open(join("docs", "_docs", module), "r") as doc:
                docs[module_name] = json.load(doc)
        except Exception as exc:
            print(f"[vlib:{module_name}] Loading failed")
            traceback.print_exception(exc)
    return docs


with open("headers.json", "r") as file:
    headers = json.load(file)


def levenshtein(x: str, y: str) -> int:
    m = len(x)
    n = len(y)
    d = [[i] for i in range(1, m + 1)]
    d.insert(0, list(range(0, n + 1)))
    for j in range(1, n + 1):
        for i in range(1, m + 1):
            if x[i - 1] == y[j - 1]:
                substitution_cost = 0
            else:
                substitution_cost = 1
            d[i].insert(
                j,
                min(
                    d[i - 1][j] + 1,
                    d[i][j - 1] + 1,
                    d[i - 1][j - 1] + substitution_cost,
                ),
            )
    return d[-1][-1]


class EvalModal(discord.ui.Modal, title="Evaluate V code"):
    code = discord.ui.TextInput(
        label="Code", style=discord.TextStyle.paragraph, custom_id="code"
    )
    build_arguments = discord.ui.TextInput(
        label="Build arguments",
        custom_id="build_arguments",
        required=False,
        max_length=100,
    )
    run_arguments = discord.ui.TextInput(
        label="Run arguments", custom_id="run_arguments", required=False, max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction["Bot"]) -> None:
        build_arguments = self.build_arguments.value
        run_arguments = self.run_arguments.value
        response = await interaction.client.v.run(
            self.code.value,
            build_arguments=build_arguments,
            run_arguments=run_arguments,
        )
        if response.error != "":
            embed = discord.Embed(
                color=0x4287F5,
                title="Compilation failed!",
            )
            if build_arguments != "":
                embed.add_field(name="Build arguments", value=build_arguments)
            if run_arguments != "":
                embed.add_field(name="Run arguments", value=run_arguments)
            if len(response.error) >= 1989:
                return await interaction.response.send_message(
                    file=discord.File(
                        io.BytesIO(response.error.encode("utf_8")), "error.rs"
                    ),
                    embed=embed if len(embed.fields) > 0 else discord.utils.MISSING,
                    view=DeleteButtonView(interaction.user.id),
                )
            return await interaction.response.send_message(
                f"```rs\n{response.error}\n```",
                embed=embed if len(embed.fields) > 0 else discord.utils.MISSING,
                view=DeleteButtonView(interaction.user.id),
            )
        embed = discord.Embed(
            color=0x4287F5,
            title="Successful execution",
        )
        if build_arguments != "":
            embed.add_field(name="Build arguments", value=build_arguments)
        if run_arguments != "":
            embed.add_field(name="Run arguments", value=run_arguments)
        if len(response.output) >= 1989:
            return await interaction.response.send_message(
                file=discord.File(
                    io.BytesIO(response.output.encode("utf_8")), "output.rs"
                ),
                embed=embed if len(embed.fields) > 0 else discord.utils.MISSING,
                view=DeleteButtonView(interaction.user.id),
            )
        return await interaction.response.send_message(
            f"```rs\n{response.output}\n```",
            embed=embed if len(embed.fields) > 0 else discord.utils.MISSING,
            view=DeleteButtonView(interaction.user.id),
        )


class CgenModal(discord.ui.Modal, title="Show cgen output from V code"):
    code = discord.ui.TextInput(
        label="Code", style=discord.TextStyle.paragraph, custom_id="code"
    )
    build_arguments = discord.ui.TextInput(
        label="Build arguments",
        custom_id="build_arguments",
        required=False,
        max_length=100,
    )

    async def on_submit(self, interaction: discord.Interaction["Bot"]) -> None:
        build_arguments = self.build_arguments.value
        response = await interaction.client.v.cgen(
            self.code.value, build_arguments=build_arguments
        )
        if response.error != "":
            embed = discord.Embed(
                color=0x4287F5,
                title="Compilation failed!",
            )
            if build_arguments != "":
                embed.add_field(name="Build arguments", value=build_arguments)
            if len(response.error) >= 1989:
                return await interaction.response.send_message(
                    file=discord.File(
                        io.BytesIO(response.error.encode("utf_8")), "error.rs"
                    ),
                    embed=embed if len(embed.fields) > 0 else discord.utils.MISSING,
                    view=DeleteButtonView(interaction.user.id),
                )
            return await interaction.response.send_message(
                f"```rs\n{response.error}\n```",
                embed=embed if len(embed.fields) > 0 else discord.utils.MISSING,
                view=DeleteButtonView(interaction.user.id),
            )
        embed = discord.Embed(
            color=0x4287F5,
            title="Successful compilation",
        )
        if build_arguments != "":
            embed.add_field(name="Build arguments", value=build_arguments)
        if len(response.cgen_code) >= 1990:
            return await interaction.response.send_message(
                file=discord.File(
                    io.BytesIO(response.cgen_code.encode("utf_8")), "output.c"
                ),
                embed=embed if len(embed.fields) > 0 else discord.utils.MISSING,
                view=DeleteButtonView(interaction.user.id),
            )
        return await interaction.response.send_message(
            f"```c\n{response.cgen_code}\n```",
            embed=embed if len(embed.fields) > 0 else discord.utils.MISSING,
            view=DeleteButtonView(interaction.user.id),
        )


class FormatModal(discord.ui.Modal, title="Format V code"):
    code = discord.ui.TextInput(
        label="Code", style=discord.TextStyle.paragraph, custom_id="code"
    )

    async def on_submit(self, interaction: discord.Interaction["Bot"]) -> None:
        response = await interaction.client.v.format(self.code.value)
        if response.error != "":
            if len(response.error) >= 1989:
                return await interaction.response.send_message(
                    file=discord.File(
                        io.BytesIO(response.error.encode("utf_8")), "error.rs"
                    ),
                    view=DeleteButtonView(interaction.user.id),
                )
            return await interaction.response.send_message(
                f"```rs\n{response.error}\n```",
                view=DeleteButtonView(interaction.user.id),
            )
        if len(response.output) >= 1989:
            return await interaction.response.send_message(
                file=discord.File(
                    io.BytesIO(response.output.encode("utf_8")), "output.rs"
                ),
                view=DeleteButtonView(interaction.user.id),
            )
        return await interaction.response.send_message(
            f"```rs\n{response.output}\n```", view=DeleteButtonView(interaction.user.id)
        )


@dataclasses.dataclass
class Section:
    name: str = ""
    content: str = ""
    comments: list[str] = dataclasses.field(default_factory=lambda: [])


class BaseCog(commands.Cog, name="base"):
    docs: dict[str, typing.Any]

    def __init__(self) -> None:
        self.docs = load_docs()

    @commands.hybrid_command("docs")
    async def search_docs(self, ctx: commands.Context, query: str) -> None:
        """Search within the docs

        Parameters
        ----------
        query: :class:`str`
            The query for the search
        """
        query = "#" + query
        scores = [levenshtein(query, h) for h in headers]
        lowest = min(scores)
        header = headers[scores.index(lowest)]
        await ctx.send(
            f"<https://github.com/vlang/v/blob/master/doc/docs.md{header}>",
            view=DeleteButtonView(ctx.author.id),
        )

    @commands.hybrid_command()
    async def vdoc(self, ctx: commands.Context, module: str, *, query: str) -> None:
        """Search within a vlib.

        Parameters
        ----------
        module: :class:`str`
            The module to search in
        query: :class:`str`
            The query for the search
        """
        lowest, closest = 2147483647, Section()
        contents = self.docs.get(module)
        if contents is None:
            await ctx.send(f"Module `{module}` not found.", ephemeral=True)
            return
        for section in contents["contents"]:
            score = levenshtein(query, section["name"])
            if score < lowest:
                lowest = score
                closest = Section(
                    name=section["name"],
                    content=section["content"],
                    comments=[comment["text"] for comment in section["comments"]],
                )
            for child in section["children"]:
                child_score = levenshtein(query, child["name"])
                if child_score < lowest:
                    lowest = child_score
                    closest = Section(
                        name=section["name"],
                        content=section["content"],
                        comments=[comment["text"] for comment in section["comments"]],
                    )
        description = f"```v\n{closest.content}```"
        blob = ""
        for comment in closest.comments:
            blob += comment.lstrip("\u0001")
        if blob != "":
            description += f"\n>>> {blob}"
        await ctx.send(
            embed=discord.Embed(
                title=f"{module} {closest.name}",
                description=description,
                url=config["docs"].get(
                    module, f"https://modules.vlang.io/{module}.html"
                )
                + "#"
                + closest.name,
                color=0x4287F5,
            ),
            view=DeleteButtonView(ctx.author.id),
        )

    @commands.command("reload", hidden=True)
    @commands.is_owner()
    async def reload_docs(self, ctx: commands.Context) -> None:
        """Reload docs."""
        self.docs = load_docs()
        await ctx.message.add_reaction("\N{THUMBS UP SIGN}")

    @commands.command("vup", hidden=True)
    @commands.is_owner()
    async def vup(self, ctx: commands.Context) -> None:
        """Update V."""
        await ctx.typing()
        process = await asyncio.create_subprocess_shell(
            "v up",
            stderr=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            await ctx.send(
                "`v up` exited with error:",
                files=[
                    discord.File(io.BytesIO(stderr), "stderr.txt"),
                    discord.File(io.BytesIO(stdout), "stdout.txt"),
                ],
                view=DeleteButtonView(ctx.author.id),
            )
        else:
            await ctx.message.add_reaction("\N{THUMBS UP SIGN}")

    @commands.command("regenerate", hidden=True)
    @commands.is_owner()
    async def regenerate_docs(self, ctx: commands.Context) -> None:
        """Regenerate docs."""
        await ctx.typing()
        process = await asyncio.create_subprocess_shell(
            "v setup.vsh",
            stderr=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            await ctx.send(
                "`v setup.vsh` exited with error:",
                files=[
                    discord.File(io.BytesIO(stderr), "stderr.txt"),
                    discord.File(io.BytesIO(stdout), "stdout.txt"),
                ],
                view=DeleteButtonView(ctx.author.id),
            )
        else:
            await ctx.message.add_reaction("\N{THUMBS UP SIGN}")

    def clean_code(self, code: str) -> str:
        PREFIXES = ["```rs\n", "```v\n", "```\n", "``", "`"]
        for prefix in PREFIXES:
            if code.startswith(prefix):
                code = code[len(prefix) :]
                break
        SUFFIXES = ["\n```", "```", "``", "`"]
        for suffix in SUFFIXES:
            if code.endswith(suffix):
                code = code[: -len(suffix)]
                break
        return code

    v = app_commands.Group(name="v", description="V related stuff")

    @v.command(name="eval", description="Show modal, then evaluate code")
    async def slash_eval(self, interaction: discord.Interaction["Bot"]) -> None:
        await interaction.response.send_modal(EvalModal(timeout=None))

    @v.command(name="cgen", description="Show modal, then show cgen output")
    async def slash_cgen(self, interaction: discord.Interaction["Bot"]) -> None:
        await interaction.response.send_modal(CgenModal(timeout=None))

    @v.command(name="format", description="Show modal, then format code")
    async def slash_format(self, interaction: discord.Interaction["Bot"]) -> None:
        await interaction.response.send_modal(FormatModal(timeout=None))

    @commands.command("eval", aliases=["e", "exec", "exe", "evl"])
    async def text_eval(self, ctx: commands.Context["Bot"], *, code: str) -> None:
        """Execute V code.

        Parameters
        ----------
        code: :class:`str`
            The V code to format
        """
        response = await ctx.bot.v.run(self.clean_code(code))
        if response.error != "":
            if len(response.error) >= 1989:
                await ctx.send(
                    file=discord.File(
                        io.BytesIO(response.error.encode("utf_8")), "error.rs"
                    ),
                    view=DeleteButtonView(ctx.author.id),
                )
            else:
                await ctx.send(f"```rs\n{response.error}\n```")
            return
        elif len(response.output) >= 1989:
            await ctx.send(
                file=discord.File(
                    io.BytesIO(response.output.encode("utf_8")), "output.rs"
                ),
                view=DeleteButtonView(ctx.author.id),
            )
            return
        await ctx.send(
            f"```rs\n{response.output}\n```", view=DeleteButtonView(ctx.author.id)
        )

    @commands.command("cgen", aliases=["c", "gen", "g"])
    async def text_cgen(self, ctx: commands.Context["Bot"], *, code: str) -> None:
        """Show cgen output from V code.

        Parameters
        ----------
        code: :class:`str`
            The V code to format
        """
        response = await ctx.bot.v.cgen(self.clean_code(code))
        if response.error != "":
            if len(response.error) >= 1989:
                await ctx.send(
                    file=discord.File(
                        io.BytesIO(response.error.encode("utf_8")), "error.rs"
                    ),
                    view=DeleteButtonView(ctx.author.id),
                )
            else:
                await ctx.send(
                    f"```rs\n{response.error}\n```",
                    view=DeleteButtonView(ctx.author.id),
                )
            return
        elif len(response.cgen_code) >= 1990:
            await ctx.send(
                file=discord.File(
                    io.BytesIO(response.cgen_code.encode("utf_8")), "output.c"
                ),
                view=DeleteButtonView(ctx.author.id),
            )
            return
        await ctx.send(
            f"```c\n{response.cgen_code}\n```", view=DeleteButtonView(ctx.author.id)
        )

    @commands.command("format", aliases=["f", "fmt", "formt"])
    async def text_format(self, ctx: commands.Context["Bot"], *, code: str) -> None:
        """Format V code.

        Parameters
        ----------
        code: :class:`str`
            The V code to format
        """
        response = await ctx.bot.v.format(self.clean_code(code))
        if response.error != "":
            if len(response.error) >= 1989:
                await ctx.send(
                    file=discord.File(
                        io.BytesIO(response.error.encode("utf_8")), "error.rs"
                    ),
                    view=DeleteButtonView(ctx.author.id),
                )
            else:
                await ctx.send(
                    f"```rs\n{response.error}\n```",
                    view=DeleteButtonView(ctx.author.id),
                )
            return
        elif len(response.output) >= 1989:
            await ctx.send(
                file=discord.File(
                    io.BytesIO(response.output.encode("utf_8")), "output.rs"
                ),
                view=DeleteButtonView(ctx.author.id),
            )
            return
        await ctx.send(
            f"```rs\n{response.output}\n```", view=DeleteButtonView(ctx.author.id)
        )


# make vb!help not depend on cache
class Context(commands.Context["Bot"]):
    @property
    def clean_prefix(self) -> str:
        return self.prefix or str(self.bot.command_prefix)


class Bot(commands.Bot):
    _v: typing.Optional[vplayground.V]

    @property
    def v(self) -> vplayground.V:
        if self._v is None:
            raise ValueError
        return self._v

    async def get_context(
        self, origin: typing.Union[discord.Message, discord.Interaction]
    ) -> Context:
        return await super().get_context(origin, cls=Context)


bot = Bot(
    command_prefix="vb!",
    intents=discord.Intents(messages=True, message_content=True),
    max_messages=None,
    allowed_mentions=discord.AllowedMentions.none(),
)


class DeleteButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template="vbot-delete:(?P<user_id>[0-9]+)",
):
    def __init__(self, user_id: int) -> None:
        self.user_id: int = user_id
        super().__init__(
            discord.ui.Button(
                style=discord.ButtonStyle.danger,
                custom_id=f"vbot-delete:{user_id}",
                emoji="\N{WASTEBASKET}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls, _1: discord.Interaction, _2: discord.ui.Button, match: re.Match[str], /
    ):
        return cls(int(match["user_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "Thats not your button.", ephemeral=True
            )
        if interaction.message is not None:
            await interaction.message.delete()
        await interaction.response.send_message("Deleted the message.", ephemeral=True)


bot.add_dynamic_items(DeleteButton)


class DeleteButtonView(discord.ui.View):
    def __init__(self, user_id: int) -> None:
        super().__init__(timeout=None)
        self.add_item(DeleteButton(user_id))


async def main() -> None:
    discord.utils.setup_logging()
    bot._v = vplayground.V(aiohttp.ClientSession())
    await bot.add_cog(BaseCog())
    await bot.load_extension("jishaku")
    await bot.start(config["token"])


if __name__ == "__main__":
    asyncio.run(main())
