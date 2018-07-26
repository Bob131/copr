import flask
import wtforms
from . import query_params, pagination, get_copr, Paginator
from .json2form import get_form_compatible_data
from coprs.exceptions import ApiError
from coprs.exceptions import ApiError, InsufficientRightsException, ActionInProgressException, NoPackageSourceException
from coprs.views.misc import api_login_required
from coprs import db, models, forms
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.packages_logic import PackagesLogic

# @TODO if we need to do this on several places, we should figure a better way to do it
from coprs.views.apiv3_ns.apiv3_builds import to_dict as build_to_dict

# @TODO Don't import things from APIv1
from coprs.views.api_ns.api_general import process_package_add_or_edit


def to_dict(package):
    # @TODO review the fields
    api_keys = ["id", "name", "enable_net", "old_status", "source_type", "webhook_rebuild"]
    package_dict = {k: v for k, v in package.to_dict().items() if k in api_keys}
    package_dict.update({
        "copr": package.copr.name,
        "owner": package.copr.owner_name,
        "source_dict": package.source_json_dict,
    })
    return package_dict


@apiv3_ns.route("/package", methods=["GET"])
@query_params()
def get_package(ownername, projectname, packagename):
    copr = get_copr(ownername, projectname)
    try:
        package = PackagesLogic.get(copr.id, packagename)[0]
    except IndexError:
        raise ApiError("No package with name {name} in copr {copr}".format(name=packagename, copr=copr.name))
    return flask.jsonify(to_dict(package))


@apiv3_ns.route("/package/list/", methods=["GET"])
@pagination()
@query_params()
def get_package_list(ownername, projectname, **kwargs):
    copr = get_copr(ownername, projectname)
    paginator = Paginator(PackagesLogic.get_all(copr.id), models.Package, **kwargs)
    packages = paginator.map(to_dict)
    return flask.jsonify(items=packages, meta=paginator.meta)


@apiv3_ns.route("/package/add", methods=["POST"])
@query_params()
@api_login_required
def package_add(ownername, projectname, package_name, source_type_text):
    copr = get_copr(ownername, projectname)
    process_package_add_or_edit(copr, source_type_text)
    package = PackagesLogic.get(copr.id, package_name).first()
    return flask.jsonify(to_dict(package))


@apiv3_ns.route("/package/edit", methods=["POST"])
@query_params()
@api_login_required
def package_edit(ownername, projectname, package_name, source_type_text=None):
    copr = get_copr(ownername, projectname)
    try:
        package = PackagesLogic.get(copr.id, package_name)[0]
        source_type_text = source_type_text or package.source_type_text
    except IndexError:
        raise ApiError("Package {name} does not exists in copr {copr}."
                       .format(name=package_name, copr=copr.full_name))

    process_package_add_or_edit(copr, source_type_text, package=package)
    return flask.jsonify(to_dict(package))


@apiv3_ns.route("/package/reset", methods=["POST"])
@api_login_required
def package_reset():
    copr = get_copr()
    form = forms.BasePackageForm()
    try:
        package = PackagesLogic.get(copr.id, form.package_name.data)[0]
    except IndexError:
        raise ApiError("No package with name {name} in copr {copr}"
                       .format(name=form.package_name.data, copr=copr.name))
    try:
        PackagesLogic.reset_package(flask.g.user, package)
        db.session.commit()
    except InsufficientRightsException as e:
        raise ApiError(str(e))

    return flask.jsonify(to_dict(package))


@apiv3_ns.route("/package/build", methods=["POST"])
@api_login_required
def package_build():
    copr = get_copr()
    data = get_form_compatible_data()
    form = forms.RebuildPackageFactory.create_form_cls(copr.active_chroots)(data, csrf_enabled=False)
    try:
        package = PackagesLogic.get(copr.id, form.package_name.data)[0]
    except IndexError:
        raise ApiError("No package with name {name} in copr {copr}"
                             .format(name=form.package_name.data, copr=copr.name))
    if form.validate_on_submit():
        try:
            build = PackagesLogic.build_package(flask.g.user, copr, package, form.selected_chroots, **form.data)
            db.session.commit()
        except (InsufficientRightsException, ActionInProgressException, NoPackageSourceException) as e:
            raise ApiError(str(e))
    else:
        raise ApiError(form.errors)
    return flask.jsonify(build_to_dict(build))


@apiv3_ns.route("/package/delete", methods=["POST"])
@api_login_required
def package_delete():
    copr = get_copr()
    form = forms.BasePackageForm()
    try:
        package = PackagesLogic.get(copr.id, form.package_name.data)[0]
    except IndexError:
        raise ApiError("No package with name {name} in copr {copr}"
                             .format(name=form.package_name.data, copr=copr.name))

    try:
        PackagesLogic.delete_package(flask.g.user, package)
        db.session.commit()
    except (InsufficientRightsException, ActionInProgressException) as e:
        raise ApiError(str(e))

    return flask.jsonify(to_dict(package))
