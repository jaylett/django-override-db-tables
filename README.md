# Django database table overrides

Sometimes you need to vary the database table a particular ORM model
uses at runtime; in particular, for some multi-tenancy situations you
may have a table per client. You want to affect all uses of the ORM
within a callstack; context managers are generally the right way to
approach this.

However this is harder than it appears, so we have three different
ways of achieving this depending on what tradeoffs you're comfortable
with. If you can't decide, use the first one.

## Thread-safe context manager on derived model

```python
from django_override_db_tables import (
  OverrideDatabaseTables,
  SwappableDbTableModel
)

class MyModel(SwappableDbTableModel):
  # fields here ...

with OverrideDatabaseTables(MyModel, 'custom_db_table'):
  # use the ORM as normal
  # ...
```

`SwappableDbTableModel` is a very thin abstract model which defines no
fields but changes the metaclass to introduce a different [Meta
options](https://docs.djangoproject.com/en/1.6/ref/models/options/)
class which makes it possible to safely swap out
[`db_table`](https://docs.djangoproject.com/en/1.6/ref/models/options/#db-table).

(It does so by changing `db_table` to be a property that uses
`threading.local` to provide thread-safe storage of the database table
currently in use.)

You can assign from it in the `with` statement; if you override one
model's db table, that model is the assignable, or you can override
multiple ones and it'll return a sequence.

Unless you cannot change the `Model` baseclass you use, this is the
method we recommend.

Note that each individual context manager instance is *not*
re-entrant, ie you cannot nest `with` clauses using the same instance.

## Thread-locked context manager with plain models

```python
from django_override_db_tables import LockingOverrideDatabaseTables

with LockingOverrideDatabaseTables(MyModel, 'custom_db_table'):
  # use the ORM as normal
  # ...
```

This works with any Django ORM models, without modification, but will
lock across callstacks when each enters their outermost
`LockingOverrideDatabaseTables`. Providing you spend little time
within a context manager, this will often be an acceptable tradeoff.

You can assign from it in the `with` statement; if you override one
model's db table, that model is the assignable, or you can override
multiple ones and it'll return a sequence.

## Context manager as generator

```python
from django_override_db_tables import ReplaceDatabaseTable

with ReplaceDatabaseTable(
    MyAbstractModel,
    'custom_db_table'
) as MyModel:
  # use the ORM as normal
  # ...
```

This doesn't require locking between threads or thread locals, but
does mean that you have to pass the new ORM model around *and* that
your model must be abstract (otherwise we can't inherit `Meta`
options). It's unlikely that you want to use this.

## License and contact

MIT license; [source is on github][Package source]; please report bugs
there.

James Aylett

  [Package source]: https://github.com/jaylett/django-override-db-tables
