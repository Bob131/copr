import logging
import munch
import subprocess
import rpm
import glob
import os
import re
import shutil
import fileinput
import configparser
import pprint
import datetime

log = logging.getLogger("__main__")

CONF_DIRS = [os.getcwd(), "/etc/copr-rpmbuild"]


class SourceType:
    LINK = 1
    UPLOAD = 2
    PYPI = 5
    RUBYGEMS = 6
    SCM = 8


def cmd_debug(result):
    log.debug("")
    log.debug("cmd: {}".format(result.cmd))
    log.debug("cwd: {}".format(result.cwd))
    log.debug("rc: {}".format(result.returncode))
    log.debug("stdout: {}".format(result.stdout))
    log.debug("stderr: {}".format(result.stderr))
    log.debug("")


def run_cmd(cmd, cwd=".", preexec_fn=None):
    """
    Runs given command in a subprocess.

    :param list(str) cmd: command to be executed and its arguments
    :param str cwd: In which directory to execute the command
    :param func preexec_fn: a callback invoked before exec in subprocess

    :raises RuntimeError
    :returns munch.Munch(cmd, stdout, stderr, returncode)
    """
    log.info('Running: {cmd}'.format(cmd=' '.join(cmd)))
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, preexec_fn=preexec_fn)
    try:
        (stdout, stderr) = process.communicate()
    except OSError as e:
        raise RuntimeError(str(e))

    result = munch.Munch(
        cmd=cmd,
        stdout=stdout.decode(encoding='utf-8').strip(),
        stderr=stderr.decode(encoding='utf-8').strip(),
        returncode=process.returncode,
        cwd=cwd
    )
    cmd_debug(result)

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return result


def locate_spec(dirpath):
    spec_path = None
    path_matches = glob.glob(os.path.join(dirpath, '*.spec'))
    for path_match in path_matches:
        if os.path.isfile(path_match):
            spec_path = path_match
            break
    if not spec_path:
        raise RuntimeError('No .spec found at {}'.format(dirpath))
    return spec_path


def locate_srpm(dirpath):
    srpm_path = None
    path_matches = glob.glob(os.path.join(dirpath, '*.src.rpm'))
    for path_match in path_matches:
        if os.path.isfile(path_match):
            srpm_path = path_match
            break
    if not srpm_path:
        raise RuntimeError('No .src.rpm found at {}'.format(dirpath))
    return srpm_path


def get_package_name(spec_path):
    """
    Obtain name of a package described by spec
    at spec_path.

    :param str spec_path: path to a spec file

    :returns str: package name

    :raises PackageNameCouldNotBeObtainedException
    """
    ts = rpm.ts()

    try:
        rpm_spec = ts.parseSpec(spec_path)
    except ValueError as e:
        log.debug("Could not parse {} with error {}. Trying manual parsing."
                 .format(spec_path, str(e)))

        with open(spec_path, 'r') as spec_file:
            spec_lines = spec_file.readlines()

        patterns = [
            re.compile(r'^(name):\s*(\S*)$', re.IGNORECASE),
            re.compile(r'^%global\s*(\S*)\s*(\S*)$'),
            re.compile(r'^%define\s*(\S*)\s*(\S*)$')]

        for spec_line in spec_lines:
            for pattern in patterns:
                match = pattern.match(spec_line)
                if not match:
                    continue
                rpm.addMacro(
                    match.group(1), match.group(2))

    package_name = rpm.expandMacro("%{name}")
    rpm.reloadConfig()

    if not re.match(r'[a-zA-Z0-9-._+]+', package_name):
        raise PackageNameCouldNotBeObtainedException(
            "Got invalid package package name '{}' from {}.".format(package_name, spec_path))

    return package_name


def string2list(string):
    return [elem.strip() for elem in re.split(r"\s*,\s*|\s+", string) if elem]


def read_config(config_path=None):
    config = configparser.RawConfigParser(defaults={
        "resultdir": "/var/lib/copr-rpmbuild/results",
        "lockfile": "/var/lib/copr-rpmbuild/lockfile",
        "logfile": "/var/lib/copr-rpmbuild/main.log",
        "pidfile": "/var/lib/copr-rpmbuild/pid",
        "enabled_source_protocols": "https ftps",
    })
    config_paths = [os.path.join(path, "main.ini") for path in CONF_DIRS]
    config.read(config_path or reversed(config_paths))
    if not config.sections():
        log.error("No configuration file main.ini in: {}".format(" ".join(CONF_DIRS)))
        sys.exit(1)
    return config


def path_join(*args):
    return os.path.normpath('/'.join(args))


def get_mock_uniqueext():
    """
    This is a hack/workaround not to reuse already setup
    chroot from a previous run but to always setup a new
    one. Upon key interrupt during build, mock chroot
    becomes further unuseable and there are also problems
    with method _fixup_build_user in mock for make_srpm
    method together with --private-users=pick for sytemd-
    nspawn.
    """
    return datetime.datetime.now().strftime('%s.%f')
