#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
"""Test the ExpiredDataRemover object."""
from datetime import datetime
from unittest.mock import patch

import pytz

from api.models import Provider
from masu.external.date_accessor import DateAccessor
from masu.processor.expired_data_remover import ExpiredDataRemover
from masu.processor.expired_data_remover import ExpiredDataRemoverError
from masu.test import MasuTestCase


class ExpiredDataRemoverTest(MasuTestCase):
    """Test Cases for the ExpiredDataRemover object."""

    def test_initializer(self):
        """Test to init."""
        remover = ExpiredDataRemover(self.schema, Provider.PROVIDER_AWS)
        self.assertEqual(remover._months_to_keep, 3)
        self.assertEqual(remover._line_items_months, 1)
        remover2 = ExpiredDataRemover(self.schema, Provider.PROVIDER_AWS, 2, 2)
        self.assertEqual(remover2._months_to_keep, 2)
        self.assertEqual(remover2._line_items_months, 2)

    def test_initializer_ocp(self):
        """Test to init for OCP."""
        remover = ExpiredDataRemover(self.schema, Provider.PROVIDER_OCP)
        self.assertEqual(remover._months_to_keep, 3)
        self.assertEqual(remover._line_items_months, 1)

    def test_initializer_azure(self):
        """Test to init for Azure."""
        remover = ExpiredDataRemover(self.schema, Provider.PROVIDER_AZURE)
        self.assertEqual(remover._months_to_keep, 3)
        self.assertEqual(remover._line_items_months, 1)

    def test_initializer_invalid_provider(self):
        """Test to init with unknown provider."""
        with self.assertRaises(ExpiredDataRemoverError):
            ExpiredDataRemover(self.schema, "BAD")

    @patch("masu.processor.aws.aws_report_db_cleaner.AWSReportDBCleaner.__init__", side_effect=Exception)
    def test_initializer_provider_exception(self, mock_aws_cleaner):
        """Test to init."""
        with self.assertRaises(ExpiredDataRemoverError):
            ExpiredDataRemover(self.schema, Provider.PROVIDER_AWS)

    def test_calculate_expiration_date(self):
        """Test that the expiration date is correctly calculated."""
        date_matrix = [
            {
                "current_date": datetime(year=2018, month=7, day=1),
                "expected_expire": datetime(year=2018, month=4, day=1, tzinfo=pytz.UTC),
                "months_to_keep": None,
            },
            {
                "current_date": datetime(year=2018, month=7, day=31),
                "expected_expire": datetime(year=2018, month=4, day=1, tzinfo=pytz.UTC),
                "months_to_keep": None,
            },
            {
                "current_date": datetime(year=2018, month=3, day=20),
                "expected_expire": datetime(year=2017, month=12, day=1, tzinfo=pytz.UTC),
                "months_to_keep": None,
            },
            {
                "current_date": datetime(year=2018, month=7, day=1),
                "expected_expire": datetime(year=2017, month=7, day=1, tzinfo=pytz.UTC),
                "months_to_keep": 12,
            },
            {
                "current_date": datetime(year=2018, month=7, day=31),
                "expected_expire": datetime(year=2017, month=7, day=1, tzinfo=pytz.UTC),
                "months_to_keep": 12,
            },
            {
                "current_date": datetime(year=2018, month=3, day=20),
                "expected_expire": datetime(year=2016, month=3, day=1, tzinfo=pytz.UTC),
                "months_to_keep": 24,
            },
        ]
        for test_case in date_matrix:
            with patch.object(DateAccessor, "today", return_value=test_case.get("current_date")):
                retention_policy = test_case.get("months_to_keep")
                if retention_policy:
                    remover = ExpiredDataRemover(self.schema, Provider.PROVIDER_AWS, retention_policy)
                else:
                    remover = ExpiredDataRemover(self.schema, Provider.PROVIDER_AWS)
                expire_date = remover._calculate_expiration_date()
                self.assertEqual(expire_date, test_case.get("expected_expire"))

    def test_remove(self):
        """Test that removes the expired data based on the retention policy."""
        remover = ExpiredDataRemover(self.schema, Provider.PROVIDER_AWS)
        removed_data = remover.remove()
        self.assertEqual(len(removed_data), 0)

    @patch("masu.processor.expired_data_remover.AWSReportDBCleaner.purge_expired_report_data")
    def test_remove_provider(self, mock_purge):
        """Test that remove is called with provider_uuid."""
        provider_uuid = self.aws_provider_uuid
        remover = ExpiredDataRemover(self.schema, Provider.PROVIDER_AWS)
        remover.remove(provider_uuid=provider_uuid)
        mock_purge.assert_called_with(simulate=False, provider_uuid=provider_uuid)

    @patch("masu.processor.expired_data_remover.AWSReportDBCleaner.purge_expired_line_item")
    def test_remove_provider_items_only(self, mock_purge):
        """Test that remove is called with provider_uuid items only."""
        provider_uuid = self.aws_provider_uuid
        remover = ExpiredDataRemover(self.schema, Provider.PROVIDER_AWS)
        date = remover._calculate_expiration_date(line_items_only=True)
        remover.remove(provider_uuid=provider_uuid, line_items_only=True)
        mock_purge.assert_called_with(expired_date=date, simulate=False, provider_uuid=provider_uuid)

    @patch("masu.processor.expired_data_remover.AWSReportDBCleaner.purge_expired_line_item")
    def test_remove_items_only(self, mock_purge):
        """Test that remove is called with provider_uuid items only."""
        remover = ExpiredDataRemover(self.schema, Provider.PROVIDER_AWS)
        date = remover._calculate_expiration_date(line_items_only=True)
        remover.remove(line_items_only=True)
        mock_purge.assert_called_with(expired_date=date, simulate=False)

    def test_remove_items_only_azure(self):
        """Test that remove is called with provider_uuid items only."""
        azure_types = [Provider.PROVIDER_AZURE, Provider.PROVIDER_AZURE_LOCAL]
        for az_type in azure_types:
            remover = ExpiredDataRemover(self.schema, az_type)
            result_no_provider = remover.remove(line_items_only=True)
            self.assertIsNone(result_no_provider)
            result_with_provider = remover.remove(line_items_only=True, provider_uuid="1234")
            self.assertIsNone(result_with_provider)
