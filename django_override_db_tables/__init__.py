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
