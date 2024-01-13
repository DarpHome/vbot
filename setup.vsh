import os
import x.json2

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

println('Loading headers')
headers := load_docs_headers() or {
	eprintln('Failed to load docs headers: ${err}')
	exit(1)
}

println('Writing headers')
os.write_file('headers.json', json2.Any(headers.map(|h| json2.Any(h))).json_str()) or {
	eprintln('Failed to write headers: ${err}')
	exit(1)
}

vlib_docs := os.execute('v doc -m -f json ${os.join_path(@VEXEROOT, 'vlib')} -o docs/')
if vlib_docs.exit_code != 0 {
	eprintln('Failed to generate vlib docs: ${vlib_docs.output}')
	exit(1)
}

println('Trying discord docs')
println(os.execute('v doc -m -f json discord -o docs').output)