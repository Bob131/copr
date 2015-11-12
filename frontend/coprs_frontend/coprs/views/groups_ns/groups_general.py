# coding: utf-8

import flask
from flask import render_template, session, url_for
from coprs.exceptions import InsufficientRightsException
from coprs.forms import ActivateFasGroupForm
from coprs.helpers import Paginator
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.coprs_logic import CoprsLogic
from coprs.logic.users_logic import UsersLogic

from ... import db
from ..misc import login_required

from . import groups_ns


@groups_ns.route("/activate/<fas_group>", methods=["GET", "POST"])
@login_required
def activate_group(fas_group):
    form = ActivateFasGroupForm()

    if form.validate_on_submit():
        if UsersLogic.is_blacklisted_group(fas_group):
            flask.flash("This group is blacklisted and cannot be added.")
            return flask.redirect(url_for(
                "groups_ns.list_user_groups"))

        if fas_group not in flask.g.user.user_teams:
            raise InsufficientRightsException(
                "User '{}' doesn't have access to fas group {}"
                .format(flask.g.user.username, fas_group))

        alias = form.name.data
        group = UsersLogic.get_group_by_fas_name_or_create(
            fas_group, alias)

        db.session.add(group)
        db.session.commit()

        flask.flash(
            "FAS group {} is activated in the Copr under the alias {} "
            .format(fas_group, alias)
        )
        return flask.redirect(url_for(
            "groups_ns.list_projects_by_group", group_name=alias))

    else:
        return flask.render_template(
            "groups/activate_fas_group.html",
            fas_group=fas_group,
            form=form,
            user=flask.g.user,
        )


@groups_ns.route("/g/<group_name>/coprs/", defaults={"page": 1})
@groups_ns.route("/g/<group_name>/coprs/<int:page>")
def list_projects_by_group(group_name, page=1):
    group = ComplexLogic.get_group_by_name_safe(group_name)
    query = CoprsLogic.get_multiple_by_group_id(group.id)

    paginator = Paginator(query, query.count(), page)

    coprs = paginator.sliced_query

    return render_template(
        "coprs/show/group.html",
        user=flask.g.user,
        coprs=coprs,
        paginator=paginator,
        tasks_info=ComplexLogic.get_queues_size(),
        group=group
    )


@groups_ns.route("/list/my")
@login_required
def list_user_groups():
    teams = flask.g.user.user_teams
    active_map = {
        group.fas_name: group.name for group in
        UsersLogic.get_groups_by_fas_names_list(teams).all()
    }

    teams = UsersLogic.filter_blacklisted_teams(teams)
    copr_groups = {
        fas_name: active_map.get(fas_name)
        for fas_name in teams
    }
    return render_template(
        "groups/user_fas_groups.html",
        user=flask.g.user,
        teams=teams,
        copr_groups=copr_groups)

