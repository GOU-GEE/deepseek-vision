# DSH compatibility evidence

Checked on 2026-09-07 for `dsh-plugin-deepseek-vision` 0.4.2.

## Exact release declarations

| DSH release | Official tag commit | Result | Evidence scope |
| --- | --- | --- | --- |
| `0.1.2-alpha.5` | `db6bdc3576c2d4e7c965e8e3ed0c2a731eed87f5` | compatible | Source contract review |
| `0.1.2-rc.1` | `a66e4702047846cdaa10c66c9d3df3951f5ea70d` | compatible | Source contract review |
| `0.1.3-alpha.1` | `d347e703908d0406b7a7ef80e3a0e594d86b2215` | compatible | Source contract review |

For every fixed official tag above, the review confirmed:

- `@deepseek-ai/dsh-mcp-client` still exports `Config`, `apply`, and `inject`,
  with the same stdio configuration used by this Bundle;
- the Web packages that own sessions, conversation input, input triggers,
  settings, and plugin settings remain present under their declared package
  names;
- the `settings.plugin.item` and `conversation.input.dock` slots, and the
  input-trigger registration surface used by `client.js`, remain present;
- the Bundle adds only its own `deepseek-vision-host` and
  `deepseek-vision-mcp` entry IDs.

This is author-declared source compatibility, not a claim that DSH STORE has
performed runtime or security verification. Install/start/uninstall operation
evidence remains independent. CI continues to install the packed Bundle into a
disposable profile with the latest DSH CLI currently obtainable from the public
npm registry (`0.1.0-rc.6`), dump the composed configuration, start the Web
profile on an ephemeral loopback port, and uninstall it. The same disposable
Profile sequence passed locally on macOS arm64 on 2026-09-07; rollback remains
`unknown` because this release does not claim rollback verification.
