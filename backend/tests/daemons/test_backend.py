import os
import tempfile
import shutil
import time

from munch import Munch

import pytest
import retask
from retask import ConnectionError
import six
import sys

from backend.daemons.backend import CoprBackend, run_backend
from backend.exceptions import CoprBackendError

if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock


STDOUT = "stdout"
STDERR = "stderr"
COPR_OWNER = "copr_owner"
COPR_NAME = "copr_name"
COPR_VENDOR = "vendor"

MODULE_REF = "backend.daemons.backend"

@pytest.yield_fixture
def mc_rt_channel():
    with mock.patch("{}.jobgrabcontrol.Channel".format(MODULE_REF)) as mc_channel:
        yield mc_channel

@pytest.yield_fixture
def mc_worker():
    with mock.patch("{}.Worker".format(MODULE_REF)) as worker:
        yield worker

@pytest.yield_fixture
def mc_time():
    with mock.patch("{}.time".format(MODULE_REF)) as time_:
        yield time_

@pytest.yield_fixture
def mc_be():
    with mock.patch("{}.CoprBackend".format(MODULE_REF)) as obj:
        yield obj

@pytest.yield_fixture
def mc_daemon_context():
    with mock.patch("{}.DaemonContext".format(MODULE_REF)) as obj:
        yield obj


