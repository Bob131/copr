import ujson as json
from coprs import exceptions
from flask import url_for

from coprs import app, db
from coprs.models import User, Group
from coprs.helpers import copr_url
from sqlalchemy import update


class UsersLogic(object):

    @classmethod
    def get(cls, username):
        return User.query.filter(User.username == username)

    @classmethod
    def get_by_api_login(cls, login):
        return User.query.filter(User.api_login == login)

    @classmethod
    def raise_if_cant_update_copr(cls, user, copr, message):
        """
        Raise InsufficientRightsException if given user cant update
        given copr. Return None otherwise.
        """

        # TODO: this is a bit inconsistent - shouldn't the user method be
        # called can_update?
        if not user.can_edit(copr):
            raise exceptions.InsufficientRightsException(message)

    @classmethod
    def raise_if_cant_build_in_copr(cls, user, copr, message):
        """
        Raises InsufficientRightsException if given user cant build in
        given copr. Return None otherwise.
        """

        if not user.can_build_in(copr):
            raise exceptions.InsufficientRightsException(message)

    @classmethod
    def raise_if_not_in_group(cls, user, group):
        if group.fas_name not in user.user_teams:
            raise exceptions.InsufficientRightsException(
                "User '{}' doesn't have access to group {}({})"
                .format(user.username, group.name, group.fas_name))

    @classmethod
    def get_group_by_alias(cls, name):
        return Group.query.filter(Group.name == name)

    @classmethod
    def group_alias_exists(cls, name):
        query = cls.get_group_by_alias(name)
        return query.count() != 0

    @classmethod
    def get_group_by_fas_name(cls, fas_name):
        return Group.query.filter(Group.fas_name == fas_name)

    @classmethod
    def get_groups_by_fas_names_list(cls, fas_name_list):
        return Group.query.filter(Group.fas_name.in_(fas_name_list))

    @classmethod
    def get_groups_by_names_list(cls, name_list):
        return Group.query.filter(Group.name.in_(name_list))

    @classmethod
    def create_group_by_fas_name(cls, fas_name, alias=None):
        if alias is None:
            alias = fas_name

        group = Group(
            fas_name=fas_name,
            name=alias,
        )
        db.session.add(group)
        return group

    @classmethod
    def get_group_by_fas_name_or_create(cls, fas_name, alias=None):
        mb_group = cls.get_group_by_fas_name(fas_name).first()
        if mb_group is not None:
            return mb_group

        group = cls.create_group_by_fas_name(fas_name, alias)
        db.session.flush()
        return group

    @classmethod
    def filter_blacklisted_teams(cls, teams):
        """ removes blacklisted groups from teams list
            :type teams: list of str
            :return: filtered teams
            :rtype: list of str
        """
        blacklist = set(app.config.get("BLACKLISTED_GROUPS", []))
        return filter(lambda t: t not in blacklist, teams)

    @classmethod
    def is_blacklisted_group(cls, fas_group):
        if "BLACKLISTED_GROUPS" in app.config:
            return fas_group in app.config["BLACKLISTED_GROUPS"]
        else:
            return False

    @classmethod
    def delete_user_data(cls, fas_name):
        query = update(User).where(User.username==fas_name).\
            values(
                timezone=None,
                proven=False,
                admin=False,
                proxy=False,
                api_login='',
                api_token='',
                api_token_expiration='1970-01-01',
                openid_groups=None
            )
        db.engine.connect().execute(query)


class UserDataDumper(object):
    def __init__(self, user):
        self.user = user

    def dumps(self, pretty=False):
        if pretty:
            return json.dumps(self.data, indent=2)
        return json.dumps(self.data)

    @property
    def data(self):
        data = self.user_information
        data["groups"] = self.groups
        data["projects"] = self.projects
        data["builds"] = self.builds
        return data

    @property
    def user_information(self):
        return {
            "username": self.user.name,
            "email": self.user.mail,
            "timezone": self.user.timezone,
            "api_login": self.user.api_login,
            "api_token": self.user.api_token,
            "api_token_expiration": self.user.api_token_expiration.strftime("%b %d %Y %H:%M:%S"),
            "gravatar": self.user.gravatar_url,
        }

    @property
    def groups(self):
        return [{"name": g.name,
                 "url": url_for("groups_ns.list_projects_by_group", group_name=g.name, _external=True)}
                for g in self.user.user_groups]

    @property
    def projects(self):
        # @FIXME We get into circular import when this import is on module-level
        from coprs.logic.coprs_logic import CoprsLogic
        return [{"full_name": p.full_name,
                 "url": copr_url("coprs_ns.copr_detail", p, _external=True)}
                for p in CoprsLogic.filter_by_user_name(CoprsLogic.get_multiple(), self.user.name)]

    @property
    def builds(self):
        return [{"id": b.id,
                 "project": b.copr.full_name,
                 "url": copr_url("coprs_ns.copr_build", b.copr, build_id=b.id, _external=True)}
                for b in self.user.builds]
