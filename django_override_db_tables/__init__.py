import threading


# Are we currently running within a context processor override?
thread_data = threading.local()
# Lock between different stacks of overrides in different threads.
lock = threading.Lock()


class LockingOverrideDatabaseTables(object):
    """
    Context manager for temporarily overriding models'
    ORM database tables (Meta.db_table) used in queries.

    This isn't re-entrant; you cannot use the same object
    recursively. However you can use different ones.
    """

    def __init__(self, *args):
        if len(args) % 2 != 0:
            raise ValueError(
                "LockingOverrideDatabaseTables takes pairs of arguments: "
                "<model>, <db_table_name>"
            )

        self.mapping = dict(
            zip(
                args[0::2],
                args[1::2],
            )
        )

    def __enter__(self):
        # inside an override! at the top of the stack (ie not
        # previously overridden) we need
        try:
            thread_data.depth += 1
        except AttributeError:
            thread_data.depth = 1
        if thread_data.depth == 1:
            lock.acquire()

        # first we store the old db tables so we can restore them
        self.old_mapping = dict(
            (
                k,
                k._meta.db_table
            ) for k, _ in
            self.mapping.items()
        )

        # then we perform the overrides
        for k, v in self.mapping.items():
            k._meta.db_table = v

        models = self.mapping.keys()
        if len(models) == 1:
            return models[0]
        else:
            return models

    def __exit__(self, exc_type, exc_value, traceback):
        # reset db tables back to whatever they were before
        for k, v in self.old_mapping.items():
            k._meta.db_table = v

        try:
            thread_data.depth -= 1
        except:
            pass

        if thread_data.depth == 0:
            lock.release()

        # and don't prevent propagation of exceptions
        return False


class ReplaceDatabaseTable(object):
    """
    Context manager for creating a new (temporary) model,
    from an abstract model, with a specific db_table.

    Fully re-entrant, thread-safe and lock-free since it doesn't
    actually alter anything, only create new objects.
    """

    def __init__(self, model, db_table):
        self.model = model
        self.db_table = db_table

    def __enter__(self):

        def replace_database_table(model, db_table):
            # Thank you Python...
            _db_table = db_table

            class DbTableSwappingMetaclass(models.base.ModelBase):
                def __new__(cls, name, bases, attrs):
                    name += '--x-dbtable-overridden--' + db_table
                    return models.base.ModelBase.__new__(
                        cls, name, bases, attrs
                    )

            class ModelWithSwappedDbTable(model):
                __metaclass__ = DbTableSwappingMetaclass

                class Meta(model.Meta):
                    db_table = _db_table

            return ModelWithSwappedDbTable

        return replace_database_table(self.model, self.db_table)

    def __exit__(self, exc_type, exc_value, traceback):
        # allow exceptions to propagate
        return False


class SwappableDbTableMetaclass(models.base.ModelBase):
    def __new__(cls, name, bases, attrs):
        kls = models.base.ModelBase.__new__(cls, name, bases, attrs)

        _old_db_table = kls._meta.db_table

        # Create a thread local subclass that defaults db_table
        # to _old_db_table (ie whatever was already configured).
        class DbTableLocal(threading.local):
            def __init__(self):
                self.__dict__['db_table'] = _old_db_table

        # Dynamically create an Options subclass that changes
        # db_table into a property deferred onto a thread local,
        # as shown in <http://stackoverflow.com/questions/8544983/>.
        class DbTableThreadLocalOptionsMixin(object):
            _db_table_ = DbTableLocal()

            def get_db_table(self):
                return self._db_table_.db_table

            def set_db_table(self, table):
                self._db_table_.db_table = table

            db_table = property(get_db_table, set_db_table)

        kls._meta.__class__ = type(
            'DbTableThreadLocalOptions',
            (
                DbTableThreadLocalOptionsMixin,
                models.options.Options,
            ),
            {},
        )

        return kls


class SwappableDbTableModel(models.Model):
    __metaclass__ = SwappableDbTableMetaclass

    class Meta:
        abstract = True
        # This needs to be here or (in Django 1.6) the metaclass
        # construction fails trying to figure out the app_label
        # (because we're not in an app). In Django 1.7 this should
        # cease to be the case.
        #
        # Note that if you subclass this and inherit from the Meta,
        # you must set this to None to get expected default behaviour:
        #
        # class MyModel(SwappableDbTableModel):
        #     ...
        #     class Meta(SwappableDbTableModel.Meta):
        #         app_label = None
        app_label = 'django_override_db_tables'


class OverrideDatabaseTables(object):
    """
    Context manager for adjusting SwappableDbTableModel(s).
    """

    def __init__(self, *args):
        if len(args) % 2 != 0:
            raise ValueError(
                "OverrideDatabaseTables takes pairs of arguments: "
                "<model>, <db_table_name>"
            )

        if len(
            [
                model for model in args[
                    0::2
                ] if SwappableDbTableModel not in type(model).mro(model)
            ]
        ) > 0:
            raise AttributeError(
                "Models to OverrideDatabaseTables must be subclasses of "
                "SwappableDbTableModel."
            )

        self.mapping = dict(
            zip(
                args[0::2],
                args[1::2],
            )
        )

    def __enter__(self):
        # first we store the old db tables so we can restore them
        self.old_mapping = dict(
            (
                k,
                k._meta.db_table
            ) for k, _ in
            self.mapping.items()
        )

        # then we perform the overrides
        for k, v in self.mapping.items():
            k._meta.db_table = v

        models = self.mapping.keys()
        if len(models) == 1:
            return models[0]
        else:
            return models

    def __exit__(self, exc_type, exc_value, traceback):
        # reset db tables back to whatever they were before
        for k, v in self.old_mapping.items():
            k._meta.db_table = v

        # and don't prevent propagation of exceptions
        return False
