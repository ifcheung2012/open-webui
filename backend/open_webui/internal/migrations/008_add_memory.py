"""Peewee migrations -- 008_add_memory.py.

OpenWebUI 数据库迁移 -- 添加记忆功能表。
此迁移添加了Memory表，用于存储用户的长期记忆内容，支持AI对话中的记忆功能。

Some examples (model - class or model name)::

    > Model = migrator.orm['table_name']            # Return model in current state by name
    > Model = migrator.ModelClass                   # Return model in current state by name

    > migrator.sql(sql)                             # Run custom SQL
    > migrator.run(func, *args, **kwargs)           # Run python function with the given args
    > migrator.create_model(Model)                  # Create a model (could be used as decorator)
    > migrator.remove_model(model, cascade=True)    # Remove a model
    > migrator.add_fields(model, **fields)          # Add fields to a model
    > migrator.change_fields(model, **fields)       # Change fields
    > migrator.remove_fields(model, *field_names, cascade=True)
    > migrator.rename_field(model, old_field_name, new_field_name)
    > migrator.rename_table(model, new_table_name)
    > migrator.add_index(model, *col_names, unique=False)
    > migrator.add_not_null(model, *field_names)
    > migrator.add_default(model, field_name, default)
    > migrator.add_constraint(model, name, sql)
    > migrator.drop_index(model, *col_names)
    > migrator.drop_not_null(model, *field_names)
    > migrator.drop_constraints(model, *constraints)

"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator


with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """
    创建Memory表的迁移函数。
    
    添加Memory(记忆)表，用于存储用户的长期记忆内容，提升AI对话的连续性和上下文感知能力。
    每个记忆条目都与特定用户关联，并包含创建和更新时间戳。
    
    参数:
        migrator: Peewee迁移器对象
        database: 数据库连接实例
        fake: 是否模拟迁移而不实际执行
    """
    @migrator.create_model
    class Memory(pw.Model):
        """
        记忆表，存储用户的长期记忆内容
        
        字段说明:
        - id: 记忆条目的唯一标识符
        - user_id: 拥有此记忆的用户ID
        - content: 记忆内容文本
        - updated_at: 记忆最后更新时间
        - created_at: 记忆创建时间
        """
        id = pw.CharField(max_length=255, unique=True)
        user_id = pw.CharField(max_length=255)
        content = pw.TextField(null=False)
        updated_at = pw.BigIntegerField(null=False)
        created_at = pw.BigIntegerField(null=False)

        class Meta:
            table_name = "memory"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """
    回滚迁移，删除Memory表。
    
    当需要撤销此迁移时，删除Memory表。
    
    参数:
        migrator: Peewee迁移器对象
        database: 数据库连接实例
        fake: 是否模拟回滚而不实际执行
    """

    migrator.remove_model("memory")
