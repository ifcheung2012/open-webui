"""Peewee migrations -- 015_add_functions.py.

OpenWebUI 数据库迁移 -- 添加函数管理表。
此迁移添加了Function表，用于存储和管理用户定义的函数，实现自定义函数功能和管道处理能力。

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
    创建Function表的迁移函数。
    
    添加Function(函数)表，用于存储用户自定义的处理函数。
    这些函数可以在聊天对话流程中的不同阶段被调用，提供信息过滤、消息转换等功能，
    增强AI对话的灵活性和可扩展性。
    
    参数:
        migrator: Peewee迁移器对象
        database: 数据库连接实例
        fake: 是否模拟迁移而不实际执行
    """

    @migrator.create_model
    class Function(pw.Model):
        """
        函数表，存储用户自定义的处理函数
        
        字段说明:
        - id: 函数的唯一标识符
        - user_id: 创建此函数的用户ID
        - name: 函数名称
        - type: 函数类型，如'filter'(过滤器)、'action'(动作)等
        - content: 函数内容，通常是代码实现
        - meta: 函数元数据，JSON格式存储
        - created_at: 创建时间戳
        - updated_at: 最后更新时间戳
        """
        id = pw.TextField(unique=True)
        user_id = pw.TextField()

        name = pw.TextField()
        type = pw.TextField()

        content = pw.TextField()
        meta = pw.TextField()

        created_at = pw.BigIntegerField(null=False)
        updated_at = pw.BigIntegerField(null=False)

        class Meta:
            table_name = "function"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """
    回滚迁移，删除Function表。
    
    当需要撤销此迁移时，删除Function表。
    
    参数:
        migrator: Peewee迁移器对象
        database: 数据库连接实例
        fake: 是否模拟回滚而不实际执行
    """

    migrator.remove_model("function")
