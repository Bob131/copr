import json

from tests.coprs_test_case import CoprsTestCase
from coprs.logic.builds_logic import BuildsLogic
from coprs import helpers


class TestWaitingBuilds(CoprsTestCase):

    def test_no_pending_builds(self):
        assert b'[]' in self.tc.get(
            "/backend/pending-jobs/", headers=self.auth_header).data

    def test_pending_build_only_lists_not_started_or_ended(
            self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):

        for build_chroots in [self.b2_bc, self.b3_bc, self.b4_bc]:
            for build_chroot in build_chroots:
                build_chroot.status = 3 # running

        for build_chroot in self.b1_bc:
            build_chroot.status = 0 # failed

        self.db.session.commit()

        r = self.tc.get("/backend/pending-jobs/", headers=self.auth_header)
        assert json.loads(r.data.decode("utf-8")) == []

        for build_chroot in self.b2_bc:
            build_chroot.status = 4 # pending
            self.db.session.add(build_chroot)

        self.db.session.commit()

        r = self.tc.get("/backend/pending-jobs/", headers=self.auth_header)
        assert json.loads(r.data.decode("utf-8")) != []


    def test_pending_bg_build(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        self.b2.is_background = True
        for build_chroots in [self.b2_bc, self.b3_bc, self.b4_bc]:
            for build_chroot in build_chroots:
                build_chroot.status = 4  # pending
        self.db.session.commit()

        r = self.tc.get("/backend/pending-jobs/")
        data = json.loads(r.data.decode("utf-8"))
        assert data[0]["build_id"] == 3


# status = 0 # failure
# status = 1 # succeeded
class TestUpdateBuilds(CoprsTestCase):
    data1 = """
{
  "builds":[
   {
     "id": 1,
     "copr_id": 2,
     "result_dir": "bar",
     "started_on": 1390866440
   }
  ]
}"""

    data2 = """
{
  "builds":[
   {
     "id": 1,
     "copr_id": 2,
     "status": 1,
     "chroot": "fedora-18-x86_64",
     "result_dir": "bar",
     "ended_on": 1490866440
   }
  ]
}"""

    data3 = """
{
  "builds":[
   {
     "id": 1,
     "copr_id": 2,
     "chroot": "fedora-18-x86_64",
     "status": 6,
     "result_dir": "bar",
     "started_on": 1390866440
   },
   {
     "id": 2,
     "copr_id": 1,
     "status": 0,
     "chroot": "fedora-18-x86_64",
     "result_dir": "bar",
     "ended_on": 1390866440
   },
   {
     "id": 123321,
     "copr_id": 1,
     "status": 0,
     "chroot": "fedora-18-x86_64",
     "result_dir": "bar",
     "ended_on": 1390866440
   },
   {
     "id": 1234321,
     "copr_id": 2,
     "chroot": "fedora-18-x86_64",
     "result_dir": "bar",
     "started_on": 1390866440
   }
  ]
}"""

    def test_updating_requires_password(self, f_users, f_coprs, f_builds, f_db):
        r = self.tc.post("/backend/update/",
                         content_type="application/json",
                         data="")
        assert b"You have to provide the correct password" in r.data

    # todo: add test for `backend/starting_build/`

    def test_update_build_ended(self, f_users, f_coprs, f_mock_chroots,
                                f_builds, f_db):
        self.db.session.commit()
        r = self.tc.post("/backend/update/",
                         content_type="application/json",
                         headers=self.auth_header,
                         data=self.data2)
        assert json.loads(r.data.decode("utf-8"))["updated_builds_ids"] == [1]
        assert json.loads(r.data.decode("utf-8"))["non_existing_builds_ids"] == []

        updated = self.models.Build.query.filter(
            self.models.Build.id == 1).one()

        assert updated.status == 1
        assert updated.chroots_ended_on == {'fedora-18-x86_64': 1490866440}

    def test_update_more_existent_and_non_existent_builds(
            self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):

        self.db.session.add(self.b1)
        self.db.session.commit()

        r = self.tc.post("/backend/update/",
                         content_type="application/json",
                         headers=self.auth_header,
                         data=self.data3)

        assert sorted(json.loads(r.data.decode("utf-8"))["updated_builds_ids"]) == [1, 2]
        assert sorted(json.loads(r.data.decode("utf-8"))["non_existing_builds_ids"]) == [
            123321, 1234321]

        started = self.models.Build.query.filter(
            self.models.Build.id == 1).first()
        assert started.chroots_started_on == {'fedora-18-x86_64': 1390866440}

        ended = self.models.Build.query.filter(
            self.models.Build.id == 2).first()
        assert ended.status == 0
        assert ended.result_dir == "bar"
        assert ended.chroots_ended_on == {'fedora-18-x86_64': 1390866440}


class TestWaitingActions(CoprsTestCase):

    def test_no_waiting_actions(self):
        assert b'null' in self.tc.get(
            "/backend/pending-action/", headers=self.auth_header).data

    def test_waiting_actions_only_lists_not_started_or_ended(
            self, f_users, f_coprs, f_actions, f_db):

        for a in [self.a1, self.a2, self.a3]:
            a.result = helpers.BackendResultEnum("success")

        self.db.session.commit()

        r = self.tc.get("/backend/pending-action/", headers=self.auth_header)
        assert json.loads(r.data.decode("utf-8")) == None

        for a in [self.a1, self.a2, self.a3]:
            a.result = helpers.BackendResultEnum("waiting")
            self.db.session.add(a)

        self.db.session.commit()
        r = self.tc.get("/backend/pending-action/", headers=self.auth_header)
        assert json.loads(r.data.decode("utf-8")) != None


class TestUpdateActions(CoprsTestCase):
    data1 = """
{
  "actions":[
    {
      "id": 1,
      "result": 1,
      "message": "no problem",
      "ended_on": 1390866440
    }
  ]
}"""
    data2 = """
{
  "actions":[
    {
      "id": 1,
      "result": 1,
      "message": null,
      "ended_on": 1390866440
    },
    {
      "id": 2,
      "result": 2,
      "message": "problem!",
      "ended_on": 1390866440
    },
    {
      "id": 100,
      "result": 123,
      "message": "wheeeee!",
      "ended_on": 1390866440
    }
  ]
}"""

    def test_update_one_action(self, f_users, f_coprs, f_actions, f_db):
        r = self.tc.post("/backend/update/",
                         content_type="application/json",
                         headers=self.auth_header,
                         data=self.data1)
        assert json.loads(r.data.decode("utf-8"))["updated_actions_ids"] == [1]
        assert json.loads(r.data.decode("utf-8"))["non_existing_actions_ids"] == []

        updated = self.models.Action.query.filter(
            self.models.Action.id == 1).first()
        assert updated.result == 1
        assert updated.message == "no problem"
        assert updated.ended_on == 1390866440

    def test_update_more_existent_and_non_existent_builds(self, f_users,
                                                          f_coprs, f_actions,
                                                          f_db):
        r = self.tc.post("/backend/update/",
                         content_type="application/json",
                         headers=self.auth_header,
                         data=self.data2)
        assert sorted(json.loads(r.data.decode("utf-8"))["updated_actions_ids"]) == [1, 2]
        assert json.loads(r.data.decode("utf-8"))["non_existing_actions_ids"] == [100]

        updated = self.models.Action.query.filter(
            self.models.Action.id == 1).first()
        assert updated.result == 1
        assert updated.message is None
        assert updated.ended_on == 1390866440

        updated2 = self.models.Action.query.filter(
            self.models.Action.id == 2).first()
        assert updated2.result == 2
        assert updated2.message == "problem!"
        assert updated2.ended_on == 1390866440


class TestImportingBuilds(CoprsTestCase):
    def test_bg_priority_in_queue(self, f_users, f_coprs, f_mock_chroots, f_db):
        BuildsLogic.create_new_from_url(self.u1, self.c1, "foo", background=True)
        BuildsLogic.create_new_from_url(self.u1, self.c1, "bar")

        r = self.tc.get("/backend/importing/")
        data = json.loads(r.data.decode("utf-8"))
        assert data[0]["srpm_url"] == "bar"

    def test_importing_queue_multiple_bg(self, f_users, f_coprs, f_mock_chroots, f_db):
        BuildsLogic.create_new_from_url(self.u1, self.c1, "foo", background=True)
        BuildsLogic.create_new_from_url(self.u1, self.c1, "bar", background=True)

        r = self.tc.get("/backend/importing/")
        data = json.loads(r.data.decode("utf-8"))
        assert data[0]["srpm_url"] == "foo"
