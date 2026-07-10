"""DoS guards on the import upload path: file-size cap + row cap."""
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.groups.models import ExpenseGroup
from apps.imports.services.parser import MAX_ROWS, ParseError, parse

HEADER = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"


class UploadSizeLimitTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="u@f.com", display_name="U", password="strongpass123")
        self.client.force_authenticate(self.user)
        self.group = ExpenseGroup.objects.create(name="G", created_by=self.user)

    def test_oversized_upload_is_rejected_before_parsing(self):
        big = SimpleUploadedFile("big.csv", b"x" * (5 * 1024 * 1024 + 1), content_type="text/csv")
        resp = self.client.post(f"/api/groups/{self.group.id}/import/", {"file": big})
        self.assertEqual(resp.status_code, 413, resp.data)

    def test_oversized_upload_rejected_on_scan_too(self):
        big = SimpleUploadedFile("big.csv", b"x" * (5 * 1024 * 1024 + 1), content_type="text/csv")
        resp = self.client.post(f"/api/groups/{self.group.id}/import/scan-roster/", {"file": big})
        self.assertEqual(resp.status_code, 413, resp.data)


class ParserRowCapTests(APITestCase):
    def test_row_cap_raises(self):
        body = "2026-01-01,x,A,1,INR,equal,A,,\n" * (MAX_ROWS + 1)
        with self.assertRaises(ParseError):
            parse((HEADER + body).encode("utf-8"), "big.csv")

    def test_under_the_cap_is_fine(self):
        body = "2026-01-01,x,A,1,INR,equal,A,,\n" * 10
        rows = parse((HEADER + body).encode("utf-8"), "small.csv")
        self.assertEqual(len(rows), 10)
