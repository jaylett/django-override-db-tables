if __name__ == "__main__":
    import sys
    from django.conf import settings

    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
            },
        },
    )

    # after we have some settings
    from django.test.runner import DiscoverRunner
    test_runner = DiscoverRunner(verbosity=1, failfast=False)

    failures = test_runner.run_tests(['tests.Tests'])

    if failures:
        sys.exit(failures)
