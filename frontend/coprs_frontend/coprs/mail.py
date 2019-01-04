import flask
import platform
import smtplib
from email.mime.text import MIMEText
from coprs import app, helpers


class Message(object):
    subject = None
    text = None


class PermissionRequestMessage(Message):
    def __init__(self, copr, applicant, permission_dict):
        """
        :param models.Copr copr:
        :param models.User applicant: object of a user that applies for new permissions (e.g. flask.g.user)
        :param models.CoprPermission permission: permission object
        :param dict permission_dict: {"old_builder": int, "old_admin": int, "new_builder": int, "new_admin": int}
        """
        self.subject = "[Copr] {0}: {1} is asking permissions".format(copr.name, applicant.name)
        self.text = ("{0} is asking for these permissions:\n\n"
                     "Builder: {1} -> {2}\n"
                     "Admin: {3} -> {4}\n\n"
                     "Project: {5}\n"
                     "Owner: {6}".format(
                         applicant.name,
                         helpers.PermissionEnum(permission_dict.get("old_builder", 0)),
                         helpers.PermissionEnum(permission_dict.get("new_builder")),
                         helpers.PermissionEnum(permission_dict.get("old_admin", 0)),
                         helpers.PermissionEnum(permission_dict.get("new_admin")),
                         copr.name,
                         copr.owner_name))


class PermissionChangeMessage(Message):
    def __init__(self, copr, permission_dict):
        """
        :param models.Copr copr:
        :param dict permission_dict: {"old_builder": int, "old_admin": int, "new_builder": int, "new_admin": int}
        """
        self.subject = "[Copr] {0}: Your permissions have changed".format(copr.name)
        self.text = (
            "Your permissions have changed:\n\n"
            "Builder: {0} -> {1}\n"
            "Admin: {2} -> {3}\n\n"
            "Project: {4}\n"
            "Owner: {5}".format(
                helpers.PermissionEnum(permission_dict["old_builder"]),
                helpers.PermissionEnum(permission_dict["new_builder"]),
                helpers.PermissionEnum(permission_dict["old_admin"]),
                helpers.PermissionEnum(permission_dict["new_admin"]),
                copr.name, copr.user.name))


class LegalFlagMessage(Message):
    def __init__(self, copr, reporter, reason):
        """
        :param models.Copr copr:
        :param models.User reporter: A person who reported the legal issue (e.g. flask.g.user)
        :param str reason: What is the legal issue?
        """
        self.subject = "Legal flag raised on {0}".format(copr.name)
        self.text = ("{0}\n"
                     "Navigate to {1}\n"
                     "Contact on owner is: {2} <{3}>\n"
                     "Reported by {4} <{5}>".format(
                        reason,
                        flask.url_for("admin_ns.legal_flag", _external=True),
                        copr.user.username,
                        copr.user.mail,
                        reporter.name,
                        reporter.mail))


class OutdatedChrootMessage(Message):
    def __init__(self, copr_chroots):
        """
        :param models.Copr copr:
        :param list copr_chroots: list of models.CoprChroot instances
        """
        self.subject = "Upcoming deletion of outdated chroots in your projects"
        self.text = ("You have been notified because you are an admin of projects,"
                     "that have some builds in outdated chroots\n\n"

                     "According to the 'Copr outdated chroots removal policy'\n"
                     "https://docs.pagure.org/copr.copr/copr_outdated_chroots_removal_policy.html\n"
                     "data are going to be preserved {0} days after the chroot is EOL"
                     "and then automatically deleted, unless you decide to prolong the expiration period.\n\n"

                     "Please, visit the projects settings if you want to extend the time.\n\n"
                     .format(app.config["DELETE_EOL_CHROOTS_AFTER"]))

        for chroot in copr_chroots:
            self.text += (
                "Project: {0}\n"
                "Chroot: {1}\n"
                "Remaining: {2} days\n"
                "{3}\n\n".format(chroot.copr.full_name, chroot.name, chroot.delete_after_days,
                                 helpers.copr_url('coprs_ns.copr_repositories', chroot.copr, _external=True)))


def send_mail(recipient, message, sender=None):
    """
    :param str/list recipient: One recipient email as a string or multiple emails in a list
    :param Message message:
    :param str sender: Email of a sender
    :return:
    """
    msg = MIMEText(message.text)
    msg["Subject"] = message.subject
    msg["From"] = sender or "root@{0}".format(platform.node())
    msg["To"] = ", ".join(recipient) if type(recipient) == list else recipient
    s = smtplib.SMTP("localhost")
    s.sendmail("root@{0}".format(platform.node()), recipient, msg.as_string())
    s.quit()