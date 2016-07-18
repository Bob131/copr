from io import BytesIO
from zlib import compress, decompress

import flask
from flask import Response, url_for, render_template

from coprs import db
from coprs import forms
from coprs.exceptions import AccessRestricted

from coprs.logic import coprs_logic
from coprs.logic.complex_logic import ComplexLogic
from coprs.logic.coprs_logic import CoprChrootsLogic
from coprs.views.coprs_ns.coprs_general import url_for_copr_edit

from coprs.views.misc import login_required, page_not_found, req_with_copr, req_with_copr
from coprs.views.coprs_ns import coprs_ns


@coprs_ns.route("/<username>/<coprname>/edit_chroot/<chrootname>/")
@login_required
@req_with_copr
def chroot_edit(copr, chrootname):
    return render_chroot_edit(copr, chrootname)


@coprs_ns.route("/g/<group_name>/<coprname>/edit_chroot/<chrootname>/")
@login_required
@req_with_copr
def group_chroot_edit(copr, chrootname):
    return render_chroot_edit(copr, chrootname)


def render_chroot_edit(copr, chroot_name):
    chroot = ComplexLogic.get_copr_chroot_safe(copr, chroot_name)

    # todo: get COPR_chroot, not mock chroot, WTF?!
    # form = forms.ChrootForm(buildroot_pkgs=copr.buildroot_pkgs(chroot))

    form = forms.ChrootForm(buildroot_pkgs=chroot.buildroot_pkgs)
    # FIXME - test if chroot belongs to copr
    if flask.g.user.can_build_in(copr):
        return render_template("coprs/detail/edit_chroot.html",
                               form=form, copr=copr, chroot=chroot)
    else:
        raise AccessRestricted(
            "You are not allowed to modify chroots in project {0}."
            .format(copr.name))


@coprs_ns.route("/<username>/<coprname>/update_chroot/<chrootname>/",
                methods=["POST"])
@login_required
@req_with_copr
def chroot_update(copr, chrootname):
    return process_chroot_update(copr, chrootname)


@coprs_ns.route("/g/<group_name>/<coprname>/update_chroot/<chrootname>/",
                methods=["POST"])
@login_required
@req_with_copr
def group_chroot_update(copr, chrootname):
    return process_chroot_update(copr, chrootname)


def process_chroot_update(copr, chroot_name):

    form = forms.ChrootForm()
    chroot = ComplexLogic.get_copr_chroot_safe(copr, chroot_name)

    if not flask.g.user.can_build_in(copr):
        raise AccessRestricted(
            "You are not allowed to modify chroots in project {0}."
            .format(copr.name))

    if form.validate_on_submit():
        if "submit" in flask.request.form:
            action = flask.request.form["submit"]
            if action == "update":
                comps_name = comps_xml = None
                module_md_name = module_md = None

                if form.comps.has_file():
                    comps_xml = form.comps.data.stream.read()
                    comps_name = form.comps.data.filename

                if form.module_md.has_file():
                    module_md = form.module_md.data.stream.read()
                    module_md_name = form.module_md.data.filename

                coprs_logic.CoprChrootsLogic.update_chroot(
                    flask.g.user, chroot, form.buildroot_pkgs.data,
                    comps=comps_xml, comps_name=comps_name,
                    module_md=module_md, module_md_name=module_md_name
                )

            elif action == "delete_comps":
                CoprChrootsLogic.remove_comps(flask.g.user, chroot)

            elif action == "delete_module_md":
                CoprChrootsLogic.remove_module_md(flask.g.user, chroot)

            flask.flash(
                "Buildroot {0} in project {1} has been updated successfully.".format(
                    chroot_name, copr.name))

            db.session.commit()
        return flask.redirect(url_for_copr_edit(copr))

    else:
        flask.flash("You are not allowed to modify chroots.")
        return render_chroot_edit(copr, chroot_name)


@coprs_ns.route("/<username>/<coprname>/chroot/<chrootname>/comps/")
@req_with_copr
def chroot_view_comps(copr, chrootname):
    return render_chroot_view_comps(copr, chrootname)


@coprs_ns.route("/g/<group_name>/<coprname>/chroot/<chrootname>/comps/")
@req_with_copr
def group_chroot_view_comps(copr, chrootname):
    return render_chroot_view_comps(copr, chrootname)


def render_chroot_view_comps(copr, chroot_name):
    chroot = ComplexLogic.get_copr_chroot_safe(copr, chroot_name)
    return Response(chroot.comps or "", mimetype="text/plain; charset=utf-8")


@coprs_ns.route("/<username>/<coprname>/chroot/<chrootname>/module_md/")
@req_with_copr
def chroot_view_module_md(copr, chrootname):
    return render_chroot_view_module_md(copr, chrootname)


@coprs_ns.route("/g/<group_name>/<coprname>/chroot/<chrootname>/module_md/")
@req_with_copr
def group_chroot_view_module_md(copr, chrootname):
    return render_chroot_view_module_md(copr, chrootname)


def render_chroot_view_module_md(copr, chroot_name):
    chroot = ComplexLogic.get_copr_chroot_safe(copr, chroot_name)
    return Response(chroot.module_md or "", mimetype="text/plain; charset=utf-8")
