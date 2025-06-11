"""Peewee migrations -- 014_add_files.py.

OpenWebUI 数据库迁移 -- 添加文件管理表。
此迁移添加了File表，用于存储和管理用户上传的文件信息，支持文件上传和处理功能。

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
    创建File表的迁移函数。
    
    添加File(文件)表，用于存储用户上传文件的元数据信息。
    这使得系统可以跟踪用户上传的文件，用于对话中的文件引用、知识库文档管理等功能。
    文件本身存储在文件系统中，表中仅存储元数据信息。
    
    参数:
        migrator: Peewee迁移器对象
        database: 数据库连接实例
        fake: 是否模拟迁移而不实际执行
    """

    @migrator.create_model
    class File(pw.Model):
        """
        文件表，存储用户上传文件的元数据
        
        字段说明:
        - id: 文件的唯一标识符
        - user_id: 上传此文件的用户ID
        - filename: 文件名
        - meta: 文件元数据，JSON格式存储，包含文件类型、大小等信息
        - created_at: 上传时间戳
        """
        id = pw.TextField(unique=True)
        user_id = pw.TextField()
        filename = pw.TextField()
        meta = pw.TextField()
        created_at = pw.BigIntegerField(null=False)

        class Meta:
            table_name = "file"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """
    回滚迁移，删除File表。
    
    当需要撤销此迁移时，删除File表。
    注意：这只会删除文件元数据表，不会删除文件系统中的实际文件。
    
    参数:
        migrator: Peewee迁移器对象
        database: 数据库连接实例
        fake: 是否模拟回滚而不实际执行
    """

    migrator.remove_model("file")
