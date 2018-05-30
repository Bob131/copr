#!/usr/bin/env python3

import re
import os
import fcntl
import sys
import argparse
import requests
import json
import logging
import tempfile
import shutil
import pprint
import tempfile
import stat
import pipes
import pkg_resources

from simplejson.scanner import JSONDecodeError

from copr_rpmbuild import providers
from copr_rpmbuild.builders.mock import MockBuilder
from copr_rpmbuild.helpers import read_config, extract_srpm, locate_srpm, SourceType

try:
    from urllib.parse import urlparse, urljoin
except ImportError:
    from urlparse import urlparse, urljoin

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
log.addHandler(logging.StreamHandler(sys.stdout))

VERSION = pkg_resources.require('copr-rpmbuild')[0].version


def daemonize():
    try:
        pid = os.fork()
    except OSError as e:
        self.log.error("Unable to fork, errno: {0}".format(e.errno))
        sys.exit(1)

    if pid != 0:
        log.info(pid)
        os._exit(0)

    process_id = os.setsid()
    if process_id == -1:
        sys.exit(1)

    devnull_fd = os.open('/dev/null', os.O_RDWR)
    os.dup2(devnull_fd, 0)
    os.dup2(devnull_fd, 1)
    os.dup2(devnull_fd, 2)
    os.close(devnull_fd)


def get_parser():
    shared_parser = argparse.ArgumentParser(add_help=False)
    shared_parser.add_argument("-d", "--detached", default=False, action="store_true",
                               help="Run build in background. Log into /var/lib/copr-rpmbuild/main.log.")
    shared_parser.add_argument("-v", "--verbose", action="count",
                               help="Print debugging information.")
    shared_parser.add_argument("-r", "--chroot",
                               help="Name of the chroot to build rpm package in (e.g. epel-7-x86_64).")
    shared_parser.add_argument("--drop-resultdir", action="store_true",
                               help="Drops resultdir and its content at the beggining before continuing.")

    product = shared_parser.add_mutually_exclusive_group()
    product.add_argument("--rpm", action="store_true", help="Build rpms. This is the default action.")
    product.add_argument("--srpm", action="store_true", help="Build srpm.")
    #product.add_argument("--tgz", action="store_true", help="Make tar.gz with build sources, spec and patches.")

    base_parser = argparse.ArgumentParser(description="COPR building tool.", parents=[shared_parser])
    base_parser.add_argument("-c", "--config", type=str, help="Use specific configuration .ini file.")
    base_parser.add_argument("--version", action="version", version="%(prog)s version " + VERSION)
    base_parser.add_argument("--build-id", type=str, help="COPR build ID")

    subparsers = base_parser.add_subparsers(title="submodes", dest="submode")
    scm_parser = subparsers.add_parser("scm", parents=[shared_parser],
                                       help="Build from an SCM repository.")

    scm_parser.add_argument("--clone-url", required=True,
                            help="clone url to a project versioned by Git or SVN, required")
    scm_parser.add_argument("--commit", dest="committish", default="",
                            help="branch name, tag name, or git hash to be built")
    scm_parser.add_argument("--subdir", dest="subdirectory", default="",
                            help="relative path from the repo root to the package content")
    scm_parser.add_argument("--spec", default="",
                            help="relative path from the subdirectory to the .spec file")
    scm_parser.add_argument("--type", dest="type", choices=["git", "svn"], default="git",
                            help="Specify versioning tool. Default is 'git'.")
    scm_parser.add_argument("--method", dest="srpm_build_method", default="rpkg",
                            choices=["rpkg", "tito", "tito_test", "make_srpm"],
                            help="Srpm build method. Default is 'rpkg'.")
    return base_parser


