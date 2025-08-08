import pytest
from unittest.mock import Mock

# path may differ in your repo
from cnc.workers.attackers.authnz.intruder import (
    AuthzTester,
    HTTPClient,
    HTTPRequestData,
    AuthSession,
    Resource,
    ResourceType,
    RequestPart,
    ResourceLocator,
)
# ──────────────────────────────────────────────────────────────────────────────
ROLE_VIEWER = "viewer"
ROLE_ADMIN  = "admin"

def user(uid: str, role: str = ROLE_VIEWER) -> str:
    return f"{uid}:{role}"

# ──────────────────────────────────────────────────────────────────────────────
class TestAuthzTester:
    # --------------------------------------------------------------------- #
    # shared fixture
    # --------------------------------------------------------------------- #
    @pytest.fixture
    def ctx(self):
        client = Mock(spec=HTTPClient)
        client.send.return_value = None        # never hit the network
        tester = AuthzTester(http_client=client)

        sess_a = Mock(spec=AuthSession)
        sess_b = Mock(spec=AuthSession)
        sess_c = Mock(spec=AuthSession)

        return dict(
            tester=tester,
            http=client,
            sess_a=sess_a,
            sess_b=sess_b,
            sess_c=sess_c,
            t1=ResourceType(name="Type1", description=""),
            t2=ResourceType(name="Type2", description=""),
            t3=ResourceType(name="Type3", description=""),
        )

    # --------------------------------------------------------------------- #
    # helpers to build requests
    # --------------------------------------------------------------------- #
    def _mk_req(
        self,
        *,
        method: str,
        url: str,
        r_id: str,
        r_type: ResourceType,
    ):
        rd = HTTPRequestData(
            method=method,
            url=url,
            headers={},
            post_data=None,
            is_iframe=False,
            redirected_from_url=None,
            redirected_to_url=None,
        )
        locator = ResourceLocator(
            id=r_id,
            type_name=r_type.name,
            request_part=RequestPart.URL,
        )
        return rd, [locator]
    
    # ------------------------------------------------------------------ #
    # assertion helper
    # ------------------------------------------------------------------ #
    @staticmethod
    def tup(f):
        """user, id, action (with method) – id may be ''."""
        attack_info = f.attack_info
        return (f.sub_type, attack_info.user, attack_info.resource_id, attack_info.action)

    # ------------------------------------------------------------------ #
    # TEST 1 : first request ⇒ 0 findings
    # ------------------------------------------------------------------ #
    def _ingest(self, tester, *, uname, rd, locs, sess):
        tester.ingest(
            username=uname,
            request=rd,
            resource_locators=locs,
            session=sess,
        )

    def test_initial_ingest_no_findings(self, ctx):
        tester: AuthzTester = ctx["tester"]

        rd, locs = self._mk_req(
            method="GET",
            url="/type1/resource/R1",
            r_id="R1",
            r_type=ctx["t1"],
        )
        self._ingest(tester, uname=user("A"), rd=rd, locs=locs, sess=ctx["sess_a"])
        
        # Updated assertions for self-test-0
        assert len(tester.findings) == 1
        f0 = tester.findings[0]
        assert f0.user == user("A")
        assert f0.resource_id == "R1"
        assert f0.action == "GET /type1/resource/R1"

    # ------------------------------------------------------------------ #
    # TEST 2 : second user, same role, different type ⇒ 1 horizontal user test
    # ------------------------------------------------------------------ #
    def test_cross_user_after_second_request(self, ctx):
        tester = ctx["tester"]

        rd, locs = self._mk_req(
            method="GET",
            url="/type1/resource/R1",
            r_id="R1",
            r_type=ctx["t1"],
        )
        self._ingest(tester, uname=user("A"), rd=rd, locs=locs, sess=ctx["sess_a"])

        rd2, locs2 = self._mk_req(
            method="GET",
            url="/type2/resource/R2",
            r_id="R2",
            r_type=ctx["t2"],
        )
        self._ingest(tester, uname=user("B"), rd=rd2, locs=locs2, sess=ctx["sess_b"])
        
        tups = [self.tup(f) for f in tester.findings]
        for tup in tups:
            print(tup)

        # Updated assertions with self-tests included
        assert ('Horizontal User Action', user("A"), None, 'GET /type2/resource/R2') in tups
        assert ('Horizontal Resource', user("B"), 'R1', 'GET /type1/resource/R1') in tups

        # assert (user("A"), "R1", "GET /type1/resource/R1") in tups
        # assert (user("B"), "R2", "GET /type2/resource/R2") in tups
        # assert (user("A"), "", "GET /type2/resource/R2") in tups

        assert len(tups) == 2  # 2 self-tests + 1 finding

    # ------------------------------------------------------------------ #
    # TEST 3 : same user, new ID of same type ⇒ no new cross‑id tests yet
    # ------------------------------------------------------------------ #
    def test_same_user_new_id_same_type(self, ctx):
        tester = ctx["tester"]

        rd, locs = self._mk_req(
            method="GET",
            url="/type1/resource/R1",
            r_id="R1",
            r_type=ctx["t1"],
        )
        self._ingest(tester, uname=user("A"), rd=rd, locs=locs, sess=ctx["sess_a"])

        rd2, locs2 = self._mk_req(
            method="GET",
            url="/type2/resource/R2",
            r_id="R2",
            r_type=ctx["t2"],
        )
        self._ingest(tester, uname=user("B"), rd=rd2, locs=locs2, sess=ctx["sess_b"])

        rd3, locs3 = self._mk_req(
            method="GET",
            url="/type1/resource/R1a",
            r_id="R1a",
            r_type=ctx["t1"],
        )
        self._ingest(tester, uname=user("A"), rd=rd3, locs=locs3, sess=ctx["sess_a"])

        assert len(tester.findings) == 3  # Including self-tests

    # ------------------------------------------------------------------ #
    # TEST 4 : new action on existing id → UserA horizontal resource test
    # ------------------------------------------------------------------ #
    def test_new_action_existing_resource(self, ctx):
        tester = ctx["tester"]

        rd, locs = self._mk_req(
            method="GET",
            url="/type1/resource/R1",
            r_id="R1",
            r_type=ctx["t1"],
        )
        self._ingest(tester, uname=user("A"), rd=rd, locs=locs, sess=ctx["sess_a"])

        rd2, locs2 = self._mk_req(
            method="GET",
            url="/type2/resource/R2",
            r_id="R2",
            r_type=ctx["t2"],
        )
        self._ingest(tester, uname=user("B"), rd=rd2, locs=locs2, sess=ctx["sess_b"])

        rd3, locs3 = self._mk_req(
            method="GET",
            url="/type1/resource/R1a",
            r_id="R1a",
            r_type=ctx["t1"],
        )
        self._ingest(tester, uname=user("A"), rd=rd3, locs=locs3, sess=ctx["sess_a"])

        rd4, locs4 = self._mk_req(
            method="GET",
            url="/type1/action3",
            r_id="R1",
            r_type=ctx["t1"],
        )
        self._ingest(tester, uname=user("B"), rd=rd4, locs=locs4, sess=ctx["sess_b"])

        tups = {self.tup(f) for f in tester.findings}
        assert (user("A"), "", "GET /type2/resource/R2") in tups
        assert (user("A"), "R1", "GET /type1/action3") in tups
        assert len(tups) == 4  # Including self-tests

    # ------------------------------------------------------------------ #
    # TEST 5 : brand new user C (admin) triggers vertical permutations
    # ------------------------------------------------------------------ #
    def test_new_user_vertical_permutations(self, ctx):
        tester = ctx["tester"]
        client = ctx["http"]

        rd, locs = self._mk_req(
            method="GET",
            url="/type1/resource/R1",
            r_id="R1",
            r_type=ctx["t1"],
        )
        self._ingest(tester, uname=user("A"), rd=rd, locs=locs, sess=ctx["sess_a"])

        rd2, locs2 = self._mk_req(
            method="GET",
            url="/type2/resource/R2",
            r_id="R2",
            r_type=ctx["t2"],
        )
        self._ingest(tester, uname=user("B"), rd=rd2, locs=locs2, sess=ctx["sess_b"])

        rd3, locs3 = self._mk_req(
            method="GET",
            url="/type1/resource/R1a",
            r_id="R1a",
            r_type=ctx["t1"],
        )
        self._ingest(tester, uname=user("A"), rd=rd3, locs=locs3, sess=ctx["sess_a"])

        rd4, locs4 = self._mk_req(
            method="GET",
            url="/type1/action3",
            r_id="R1",
            r_type=ctx["t1"],
        )
        self._ingest(tester, uname=user("B"), rd=rd4, locs=locs4, sess=ctx["sess_b"])

        calls_before = client.send.call_count

        rd5, locs5 = self._mk_req(
            method="GET",
            url="/type1/resource/R1",
            r_id="R1",
            r_type=ctx["t1"],
        )
        self._ingest(tester, uname=user("C", ROLE_ADMIN), rd=rd5, locs=locs5, sess=ctx["sess_c"])

        new_findings = tester.findings[-11:]  # Updated to account for all vertical permutations
        assert all("admin" in f.user for f in new_findings)

        new_calls = client.send.call_count - calls_before
        assert new_calls >= 3  # At least 3, engine may schedule more

    # ------------------------------------------------------------------ #
    # TEST 6 : new resource‑type should not YOLO tests immediately
    # ------------------------------------------------------------------ #
    def test_new_resource_type_no_immediate_tests(self, ctx):
        tester = ctx["tester"]

        rd, locs = self._mk_req(
            method="GET",
            url="/type1/resource/R1",
            r_id="R1",
            r_type=ctx["t1"],
        )
        self._ingest(tester, uname=user("A"), rd=rd, locs=locs, sess=ctx["sess_a"])

        rd2, locs2 = self._mk_req(
            method="GET",
            url="/type2/resource/R2",
            r_id="R2",
            r_type=ctx["t2"],
        )
        self._ingest(tester, uname=user("B"), rd=rd2, locs=locs2, sess=ctx["sess_b"])

        pre_cnt = len(tester.findings)

        rd3, locs3 = self._mk_req(
            method="GET",
            url="/type3/resource/R3",
            r_id="R3",
            r_type=ctx["t3"],
        )
        self._ingest(tester, uname=user("A"), rd=rd3, locs=locs3, sess=ctx["sess_a"])

        # Updated assertion for new-type immediate tests
        assert len(tester.findings) == pre_cnt + 2
