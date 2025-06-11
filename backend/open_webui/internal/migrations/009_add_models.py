"""Peewee migrations -- 009_add_models.py.

OpenWebUI 数据库迁移 -- 添加模型管理表。
此迁移添加了Model表，用于存储和管理用户可配置的AI模型，实现对模型的灵活管理和自定义。

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
    创建Model表的迁移函数。
    
    添加Model(模型)表，用于存储和管理用户自定义的AI模型配置。
    这使得用户能够创建、编辑和管理自己的模型配置，为不同的对话场景选择合适的模型。
    
    参数:
        migrator: Peewee迁移器对象
        database: 数据库连接实例
        fake: 是否模拟迁移而不实际执行
    """

    @migrator.create_model
    class Model(pw.Model):
        """
        模型表，存储AI模型的配置和元数据
        
        字段说明:
        - id: 模型的唯一标识符
        - user_id: 创建此模型配置的用户ID
        - base_model_id: 基础模型ID，可选，指向实际使用的模型
        - name: 模型的显示名称
        - meta: 模型元数据，JSON格式存储
        - params: 模型参数，JSON格式存储
        - created_at: 创建时间戳
        - updated_at: 最后更新时间戳
        """
        id = pw.TextField(unique=True)
        user_id = pw.TextField()
        base_model_id = pw.TextField(null=True)

        name = pw.TextField()

        meta = pw.TextField()
        params = pw.TextField()

        created_at = pw.BigIntegerField(null=False)
        updated_at = pw.BigIntegerField(null=False)

        class Meta:
            table_name = "model"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """
    回滚迁移，删除Model表。
    
    当需要撤销此迁移时，删除Model表。
    
    参数:
        migrator: Peewee迁移器对象
        database: 数据库连接实例
        fake: 是否模拟回滚而不实际执行
    """

    migrator.remove_model("model")
