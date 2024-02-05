import ast
import asyncio
import dataclasses
import hikari
import json
import os
from os.path import join
import tanjun
import textwrap
import traceback
import typing

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


docs: dict[str, typing.Any] = load_docs()

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


bot = hikari.GatewayBot(
    config["token"],
    intents=hikari.Intents.ALL_MESSAGES | hikari.Intents.MESSAGE_CONTENT,
)
client = tanjun.Client.from_gateway_bot(
    bot,
    declare_global_commands=True,
    mention_prefix=False,
).add_prefix("vb!")


async def handle_components(interaction: hikari.ComponentInteraction) -> None:
    typ, arg = interaction.custom_id.split(":", 2)
    if typ == "vbot-delete":
        if interaction.user.id != int(arg):
            await interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE,
                "Thats not your button.",
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return
        await interaction.message.delete()
        await interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE,
            "Deleted the message.",
            flags=hikari.MessageFlag.EPHEMERAL,
        )


@bot.listen(hikari.InteractionCreateEvent)
async def on_interaction(event: hikari.InteractionCreateEvent) -> None:
    if isinstance(event.interaction, hikari.ComponentInteraction):
        await handle_components(event.interaction)


base = tanjun.Component()


@base.with_slash_command
@tanjun.with_str_slash_option("query", "The query for the search")
@tanjun.as_slash_command("docs", "Search within the docs")
async def search_docs(ctx: tanjun.abc.SlashContext, query: str) -> None:
    query = "#" + query
    scores = [levenshtein(query, h) for h in headers]
    lowest = min(scores)
    header = headers[scores.index(lowest)]
    await ctx.respond(
        f"<https://github.com/vlang/v/blob/master/doc/docs.md{header}>",
        component=ctx.client.rest.build_message_action_row().add_interactive_button(
            hikari.ButtonStyle.DANGER,
            f"vbot-delete:{ctx.author.id}",
            emoji="\N{WASTEBASKET}",
        ),
    )


@dataclasses.dataclass
class Section:
    name: str = ""
    content: str = ""
    comments: list[str] = dataclasses.field(default_factory=lambda: [])


@base.with_slash_command
@tanjun.with_str_slash_option("query", "The query for the search")
@tanjun.with_str_slash_option("module", "The module to search in")
@tanjun.as_slash_command("vdoc", "Search within a vlib")
async def vdoc(ctx: tanjun.abc.SlashContext, module: str, query: str) -> None:
    lowest, closest = 2147483647, Section()
    contents = docs.get(module)
    if contents is None:
        await ctx.respond(
            f"Module `{module}` not found.",
            component=ctx.client.rest.build_message_action_row().add_interactive_button(
                hikari.ButtonStyle.DANGER,
                f"vbot-delete:{ctx.author.id}",
                emoji="\N{WASTEBASKET}",
            ),
        )
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
    await ctx.respond(
        embed=hikari.Embed(
            title=f"{module} {closest.name}",
            description=description,
            url=f"https://modules.vlang.io/{module}.html#{closest.name}",
            color=0x4287F5,
        ),
        component=ctx.client.rest.build_message_action_row().add_interactive_button(
            hikari.ButtonStyle.DANGER,
            f"vbot-delete:{ctx.author.id}",
            emoji="\N{WASTEBASKET}",
        ),
    )


def rewrite_node(node: ast.AsyncFunctionDef):
    if len(node.body) == 0:
        body = [
            ast.Return(ast.Constant(None)),
        ]
    elif len(node.body) == 1:
        body = (
            [
                ast.Return(
                    node.body[0]
                    if isinstance(node.body[0], ast.expr)
                    else node.body[0].value
                ),
            ]
            if isinstance(node.body[0], (ast.Expr, ast.expr))
            else node.body[0]
        )
    else:
        body = [
            *(
                [
                    *node.body[:-1],
                    ast.Return(
                        node.body[-1]
                        if isinstance(node.body[-1], ast.expr)
                        else node.body[-1].value
                    ),
                ]
                if isinstance(node.body[-1], (ast.Expr, ast.expr))
                else node.body
            ),
        ]

    return ast.AsyncFunctionDef(
        _fields=node._fields,
        lineno=node.lineno,
        col_offset=node.col_offset,
        end_lineno=node.end_lineno,
        name=node.name,
        args=node.args,
        body=body,
        decorator_list=node.decorator_list,
        returns=node.returns,
        type_comment=node.type_comment,
    )


