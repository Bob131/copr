import os
import sys
import logging
import shutil
import subprocess
from threading import Timer

from jinja2 import Environment, FileSystemLoader
from ..helpers import run_cmd, locate_spec, locate_srpm, CONF_DIRS, get_mock_uniqueext

log = logging.getLogger("__main__")


class GentlyTimeoutedPopen(subprocess.Popen):
    timers = []

    def __init__(self, cmd, timeout=None, **kwargs):
        super(GentlyTimeoutedPopen, self).__init__(cmd, **kwargs)
        if not timeout:
            return

        def timeout_cb(me, string, signal):
            log.error(" !! Copr timeout => sending {0}".format(string))
            me.send_signal(signal)

        delay = timeout
        for string, signal in [('INT', 2), ('TERM', 15), ('KILL', 9)]:
            timer = Timer(delay, timeout_cb, [self, string, signal])
            timer.start()
            self.timers.append(timer)
            delay = delay + 10

    def done(self):
        for timer in self.timers:
            timer.cancel()


class MockBuilder(object):
    def __init__(self, task, sourcedir, resultdir, config):
        self.task_id = task.get("task_id")
        self.chroot = task.get("chroot")
        self.buildroot_pkgs = task.get("buildroot_pkgs")
        self.enable_net = task.get("enable_net")
        self.repos = task.get("repos")
        self.use_bootstrap_container = task.get("use_bootstrap_container")
        self.pkg_manager_conf = "dnf" if "custom-1" in task.get("chroot") else "yum"
        self.timeout = task.get("timeout", 3600)
        self.with_opts = task.get("with_opts")
        self.without_opts = task.get("without_opts")
        self.sourcedir = sourcedir
        self.resultdir = resultdir
        self.config = config
        self.logfile = self.config.get("main", "logfile")
        log.info(self.__dict__)

    def run(self):
        configdir = os.path.join(self.resultdir, "configs")
        os.makedirs(configdir)
        shutil.copy2("/etc/mock/site-defaults.cfg", configdir)
        shutil.copy2("/etc/mock/{0}.cfg".format(self.chroot), configdir)
        cfg = self.render_config_template()
        with open(os.path.join(configdir, "child.cfg"), "w") as child:
            child.write(cfg)

        open(self.logfile, 'w').close() # truncate logfile

        spec = locate_spec(self.sourcedir)
        shutil.copy(spec, self.resultdir)
        self.produce_srpm(spec, self.sourcedir, configdir, self.resultdir)

        srpm = locate_srpm(self.resultdir)
        self.produce_rpm(srpm, configdir, self.resultdir)

    def render_config_template(self):
        jinja_env = Environment(loader=FileSystemLoader(CONF_DIRS))
        template = jinja_env.get_template("mock.cfg.j2")
        return template.render(chroot=self.chroot, task_id=self.task_id, buildroot_pkgs=self.buildroot_pkgs,
                               enable_net=self.enable_net, use_bootstrap_container=self.use_bootstrap_container,
                               repos=self.repos, pkg_manager_conf=self.pkg_manager_conf)

    def preexec_fn_build_stream(self):
        if not self.logfile:
            return
        filter_continuing_lines = r"sed 's/.*\x0D\([^\x0a]\)/\1/g' --unbuffered"
        tee_output = "tee -a {}".format(self.logfile)
        cmd = filter_continuing_lines + "|" + tee_output
        tee = subprocess.Popen(cmd, stdin=subprocess.PIPE, shell=True)
        os.dup2(tee.stdin.fileno(), sys.stdout.fileno())
        os.dup2(tee.stdin.fileno(), sys.stderr.fileno())

    def produce_srpm(self, spec, sources, configdir, resultdir):
        cmd = [
            "unbuffer", "/usr/bin/mock",
            "--buildsrpm",
            "--spec", spec,
            "--sources", sources,
            "--configdir", configdir,
            "--resultdir", resultdir,
            "--define", "%_disable_source_fetch 0",
            "--uniqueext", get_mock_uniqueext(),
            "-r", "child"]

        for with_opt in self.with_opts:
            cmd += ["--with", with_opt]

        for without_opt in self.without_opts:
            cmd += ["--without", without_opt]

        log.info('Running: {}'.format(' '.join(cmd)))

        process = GentlyTimeoutedPopen(cmd, stdin=subprocess.PIPE,
                preexec_fn=self.preexec_fn_build_stream, timeout=self.timeout)

        try:
            process.communicate()
        except OSError as e:
            raise RuntimeError(str(e))
        finally:
            process.done()

        if process.returncode != 0:
            raise RuntimeError("Build failed")

    def produce_rpm(self, srpm, configdir, resultdir):
        cmd = ["unbuffer", "/usr/bin/mock",
               "--rebuild", srpm,
               "--configdir", configdir,
               "--resultdir", resultdir,
               "--uniqueext", get_mock_uniqueext(),
               "-r", "child"]

        for with_opt in self.with_opts:
            cmd += ["--with", with_opt]

        for without_opt in self.without_opts:
            cmd += ["--without", without_opt]

        log.info('Running: {}'.format(' '.join(cmd)))

        process = GentlyTimeoutedPopen(cmd, stdin=subprocess.PIPE,
                preexec_fn=self.preexec_fn_build_stream, timeout=self.timeout)

        try:
            process.communicate()
        except OSError as e:
            raise RuntimeError(str(e))
        finally:
            process.done()

        if process.returncode != 0:
            raise RuntimeError("Build failed")

    def touch_success_file(self):
        with open(os.path.join(self.resultdir, "success"), "w") as success:
            success.write("done")
