import os

mockchain = "/usr/bin/mockchain"
# rsync path
rsync = "/usr/bin/rsync"

DEF_REMOTE_BASEDIR = "/var/tmp"
DEF_BUILD_TIMEOUT = 3600 * 6
DEF_REPOS = []
DEF_CHROOT = None
DEF_BUILD_USER = "mockbuilder"
DEF_DESTDIR = os.getcwd()
DEF_MACROS = {}
DEF_BUILDROOT_PKGS = ""


DEF_CONSECUTIVE_FAILURE_THRESHOLD = 10
CONSECUTIVE_FAILURE_REDIS_KEY = "copr:sys:consecutive_build_fails"


class BuildStatus(object):
    FAILURE = 0
    SUCCEEDED = 1
    RUNNING = 3
    PENDING = 4
    SKIPPED = 5

    @classmethod
    def string(cls, number):
        """ convert number to string """
        for key, val in cls.__dict__.iteritems():
            if isinstance(val, int) and number == val:
                return key
        raise AttributeError("no such status id: {0} ".format(number))


LOG_PUB_SUB = "copr:backend:log:pubsub::"

from logging import Formatter
default_log_format = Formatter(
    '[%(asctime)s][%(levelname)6s][%(name)10s][%(filename)s:%(funcName)s:%(lineno)d] %(message)s')
build_log_format = Formatter(
    '[%(asctime)s][%(levelname)6s][PID:%(process)d] %(message)s')
