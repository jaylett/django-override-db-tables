from django.db import models
from django.test import TestCase
from django_override_db_tables import (
    LockingOverrideDatabaseTables,
    ReplaceDatabaseTable,
)
import threading
import time


class TestModel(models.Model):
    name = models.CharField(max_length=20)

    class Meta:
        db_table = 'pigeon'
        app_label = 'test'


class LockingOverrideTests(TestCase):
    """Test LockingOverrideDatabaseTables."""

    def test_success(self):
        qset = TestModel.objects.filter(name='James')
        self.assertEqual(
            """SELECT "pigeon"."id", "pigeon"."name" FROM "pigeon" """
            """WHERE "pigeon"."name" = James """,
            str(qset.query),
        )
        with LockingOverrideDatabaseTables(TestModel, 'skyrat'):
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
            with LockingOverrideDatabaseTables(TestModel, 'skyrat'):
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
        with LockingOverrideDatabaseTables(TestModel, 'skyrat'):
            qset = TestModel.objects.filter(name='Katia')
            self.assertEqual(
                """SELECT "skyrat"."id", "skyrat"."name" FROM "skyrat" """
                """WHERE "skyrat"."name" = Katia """,
                str(qset.query),
            )
            with LockingOverrideDatabaseTables(TestModel, 'columbidae'):
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


class LockingOverrideConcurrency(TestCase):
    """Test that overrides in multiple threads won't conflict."""

    def test_two_threads(self):
        # Both are moved gradually through their sequence by
        # having this (the main) thread repeatedly release
        # a semaphore that prevents them moving further forward.
        #
        # This both served to demonstrate the problem of interleved
        # context processors, *and* still works once each thread's
        # stack of context processors uses a lock to prevent them
        # running concurrently.
        sequence = []

        def log_position(thread, position):
            where = "%s%s" % (thread, position)
            sequence.append(where)
            # print(where)

        def first(semaphore):
            first.as_expected = False
            semaphore.acquire(True)
            with LockingOverrideDatabaseTables(TestModel, 'columbidae'):
                log_position('f', 'I')
                qset = TestModel.objects.filter(name='Nick')
                if (
                    """SELECT "columbidae"."id", "columbidae"."name" """
                    """FROM "columbidae" """
                    """WHERE "columbidae"."name" = Nick """ !=
                    str(qset.query)
                ):
                    return
            log_position('f', 'II')
            qset = TestModel.objects.filter(name='James')
            if (
                """SELECT "pigeon"."id", "pigeon"."name" FROM "pigeon" """
                """WHERE "pigeon"."name" = James """ !=
                str(qset.query)
            ):
                return

            first.as_expected = True

        def second(semaphore):
            second.as_expected = False
            with LockingOverrideDatabaseTables(TestModel, 'skyrat'):
                log_position('s', 'I')
                semaphore.acquire(True)
                qset = TestModel.objects.filter(name='Katia')
                if (
                    """SELECT "skyrat"."id", "skyrat"."name" FROM "skyrat" """
                    """WHERE "skyrat"."name" = Katia """ !=
                    str(qset.query)
                ):
                    return

                log_position('s', 'II')

            qset = TestModel.objects.filter(name='James')
            if (
                """SELECT "pigeon"."id", "pigeon"."name" FROM "pigeon" """
                """WHERE "pigeon"."name" = James """ !=
                str(qset.query)
            ):
                return

            second.as_expected = True

        sem1 = threading.Semaphore()
        sem2 = threading.Semaphore()
        sem1.acquire(True)
        sem2.acquire(True)

        first_thread = threading.Thread(target=first, args=[sem1])
        second_thread = threading.Thread(target=second, args=[sem2])
        first_thread.daemon = True
        second_thread.daemon = True

        first_thread.start()
        second_thread.start()

        # The second thread will run until it is inside its
        # context processor. Let's make sure we give it time
        # to get there before unblocking the first thread.
        time.sleep(1)
        # Let the first thread run through everything. It won't,
        # because by then the second thread will have obtained the
        # global lock on overrides.
        sem1.release()
        # And let the second thread run to completion.
        sem2.release()
        # At this point, it releases the global lock and the first
        # thread can run to completion.

        # and wait for both to complete
        first_thread.join()
        second_thread.join()

        self.assertEqual(True, first.as_expected)
        self.assertEqual(True, second.as_expected)
        # Check that the operations were carried out in the correct
        # order
        #
        # This is what it should look like without locking:
        #
        # self.assertEqual(
        #     [ 'sI', 'fI', 'fII', 'sII' ],
        #     sequence
        # )
        #
        # This is what it looks like with locking:
        #
        self.assertEqual(
            ['sI', 'sII', 'fI', 'fII'],
            sequence
        )

        # then check that everything has been reset correctly
        qset = TestModel.objects.filter(name='James')
        self.assertEqual(
            """SELECT "pigeon"."id", "pigeon"."name" FROM "pigeon" """
            """WHERE "pigeon"."name" = James """,
            str(qset.query),
        )


