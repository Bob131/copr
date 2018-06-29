import flask
from time import time

from coprs.views.status_ns import status_ns
from coprs.logic import builds_logic
from coprs import helpers


@status_ns.route("/")
@status_ns.route("/pending/")
def pending():
    tasks = builds_logic.BuildsLogic.get_pending_build_tasks(background=False).limit(300).all()
    bg_tasks_cnt = builds_logic.BuildsLogic.get_pending_build_tasks(background=True).count()
    return flask.render_template("status/pending.html",
                                 number=len(tasks),
                                 tasks=tasks, bg_tasks_cnt=bg_tasks_cnt)


@status_ns.route("/running/")
def running():
    tasks = builds_logic.BuildsLogic.get_build_tasks(helpers.StatusEnum("running")).limit(300).all()
    return flask.render_template("status/running.html",
                                 number=len(tasks),
                                 tasks=tasks)


@status_ns.route("/importing/")
def importing():
    tasks = builds_logic.BuildsLogic.get_build_importing_queue(background=False).limit(300).all()
    bg_tasks_cnt = builds_logic.BuildsLogic.get_build_importing_queue(background=True).count()
    return flask.render_template("status/importing.html",
                                 number=len(list(tasks)),
                                 bg_tasks_cnt=bg_tasks_cnt,
                                 tasks=tasks)


@status_ns.route("/stats/")
def stats():
    curr_time = int(time())
    chroots_24h = builds_logic.BuildsLogic.get_chroot_histogram(curr_time - 86400, curr_time)
    chroots_90d = builds_logic.BuildsLogic.get_chroot_histogram(curr_time - 90*86400, curr_time)
    data_24h = builds_logic.BuildsLogic.get_tasks_histogram('10min', curr_time - 86400, curr_time, 600)
    data_90d = builds_logic.BuildsLogic.get_tasks_histogram('24h', curr_time - 90*86400, curr_time, 86400)

    return flask.render_template("status/stats.html",
                                 data1=data_24h,
                                 data2=data_90d,
                                 chroots1=chroots_24h,
                                 chroots2=chroots_90d)
