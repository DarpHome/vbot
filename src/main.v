module main

import arrays
import cli
import discord
import os
import strings
import x.json2

struct Config {
	token            string              @[json: 'token']
	authorized_roles []discord.Snowflake @[json: 'authorized_roles']
}

// json2.decode cannot parse arrays atm
fn Config.parse(j json2.Any) !Config {
	match j {
		map[string]json2.Any {
			return Config{
				token: j['token']! as string
				authorized_roles: discord.maybe_map(j['authorized_roles']! as []json2.Any,
					fn (k json2.Any) !discord.Snowflake {
					return discord.Snowflake.parse(k)!
				})!
			}
		}
		else {
			return error('expected Config to be object, got ${j.type_name()}')
		}
	}
}

fn load_docs_headers() ![]string {
	mut headers := []string{}

	content := os.read_file('${@VEXEROOT}/doc/docs.md')!

	for line in content.split_into_lines() {
		stripped := line.trim_space()

		if stripped.starts_with('* [') {
			header := stripped[(stripped.index_u8(`(`) + 1)..(stripped.len - 1)]

			if header[0] == `#` {
				headers << header
			}
		}
	}
	return headers
}

struct State {
	headers []string
}

fn is_sanitized(argument string) bool {
	for letter in argument {
		match letter {
			`0`...`9`, `a`...`z`, `A`...`Z`, `.`, `_` {}
			else { return false }
		}
	}
	return true
}

struct Section {
	name     string
	content  string
	comments []string
}

fn run_vlib_command(state &State, data discord.ApplicationCommandData, event discord.InteractionCreateEvent) ! {
	vlib_module := data.get('module') or { return } as string
	if !is_sanitized(vlib_module) {
		event.creator.create_interaction_response(event.interaction.id, event.interaction.token,
			discord.MessageInteractionResponse{
			content: 'Only letters, numbers, ., and _ are allowed in module names.'
		})!
		return
	}
	query := data.get('query') or { return } as string
	if !is_sanitized(query) {
		event.creator.create_interaction_response(event.interaction.id, event.interaction.token,
			discord.MessageInteractionResponse{
			content: 'Only letters, numbers, ., and _ are allowed in queries.'
		})!
		return
	}
	event.creator.create_interaction_response(event.interaction.id, event.interaction.token,
		discord.InteractionResponse{
		typ: .deferred_channel_message_with_source
	})!
	result := os.execute('v doc -f json -o stdout ${vlib_module}')
	if result.exit_code != 0 {
		event.creator.create_followup_message(event.interaction.application_id, event.interaction.token,
			content: 'Module `${vlib_module}` not found.'
		)!
		return
	}
	j := json2.raw_decode(result.output) or {
		event.creator.create_followup_message(event.interaction.application_id, event.interaction.token,
			content: 'Decoding `v doc` json failed.'
		)!
		return
	}
	mut lowest, mut closest := 2147483647, Section{}
	sections := j.as_map()['contents']!.arr()

	for section_ in sections {
		section := section_.as_map()
		name := section['name']!.str()
		score := strings.levenshtein_distance(query, name)

		if score < lowest {
			lowest = score
			closest = Section{
				name: name
				content: section['content']!.str()
				comments: discord.maybe_map(section['comments']!.arr(), fn (k json2.Any) !string {
					return k.as_map()['text']!.str()
				})!
			}
		}

		for child_ in section['children']!.arr() {
			child := child_.as_map()
			child_name := child['name']!.str()
			child_score := strings.levenshtein_distance(query, child_name)

			if child_score < lowest {
				lowest = child_score
				closest = Section{
					name: child_name
					content: child['content']!.str()
					comments: discord.maybe_map(child['comments']!.arr(), fn (k json2.Any) !string {
						return k.as_map()['text']!.str()
					})!
				}
			}
		}
	}

	mut description := '```v\n${closest.content}```'
	mut blob := ''

	for comment in closest.comments {
		blob += comment.trim_left('\u0001')
	}

	if blob != '' {
		description += '\n>>> ${blob}'
	}
	event.creator.create_followup_message(event.interaction.application_id, event.interaction.token,
		embeds: [
			discord.Embed{
				title: '${vlib_module}.${closest.name}'
				description: '${description}'
				url: 'https://modules.vlang.io/${vlib_module}.html#${closest.name}'
				color: 0x4287f5
			},
		]
	)!
}

fn run_docs_command(state &State, data discord.ApplicationCommandData, event discord.InteractionCreateEvent) ! {
	query := '#' + (data.get('query')! as string)
	scores := state.headers.map(fn [query] (h string) int {
		return strings.levenshtein_distance(query, h)
	})
	lowest := arrays.min(scores)!
	header := state.headers[scores.index(lowest)]
	event.creator.create_interaction_response(event.interaction.id, event.interaction.token,
		discord.MessageInteractionResponse{
		content: '<https://github.com/vlang/v/blob/master/doc/docs.md${header}>'
	})!
}

fn on_interaction(event discord.InteractionCreateEvent) ! {
	state := unsafe { &State(event.creator.user_data['state']!) }
	match event.interaction.typ {
		.application_command {
			d := event.interaction.get_application_command_data()!
			match d.name {
				'vlib' {
					run_vlib_command(state, d, event)!
				}
				'docs' {
					run_docs_command(state, d, event)!
				}
				else {}
			}
		}
		else {}
	}
}

fn run_bot(config Config) ! {
	mut bot := discord.bot(config.token, intents: .message_content | .guild_messages)
	state := &State{
		headers: load_docs_headers()!
	}
	bot.user_data['state'] = state
	bot.events.on_interaction_create.listen(on_interaction)
	bot.launch()!
}

fn run_sync(config Config) ! {
	bot := discord.make_client('Bot ' + config.token)
	application := bot.fetch_my_application()!
	bot.bulk_overwrite_global_application_commands(application.id, [
		discord.CreateApplicationCommandParams{
			name: 'docs'
			description: 'Search within the docs'
			options: [
				discord.ApplicationCommandOption{
					typ: .string
					name: 'query'
					description: 'The query for the search'
					required: true
				},
			]
		},
		discord.CreateApplicationCommandParams{
			name: 'vlib'
			description: 'Search within a vlib module'
			options: [
				discord.ApplicationCommandOption{
					typ: .string
					name: 'module'
					description: 'The module to search in'
					required: true
				},
				discord.ApplicationCommandOption{
					typ: .string
					name: 'query'
					description: 'The query for the search'
					required: true
				},
			]
		},
	])!
}

fn main() {
	config := Config.parse(json2.raw_decode(os.read_file('config.json')!)!)!
	assert config.token != '', 'Token should be not empty'
	mut app := cli.Command{
		name: 'vbot'
		description: 'V bot'
		execute: fn [config] (_ cli.Command) ! {
			run_bot(config)!
		}
		commands: [
			cli.Command{
				name: 'sync'
				execute: fn [config] (_ cli.Command) ! {
					run_sync(config)!
				}
			},
		]
	}
	app.setup()
	app.parse(os.args)
}
