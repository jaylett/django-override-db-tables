from django.db import models
from django.test import TestCase
from django_override_db_tables import OverrideDatabaseTables


class TestModel(models.Model):
    name = models.CharField(max_length=20)

    class Meta:
        db_table = 'pigeon'
        app_label = 'test'


class Tests(TestCase):

    def test_success(self):
        qset = TestModel.objects.filter(name='James')
        self.assertEqual(
            """SELECT "pigeon"."id", "pigeon"."name" FROM "pigeon" """
            """WHERE "pigeon"."name" = James """,
            str(qset.query),
        )
        with OverrideDatabaseTables(TestModel, 'skyrat'):
            # existing queryset should be unaffected
            self.assertEqual(
                """SELECT "pigeon"."id", "pigeon"."name" FROM "pigeon" """
                """WHERE "pigeon"."name" = James """,
                str(qset.query),
            )
            # but new ones should use the override
            qset = TestModel.objects.filter(name='Katia')
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
        qset = TestModel.objects.filter(name='James')
        self.assertEqual(
            """SELECT "pigeon"."id", "pigeon"."name" FROM "pigeon" """
            """WHERE "pigeon"."name" = James """,
            str(qset.query),
        )

    def test_exception(self):
        try:
            with OverrideDatabaseTables(TestModel, 'skyrat'):
                raise ValueError
            self.fail("Should have raised a ValueError.")
        except ValueError:
            pass

        # table configuration should have been restored
        qset = TestModel.objects.filter(name='James')
        self.assertEqual(
            """SELECT "pigeon"."id", "pigeon"."name" FROM "pigeon" """
            """WHERE "pigeon"."name" = James """,
            str(qset.query),
        )

    def test_nesting(self):
        with OverrideDatabaseTables(TestModel, 'skyrat'):
            qset = TestModel.objects.filter(name='Katia')
            self.assertEqual(
                """SELECT "skyrat"."id", "skyrat"."name" FROM "skyrat" """
                """WHERE "skyrat"."name" = Katia """,
                str(qset.query),
            )
            with OverrideDatabaseTables(TestModel, 'columbidae'):
                qset2 = TestModel.objects.filter(name='Nick')
                self.assertEqual(
                    """SELECT "columbidae"."id", "columbidae"."name" """
                    """FROM "columbidae" """
                    """WHERE "columbidae"."name" = Nick """,
                    str(qset2.query),
                )
            qset3 = TestModel.objects.filter(name='Katia')
            self.assertEqual(
                """SELECT "skyrat"."id", "skyrat"."name" FROM "skyrat" """
                """WHERE "skyrat"."name" = Katia """,
                str(qset3.query),
            )

        # and resets correctly at the end
        qset = TestModel.objects.filter(name='James')
        self.assertEqual(
            """SELECT "pigeon"."id", "pigeon"."name" FROM "pigeon" """
            """WHERE "pigeon"."name" = James """,
            str(qset.query),
        )
        self.assertEqual(
            """SELECT "pigeon"."id", "pigeon"."name" FROM "pigeon" """
            """WHERE "pigeon"."name" = James """,
            str(qset.query),
        )
