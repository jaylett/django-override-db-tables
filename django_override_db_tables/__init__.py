class OverrideDatabaseTables(object):
    """
    Context manager for temporarily overriding models'
    ORM database tables (Meta.db_table) used in queries.

    Cannot be used recursively, but that should be obvious.
    """

    def __init__(self, *args):
        if len(args) % 2 != 0:
            raise ValueError(
                "OverrideDatabaseTables takes pairs of arguments: "
                "<model>, <db_table_name>"
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

    def __exit__(self, exc_type, exc_value, traceback):
        # reset db tables back to whatever they were before
        for k, v in self.old_mapping.items():
            k._meta.db_table = v

        # and don't prevent propagation of exceptions
        return False
