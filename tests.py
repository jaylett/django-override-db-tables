from django.db import models
from django.test import TestCase
from django_override_db_tables import OverrideDatabaseTables


# We make two models even though we only use one, so that two
# db tables are created during the test run.

class Me(models.Model):
    name = models.CharField(max_length=20)

    class Meta:
        db_table = 'skyrat'
        app_label = 'test'


class You(models.Model):
    name = models.CharField(max_length=20)

    class Meta:
        db_table = 'pigeon'
        app_label = 'test'


class Tests(TestCase):

    def test_success(self):
        qset = You.objects.filter(name='James')
        self.assertEqual(
            """SELECT "pigeon"."id", "pigeon"."name" FROM "pigeon" """
            """WHERE "pigeon"."name" = James """,
            str(qset.query),
        )
        with OverrideDatabaseTables(You, 'skyrat'):
            qset = You.objects.filter(name='Katia')
            self.assertEqual(
                """SELECT "skyrat"."id", "skyrat"."name" FROM "skyrat" """
                """WHERE "skyrat"."name" = Katia """,
                str(qset.query),
            )

        # qset was created inside the context manager, and will have
        # resolved tables already
        self.assertEqual(
            """SELECT "skyrat"."id", "skyrat"."name" FROM "skyrat" """
            """WHERE "skyrat"."name" = Katia """,
            str(qset.query),
        )
        # however a new one will be back to normal
        qset = You.objects.filter(name='James')
        self.assertEqual(
            """SELECT "pigeon"."id", "pigeon"."name" FROM "pigeon" """
            """WHERE "pigeon"."name" = James """,
            str(qset.query),
        )

    def test_exception(self):
        try:
            with OverrideDatabaseTables(You, 'skyrat'):
                raise ValueError
            self.fail("Should have raised a ValueError.")
        except ValueError:
            pass

        # table configuration should have been restored
        qset = You.objects.filter(name='James')
        self.assertEqual(
            """SELECT "pigeon"."id", "pigeon"."name" FROM "pigeon" """
            """WHERE "pigeon"."name" = James """,
            str(qset.query),
        )