def rewrite(code: str, *, filename: str) -> str:
    return ast.unparse(
        rewrite_node(
            typing.cast(ast.AsyncFunctionDef, ast.parse(code, filename).body[0])
        )
    )


@base.with_message_command
@tanjun.with_owner_check(error_message="Only bot owners can use this command")
@tanjun.as_message_command("reload", "Reload docs")
async def reload_docs(ctx: tanjun.abc.MessageContext) -> None:
    docs = load_docs()
    await ctx.message.add_reaction("\N{THUMBS UP SIGN}")


@base.with_message_command
@tanjun.with_owner_check(error_message="Only bot owners can use this command")
@tanjun.as_message_command("regenerate", "Regenerate docs")
async def regenerate_docs(ctx: tanjun.abc.MessageContext) -> None:
    message = await ctx.respond(
        "Regenerating...",
    )
    process = await asyncio.create_subprocess_shell(
        "v setup.vsh",
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        await message.edit(
            "`v setup.vsh` exited with error:",
            attachments=[
                hikari.Bytes(stderr, "stderr.txt"),
                hikari.Bytes(stdout, "stdout.txt"),
            ],
        )
    else:
        await ctx.message.add_reaction("\N{THUMBS UP SIGN}")


@base.with_message_command
@tanjun.with_owner_check(error_message="Only bot owners can use this command")
@tanjun.with_argument("codes", converters=str, multi=True)
@tanjun.as_message_command("eval", "Execute code")
async def owner_eval(ctx: tanjun.abc.MessageContext, codes: list[str]) -> None:
    code = " ".join(codes)
    PREFIXES = ["```python\n", "```py\n", "```\n", "``", "`"]
    for prefix in PREFIXES:
        if code.startswith(prefix):
            code = code[len(prefix) :]
            break
    SUFFIXES = ["\n```", "```", "``", "`"]
    for suffix in SUFFIXES:
        if code.endswith(suffix):
            code = code[: -len(suffix)]
            break
    CODE_START: str = "```py\n"
    CODE_END: str = "\n```"
    LIMIT: int = 2000 - (len(CODE_START) + len(CODE_END))
    component = ctx.client.rest.build_message_action_row().add_interactive_button(
        hikari.ButtonStyle.DANGER,
        f"vbot-delete:{ctx.author.id}",
        emoji="\N{WASTEBASKET}",
    )
    try:
        scope = {
            "ast": ast,
            "asyncio": asyncio,
            "bot": bot,
            "client": client,
            "ctx": ctx,
            "code": code,
            "dataclasses": dataclasses,
            "hikari": hikari,
            "json": json,
            "os": os,
            "tanjun": tanjun,
            "textwrap": textwrap,
            "traceback": traceback,
        }
        exec(
            rewrite(
                f"async def __execute_fn():\n{textwrap.indent(text=code, prefix='    ')}",
                filename="<discord>",
            ),
            scope,
        )
        r1 = await scope["__execute_fn"]()
        if r1 is None:
            await ctx.message.add_reaction("\N{GRINNING CAT FACE WITH SMILING EYES}")
            return
        r2 = repr(r1)
        if len(r2) > 1989:
            await ctx.respond(
                attachment=hikari.Bytes(r2.encode("utf_8"), "result.py"),
                component=component,
            )
        else:
            await ctx.respond(f"```py\n{r2}\n```", component=component)
    except BaseException as e:
        stacktrace = "".join(traceback.format_exception(e))
        print(stacktrace)
        await ctx.message.add_reaction("\N{CRYING CAT FACE}")
        await ctx.author.send(f"{CODE_START}{stacktrace[:LIMIT]}{CODE_END}")


async def main() -> None:
    bot.run()


if __name__ == "__main__":
    client.add_component(base)
    bot.run()
