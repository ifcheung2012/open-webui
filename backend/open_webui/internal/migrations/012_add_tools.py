"""Peewee migrations -- 012_add_tools.py.

OpenWebUI 数据库迁移 -- 添加工具管理表。
此迁移添加了Tool表，用于存储和管理用户定义的AI工具，实现函数调用和工具集成功能。

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
    创建Tool表的迁移函数。
    
    添加Tool(工具)表，用于存储和管理用户定义的AI工具配置。
    这些工具可以在AI对话中被调用，使AI具有访问外部功能和服务的能力，
    如网络搜索、数据分析、API调用等。
    
    参数:
        migrator: Peewee迁移器对象
        database: 数据库连接实例
        fake: 是否模拟迁移而不实际执行
    """

    @migrator.create_model
    class Tool(pw.Model):
        """
        工具表，存储AI可用工具的定义和配置
        
        字段说明:
        - id: 工具的唯一标识符
        - user_id: 创建此工具的用户ID
        - name: 工具的名称
        - content: 工具的实现内容，通常是代码或配置
        - specs: 工具的规格说明，JSON格式存储
        - meta: 工具元数据，JSON格式存储
        - created_at: 创建时间戳
        - updated_at: 最后更新时间戳
        """
        id = pw.TextField(unique=True)
        user_id = pw.TextField()

        name = pw.TextField()
        content = pw.TextField()
        specs = pw.TextField()

        meta = pw.TextField()

        created_at = pw.BigIntegerField(null=False)
        updated_at = pw.BigIntegerField(null=False)

        class Meta:
            table_name = "tool"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """
    回滚迁移，删除Tool表。
    
    当需要撤销此迁移时，删除Tool表。
    
    参数:
        migrator: Peewee迁移器对象
        database: 数据库连接实例
        fake: 是否模拟回滚而不实际执行
    """

    migrator.remove_model("tool")