class TestBackend(object):

    def setup_method(self, method):
        self.test_time = time.time()
        subdir = "test_createrepo_{}".format(time.time())
        self.tmp_dir_path = os.path.join(tempfile.gettempdir(), subdir)
        os.mkdir(self.tmp_dir_path)

        self.bc_patcher = mock.patch("backend.daemons.backend.BackendConfigReader")
        self.bc = self.bc_patcher.start()

        self.config_file = "/dev/null/copr.conf"
        self.ext_opts = {}

        # effective config options
        self.bc_obj = MagicMock()

        self.opts = Munch(
            build_groups=[
                {
                    "id": 0,
                    "name": "PC",
                    "archs": ["i386", "x86_64"],
                    "max_workers": 2
                },
                {
                    "id": 1,
                    "name": "ARM",
                    "archs": ["armv7"],
                    "max_workers": 3
                },
            ],
            exit_on_worker=False,
            sleeptime=1,
            frontend_base_url="http://example.com",
            frontend_auth="foobar",

            log_dir=self.tmp_dir_path,
            log_level="info",

            redis_host="127.0.0.1",
            redis_port=6379,
            redis_db=0,
        )
        self.bc_obj.read.return_value = self.opts
        self.bc.return_value = self.bc_obj

        # for run backend
        self.pidfile_path = os.path.join(self.tmp_dir_path, "backend.pid")
        self.grp_patcher = mock.patch("backend.daemons.backend.grp")
        self.pwd_patcher = mock.patch("backend.daemons.backend.pwd")
        self.grp = self.grp_patcher.start()
        self.pwd = self.pwd_patcher.start()

        self.run_opts = Munch(
            daemonize=True,
            pidfile=self.pidfile_path,
            config_file=self.config_file,

            daemon_user="foo",
            daemon_group="bar",

        )

    @pytest.fixture
    def init_be(self):
        self.be = CoprBackend(self.config_file, self.ext_opts)
        self.be.log = MagicMock()

    def teardown_method(self, method):
        # print("\nremove: {}".format(self.tmp_dir_path))
        shutil.rmtree(self.tmp_dir_path)
        self.bc_patcher.stop()
        self.grp_patcher.stop()
        self.pwd_patcher.stop()

    def test_constructor_no_config(self):
        with pytest.raises(CoprBackendError):
            self.be = CoprBackend(None, self.ext_opts)

    def test_constructor(self):
        self.init_be()
        assert self.be.config_reader == self.bc_obj
        assert self.bc_obj.read.called

    def test_init_task_queues(self, mc_rt_channel, init_be):
        self.be.jg_control = MagicMock()
        self.be.init_task_queues()
        assert self.be.jg_control.backend_start.called

    def test_update_conf(self, init_be):
        test_obj = MagicMock()
        self.bc_obj.read.return_value = test_obj

        self.be.update_conf()
        assert self.bc_obj.read.called
        assert self.be.opts == test_obj

    def test_spin_up_workers_by_group(self, mc_worker, init_be):
        worker = MagicMock()
        mc_worker.return_value = worker

        group = self.opts.build_groups[0]
        self.be.spin_up_workers_by_group(group)

        assert mc_worker.called
        assert len(mc_worker.call_args_list) == group["max_workers"]
        assert worker.start.called
        assert len(worker.start.call_args_list) == group["max_workers"]
        assert len(self.be.workers_by_group_id[0]) == group["max_workers"]

    def test_spin_up_workers_by_group_partial(self, mc_worker, init_be):
        worker = MagicMock()
        mc_worker.return_value = worker

        group = self.opts.build_groups[1]

        self.be.workers_by_group_id[1].append(worker)
        self.be.spin_up_workers_by_group(group)

        assert mc_worker.called
        assert len(mc_worker.call_args_list) == group["max_workers"] - 1
        assert worker.start.called
        assert len(worker.start.call_args_list) == group["max_workers"] - 1
        assert len(self.be.workers_by_group_id[1]) == group["max_workers"]

    def test_prune_dead_workers_by_group(self, init_be):
        worker_alive = MagicMock()
        worker_alive.is_alive.return_value = True
        worker_dead = MagicMock()
        worker_dead.is_alive.return_value = False


        self.be.workers_by_group_id[0].append(worker_alive)
        self.be.workers_by_group_id[0].append(worker_dead)

        self.be.prune_dead_workers_by_group_id(0)

        assert len(self.be.workers_by_group_id) == 1
        assert worker_dead.terminate.called
        assert not worker_alive.terminate.called

    def test_prune_dead_workers_by_group_terminate(self, init_be):
        worker_alive = MagicMock()
        worker_alive.is_alive.return_value = True
        worker_dead = MagicMock()
        worker_dead.is_alive.return_value = False

        self.be.workers_by_group_id[0].append(worker_alive)
        self.be.workers_by_group_id[0].append(worker_dead)

        self.be.opts.exit_on_worker = True

        with pytest.raises(CoprBackendError):
            self.be.prune_dead_workers_by_group_id(0)

        assert len(self.be.workers_by_group_id) == 1
        assert worker_dead.terminate.called
        assert not worker_alive.terminate.called

    def test_terminate(self, init_be):
        worker_alive = MagicMock()
        worker_alive.is_alive.return_value = True
        worker_dead = MagicMock()
        worker_dead.is_alive.return_value = False

        self.be.workers_by_group_id[0].append(worker_alive)
        self.be.workers_by_group_id[0].append(worker_dead)

        self.be.clean_task_queues = MagicMock()
        self.be.frontend_client = MagicMock()

        self.be.terminate()

        assert not self.be.is_running
        assert worker_alive.terminate_instance.called
        assert worker_dead.terminate_instance.called

    def test_run(self, mc_time, mc_rt_channel, init_be):
        worker_alive = MagicMock()
        worker_alive.is_alive.return_value = True
        worker_dead = MagicMock()
        worker_dead.is_alive.return_value = False

        self.be.clean_task_queues = MagicMock()
        self.be.update_conf = MagicMock()
        self.be.spin_up_workers_by_group = MagicMock()
        self.be.frontend_client = MagicMock()

        def spin_up():
            self.be.workers_by_group_id[0].append(worker_alive)
            self.be.workers_by_group_id[0].append(worker_dead)
            self.be.workers_by_group_id[1].append(worker_alive)
            self.be.workers_by_group_id[1].append(worker_dead)

        self.be.spin_up_workers_by_group = MagicMock()
        self.be.spin_up_workers_by_group.side_effect = lambda foo: spin_up()
        mc_time.sleep.side_effect = lambda foo: self.be.terminate()

        self.be.run()
        assert self.be.spin_up_workers_by_group.call_args_list == [
            mock.call(self.opts.build_groups[0]),
            mock.call(self.opts.build_groups[1]),
        ]
        assert self.be.update_conf.called
        assert not self.be.is_running
        assert not self.be.workers_by_group_id[0]
        assert not self.be.workers_by_group_id[1]

    def test_run_backend_basic(self, mc_be, mc_daemon_context):
        self.grp.getgrnam.return_value.gr_gid = 7
        self.pwd.getpwnam.return_value.pw_uid = 9

        run_backend(self.run_opts)
        ddc = mc_daemon_context.call_args[1]
        assert ddc["signal_map"] == {1: u'terminate', 15: u'terminate'}
        assert ddc["umask"] == 0o22
        assert ddc["gid"] == 7
        assert ddc["uid"] == 9
        assert ddc["stderr"] == sys.stderr

        assert mc_be.called
        expected_call = mock.call(self.config_file, ext_opts=self.run_opts)
        assert mc_be.call_args == expected_call

    def test_run_backend_keyboard_interrupt(self, mc_be, mc_daemon_context, capsys):
        mc_be.return_value.run.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            run_backend(self.run_opts)

        stdout, stderr = capsys.readouterr()
        assert "Killing/Dying" in stderr