class AbstractTestModel(models.Model):
    name = models.CharField(max_length=20)

    class Meta:
        abstract = True
        db_table = 'pigeon'
        app_label = 'test'


class ReplaceTests(TestCase):
    """Test ReplaceDatabaseTable."""

    # almost identical to LockingOverrideTests, but needs the return from
    # the context manager, and has to be based on the AbstractTestModel
    # (so we don't care about resetting the db table of anything we
    # replace the db table of).

    def test_success(self):
        with ReplaceDatabaseTable(AbstractTestModel, 'skyrat') as TM:
            qset = TM.objects.filter(name='Katia')
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

    def test_exception(self):
        try:
            with ReplaceDatabaseTable(AbstractTestModel, 'skyrat'):
                raise ValueError
            self.fail("Should have raised a ValueError.")
        except ValueError:
            pass

    def test_nesting(self):
        with ReplaceDatabaseTable(AbstractTestModel, 'skyrat') as TM:
            qset = TM.objects.filter(name='Katia')
            self.assertEqual(
                """SELECT "skyrat"."id", "skyrat"."name" FROM "skyrat" """
                """WHERE "skyrat"."name" = Katia """,
                str(qset.query),
            )
            with ReplaceDatabaseTable(AbstractTestModel, 'columbidae') as TM2:
                qset2 = TM2.objects.filter(name='Nick')
                self.assertEqual(
                    """SELECT "columbidae"."id", "columbidae"."name" """
                    """FROM "columbidae" """
                    """WHERE "columbidae"."name" = Nick """,
                    str(qset2.query),
                )
            qset3 = TM.objects.filter(name='Katia')
            self.assertEqual(
                """SELECT "skyrat"."id", "skyrat"."name" FROM "skyrat" """
                """WHERE "skyrat"."name" = Katia """,
                str(qset3.query),
            )


class ReplaceConcurrency(TestCase):
    """Test that replace in multiple threads won't conflict."""

    def test_two_threads(self):
        # Both are moved gradually through their sequence by
        # having this (the main) thread repeatedly release
        # a semaphore that prevents them moving further forward.
        #
        # Could probably be done more simply, but this works and
        # matches LockingOverrideConcurrency, above.
        sequence = []

        def log_position(thread, position):
            where = "%s%s" % (thread, position)
            sequence.append(where)
            # print(where)

        def first(sem1, sem2):
            first.as_expected = False
            sem1.acquire(True)
            with ReplaceDatabaseTable(AbstractTestModel, 'columbidae') as TM:
                log_position('f', 'I')
                qset = TM.objects.filter(name='Nick')
                if (
                    """SELECT "columbidae"."id", "columbidae"."name" """
                    """FROM "columbidae" """
                    """WHERE "columbidae"."name" = Nick """ !=
                    str(qset.query)
                ):
                    return
            log_position('f', 'II')
            sem2.release()

            first.as_expected = True

        def second(sem1, sem2):
            second.as_expected = False
            with ReplaceDatabaseTable(AbstractTestModel, 'skyrat') as TM:
                log_position('s', 'I')
                sem1.release()
                sem2.acquire(True)
                qset = TM.objects.filter(name='Katia')
                if (
                    """SELECT "skyrat"."id", "skyrat"."name" FROM "skyrat" """
                    """WHERE "skyrat"."name" = Katia """ !=
                    str(qset.query)
                ):
                    return

                log_position('s', 'II')

            second.as_expected = True

        sem1 = threading.Semaphore()
        sem2 = threading.Semaphore()
        sem1.acquire(True)
        sem2.acquire(True)

        first_thread = threading.Thread(target=first, args=[sem1, sem2])
        second_thread = threading.Thread(target=second, args=[sem1, sem2])
        first_thread.daemon = True
        second_thread.daemon = True

        first_thread.start()
        second_thread.start()

        # and wait for both to complete
        first_thread.join()
        second_thread.join()

        self.assertEqual(True, first.as_expected)
        self.assertEqual(True, second.as_expected)
        # Check that the operations were carried out in the correct
        # order
        self.assertEqual(
            ['sI', 'fI', 'fII', 'sII'],
            sequence
        )
