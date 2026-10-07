from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.core.management import call_command
from django.core.cache import cache
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.common_reference.models import Country
from .permissions import ReferencePermissions, IsAdminOrTeacher

class ReferenceProbe(APIView):
    permission_classes=[ReferencePermissions]
    permission_model=Country
    def get(self,request): return Response({})
    def post(self,request): return Response({})

class AuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user=get_user_model().objects.create_user(username="user",password="valid-password-123")
        self.client=APIClient(enforce_csrf_checks=True)
        self.origin="http://testserver"
    def bootstrap(self):
        response=self.client.get("/api/v1/auth/csrf/")
        return response.json()["csrfToken"]
    def post(self,path,data=None,token=None,origin=None):
        return self.client.post("/api/v1/auth/"+path+"/",data or {},format="json",
            HTTP_ORIGIN=origin or self.origin,HTTP_X_CSRFTOKEN=token or self.bootstrap())
    def login(self):
        return self.post("login",{"username":"user","password":"valid-password-123"})
    def test_login_me_cookie_and_privilege_escalation(self):
        response=self.login(); self.assertEqual(response.status_code,200)
        cookie=response.cookies["sims_refresh"]
        self.assertTrue(cookie["httponly"]); self.assertEqual(cookie["samesite"],"Strict")
        self.assertEqual(cookie["path"],"/api/v1/auth/")
        self.client.credentials(HTTP_AUTHORIZATION="Bearer "+response.json()["access"])
        self.assertEqual(self.client.get("/api/v1/auth/me/").json()["user_id"],self.user.pk)
        self.assertEqual(self.client.patch("/api/v1/auth/me/",{"is_superuser":True}).status_code,405)
        self.assertEqual(self.post("login",{"username":"user","password":"valid-password-123","is_superuser":True,"groups":["Admin"]}).status_code,400)
        self.user.refresh_from_db(); self.assertFalse(self.user.is_superuser); self.assertFalse(self.user.groups.exists())
    def test_csrf_and_origin_on_all_mutations(self):
        for path in ("login","refresh","logout"):
            self.assertEqual(self.client.post(f"/api/v1/auth/{path}/",{},HTTP_ORIGIN=self.origin).status_code,403)
            self.assertEqual(self.post(path,origin="https://evil.example").status_code,403)
        self.assertEqual(self.client.post("/api/v1/auth/logout/",{},HTTP_X_CSRFTOKEN=self.bootstrap()).status_code,403)
    def test_rotation_replay_logout_and_inactive(self):
        login=self.login(); old=login.cookies["sims_refresh"].value
        refresh=self.post("refresh"); self.assertEqual(refresh.status_code,200)
        new=refresh.cookies["sims_refresh"].value; self.assertNotEqual(old,new)
        self.client.cookies["sims_refresh"]=old
        self.assertEqual(self.post("refresh").status_code,401)
        self.client.cookies["sims_refresh"]=new
        response=self.post("logout"); self.assertEqual(response.status_code,204)
        self.assertEqual(response.cookies["sims_refresh"]["max-age"],0)
        self.client.cookies["sims_refresh"]=new
        self.assertEqual(self.post("refresh").status_code,401)
        response=self.login(); access=response.json()["access"]
        self.user.is_active=False; self.user.save()
        self.assertEqual(self.post("refresh").status_code,401)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer "+access)
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code,401)
        self.assertEqual(self.login().status_code,401)
    def test_generic_credentials_and_throttle(self):
        first=self.post("login",{"username":"missing","password":"wrong"})
        second=self.post("login",{"username":"user","password":"wrong"})
        self.assertEqual(first.json(),second.json())
        for _ in range(3): self.post("login",{"username":"user","password":"wrong"})
        self.assertEqual(self.login().status_code,429)
    @override_settings(AUTH_COOKIE_SECURE=True)
    def test_production_cookie_secure(self):
        self.assertTrue(self.login().cookies["sims_refresh"]["secure"])
    def test_current_permissions_and_read_write_separation(self):
        call_command("seed_role_groups",verbosity=0)
        factory=APIRequestFactory()
        def status(method,user):
            request=getattr(factory,method)("/")
            if user: force_authenticate(request,user=user)
            return ReferenceProbe.as_view()(request).status_code
        self.assertEqual(status("get",None),401)
        for name in ("Student","Teacher","Admin"):
            user=get_user_model().objects.create_user(username=name)
            user.groups.add(Group.objects.get(name=name))
            self.assertEqual(status("get",user),200); self.assertEqual(status("post",user),403)
        self.user.user_permissions.add(Permission.objects.get(codename="add_country"))
        self.assertEqual(status("post",self.user),403)
        self.user.user_permissions.add(Permission.objects.get(codename="maintain_reference"))
        self.assertEqual(status("post",get_user_model().objects.get(pk=self.user.pk)),200)
        self.user.user_permissions.clear()
        self.assertEqual(status("post",get_user_model().objects.get(pk=self.user.pk)),403)
        self.user.is_superuser=True; self.user.save()
        self.assertEqual(status("post",get_user_model().objects.get(pk=self.user.pk)),200)

from concurrent.futures import ThreadPoolExecutor
from django.test import TransactionTestCase
from django.db import connections

class RefreshRaceTests(TransactionTestCase):
    def test_only_one_parallel_consumer_succeeds(self):
        cache.clear()
        get_user_model().objects.create_user(username="race",password="test-password")
        client=APIClient(enforce_csrf_checks=True)
        csrf=client.get("/api/v1/auth/csrf/").json()["csrfToken"]
        login=client.post("/api/v1/auth/login/",{"username":"race","password":"test-password"},format="json",
            HTTP_ORIGIN="http://testserver",HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(login.status_code,200)
        cookies={key:value.value for key,value in client.cookies.items()}
        csrf=login.json()["csrfToken"]
        def consume(_):
            other=APIClient(enforce_csrf_checks=True)
            for key,value in cookies.items(): other.cookies[key]=value
            try:
                return other.post("/api/v1/auth/refresh/",{},format="json",HTTP_ORIGIN="http://testserver",HTTP_X_CSRFTOKEN=csrf).status_code
            finally:
                connections["default"].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(consume,range(2))),[200,401])
