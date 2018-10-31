import random
import string

import click


import logging
import os
import sys

from flexget import logger
from flexget.entry import Entry
from flexget.ipc import IPCClient
from flexget.manager import Manager
from flexget.utils.tools import get_latest_flexget_version_number, get_current_flexget_version


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class AliasedGroup(click.Group):
    def _resolve_command(self, ctx, args):
        """Click's 'ignore_unknown_options' doesn't really work  with Groups. This fixes that."""
        if args and ctx.ignore_unknown_options:
            for i in range(len(args)):
                # Look for an argument that appears to be a command name
                if not click.parser.split_opt(args[i])[0]:
                    unknown_opts, args = args[:i], args[i:]
                    ctx.args.extend(unknown_opts)
                    break
            cmd_name, cmd, args = click.Group.resolve_command(self, ctx, args)
            return cmd.name, cmd, args

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx)
                   if x.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))

    def parse_core_options(self, args=None):
        """
        Returns known core options without validating anything. Works before plugins are loaded.
        """
        if args is None:
            args = click.get_os_args()
        with self.make_context('flexget', args, ignore_unknown_options=True, help_option_names=[]) as ctx:
            return ctx.params



def inject_callback(ctx, param, value):
    return [Entry(**{
        'title': title,
        'url': 'http://localhost/inject/%s' % ''.join(random.sample(string.ascii_letters + string.digits, 30))
    }) for title in value]


def version_callback(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    current = get_current_flexget_version()
    latest = get_latest_flexget_version_number()

    # Print the version number
    click.echo('%s' % get_current_flexget_version())
    # Check for latest version from server
    if latest:
        if current == latest:
            click.echo('You are on the latest release.')
        else:
            click.echo('Latest release: %s' % latest)
    else:
        click.echo('Error getting latest version number from https://pypi.python.org/pypi/FlexGet')
    ctx.exit()


def debug_callback(ctx, param, value):
    if value:
        ctx.default_map['loglevel'] = 'debug'
    return value


def debug_trace_callback(ctx, param, value):
    if value:
        ctx.default_map['loglevel'] = 'trace'
        ctx.default_map['debug'] = True
    return value


def cron_callback(ctx, param, value):
    if value:
        ctx.default_map['loglevel'] = 'info'
    return value


pass_manager = click.make_pass_decorator(Manager)


@click.group("flexget", cls=AliasedGroup, context_settings={'default_map': {}})
@click.option(
    "-V",
    "--version",
    is_flag=True,
    callback=version_callback,
    expose_value=False,
    is_eager=True,
    help="Print FlexGet version and exit.",
)
@click.option(
    "--test",
    is_flag=True,
    default=False,
    help="Verbose what would happen on normal execution.",
)
@click.option(
    "-c",
    "--config",
    default="config.yml",
    help="Specify configuration file.",
    show_default=True
)
@click.option(
    "--logfile",
    "-l",
    default="flexget.log",
    help="Specify a custom logfile name/location.  [default: flexget.log in the config directory]",
)
@click.option(
    "--loglevel",
    "-L",
    help="Set the verbosity of the logger.",
    type=click.Choice(
        ["none", "critical", "error", "warning", "info", "verbose", "debug", "trace"]
    ),
    default="verbose",
)
@click.option('--bugreport', 'debug_tb', is_flag=True,
              help='Use this option to create a detailed bug report, '
                                 'note that the output might contain PRIVATE data, so edit that out')
@click.option('--profile', 'do_profile', is_flag=True,   # TODO: make this a plugin?
                             help='Use the python profiler for this run to debug performance issues.')
@click.option('--debug', is_flag=True, callback=debug_callback, hidden=True)
@click.option('--debug-trace', is_flag=True, callback=debug_trace_callback, hidden=True)
@click.option('--debug-sql', is_flag=True, hidden=True)
@click.option('--experimental', is_flag=True, hidden=True)
@click.option('--ipc-port', type=click.IntRange(min=0), hidden=True)
@click.option('--cron', is_flag=True, callback=cron_callback,
                            help='use when executing FlexGet non-interactively: allows background '
                                 'maintenance to run, disables stdout and stderr output, reduces logging level')
@pass_manager
def run_flexget(manager, **params):
    # manager gets initialized with options before plugins are loaded. Update options with fully parsed versions now
    # TODO: is this the right answer? What about when it's an IPC run and manager already has inited options?
    manager.options = params


@run_flexget.command('execute', help='execute tasks now')
@click.option('--task', '--tasks', metavar='TASK', multiple=True,
                         help='run only specified task(s), optionally using glob patterns ("tv-*"). '
                              'matching is case-insensitive')
@click.option('--learn', is_flag=True,
                         help='matches are not downloaded but will be skipped in the future')
@click.option('--disable-phase', '--disable-phases', 'disable_phases', multiple=True, hidden=True)
@click.option('--inject', multiple=True, callback=inject_callback, hidden=True)
# Plugins should respect these flags where appropriate
@click.option('--retry', is_flag=True, hidden=True)
@click.option('--no-cache', 'nocache', is_flag=True,
                         help='disable caches. works only in plugins that have explicit support')
@pass_manager
def execute(manager, **params):
    print("running execute")
    manager.execute_command(options=params)


@run_flexget.group('daemon', help='run continuously, executing tasks according to schedules defined in config')
@click.pass_context
def daemon(ctx, **params):
    # TODO: set loglevel to info?
    pass


@daemon.command('start', help='start the daemon')
# TODO: no daemonize on windows
@click.option('-d', '--daemonize', is_flag=True, help='causes process to daemonize after starting')
@click.option('--autoreload-config', is_flag=True,
                          help='automatically reload the config from disk if the daemon detects any changes')
def daemon_start(**params):
    click.echo('daemon_start')


@daemon.command('stop', help='shutdown the running daemon')
@click.option('--wait', is_flag=True,
              help='wait for all queued tasks to finish before stopping daemon')
def daemon_stop(**params):
    click.echo('daemon_stop')


@daemon.command('status', help='check if a daemon is running')
def daemon_status(**params):
    click.echo('daemon_status')


@daemon.command('reload-config', help='causes a running daemon to reload the config from disk')
def daemon_reload(**params):
    click.echo('daemon_reload')


def main():
    # with run_flexget.make_context("flexget", click.get_os_args(), ignore_unknown_options=True, allow_extra_args=True) as ctx:
    #     print(ctx)
    logger.initialize()
    try:
        params = run_flexget.parse_core_options()
    except click.exceptions.Exit as e:
        # -V can end us up here
        return
    manager = Manager(params)
    args = click.get_os_args()
    try:
        manager.run_ipc_command(args)
        return
    except Exception:  # TODO: Fix this
        pass
    manager.run_local_command(args)
    #rv = run_flexget(standalone_mode=False)


if __name__ == "__main__":
    main()
