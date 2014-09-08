if __name__ == "__main__":
    import sys
    from django.conf import settings

    settings.configure(
        DEBUG=True,
        MIDDLEWARE_CLASSES=[],
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
            },
        },
    )

    # for Django 1.7
    import django
    try:
        django.setup()
    except AttributeError:
        pass

    # after we have some settings
    from django.test.runner import DiscoverRunner
    test_runner = DiscoverRunner(verbosity=1, failfast=False)

    failures = test_runner.run_tests(['tests'])

    if failures:
        sys.exit(failures)