def main():
    parser = get_parser()
    args = parser.parse_args()

    config = read_config(args.config)

    if args.verbose:
        log.setLevel(logging.DEBUG)

    if args.detached:
        daemonize()

    # Write pid
    pidfile = open(config.get("main", "pidfile"), "w")
    pidfile.write(str(os.getpid()))
    pidfile.close()

    # Log also to a file
    open(config.get("main", "logfile"), 'w').close() # truncate log
    log.addHandler(logging.FileHandler(config.get("main", "logfile")))

    log.info('Running: {0}'.format(" ".join(map(pipes.quote, sys.argv))))
    log.info('Version: {0}'.format(VERSION))

    # Allow only one instance
    lockfd = os.open(config.get("main", "lockfile"), os.O_RDWR | os.O_CREAT)
    try:
        fcntl.lockf(lockfd, fcntl.LOCK_EX, 1)
        init(args, config)
        action = build_srpm if args.srpm else build_rpm
        action(args, config)
    except (BlockingIOError, RuntimeError, IOError):
        log.exception("")
        sys.exit(1)
    except: # Programmer's mistake
        log.exception("")
        sys.exit(1)
    finally:
        fcntl.lockf(lockfd, fcntl.LOCK_UN, 1)
        os.close(lockfd)


def init(args, config):
    resultdir = config.get("main", "resultdir")
    if os.path.exists(resultdir) and args.drop_resultdir:
        shutil.rmtree(resultdir)
        os.makedirs(resultdir)


def task_merge_args(task, args):
    if args.chroot:
        task['chroot'] = args.chroot

    if args.submode == 'scm':
        task["source_type"] = SourceType.SCM
        task["source_json"].update({
            'clone_url': args.clone_url,
            'committish': args.committish,
            'subdirectory': args.subdirectory,
            'spec': args.spec,
            'type': args.type,
            'srpm_build_method': args.srpm_build_method,
        })


def produce_srpm(task, config, resultdir):
    """
    create tmpdir to allow --private-users=pick with make_srpm
    that changes permissions on the result directory to out of scope values
    """
    with tempfile.TemporaryDirectory(dir=resultdir) as tmpdir:
        tmpdir_abspath = os.path.join(resultdir, tmpdir)
        os.chmod(tmpdir, stat.S_IRWXU|stat.S_IRWXO)
        provider = providers.factory(task["source_type"])(
            task["source_json"], tmpdir_abspath, config)
        provider.produce_srpm()
        for item in os.listdir(tmpdir_abspath):
            shutil.copy(os.path.join(tmpdir_abspath, item), resultdir)


def build_srpm(args, config):
    if args.chroot:
        raise RuntimeError("--chroot option is not supported with --srpm")

    resultdir = config.get("main", "resultdir")

    task = {'source_type': None, 'source_json': {}}
    if args.build_id:
        task.update(get_task("/backend/get-srpm-build-task/", args.build_id, config))

    task_merge_args(task, args)

    pp = pprint.PrettyPrinter(width=120)
    log.info("Task:\n"+pp.pformat(task)+'\n')

    produce_srpm(task, config, resultdir)

    log.info("Output: {}".format(
        os.listdir(resultdir)))

    with open(os.path.join(resultdir, 'success'), "w") as success:
        success.write("done")


def build_rpm(args, config):
    if not args.chroot:
        raise RuntimeError("Missing --chroot parameter")

    task = {'source_type': None, 'source_json': {}}
    if args.build_id:
        task_id = "-".join([args.build_id, args.chroot])
        task.update(get_task("/backend/get-build-task/", task_id, config))

    task_merge_args(task, args)

    pp = pprint.PrettyPrinter(width=120)
    log.info("Task:\n"+pp.pformat(task)+'\n')

    sourcedir = tempfile.mkdtemp()
    scm_provider = providers.ScmProvider(task["source_json"], sourcedir, config)

    if task.get("fetch_sources_only"):
        scm_provider.produce_sources()
    else:
        scm_provider.produce_srpm()
        built_srpm = locate_srpm(sourcedir)
        extract_srpm(built_srpm, sourcedir)

    resultdir = config.get("main", "resultdir")
    builder = MockBuilder(task, sourcedir, resultdir, config)
    builder.run()
    builder.touch_success_file()
    shutil.rmtree(sourcedir)


def get_task(endpoint, id, config):
    try:
        url = urljoin(urljoin(config.get("main", "frontend_url"), endpoint), id)
        response = requests.get(url)
        task = response.json()
        task["source_json"] = json.loads(task["source_json"])
    except JSONDecodeError:
        raise RuntimeError("No valid task at {}".format(url))
    return task


if __name__ == "__main__":
    main()
