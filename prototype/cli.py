# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
"""Installed command dispatcher; setup never reads or approves conversations."""
import json
import runpy
import sys

COMMANDS = {'audit':'audit','trace':'trace','trace-eval':'trace_eval','savings-real':'savings_real','repeats':'repeats','benchmark':'benchmark','import':'imports','start':'session_manager','demo':'demo','download-model':'setup_semantic','semantic':'configure_semantic','mcp':'mcp_server','migrate':'migrate','usage':'usage','claude-code':'automation'}


def main():
    if len(sys.argv) == 1 or sys.argv[1] in ('--help', '-h'):
        print('Context Bridge — find past Claude and ChatGPT conversations\n\nUsage: context-bridge COMMAND [options]\n\nCommands:\n  audit           Experimental local reconciliation and action checks\n  trace           Experimental commit-to-approved-turn evidence (read-only)\n  trace-eval      Label a local trace feasibility sample\n  savings-real    Run the public-document research experiment (opt-in)\n  repeats         Measure local repeat-research opportunity (not savings)\n  usage           Inspect, configure or clear local usage accounting\n  savings         Estimate reuse tokens and optional user-priced costs\n  agent-guide     Print consultation instructions for agents\n  claude-code     Opt-in automatic consultation hook\n  list            List conversations and message counts\n  stats           Show local library totals by provider\n  remove          Remove a conversation or provider from this library\n  exclusions      List or clear durable web conversation exclusions\n  import          Import ChatGPT, Claude or approved Claude Code histories\n  mcp             Search your local library from an MCP client\n  start           Open the optional local session manager\n  paths           Show local storage locations\n  migrate         Copy an older library without deleting it\n  demo            Try three cited searches over a disposable synthetic library\n  semantic        Enable or disable optional offline semantic search\n  download-model  Fetch a checksum-verified local embedding model\n  benchmark       Measure search on disposable synthetic messages\n\nUse COMMAND --help for options. Installation does not approve or read chats.')
        return
    command = sys.argv[1]
    words = command.split()
    known = set(COMMANDS) | {'list', 'stats', 'remove', 'exclusions', 'paths','savings','agent-guide'}
    if any(char.isspace() for char in command) and words and words[0] in known:
        raise SystemExit('Arguments were passed as one string. Use separate arguments: ' + ' '.join(words))
    if command=='savings':
        from .usage import main as usage_main
        sys.argv=['context-bridge savings',*sys.argv[2:]]
        usage_main(savings=True)
        return
    if command=='agent-guide':
        import argparse
        from .reuse_policy import agent_guide,PRESETS
        parser=argparse.ArgumentParser(prog='context-bridge agent-guide')
        parser.add_argument('--policy',choices=tuple(PRESETS),default='balanced')
        args=parser.parse_args(sys.argv[2:])
        print(agent_guide(args.policy))
        return
    if command in ('list', 'stats', 'remove', 'exclusions'):
        from .library import main as library_main
        library_main([command, *sys.argv[2:]])
        return
    if command == '--version':
        from . import __version__
        print(__version__)
        return
    if command == 'paths':
        from .paths import data_home
        home = data_home()
        print(json.dumps({'home': str(home), 'manager': str(home / 'manager'), 'model': str(home / 'models/all-MiniLM-L6-v2'), 'reports': str(home / 'reports')}, indent=2))
        return
    if command not in COMMANDS:
        raise SystemExit('Unknown command. Run context-bridge --help.')
    sys.argv = ['context-bridge ' + command, *sys.argv[2:]]
    try:
        runpy.run_module('.'.join((__package__, COMMANDS[command])), run_name='__main__')
    except ModuleNotFoundError as exc:
        if exc.name in ('numpy', 'onnxruntime', 'tokenizers'):
            raise SystemExit('Optional semantic dependencies are missing. Install this package with its [semantic] extra in the same environment.')
        raise
